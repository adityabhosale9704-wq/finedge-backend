const token = getAuthToken();
const SOP_API_BASE = API_BASE + '/sop/';

if (!token) {
  window.location.href = 'login.html';
}

let currentType = 'recruitment';
let steps = [];
let editingId = null;
let deletingId = null;
let busy = false;

const content = document.getElementById('sop-content');
const stepModal = document.getElementById('step-modal-overlay');
const deleteModal = document.getElementById('delete-modal-overlay');
const stepForm = document.getElementById('step-form');
const stepFormError = document.getElementById('step-form-error');
const stepSubmitButton = document.getElementById('step-submit-button');

function escapeHtml(value) {
  if (value === undefined || value === null) {
    return '';
  }
  const div = document.createElement('div');
  div.textContent = String(value);
  return div.innerHTML;
}

async function api(path, options) {
  const response = await fetch(SOP_API_BASE + path, Object.assign({
    headers: authHeaders(token, true)
  }, options || {}));

  if (response.status === 401) {
    logout();
    throw new Error('Session expired.');
  }

  const data = await response.json().catch(function () { return null; });
  if (!response.ok) {
    throw new Error(describeApiError(data) || 'Request failed (' + response.status + ').');
  }
  return data;
}

async function loadSteps() {
  content.innerHTML = '<div class="loading-state"><div class="spinner"></div><div>Loading steps...</div></div>';
  try {
    steps = await api(currentType + '/steps/');
    render();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message || 'Could not load steps.') +
      '</div><button type="button" class="btn-secondary" id="retry-button">Retry</button></div>';
    document.getElementById('retry-button').addEventListener('click', loadSteps);
  }
}

function render() {
  if (steps.length === 0) {
    content.innerHTML = '<div class="message">No steps defined for this process yet. Use "+ Add Step" to create the first one.</div>';
    return;
  }

  const rows = steps.map(function (step, index) {
    const required = step.required
      ? '<span class="chip chip-green">Required</span>'
      : '<span class="chip chip-navy">Optional</span>';
    const active = step.active
      ? '<span class="chip chip-green">Active</span>'
      : '<span class="chip chip-red">Inactive</span>';
    const isFirst = index === 0;
    const isLast = index === steps.length - 1;

    return '<tr class="' + (step.active ? '' : 'inactive') + '">' +
      '<td class="sop-no">' + escapeHtml(step.step_no) + '</td>' +
      '<td>' + escapeHtml(step.who) + '</td>' +
      '<td>' + escapeHtml(step.when) + '</td>' +
      '<td class="sop-how">' + escapeHtml(step.how) + '</td>' +
      '<td>' + required + '</td>' +
      '<td>' + active + '</td>' +
      '<td class="sop-actions">' +
      '<button type="button" class="icon-btn move-btn" data-dir="up" data-id="' + escapeHtml(step.id) + '" title="Move up"' + (isFirst ? ' disabled' : '') + '>&#9650;</button>' +
      '<button type="button" class="icon-btn move-btn" data-dir="down" data-id="' + escapeHtml(step.id) + '" title="Move down"' + (isLast ? ' disabled' : '') + '>&#9660;</button>' +
      '<button type="button" class="btn-edit btn-row edit-btn" data-id="' + escapeHtml(step.id) + '">Edit</button>' +
      '<button type="button" class="btn-delete btn-row delete-btn" data-id="' + escapeHtml(step.id) + '">Delete</button>' +
      '</td>' +
      '</tr>';
  }).join('');

  content.innerHTML =
    '<table class="sop-table">' +
    '<thead><tr><th>#</th><th>Who</th><th>When</th><th>How</th><th>Required</th><th>Status</th><th>Actions</th></tr></thead>' +
    '<tbody>' + rows + '</tbody></table>';

  content.querySelectorAll('.edit-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { openStepModal(btn.getAttribute('data-id')); });
  });
  content.querySelectorAll('.delete-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { openDeleteModal(btn.getAttribute('data-id')); });
  });
  content.querySelectorAll('.move-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      moveStep(btn.getAttribute('data-id'), btn.getAttribute('data-dir'));
    });
  });
}

// ---------- Tabs ----------

document.querySelectorAll('#sop-tabs .tab').forEach(function (tab) {
  tab.addEventListener('click', function () {
    currentType = tab.getAttribute('data-type');
    document.querySelectorAll('#sop-tabs .tab').forEach(function (t) {
      t.classList.toggle('active', t === tab);
    });
    loadSteps();
  });
});

// ---------- Add / edit ----------

document.getElementById('add-step-button').addEventListener('click', function () { openStepModal(null); });
document.getElementById('step-cancel-button').addEventListener('click', closeStepModal);
stepModal.addEventListener('click', function (event) {
  if (event.target === stepModal) { closeStepModal(); }
});

function openStepModal(id) {
  editingId = id;
  const step = id ? steps.find(function (s) { return s.id === id; }) : null;
  document.getElementById('step-modal-title').textContent = step ? 'Edit Step ' + step.step_no : 'Add Step';
  stepSubmitButton.textContent = step ? 'Save Changes' : 'Add Step';
  document.getElementById('step-who').value = step ? step.who : '';
  document.getElementById('step-when').value = step ? step.when : '';
  document.getElementById('step-how').value = step ? step.how : '';
  document.getElementById('step-tat').value = step ? step.tat_days : 1;
  document.getElementById('step-required').checked = step ? step.required : true;
  document.getElementById('step-active').checked = step ? step.active : true;
  stepFormError.style.display = 'none';
  stepModal.classList.add('open');
  document.getElementById('step-who').focus();
}

function closeStepModal() {
  stepModal.classList.remove('open');
  editingId = null;
}

stepForm.addEventListener('submit', async function (event) {
  event.preventDefault();

  const payload = {
    who: document.getElementById('step-who').value.trim(),
    when: document.getElementById('step-when').value.trim(),
    how: document.getElementById('step-how').value.trim(),
    tat_days: parseInt(document.getElementById('step-tat').value, 10),
    required: document.getElementById('step-required').checked,
    active: document.getElementById('step-active').checked
  };

  const missing = ['who', 'when', 'how'].filter(function (field) { return !payload[field]; });
  if (missing.length > 0) {
    stepFormError.textContent = 'Please fill in: ' + missing.join(', ') + '.';
    stepFormError.style.display = 'block';
    return;
  }
  if (isNaN(payload.tat_days) || payload.tat_days < 0) {
    payload.tat_days = 1;
  }

  stepSubmitButton.disabled = true;
  try {
    if (editingId) {
      steps = await api('steps/' + editingId + '/', { method: 'PATCH', body: JSON.stringify(payload) });
      showToast('Step updated.', 'success');
    } else {
      steps = await api(currentType + '/steps/', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Step added.', 'success');
    }
    closeStepModal();
    render();
  } catch (err) {
    stepFormError.textContent = err.message || 'Something went wrong. Please try again.';
    stepFormError.style.display = 'block';
  } finally {
    stepSubmitButton.disabled = false;
  }
});

// ---------- Delete ----------

document.getElementById('delete-cancel-button').addEventListener('click', closeDeleteModal);
deleteModal.addEventListener('click', function (event) {
  if (event.target === deleteModal) { closeDeleteModal(); }
});

function openDeleteModal(id) {
  const step = steps.find(function (s) { return s.id === id; });
  if (!step) { return; }
  deletingId = id;
  document.getElementById('delete-modal-text').textContent =
    'Delete step ' + step.step_no + ' (' + step.who + ': ' + step.how + ')?';
  deleteModal.classList.add('open');
}

function closeDeleteModal() {
  deleteModal.classList.remove('open');
  deletingId = null;
}

document.getElementById('delete-confirm-button').addEventListener('click', async function () {
  if (!deletingId) { return; }
  const button = this;
  button.disabled = true;
  try {
    steps = await api('steps/' + deletingId + '/', { method: 'DELETE' });
    closeDeleteModal();
    render();
    showToast('Step deleted. Remaining steps renumbered.', 'success');
  } catch (err) {
    showToast(err.message || 'Could not delete the step.', 'error');
  } finally {
    button.disabled = false;
  }
});

// ---------- Reorder ----------

async function moveStep(id, direction) {
  if (busy) { return; }
  const index = steps.findIndex(function (s) { return s.id === id; });
  const target = direction === 'up' ? index - 1 : index + 1;
  if (index < 0 || target < 0 || target >= steps.length) { return; }

  const ids = steps.map(function (s) { return s.id; });
  const moved = ids.splice(index, 1)[0];
  ids.splice(target, 0, moved);

  busy = true;
  content.style.opacity = '0.6';
  try {
    steps = await api(currentType + '/steps/reorder/', {
      method: 'POST',
      body: JSON.stringify({ ordered_ids: ids })
    });
    render();
  } catch (err) {
    showToast(err.message || 'Could not reorder the steps.', 'error');
    loadSteps();
  } finally {
    busy = false;
    content.style.opacity = '';
  }
}

if (token) {
  loadSteps();
}
