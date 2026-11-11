const token = getAuthToken();
const WORKINDIA_API_BASE = API_BASE + '/workindia/';
const REQUISITIONS_API_BASE = API_BASE + '/requisitions/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadUploadTab();
    loadSelectedTab();
    loadLogTab();
  });
}

let uploadCandidates = [];
let selectedCandidates = [];
let logCandidates = [];
let searchTerm = '';
let searchDebounceTimer = null;

const pageError = document.getElementById('page-error');
const uploadError = document.getElementById('upload-error');
const uploadSuccess = document.getElementById('upload-success');

function escapeHtml(value) {
  if (value === undefined || value === null) {
    return '';
  }
  const div = document.createElement('div');
  div.textContent = String(value);
  return div.innerHTML;
}


function showPageError(message) {
  pageError.textContent = message;
  pageError.style.display = 'block';
}

function hidePageError() {
  pageError.textContent = '';
  pageError.style.display = 'none';
}

// ---------- Tabs ----------

document.querySelectorAll('.wi-tab-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    document.querySelectorAll('.wi-tab-btn').forEach(function (b) { b.classList.remove('active'); });
    document.querySelectorAll('.wi-tab-panel').forEach(function (p) { p.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById('tab-' + btn.getAttribute('data-tab')).classList.add('active');
  });
});

// ---------- Upload tab ----------

async function loadUploadTab() {
  const content = document.getElementById('upload-content');
  hidePageError();
  try {
    const url = WORKINDIA_API_BASE + '?stage=Uploaded' + (searchTerm ? '&q=' + encodeURIComponent(searchTerm) : '');
    const response = await fetch(url, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load uploaded candidates.');
    uploadCandidates = await response.json();
    renderUploadTable();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message) + '</div><button type="button" class="btn-secondary" id="retry-upload-button">Retry</button></div>';
    document.getElementById('retry-upload-button').addEventListener('click', loadUploadTab);
  }
}

function renderUploadTable() {
  const content = document.getElementById('upload-content');
  if (uploadCandidates.length === 0) {
    content.innerHTML = '<div class="message">No uploaded candidates found.</div>';
    return;
  }
  const rows = uploadCandidates.map(function (cand) {
    return '<tr>' +
      '<td><input type="checkbox" class="wi-select-checkbox" data-id="' + escapeHtml(cand.id) + '"></td>' +
      '<td>' + escapeHtml(cand.full_name) + '</td>' +
      '<td>' + escapeHtml(cand.mobile) + '</td>' +
      '<td>' + escapeHtml(cand.city) + '</td>' +
      '<td>' + escapeHtml(cand.qualification) + '</td>' +
      '<td>' + escapeHtml(cand.relevant_experience || cand.experience_level) + '</td>' +
      '<td>' + escapeHtml(cand.skills) + '</td>' +
      '<td><button type="button" class="btn-delete btn-row wi-remove-btn" data-id="' + escapeHtml(cand.id) + '">Remove</button></td>' +
      '</tr>';
  }).join('');

  content.innerHTML =
    '<table>' +
    '<thead><tr><th></th><th>Name</th><th>Mobile</th><th>City</th><th>Qualification</th><th>Experience</th><th>Skills</th><th>Actions</th></tr></thead>' +
    '<tbody>' + rows + '</tbody>' +
    '</table>';

  content.querySelectorAll('.wi-remove-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { handleRemove(btn.getAttribute('data-id'), loadUploadTab); });
  });
}

document.getElementById('search-input').addEventListener('input', function (event) {
  searchTerm = event.target.value.trim();
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(loadUploadTab, 300);
});

document.getElementById('bulk-select-button').addEventListener('click', async function () {
  const checked = Array.from(document.querySelectorAll('.wi-select-checkbox:checked')).map(function (cb) {
    return cb.getAttribute('data-id');
  });
  if (checked.length === 0) {
    showPageError('Check at least one candidate to move to Selected.');
    return;
  }
  hidePageError();
  try {
    await Promise.all(checked.map(function (id) {
      return fetch(WORKINDIA_API_BASE + id + '/select/', {
        method: 'POST',
        headers: authHeaders(token)
      });
    }));
    loadUploadTab();
    loadSelectedTab();
  } catch (err) {
    showPageError('Could not move candidates to Selected.');
  }
});

// ---------- CSV import ----------

document.getElementById('import-button').addEventListener('click', handleImport);

async function handleImport() {
  uploadError.style.display = 'none';
  uploadSuccess.style.display = 'none';

  const fileInput = document.getElementById('csv-file-input');
  const file = fileInput.files[0];

  if (!file) {
    uploadError.textContent = 'Please choose a CSV file first.';
    uploadError.style.display = 'block';
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  const importButton = document.getElementById('import-button');
  importButton.disabled = true;

  try {
    const response = await fetch(WORKINDIA_API_BASE + 'import/', {
      method: 'POST',
      headers: authHeaders(token),
      body: formData
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not import CSV file.');
    }

    const data = await response.json();
    uploadSuccess.textContent = 'Imported ' + data.imported + ' candidate(s) successfully.' +
      (data.skipped_duplicates ? ' Skipped ' + data.skipped_duplicates + ' duplicate mobile number(s).' : '');
    uploadSuccess.style.display = 'block';
    fileInput.value = '';
    loadUploadTab();
  } catch (err) {
    uploadError.textContent = err.message || 'Something went wrong. Please try again.';
    uploadError.style.display = 'block';
  } finally {
    importButton.disabled = false;
  }
}

// ---------- Selected tab ----------

async function loadSelectedTab() {
  const content = document.getElementById('selected-content');
  try {
    const response = await fetch(WORKINDIA_API_BASE + '?stage=Selected', { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load selected candidates.');
    selectedCandidates = await response.json();
    renderSelectedTable();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message) + '</div><button type="button" class="btn-secondary" id="retry-selected-button">Retry</button></div>';
    document.getElementById('retry-selected-button').addEventListener('click', loadSelectedTab);
  }
}

function renderSelectedTable() {
  const content = document.getElementById('selected-content');
  if (selectedCandidates.length === 0) {
    content.innerHTML = '<div class="message">No candidates in Selected stage.</div>';
    return;
  }
  const rows = selectedCandidates.map(function (cand) {
    return '<tr>' +
      '<td>' + escapeHtml(cand.full_name) + '</td>' +
      '<td>' + escapeHtml(cand.mobile) + '</td>' +
      '<td>' + escapeHtml(cand.city) + '</td>' +
      '<td>' + escapeHtml(cand.skills) + '</td>' +
      '<td>' +
      '<button type="button" class="btn-secondary btn-row wi-log-call-btn" data-id="' + escapeHtml(cand.id) + '">&#128222; Log Call</button>' +
      (cand.promoted ? '<span class="chip chip-green">Promoted</span>' : '<button type="button" class="btn-primary btn-row wi-promote-btn" data-id="' + escapeHtml(cand.id) + '">Select for Interview</button>') +
      '<button type="button" class="btn-delete btn-row wi-remove-btn" data-id="' + escapeHtml(cand.id) + '">Remove</button>' +
      '</td>' +
      '</tr>';
  }).join('');

  content.innerHTML =
    '<table>' +
    '<thead><tr><th>Name</th><th>Mobile</th><th>City</th><th>Skills</th><th>Actions</th></tr></thead>' +
    '<tbody>' + rows + '</tbody>' +
    '</table>';

  wireRowActions(content, loadSelectedTab);
}

// ---------- Interview Calling Log tab ----------

async function loadLogTab() {
  const content = document.getElementById('log-content');
  try {
    const response = await fetch(WORKINDIA_API_BASE + '?stage=Called', { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load calling log.');
    logCandidates = await response.json();
    renderLogList();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message) + '</div><button type="button" class="btn-secondary" id="retry-log-button">Retry</button></div>';
    document.getElementById('retry-log-button').addEventListener('click', loadLogTab);
  }
}

function renderLogList() {
  const content = document.getElementById('log-content');
  if (logCandidates.length === 0) {
    content.innerHTML = '<div class="message">No calls logged yet.</div>';
    return;
  }
  const sorted = logCandidates.slice().sort(function (a, b) {
    return String(b.interview_datetime || '').localeCompare(String(a.interview_datetime || ''));
  });

  content.innerHTML = sorted.map(function (cand) {
    return '<div class="diary-entry">' +
      '<div class="diary-entry-header">' +
      '<span class="step-name">' + escapeHtml(cand.full_name) + ' &middot; ' + escapeHtml(cand.mobile) + '</span>' +
      '<span class="chip">' + escapeHtml(cand.call_status || 'No status') + '</span>' +
      '</div>' +
      '<div class="step-meta" style="margin-top: 6px;">' +
      (cand.interview_datetime ? 'Interview: ' + escapeHtml(cand.interview_datetime) + ' &middot; ' : '') +
      (cand.position_discussed ? 'Position: ' + escapeHtml(cand.position_discussed) + ' &middot; ' : '') +
      (cand.email ? escapeHtml(cand.email) + ' &middot; ' : '') +
      (cand.call_notes ? escapeHtml(cand.call_notes) : 'No notes') +
      '</div>' +
      '<div class="form-actions" style="margin-top: 10px;">' +
      '<button type="button" class="btn-secondary btn-row wi-log-call-btn" data-id="' + escapeHtml(cand.id) + '">&#128222; Log Call</button>' +
      (cand.promoted ? '<span class="chip chip-green">Promoted</span>' : '<button type="button" class="btn-primary btn-row wi-promote-btn" data-id="' + escapeHtml(cand.id) + '">Select for Interview</button>') +
      '<button type="button" class="btn-delete btn-row wi-remove-btn" data-id="' + escapeHtml(cand.id) + '">Remove</button>' +
      '</div>' +
      '</div>';
  }).join('');

  wireRowActions(content, loadLogTab);
}

// ---------- Shared row actions ----------

function wireRowActions(container, refreshFn) {
  container.querySelectorAll('.wi-promote-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { openPromoteModal(btn.getAttribute('data-id')); });
  });
  container.querySelectorAll('.wi-log-call-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { openLogCallModal(btn.getAttribute('data-id')); });
  });
  container.querySelectorAll('.wi-remove-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { handleRemove(btn.getAttribute('data-id'), refreshFn); });
  });
}

async function handleRemove(id, refreshFn) {
  if (!confirm('Remove this candidate from the pipeline?')) return;
  const response = await fetch(WORKINDIA_API_BASE + id + '/remove/', {
    method: 'POST',
    headers: authHeaders(token)
  });
  if (handleUnauthorized(response)) return;
  loadUploadTab();
  loadSelectedTab();
  loadLogTab();
}

// ---------- Promote modal ----------

const promoteModalOverlay = document.getElementById('promote-modal-overlay');
const promoteForm = document.getElementById('promote-form');
const promoteFormError = document.getElementById('promote-form-error');
const promoteSubmitButton = document.getElementById('promote-submit-button');
const promoteCancelButton = document.getElementById('promote-cancel-button');
const promoteRequisitionSelect = document.getElementById('promote-requisition-select');

let promotingCandidateId = null;

promoteForm.addEventListener('submit', handlePromoteSubmit);
promoteCancelButton.addEventListener('click', closePromoteModal);
promoteModalOverlay.addEventListener('click', function (event) {
  if (event.target === promoteModalOverlay) {
    closePromoteModal();
  }
});

async function openPromoteModal(candId) {
  promotingCandidateId = candId;
  promoteFormError.style.display = 'none';
  promoteRequisitionSelect.innerHTML = '<option value="">Loading requisitions...</option>';
  promoteModalOverlay.classList.add('open');

  try {
    const response = await fetch(REQUISITIONS_API_BASE, {
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to load requisitions.');
    }

    const requisitions = await response.json();

    if (requisitions.length === 0) {
      promoteRequisitionSelect.innerHTML = '<option value="">No requisitions available</option>';
      return;
    }

    promoteRequisitionSelect.innerHTML = requisitions.map(function (req) {
      return '<option value="' + escapeHtml(req.id) + '">' +
        escapeHtml(req.role) + ' — ' + escapeHtml(req.branch) + '</option>';
    }).join('');
  } catch (err) {
    promoteFormError.textContent = err.message || 'Could not load requisitions.';
    promoteFormError.style.display = 'block';
  }
}

function closePromoteModal() {
  promoteModalOverlay.classList.remove('open');
  promoteForm.reset();
  promotingCandidateId = null;
}

async function handlePromoteSubmit(event) {
  event.preventDefault();
  if (!promotingCandidateId) {
    return;
  }

  const requisitionId = promoteRequisitionSelect.value;
  if (!requisitionId) {
    promoteFormError.textContent = 'Please select a requisition.';
    promoteFormError.style.display = 'block';
    return;
  }

  promoteSubmitButton.disabled = true;
  promoteFormError.style.display = 'none';

  try {
    const response = await fetch(WORKINDIA_API_BASE + promotingCandidateId + '/promote/', {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify({ requisition_id: requisitionId })
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not select candidate for interview.');
    }

    closePromoteModal();
    loadSelectedTab();
    loadLogTab();
  } catch (err) {
    promoteFormError.textContent = err.message || 'Something went wrong. Please try again.';
    promoteFormError.style.display = 'block';
  } finally {
    promoteSubmitButton.disabled = false;
  }
}

// ---------- Log Call modal ----------

const logCallModalOverlay = document.getElementById('log-call-modal-overlay');
const logCallForm = document.getElementById('log-call-form');
const logCallFormError = document.getElementById('log-call-form-error');
let loggingCandidateId = null;

document.getElementById('log-call-cancel-button').addEventListener('click', closeLogCallModal);
logCallModalOverlay.addEventListener('click', function (event) {
  if (event.target === logCallModalOverlay) closeLogCallModal();
});

function openLogCallModal(candId) {
  loggingCandidateId = candId;
  logCallForm.reset();
  logCallFormError.style.display = 'none';
  logCallModalOverlay.classList.add('open');
}

function closeLogCallModal() {
  logCallModalOverlay.classList.remove('open');
  logCallForm.reset();
  loggingCandidateId = null;
}

logCallForm.addEventListener('submit', async function (event) {
  event.preventDefault();
  if (!loggingCandidateId) return;

  const datetimeValue = document.getElementById('log-call-datetime').value;
  const payload = {
    call_status: document.getElementById('log-call-status').value,
    call_notes: document.getElementById('log-call-notes').value,
    email: document.getElementById('log-call-email').value,
    position_discussed: document.getElementById('log-call-position').value,
    interview_datetime: datetimeValue ? new Date(datetimeValue).toISOString() : null
  };

  try {
    const response = await fetch(WORKINDIA_API_BASE + loggingCandidateId + '/log-call/', {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Could not log call.');

    closeLogCallModal();
    loadSelectedTab();
    loadLogTab();
  } catch (err) {
    logCallFormError.textContent = err.message;
    logCallFormError.style.display = 'block';
  }
});
