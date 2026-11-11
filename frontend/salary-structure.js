const token = getAuthToken();
const STRUCTURE_API_BASE = API_BASE + '/salary-structure/';
const REVISIONS_API_BASE = API_BASE + '/salary-revisions/';
const EMPLOYEES_API_BASE = API_BASE + '/employees/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadStructure();
    loadRevisions();
  });
}

function escapeHtml(value) {
  if (value === undefined || value === null) {
    return '';
  }
  const div = document.createElement('div');
  div.textContent = String(value);
  return div.innerHTML;
}


const STRUCTURE_FIELDS = [
  { key: 'basic_pct', label: 'Basic (% of Gross)' },
  { key: 'hra_pct_metro', label: 'HRA % (Metro, of Basic)' },
  { key: 'hra_pct_nonmetro', label: 'HRA % (Non-metro, of Basic)' },
  { key: 'pf_cap_monthly', label: 'PF Cap (Monthly ₹)' },
  { key: 'gratuity_pct', label: 'Gratuity (% of Basic)' },
  { key: 'esi_limit_monthly', label: 'ESI Eligibility Limit (Monthly ₹)' },
  { key: 'professional_tax_monthly', label: 'Professional Tax (Monthly ₹)' }
];

async function loadStructure() {
  const content = document.getElementById('structure-content');
  try {
    const response = await fetch(STRUCTURE_API_BASE, {
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to load salary structure.');
    }

    const structure = await response.json();
    renderStructureForm(structure);
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' +
      escapeHtml(err.message || 'Could not load salary structure.') +
      '</div><button type="button" class="btn-secondary" id="retry-structure-button">Retry</button></div>';
    document.getElementById('retry-structure-button').addEventListener('click', loadStructure);
  }
}

function renderStructureForm(structure) {
  const content = document.getElementById('structure-content');
  content.innerHTML = '<form id="structure-form"><div class="form-grid">' +
    STRUCTURE_FIELDS.map(function (field) {
      return '<div class="field">' +
        '<label for="field-' + field.key + '">' + field.label + '</label>' +
        '<input type="number" step="any" id="field-' + field.key + '" value="' + escapeHtml(structure[field.key]) + '">' +
        '</div>';
    }).join('') +
    '</div><div class="form-actions"><button type="submit" class="btn-primary" id="structure-save-button">Save Changes</button></div></form>';

  document.getElementById('structure-form').addEventListener('submit', handleStructureSubmit);
}

async function handleStructureSubmit(event) {
  event.preventDefault();
  const saveButton = document.getElementById('structure-save-button');
  const errorEl = document.getElementById('structure-form-error');
  const successEl = document.getElementById('structure-success');
  errorEl.style.display = 'none';
  successEl.style.display = 'none';
  saveButton.disabled = true;

  const payload = {};
  STRUCTURE_FIELDS.forEach(function (field) {
    const value = parseFloat(document.getElementById('field-' + field.key).value);
    if (!isNaN(value)) {
      payload[field.key] = value;
    }
  });

  try {
    const response = await fetch(STRUCTURE_API_BASE, {
      method: 'PATCH',
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Could not save salary structure.');
    }

    const updated = await response.json();
    renderStructureForm(updated);
    successEl.textContent = 'Salary structure updated successfully.';
    successEl.style.display = 'block';
  } catch (err) {
    errorEl.textContent = err.message || 'Something went wrong. Please try again.';
    errorEl.style.display = 'block';
  } finally {
    saveButton.disabled = false;
  }
}

// ---------- Revision queue ----------

let allRevisions = [];
const revisionPageError = document.getElementById('revision-page-error');

async function loadRevisions() {
  const content = document.getElementById('revisions-content');
  revisionPageError.style.display = 'none';

  try {
    const response = await fetch(REVISIONS_API_BASE, {
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to load salary revisions.');
    }

    allRevisions = await response.json();
    renderRevisions();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' +
      escapeHtml(err.message || 'Could not load salary revisions.') +
      '</div><button type="button" class="btn-secondary" id="retry-revisions-button">Retry</button></div>';
    document.getElementById('retry-revisions-button').addEventListener('click', loadRevisions);
  }
}

function revisionStatusChip(status) {
  if (status === 'Approved') {
    return '<span class="chip chip-green">Approved</span>';
  }
  if (status === 'Rejected') {
    return '<span class="chip chip-red">Rejected</span>';
  }
  return '<span class="chip chip-amber">Pending</span>';
}

function renderRevisions() {
  const content = document.getElementById('revisions-content');

  if (allRevisions.length === 0) {
    content.innerHTML = '<div class="message">No salary revisions proposed yet.</div>';
    return;
  }

  const rows = allRevisions.map(function (rev) {
    const actions = rev.status === 'Pending'
      ? '<button type="button" class="btn-approve btn-row approve-rev-btn" data-id="' + escapeHtml(rev.id) + '">Approve</button>' +
        '<button type="button" class="btn-delete btn-row reject-rev-btn" data-id="' + escapeHtml(rev.id) + '">Reject</button>'
      : (rev.status === 'Approved'
        ? '<a href="employees.html" class="btn-view">Open Letter Studio</a>'
        : '');

    return '<tr>' +
      '<td>' + escapeHtml(rev.id) + '</td>' +
      '<td>' + escapeHtml(rev.employee_name || rev.employee_id) + '</td>' +
      '<td>' + escapeHtml(rev.current_ctc) + '</td>' +
      '<td>' + escapeHtml(rev.proposed_ctc) + '</td>' +
      '<td>' + escapeHtml(rev.effective_date) + '</td>' +
      '<td>' + (rev.reason ? escapeHtml(rev.reason) : '&mdash;') + '</td>' +
      '<td>' + revisionStatusChip(rev.status) + '</td>' +
      '<td>' + actions + '</td>' +
      '</tr>';
  }).join('');

  content.innerHTML =
    '<table><thead><tr><th>ID</th><th>Employee</th><th>Current CTC</th><th>Proposed CTC</th><th>Effective</th><th>Reason</th><th>Status</th><th>Actions</th></tr></thead><tbody>' + rows + '</tbody></table>';

  content.querySelectorAll('.approve-rev-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      handleRevisionAction(btn.getAttribute('data-id'), 'approve');
    });
  });

  content.querySelectorAll('.reject-rev-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      handleRevisionAction(btn.getAttribute('data-id'), 'reject');
    });
  });
}

async function handleRevisionAction(revId, action) {
  const confirmed = confirm('Are you sure you want to ' + action + ' this revision?');
  if (!confirmed) {
    return;
  }

  try {
    const response = await fetch(REVISIONS_API_BASE + revId + '/' + action + '/', {
      method: 'POST',
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not update revision.');
    }

    loadRevisions();
  } catch (err) {
    revisionPageError.textContent = err.message || 'Something went wrong. Please try again.';
    revisionPageError.style.display = 'block';
  }
}

// ---------- Propose revision modal ----------

const revisionModalOverlay = document.getElementById('revision-modal-overlay');
const revisionForm = document.getElementById('revision-form');
const revisionFormError = document.getElementById('revision-form-error');
const revisionSubmitButton = document.getElementById('revision-submit-button');
const revisionCancelButton = document.getElementById('revision-cancel-button');
const revisionEmployeeSelect = document.getElementById('revision-employee');

document.getElementById('add-revision-button').addEventListener('click', openRevisionModal);
revisionForm.addEventListener('submit', handleRevisionSubmit);
revisionCancelButton.addEventListener('click', closeRevisionModal);
revisionModalOverlay.addEventListener('click', function (event) {
  if (event.target === revisionModalOverlay) {
    closeRevisionModal();
  }
});

async function openRevisionModal() {
  revisionFormError.style.display = 'none';
  revisionEmployeeSelect.innerHTML = '<option value="">Loading employees...</option>';
  revisionModalOverlay.classList.add('open');

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
    if (employees.length === 0) {
      revisionEmployeeSelect.innerHTML = '<option value="">No employees available</option>';
      return;
    }

    revisionEmployeeSelect.innerHTML = employees.map(function (emp) {
      return '<option value="' + escapeHtml(emp.id) + '" data-ctc="' + escapeHtml(emp.ctc) + '">' + escapeHtml(emp.name) + '</option>';
    }).join('');

    revisionEmployeeSelect.dispatchEvent(new Event('change'));
  } catch (err) {
    revisionFormError.textContent = err.message || 'Could not load employees.';
    revisionFormError.style.display = 'block';
  }
}

revisionEmployeeSelect.addEventListener('change', function () {
  const selected = revisionEmployeeSelect.options[revisionEmployeeSelect.selectedIndex];
  if (selected && selected.getAttribute('data-ctc')) {
    document.getElementById('revision-current-ctc').value = selected.getAttribute('data-ctc');
  }
});

function closeRevisionModal() {
  revisionModalOverlay.classList.remove('open');
  revisionForm.reset();
}

async function handleRevisionSubmit(event) {
  event.preventDefault();
  revisionSubmitButton.disabled = true;
  revisionFormError.style.display = 'none';

  const payload = {
    employee_id: revisionEmployeeSelect.value,
    current_ctc: parseFloat(document.getElementById('revision-current-ctc').value),
    proposed_ctc: parseFloat(document.getElementById('revision-proposed-ctc').value),
    effective_date: document.getElementById('revision-effective-date').value,
    reason: document.getElementById('revision-reason').value
  };

  try {
    const response = await fetch(REVISIONS_API_BASE, {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not propose revision.');
    }

    closeRevisionModal();
    loadRevisions();
  } catch (err) {
    revisionFormError.textContent = err.message || 'Something went wrong. Please try again.';
    revisionFormError.style.display = 'block';
  } finally {
    revisionSubmitButton.disabled = false;
  }
}
