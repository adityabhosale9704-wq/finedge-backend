const token = getAuthToken();
const SEPARATIONS_API_BASE = API_BASE + '/separations/';
const EMPLOYEES_API_BASE = API_BASE + '/employees/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadSeparations();
    initGlobalBranchFilter('global-branch-filter-container', function () { loadSeparations(); });
  });
}

let allSeparations = [];
const expandedIds = new Set();

const pageError = document.getElementById('page-error');

function showPageError(message) {
  pageError.textContent = message;
  pageError.style.display = 'block';
}

function hidePageError() {
  pageError.textContent = '';
  pageError.style.display = 'none';
}

function escapeHtml(value) {
  if (value === undefined || value === null) {
    return '';
  }
  const div = document.createElement('div');
  div.textContent = String(value);
  return div.innerHTML;
}


async function loadSeparations() {
  hidePageError();
  const inProgressEl = document.getElementById('separations-content');

  try {
    const branchQuery = getGlobalBranchFilter() ? '?branch=' + encodeURIComponent(getGlobalBranchFilter()) : '';
    const response = await fetch(SEPARATIONS_API_BASE + branchQuery, {
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to load separations.');
    }

    allSeparations = await response.json();
    renderSeparations();
  } catch (err) {
    inProgressEl.innerHTML = '<div class="error-state"><div>' +
      escapeHtml(err.message || 'Could not load separations.') +
      '</div><button type="button" class="btn-secondary" id="retry-sep-button">Retry</button></div>';
    document.getElementById('retry-sep-button').addEventListener('click', loadSeparations);
  }
}

function renderStepsBlock(sep) {
  const steps = sep.steps || [];
  const doneCount = sep.steps_done_count || 0;
  const totalCount = sep.steps_total_count || steps.length;
  const pct = (sep.progress_pct !== undefined) ? sep.progress_pct : (totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0);

  const rows = steps.map(function (step) {
    const options = ['Pending', 'In Progress', 'Completed'].map(function (st) {
      return '<option value="' + st + '"' + (step.status === st ? ' selected' : '') + '>' + st + '</option>';
    }).join('');
    const statusCell = sep.is_complete
      ? '<span class="chip ' + (step.status === 'Completed' ? 'chip-green' : 'chip-amber') + '">' + escapeHtml(step.status) + '</span>'
      : '<select class="sep-step-status" data-sep-id="' + escapeHtml(sep.id) + '" data-step-id="' + escapeHtml(step.id) + '">' + options + '</select>';
    return '<tr>' +
      '<td>' + escapeHtml(step.step_no) + '</td>' +
      '<td>' + escapeHtml(step.who) + '</td>' +
      '<td>' + escapeHtml(step.when) + '</td>' +
      '<td>' + escapeHtml(step.how || step.step_name) + (step.required === false ? ' <span class="chip chip-navy">Optional</span>' : '') + '</td>' +
      '<td>' + statusCell + '</td>' +
      '<td>' + (step.completed_at ? escapeHtml(String(step.completed_at).slice(0, 10)) : '&mdash;') + '</td>' +
      '</tr>';
  }).join('');

  return '<div class="progress-track"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
    '<div class="progress-label">' + doneCount + '/' + totalCount + ' steps &middot; ' + pct + '%</div>' +
    '<table style="min-width: 0; margin-top: 10px;"><thead><tr><th>#</th><th>Who</th><th>When</th><th>How</th><th>Status</th><th>Completed</th></tr></thead><tbody>' + rows + '</tbody></table>';
}

function renderSeparations() {
  const inProgress = allSeparations.filter(function (s) { return !s.is_complete; });
  const completed = allSeparations.filter(function (s) { return s.is_complete; });

  renderSeparationList('separations-content', inProgress, 'No separations in progress.');
  renderSeparationList('completed-content', completed, 'No completed separations yet.');
}

function renderSeparationList(containerId, list, emptyMessage) {
  const content = document.getElementById(containerId);

  if (list.length === 0) {
    content.innerHTML = '<div class="message">' + emptyMessage + '</div>';
    return;
  }

  content.innerHTML = list.map(function (sep) {
    const isExpanded = expandedIds.has(sep.id);
    const relievingChipClass = sep.relieving_letter_status === 'Issued' ? 'chip-green' : 'chip-amber';

    let bodyHtml = '';
    if (isExpanded) {
      bodyHtml = '<div class="sep-body">' +
        renderStepsBlock(sep) +
        '<div class="sep-field-row">' +
        '<label style="margin: 0;">Relieving Letter:</label>' +
        '<select class="relieving-status-select" data-sep-id="' + escapeHtml(sep.id) + '" style="max-width: 160px;">' +
        '<option value="Pending"' + (sep.relieving_letter_status === 'Pending' ? ' selected' : '') + '>Pending</option>' +
        '<option value="Issued"' + (sep.relieving_letter_status === 'Issued' ? ' selected' : '') + '>Issued</option>' +
        '</select>' +
        '</div>' +
        '<div class="field">' +
        '<label>Full &amp; Final Settlement Note</label>' +
        '<textarea class="fnf-note-input" data-sep-id="' + escapeHtml(sep.id) + '" rows="3">' + escapeHtml(sep.full_final_settlement_note) + '</textarea>' +
        '<button type="button" class="btn-secondary save-fnf-btn" data-sep-id="' + escapeHtml(sep.id) + '" style="margin-top: 6px;">Save Note</button>' +
        '</div>' +
        '<div class="audit-box" data-entity="separation" data-entity-id="' + escapeHtml(sep.id) + '"></div>' +
        '<button type="button" class="btn-delete delete-sep-btn" data-sep-id="' + escapeHtml(sep.id) + '" style="margin-top: 10px;">Delete Separation</button>' +
        '</div>';
    } else {
      const pct = sep.progress_pct || 0;
      const cur = sep.current_step ? (sep.current_step.step_no + '. ' + sep.current_step.how) : (sep.is_complete ? 'All steps completed' : '');
      const pending = (sep.pending_tasks || []).length;
      bodyHtml = '<div class="progress-track" style="margin-top: 10px;"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="progress-label">' + pct + '% &middot; Current: ' + escapeHtml(cur) + ' &middot; ' + pending + ' pending task(s) &mdash; click to expand</div>';
    }

    return '<div class="sep-card">' +
      '<div class="sep-header sep-toggle" data-sep-id="' + escapeHtml(sep.id) + '">' +
      '<span>' +
      '<div class="sep-name">' + escapeHtml(sep.employee_name || sep.employee_id) + '</div>' +
      '<div class="sep-meta">' + (sep.employee_code ? escapeHtml(sep.employee_code) + ' &middot; ' : '') + escapeHtml(sep.designation) + (sep.department ? ' &middot; ' + escapeHtml(sep.department) : '') + '</div>' +
      '<div class="sep-meta">' + escapeHtml(sep.id) + ' &middot; Resigned: ' + escapeHtml(sep.resignation_date) + ' &middot; Last day: ' + escapeHtml(sep.last_working_day) + (sep.reason ? ' &middot; ' + escapeHtml(sep.reason) : '') + '</div>' +
      '</span>' +
      '<span class="chip ' + (sep.is_complete ? 'chip-green' : 'chip-amber') + '">' + escapeHtml(sep.status) + '</span>' +
      '</div>' +
      bodyHtml +
      '</div>';
  }).join('');

  content.querySelectorAll('.sep-toggle').forEach(function (header) {
    header.addEventListener('click', function () {
      const id = header.getAttribute('data-sep-id');
      if (expandedIds.has(id)) {
        expandedIds.delete(id);
      } else {
        expandedIds.add(id);
      }
      renderSeparations();
    });
  });

  content.querySelectorAll('.sep-step-status').forEach(function (select) {
    select.addEventListener('click', function (event) { event.stopPropagation(); });
    select.addEventListener('change', function () {
      handleStepStatus(select.getAttribute('data-sep-id'), select.getAttribute('data-step-id'), select.value);
    });
  });

  content.querySelectorAll('.audit-box').forEach(function (box) {
    renderAuditHistory(box, box.getAttribute('data-entity'), box.getAttribute('data-entity-id'));
  });

  content.querySelectorAll('.relieving-status-select').forEach(function (select) {
    select.addEventListener('click', function (event) { event.stopPropagation(); });
    select.addEventListener('change', function () {
      handleUpdateSeparation(select.getAttribute('data-sep-id'), { relieving_letter_status: select.value });
    });
  });

  content.querySelectorAll('.fnf-note-input').forEach(function (textarea) {
    textarea.addEventListener('click', function (event) { event.stopPropagation(); });
  });

  content.querySelectorAll('.save-fnf-btn').forEach(function (btn) {
    btn.addEventListener('click', function (event) {
      event.stopPropagation();
      const sepId = btn.getAttribute('data-sep-id');
      const textarea = content.querySelector('.fnf-note-input[data-sep-id="' + sepId + '"]');
      handleUpdateSeparation(sepId, { full_final_settlement_note: textarea.value });
    });
  });

  content.querySelectorAll('.delete-sep-btn').forEach(function (btn) {
    btn.addEventListener('click', function (event) {
      event.stopPropagation();
      handleDeleteSeparation(btn.getAttribute('data-sep-id'));
    });
  });
}

async function handleDeleteSeparation(sepId) {
  if (!confirm('Delete this separation record? This cannot be undone.')) {
    return;
  }
  hidePageError();
  try {
    const response = await fetch(SEPARATIONS_API_BASE + sepId + '/', {
      method: 'DELETE',
      headers: authHeaders(token)
    });
    if (handleUnauthorized(response)) {
      return;
    }
    if (!response.ok && response.status !== 204) {
      throw new Error('Could not delete separation.');
    }
    expandedIds.delete(sepId);
    loadSeparations();
  } catch (err) {
    showPageError(err.message || 'Something went wrong. Please try again.');
  }
}

async function handleStepStatus(sepId, stepId, newStatus) {
  hidePageError();
  try {
    const response = await fetch(
      SEPARATIONS_API_BASE + sepId + '/steps/' + stepId + '/status/',
      {
        method: 'POST',
        headers: authHeaders(token, true),
        body: JSON.stringify({ status: newStatus })
      }
    );

    if (handleUnauthorized(response)) {
      return;
    }

    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      throw new Error(describeApiError(data) || 'Could not update step.');
    }

    if (data.transition && data.transition.moved) {
      showToast(data.transition.message, 'success');
    }
    expandedIds.add(sepId);
    loadSeparations();
  } catch (err) {
    showToast(err.message || 'Something went wrong. Please try again.', 'error');
    loadSeparations();
  }
}

async function handleUpdateSeparation(sepId, payload) {
  hidePageError();
  try {
    const response = await fetch(SEPARATIONS_API_BASE + sepId + '/', {
      method: 'PATCH',
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Could not save changes.');
    }

    expandedIds.add(sepId);
    loadSeparations();
  } catch (err) {
    showPageError(err.message || 'Something went wrong. Please try again.');
  }
}

// ---------- New separation modal ----------

const separationModalOverlay = document.getElementById('separation-modal-overlay');
const separationForm = document.getElementById('separation-form');
const separationFormError = document.getElementById('separation-form-error');
const separationSubmitButton = document.getElementById('separation-submit-button');
const separationCancelButton = document.getElementById('separation-cancel-button');
const sepEmployeeSelect = document.getElementById('sep-employee');

document.getElementById('add-separation-button').addEventListener('click', openSeparationModal);
separationForm.addEventListener('submit', handleSeparationSubmit);
separationCancelButton.addEventListener('click', closeSeparationModal);
separationModalOverlay.addEventListener('click', function (event) {
  if (event.target === separationModalOverlay) {
    closeSeparationModal();
  }
});

async function openSeparationModal() {
  separationFormError.style.display = 'none';
  sepEmployeeSelect.innerHTML = '<option value="">Loading employees...</option>';
  separationModalOverlay.classList.add('open');

  try {
    const response = await fetch(EMPLOYEES_API_BASE, {
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to load employees.');
    }

    const employees = await response.json();
    const active = employees.filter(function (e) {
      return String(e.status || '').toLowerCase() === 'active';
    });

    if (active.length === 0) {
      sepEmployeeSelect.innerHTML = '<option value="">No active employees available</option>';
      return;
    }

    sepEmployeeSelect.innerHTML = active.map(function (emp) {
      return '<option value="' + escapeHtml(emp.id) + '">' + escapeHtml(emp.name) + '</option>';
    }).join('');
  } catch (err) {
    separationFormError.textContent = err.message || 'Could not load employees.';
    separationFormError.style.display = 'block';
  }
}

function closeSeparationModal() {
  separationModalOverlay.classList.remove('open');
  separationForm.reset();
}

async function handleSeparationSubmit(event) {
  event.preventDefault();
  separationSubmitButton.disabled = true;
  separationFormError.style.display = 'none';

  const payload = {
    employee_id: sepEmployeeSelect.value,
    resignation_date: document.getElementById('sep-resignation-date').value,
    last_working_day: document.getElementById('sep-last-working-day').value,
    notice_period_days: parseInt(document.getElementById('sep-notice-period').value, 10) || 0,
    reason: document.getElementById('sep-reason').value
  };

  try {
    const response = await fetch(SEPARATIONS_API_BASE, {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not create separation.');
    }

    const created = await response.json().catch(function () { return {}; });
    closeSeparationModal();
    showToast(created.message || 'Exit process initiated successfully.', 'success');
    loadSeparations();
  } catch (err) {
    separationFormError.textContent = err.message || 'Something went wrong. Please try again.';
    separationFormError.style.display = 'block';
  } finally {
    separationSubmitButton.disabled = false;
  }
}
