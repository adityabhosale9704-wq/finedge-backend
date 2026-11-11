const token = getAuthToken();
const REQUISITIONS_API_BASE = API_BASE + '/requisitions/';
const CANDIDATES_API_BASE = API_BASE + '/candidates/';
const BRANCHES_API_BASE = API_BASE + '/branches/';
const REFERENCE_CHECKS_API_BASE = API_BASE + '/reference-checks/';
const ROLES_API_BASE = API_BASE + '/roles/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadAll();
    loadBranchOptions();
  });
}


async function loadBranchOptions() {
  try {
    const response = await fetch(BRANCHES_API_BASE, { headers: authHeaders(token) });
    if (!response.ok) {
      return;
    }
    const branches = await response.json();
    const branchSelect = document.getElementById('req-branch');
    branchSelect.innerHTML = '<option value="" disabled selected>Select branch</option>' +
      branches.map(function (b) {
        return '<option value="' + b.name.replace(/"/g, '&quot;') + '">' + b.name + '</option>';
      }).join('');
  } catch (err) {
    // Leave the placeholder option in place if master data can't be loaded.
  }
}

let allRequisitions = [];
let allCandidates = [];
let allReferenceChecks = [];
let appointmentLetterEligibility = {};
let allRoles = [];

function findJobDescriptionForRole(roleTitle) {
  if (!roleTitle) return '';
  const match = allRoles.find(function (r) {
    return (r.title || '').trim().toLowerCase() === roleTitle.trim().toLowerCase();
  });
  return match ? (match.job_description || '') : '';
}

// Looked up on demand (not a top-level const): loadAll() is invoked near the top of
// this script, before this point is reached, and would otherwise hit a
// "Cannot access before initialization" error and never render anything.
function showPageError(message) {
  const pageError = document.getElementById('page-error');
  pageError.textContent = message;
  pageError.style.display = 'block';
}

function hidePageError() {
  const pageError = document.getElementById('page-error');
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

const AVATAR_PALETTE = ['#1b2a4a', '#a67f2c', '#2a5db0', '#1e7e34', '#8a3ab2', '#b7472a', '#0f766e'];

function getInitials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return '?';
  }
  if (parts.length === 1) {
    return parts[0].charAt(0).toUpperCase();
  }
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

function getAvatarColor(name) {
  const str = String(name || '?');
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) % AVATAR_PALETTE.length;
  }
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}


async function loadAll() {
  hidePageError();
  try {
    const [reqResponse, candResponse, refResponse, rolesResponse] = await Promise.all([
      fetch(REQUISITIONS_API_BASE, { headers: authHeaders(token) }),
      fetch(CANDIDATES_API_BASE, { headers: authHeaders(token) }),
      fetch(REFERENCE_CHECKS_API_BASE, { headers: authHeaders(token) }),
      fetch(ROLES_API_BASE, { headers: authHeaders(token) })
    ]);

    if (handleUnauthorized(reqResponse) || handleUnauthorized(candResponse) || handleUnauthorized(refResponse) || handleUnauthorized(rolesResponse)) {
      return;
    }

    // Roles are only used for an optional job-description lookup, so a missing /roles/
    // endpoint (e.g. an older deployed backend) must not block the whole page.
    if (!reqResponse.ok || !candResponse.ok || !refResponse.ok) {
      throw new Error('Failed to load recruitment data.');
    }

    allRequisitions = await reqResponse.json();
    allCandidates = await candResponse.json();
    allReferenceChecks = await refResponse.json();
    allRoles = rolesResponse.ok ? await rolesResponse.json() : [];
    await loadAppointmentLetterEligibility();
    renderAll();
  } catch (err) {
    const retryHtml = '<div class="error-state"><div>' +
      escapeHtml(err.message || 'Could not load recruitment data.') +
      '</div><button type="button" class="btn-secondary retry-recruitment-button">Retry</button></div>';
    document.getElementById('requisitions-content').innerHTML = retryHtml;
    document.getElementById('candidates-content').innerHTML = retryHtml;
    document.querySelectorAll('.retry-recruitment-button').forEach(function (btn) {
      btn.addEventListener('click', loadAll);
    });
  }
}

async function loadAppointmentLetterEligibility() {
  // Computed client-side from allReferenceChecks (already loaded in one
  // request by loadAll) instead of calling the backend once per
  // Documents-Pending candidate — same "2 positive references" rule the
  // backend's /can-issue-appointment-letter/ endpoint applies, with zero
  // extra network round trips.
  appointmentLetterEligibility = {};
  allCandidates
    .filter(function (c) { return c.stage === 'Documents Pending'; })
    .forEach(function (cand) {
      const positiveCount = allReferenceChecks.filter(function (r) {
        return r.candidate_id === cand.id && r.status === 'Positive';
      }).length;
      appointmentLetterEligibility[cand.id] = {
        can_issue: positiveCount >= 2,
        positive_count: positiveCount
      };
    });
}

function renderAll() {
  renderKpis();
  renderRequisitionsTable();
  renderCandidatesList();
}

function renderKpis() {
  const openRequisitions = allRequisitions.filter(function (r) { return r.stage !== 'Closed'; });
  const totalOpenings = openRequisitions.reduce(function (sum, r) { return sum + (r.openings || 0); }, 0);
  document.getElementById('kpi-open-requisitions').textContent = openRequisitions.length + ' / ' + totalOpenings;

  const inPipeline = allCandidates.filter(function (c) {
    return ['Joined', 'Rejected', 'Withdrawn'].indexOf(c.stage) === -1;
  }).length;
  document.getElementById('kpi-in-pipeline').textContent = inPipeline;

  document.getElementById('kpi-docs-pending').textContent = allCandidates.filter(function (c) {
    return c.stage === 'Documents Pending';
  }).length;

  document.getElementById('kpi-joined').textContent = allCandidates.filter(function (c) {
    return c.stage === 'Joined';
  }).length;
}

function computeAgingChip(req) {
  const raisedDate = new Date(req.raised_date + 'T00:00:00');
  const today = new Date();
  const daysElapsed = Math.max(0, Math.floor((today - raisedDate) / (1000 * 60 * 60 * 24)));
  const tatDays = req.tat_days || 30;
  const ratio = daysElapsed / tatDays;

  let chipClass = 'chip-green';
  if (ratio >= 1) {
    chipClass = 'chip-red';
  } else if (ratio >= 0.6) {
    chipClass = 'chip-amber';
  }

  return '<span class="chip ' + chipClass + '">' + daysElapsed + '/' + tatDays + 'd</span>';
}

function renderRequisitionsTable() {
  const content = document.getElementById('requisitions-content');

  if (allRequisitions.length === 0) {
    content.innerHTML = '<div class="message">No requisitions raised yet.</div>';
    return;
  }

  const rows = allRequisitions.map(function (req) {
    const approvalCell = req.approved_by
      ? '<span class="chip chip-green">&#10003; ' + escapeHtml(req.approved_by) + '</span>'
      : '<button type="button" class="btn-approve btn-row approve-btn" data-id="' + escapeHtml(req.id) + '">Approve</button>';

    return '<tr>' +
      '<td>' + escapeHtml(req.id) + '</td>' +
      '<td>' + escapeHtml(req.role) + '</td>' +
      '<td>' + escapeHtml(req.branch) + '</td>' +
      '<td>' + escapeHtml(req.openings) + '</td>' +
      '<td>' + escapeHtml(req.raised_by) + '</td>' +
      '<td>' + computeAgingChip(req) + '</td>' +
      '<td>' + escapeHtml(req.stage) + '</td>' +
      '<td>' + approvalCell + '</td>' +
      '<td>' + escapeHtml(req.budget) + '</td>' +
      '<td><button type="button" class="btn-edit btn-row edit-req-btn" data-id="' + escapeHtml(req.id) + '">Edit</button>' +
      '<button type="button" class="btn-delete btn-row delete-req-btn" data-id="' + escapeHtml(req.id) + '">Delete</button></td>' +
      '</tr>';
  }).join('');

  content.innerHTML =
    '<table>' +
    '<thead><tr><th>ID</th><th>Role</th><th>Branch</th><th>Openings</th><th>Raised By</th><th>Aging</th><th>Stage</th><th>Approval</th><th>Budget</th><th>Actions</th></tr></thead>' +
    '<tbody>' + rows + '</tbody>' +
    '</table>';

  content.querySelectorAll('.approve-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openApproveModal(btn.getAttribute('data-id'));
    });
  });

  content.querySelectorAll('.delete-req-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      handleRequisitionDelete(btn.getAttribute('data-id'));
    });
  });

  content.querySelectorAll('.edit-req-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const req = allRequisitions.find(function (r) { return r.id === btn.getAttribute('data-id'); });
      if (req) {
        openRequisitionModal('edit', req);
      }
    });
  });
}

async function handleRequisitionDelete(reqId) {
  const linked = allCandidates.filter(function (c) { return c.requisition_id === reqId; }).length;
  const message = linked > 0
    ? 'Requisition ' + reqId + ' has ' + linked + ' candidate(s) linked to it, so it cannot be deleted. Move or remove those candidates first.'
    : 'Delete requisition ' + reqId + '? This cannot be undone.';
  if (linked > 0) {
    alert(message);
    return;
  }
  if (!confirm(message)) {
    return;
  }

  try {
    const response = await fetch(REQUISITIONS_API_BASE + reqId + '/', {
      method: 'DELETE',
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok && response.status !== 204) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not delete requisition.');
    }

    loadAll();
  } catch (err) {
    showPageError(err.message || 'Something went wrong. Please try again.');
  }
}

function stageChipClass(stage) {
  if (stage === 'Joined') {
    return 'chip-green';
  }
  if (stage === 'Rejected' || stage === 'Withdrawn') {
    return 'chip-red';
  }
  if (stage === 'Documents Pending') {
    return 'chip-amber';
  }
  return 'chip-navy';
}

const CLOSED_CANDIDATE_STAGES = ['Joined', 'Rejected', 'Withdrawn'];
const expandedCandidateIds = new Set();

function renderCandidatesList() {
  const content = document.getElementById('candidates-content');

  if (allCandidates.length === 0) {
    content.innerHTML = '<div class="message">No candidates being tracked yet.</div>';
    return;
  }

  const cards = allCandidates.map(function (cand) {
    const requisitionLabel = cand.requisition_role
      ? escapeHtml(cand.requisition_role) + ' &mdash; ' + escapeHtml(cand.requisition_branch)
      : '&mdash; No requisition &mdash;';

    const steps = cand.steps || [];
    const doneCount = cand.steps_done_count || 0;
    const totalCount = cand.steps_total_count || steps.length;
    const pct = (cand.progress_pct !== undefined) ? cand.progress_pct : (totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0);
    const currentStepLabel = cand.current_step ? ('Current: ' + escapeHtml(cand.current_step.step_no) + '. ' + escapeHtml(cand.current_step.how)) : (totalCount > 0 ? 'All steps completed' : '');
    const isExpanded = expandedCandidateIds.has(cand.id);
    const isClosed = CLOSED_CANDIDATE_STAGES.indexOf(cand.stage) !== -1;

    const lockSteps = isClosed || cand.frozen || !!cand.onboarding_employee_id;
    const stepsHtml = steps.map(function (step) {
      const options = ['Pending', 'In Progress', 'Completed'].map(function (st) {
        return '<option value="' + st + '"' + (step.status === st ? ' selected' : '') + '>' + st + '</option>';
      }).join('');
      const statusSelect = '<select class="cand-step-status" data-cand-id="' + escapeHtml(cand.id) + '" data-step-id="' + escapeHtml(step.id) + '"' + (lockSteps ? ' disabled' : '') + '>' + options + '</select>';
      return '<div class="step-row">' +
        '<div class="step-info">' +
        '<div class="step-name' + (step.done ? ' step-done' : '') + '">' + escapeHtml(step.step_no) + '. ' + escapeHtml(step.how || step.step_name) +
        (step.required === false ? ' <span class="chip chip-navy">Optional</span>' : '') + '</div>' +
        '<div class="step-meta"><b>Who:</b> ' + (step.who ? escapeHtml(step.who) : 'Unassigned') +
        (step.when ? ' &middot; <b>When:</b> ' + escapeHtml(step.when) : '') +
        (step.completed_at ? ' &middot; completed ' + escapeHtml(String(step.completed_at).slice(0, 10)) + (step.completed_by ? ' by ' + escapeHtml(step.completed_by) : '') : '') + '</div>' +
        '</div>' +
        statusSelect +
        '</div>';
    }).join('');

    const checklistBlock = isExpanded
      ? '<div class="candidate-checklist" style="margin-top: 10px;">' +
        '<div class="progress-track"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="progress-label">' + doneCount + '/' + totalCount + ' steps &middot; ' + pct + '% &middot; ' + currentStepLabel + '</div>' +
        (steps.length === 0 ? '<div class="message" style="padding: 12px 0;">No SOP steps configured.</div>' : stepsHtml) +
        '<div class="audit-box" data-entity="candidate" data-entity-id="' + escapeHtml(cand.id) + '"></div>' +
        '</div>'
      : '<div class="progress-track" style="margin-top: 10px;"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="progress-label">' + doneCount + '/' + totalCount + ' steps &middot; ' + pct + '% &middot; ' + currentStepLabel + ' &mdash; click card to expand</div>';

    const outcomeLocked = !!cand.onboarding_employee_id || cand.outcome === 'Rejected' || cand.outcome === 'Withdrawn';
    const outcomeOptions = [['', 'Outcome: pending'], ['Selected', 'Selected'], ['Rejected', 'Rejected'], ['Withdrawn', 'Withdrawn']].map(function (o) {
      return '<option value="' + o[0] + '"' + ((cand.outcome || '') === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
    }).join('');
    const manualActions = '<select class="cand-outcome" data-id="' + escapeHtml(cand.id) + '"' + (outcomeLocked ? ' disabled' : '') + ' title="Final outcome of this candidate">' + outcomeOptions + '</select>';

    const lifecycleNote = cand.onboarding_employee_id
      ? '<div class="candidate-meta"><span class="chip chip-green">Moved to Onboarding</span></div>'
      : ((cand.outcome === 'Selected' && !cand.ready_for_onboarding && cand.onboarding_blocked_reason)
        ? '<div class="candidate-meta"><span class="chip chip-amber">Waiting: ' + escapeHtml(cand.onboarding_blocked_reason) + '</span></div>'
        : '');

    const createEmployeeBtn = cand.stage === 'Documents Pending'
      ? '<a href="documents-pending.html" class="btn-view">Upload Documents &amp; Move to Onboarding</a>'
      : '';

    const jobDescription = findJobDescriptionForRole(cand.requisition_role);
    const sendJdBtn = (cand.phone && jobDescription)
      ? '<button type="button" class="btn-secondary btn-row send-jd-btn" data-id="' + escapeHtml(cand.id) + '">Send JD</button>'
      : '';

    const positiveRefCount = allReferenceChecks.filter(function (r) {
      return r.candidate_id === cand.id && r.status === 'Positive';
    }).length;

    const eligibility = appointmentLetterEligibility[cand.id];
    const appointmentLetterBadge = (cand.stage === 'Documents Pending' && eligibility)
      ? '<div class="candidate-meta">Appointment Letter: ' +
        (eligibility.can_issue
          ? '<span class="chip chip-green">Eligible</span>'
          : '<span class="chip chip-amber">Needs 2 positive references</span>') +
        '</div>'
      : '';

    const frozenBanner = cand.frozen
      ? '<div class="form-error" style="display: block; margin-top: 10px;">' +
        '&#10060; Frozen: ' + escapeHtml(cand.frozen_reason || 'Reference check discrepancy') +
        ' <button type="button" class="btn-secondary btn-row unfreeze-btn" data-id="' + escapeHtml(cand.id) + '" style="margin-left: 8px;">Unfreeze</button>' +
        '</div>'
      : '';

    return '<div class="candidate-card candidate-card-clickable" data-id="' + escapeHtml(cand.id) + '">' +
      '<div class="candidate-header">' +
      '<span class="candidate-identity">' +
      '<span class="avatar avatar-small" style="background:' + getAvatarColor(cand.name) + '">' + escapeHtml(getInitials(cand.name)) + '</span>' +
      '<span class="candidate-name">' + escapeHtml(cand.name) + '</span>' +
      '</span>' +
      '<span class="chip ' + stageChipClass(cand.stage) + '">' + escapeHtml(cand.stage) + '</span>' +
      '</div>' +
      frozenBanner +
      '<div class="candidate-meta">' + requisitionLabel + '</div>' +
      '<div class="candidate-meta">Source: ' + (cand.source ? escapeHtml(cand.source) : '&mdash;') + '</div>' +
      '<div class="candidate-meta">Experience: ' + (cand.experience ? escapeHtml(cand.experience) : '&mdash;') + '</div>' +
      '<div class="candidate-meta">References: ' + positiveRefCount + ' positive</div>' +
      appointmentLetterBadge +
      lifecycleNote +
      checklistBlock +
      '<div class="candidate-actions" style="margin-top: 10px; flex-wrap: wrap;">' +
      createEmployeeBtn +
      sendJdBtn +
      manualActions +
      '<button type="button" class="btn-secondary btn-row ref-checks-btn" data-id="' + escapeHtml(cand.id) + '">References</button>' +
      '<button type="button" class="btn-edit btn-row edit-cand-btn" data-id="' + escapeHtml(cand.id) + '">Edit</button>' +
      '<button type="button" class="btn-delete btn-row delete-cand-btn" data-id="' + escapeHtml(cand.id) + '">Delete</button>' +
      '</div>' +
      '</div>';
  }).join('');

  content.innerHTML = '<div class="candidate-grid">' + cards + '</div>';

  content.querySelectorAll('.candidate-card-clickable').forEach(function (card) {
    card.addEventListener('click', function (event) {
      if (event.target.closest('button')) {
        return;
      }
      const id = card.getAttribute('data-id');
      if (expandedCandidateIds.has(id)) {
        expandedCandidateIds.delete(id);
      } else {
        expandedCandidateIds.add(id);
      }
      renderCandidatesList();
    });
  });

  content.querySelectorAll('.ref-checks-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openReferenceChecksModal(btn.getAttribute('data-id'));
    });
  });

  content.querySelectorAll('.unfreeze-btn').forEach(function (btn) {
    btn.addEventListener('click', async function (event) {
      event.stopPropagation();
      const candId = btn.getAttribute('data-id');
      try {
        const response = await fetch(CANDIDATES_API_BASE + candId + '/unfreeze/', {
          method: 'POST',
          headers: authHeaders(token)
        });
        if (handleUnauthorized(response)) return;
        if (!response.ok) throw new Error('Could not unfreeze candidate.');
        loadAll();
      } catch (err) {
        showPageError(err.message);
      }
    });
  });

  content.querySelectorAll('.send-jd-btn').forEach(function (btn) {
    btn.addEventListener('click', function (event) {
      event.stopPropagation();
      const candId = btn.getAttribute('data-id');
      const cand = allCandidates.find(function (c) { return c.id === candId; });
      if (!cand) return;
      const jd = findJobDescriptionForRole(cand.requisition_role);
      const message = 'Hi ' + cand.name + ', here are the role details for ' + (cand.requisition_role || 'the position') + ':\n\n' + jd;
      const phone = (cand.phone || '').replace(/\D/g, '');
      window.open('https://wa.me/' + phone + '?text=' + encodeURIComponent(message), '_blank');
    });
  });

  content.querySelectorAll('.cand-step-status').forEach(function (select) {
    select.addEventListener('change', function () {
      handleCandidateStepStatus(
        select.getAttribute('data-cand-id'),
        select.getAttribute('data-step-id'),
        select.value
      );
    });
  });

  content.querySelectorAll('.cand-outcome').forEach(function (select) {
    select.addEventListener('change', function () {
      handleCandidateOutcome(select.getAttribute('data-id'), select.value);
    });
  });

  content.querySelectorAll('.audit-box').forEach(function (box) {
    renderAuditHistory(box, box.getAttribute('data-entity'), box.getAttribute('data-entity-id'));
  });

  content.querySelectorAll('.edit-cand-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const cand = allCandidates.find(function (c) { return c.id === btn.getAttribute('data-id'); });
      if (cand) {
        openCandidateModal('edit', cand);
      }
    });
  });

  content.querySelectorAll('.delete-cand-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      handleDeleteCandidate(btn.getAttribute('data-id'));
    });
  });
}

// ---------- Requisition modal ----------

const requisitionModalOverlay = document.getElementById('requisition-modal-overlay');
const requisitionModalTitle = document.getElementById('requisition-modal-title');
const requisitionForm = document.getElementById('requisition-form');
const requisitionFormError = document.getElementById('requisition-form-error');
const requisitionSubmitButton = document.getElementById('requisition-submit-button');
const requisitionCancelButton = document.getElementById('requisition-cancel-button');
const requisitionStageField = document.getElementById('req-stage-field');

let editingRequisitionId = null;

document.getElementById('add-requisition-button').addEventListener('click', function () {
  openRequisitionModal('add', null);
});
requisitionForm.addEventListener('submit', handleRequisitionSubmit);
requisitionCancelButton.addEventListener('click', closeRequisitionModal);
requisitionModalOverlay.addEventListener('click', function (event) {
  if (event.target === requisitionModalOverlay) {
    closeRequisitionModal();
  }
});

function openRequisitionModal(mode, req) {
  editingRequisitionId = mode === 'edit' && req ? req.id : null;
  requisitionModalTitle.textContent = mode === 'edit' ? 'Edit Requisition' : 'Add Requisition';
  requisitionSubmitButton.textContent = mode === 'edit' ? 'Update' : 'Add';
  requisitionStageField.style.display = mode === 'edit' ? 'block' : 'none';

  document.getElementById('req-role').value = req ? (req.role || '') : '';
  document.getElementById('req-branch').value = req ? (req.branch || '') : '';
  document.getElementById('req-openings').value = req ? (req.openings || 1) : 1;
  document.getElementById('req-raised-by').value = req ? (req.raised_by || '') : '';
  document.getElementById('req-tat-days').value = req ? (req.tat_days || 30) : 30;
  document.getElementById('req-budget').value = req ? (req.budget || '') : '';
  document.getElementById('req-stage').value = req ? (req.stage || 'Open') : 'Open';

  requisitionFormError.style.display = 'none';
  requisitionFormError.textContent = '';
  requisitionModalOverlay.classList.add('open');
}

function closeRequisitionModal() {
  requisitionModalOverlay.classList.remove('open');
  requisitionForm.reset();
  editingRequisitionId = null;
}

async function handleRequisitionSubmit(event) {
  event.preventDefault();
  requisitionSubmitButton.disabled = true;
  requisitionFormError.style.display = 'none';

  const isEditing = editingRequisitionId !== null;

  const payload = {
    role: document.getElementById('req-role').value,
    branch: document.getElementById('req-branch').value,
    openings: parseInt(document.getElementById('req-openings').value, 10),
    raised_by: document.getElementById('req-raised-by').value,
    tat_days: parseInt(document.getElementById('req-tat-days').value, 10),
    budget: document.getElementById('req-budget').value
  };

  if (isEditing) {
    payload.stage = document.getElementById('req-stage').value;
  }

  const url = isEditing ? REQUISITIONS_API_BASE + editingRequisitionId + '/' : REQUISITIONS_API_BASE;
  const method = isEditing ? 'PATCH' : 'POST';

  try {
    const response = await fetch(url, {
      method: method,
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not save requisition.');
    }

    closeRequisitionModal();
    loadAll();
  } catch (err) {
    requisitionFormError.textContent = err.message || 'Something went wrong. Please try again.';
    requisitionFormError.style.display = 'block';
  } finally {
    requisitionSubmitButton.disabled = false;
  }
}

// ---------- Approve modal ----------

const approveModalOverlay = document.getElementById('approve-modal-overlay');
const approveForm = document.getElementById('approve-form');
const approveFormError = document.getElementById('approve-form-error');
const approveSubmitButton = document.getElementById('approve-submit-button');
const approveCancelButton = document.getElementById('approve-cancel-button');

let approvingRequisitionId = null;

approveForm.addEventListener('submit', handleApproveSubmit);
approveCancelButton.addEventListener('click', closeApproveModal);
approveModalOverlay.addEventListener('click', function (event) {
  if (event.target === approveModalOverlay) {
    closeApproveModal();
  }
});

function openApproveModal(reqId) {
  approvingRequisitionId = reqId;
  document.getElementById('approve-name').value = '';
  approveFormError.style.display = 'none';
  approveFormError.textContent = '';
  approveModalOverlay.classList.add('open');
}

function closeApproveModal() {
  approveModalOverlay.classList.remove('open');
  approveForm.reset();
  approvingRequisitionId = null;
}

async function handleApproveSubmit(event) {
  event.preventDefault();
  if (!approvingRequisitionId) {
    return;
  }

  approveSubmitButton.disabled = true;
  approveFormError.style.display = 'none';

  try {
    const response = await fetch(REQUISITIONS_API_BASE + approvingRequisitionId + '/approve/', {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify({ approved_by: document.getElementById('approve-name').value })
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not approve requisition.');
    }

    closeApproveModal();
    loadAll();
  } catch (err) {
    approveFormError.textContent = err.message || 'Something went wrong. Please try again.';
    approveFormError.style.display = 'block';
  } finally {
    approveSubmitButton.disabled = false;
  }
}

// ---------- Candidate modal ----------

const candidateModalOverlay = document.getElementById('candidate-modal-overlay');
const candidateModalTitle = document.getElementById('candidate-modal-title');
const candidateForm = document.getElementById('candidate-form');
const candidateFormError = document.getElementById('candidate-form-error');
const candidateSubmitButton = document.getElementById('candidate-submit-button');
const candidateCancelButton = document.getElementById('candidate-cancel-button');
const candidateRequisitionSelect = document.getElementById('cand-requisition');

let editingCandidateId = null;

document.getElementById('add-candidate-button').addEventListener('click', function () {
  openCandidateModal('add', null);
});
candidateForm.addEventListener('submit', handleCandidateSubmit);
candidateCancelButton.addEventListener('click', closeCandidateModal);
candidateModalOverlay.addEventListener('click', function (event) {
  if (event.target === candidateModalOverlay) {
    closeCandidateModal();
  }
});

function populateRequisitionSelect(selectedId) {
  const options = ['<option value="">No requisition</option>'].concat(
    allRequisitions.map(function (req) {
      const selected = req.id === selectedId ? ' selected' : '';
      return '<option value="' + escapeHtml(req.id) + '"' + selected + '>' +
        escapeHtml(req.role) + ' — ' + escapeHtml(req.branch) + '</option>';
    })
  );
  candidateRequisitionSelect.innerHTML = options.join('');
}

function openCandidateModal(mode, cand) {
  editingCandidateId = mode === 'edit' && cand ? cand.id : null;
  candidateModalTitle.textContent = mode === 'edit' ? 'Edit Candidate' : 'Add Candidate';
  candidateSubmitButton.textContent = mode === 'edit' ? 'Update' : 'Add';

  document.getElementById('cand-name').value = cand ? (cand.name || '') : '';
  document.getElementById('cand-phone').value = cand ? (cand.phone || '') : '';
  document.getElementById('cand-email').value = cand ? (cand.email || '') : '';
  document.getElementById('cand-source').value = cand ? (cand.source || '') : '';
  document.getElementById('cand-experience').value = cand ? (cand.experience || '') : '';
  populateRequisitionSelect(cand ? cand.requisition_id : null);

  candidateFormError.style.display = 'none';
  candidateFormError.textContent = '';
  candidateModalOverlay.classList.add('open');
}

function closeCandidateModal() {
  candidateModalOverlay.classList.remove('open');
  candidateForm.reset();
  editingCandidateId = null;
}

async function handleCandidateSubmit(event) {
  event.preventDefault();
  candidateSubmitButton.disabled = true;
  candidateFormError.style.display = 'none';

  const requisitionId = candidateRequisitionSelect.value;
  const payload = {
    name: document.getElementById('cand-name').value,
    phone: document.getElementById('cand-phone').value,
    email: document.getElementById('cand-email').value,
    source: document.getElementById('cand-source').value,
    experience: document.getElementById('cand-experience').value,
    requisition_id: requisitionId || null
  };

  const isEditing = editingCandidateId !== null;
  const url = isEditing ? CANDIDATES_API_BASE + editingCandidateId + '/' : CANDIDATES_API_BASE;
  const method = isEditing ? 'PATCH' : 'POST';

  try {
    const response = await fetch(url, {
      method: method,
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not save candidate.');
    }

    closeCandidateModal();
    loadAll();
  } catch (err) {
    candidateFormError.textContent = err.message || 'Something went wrong. Please try again.';
    candidateFormError.style.display = 'block';
  } finally {
    candidateSubmitButton.disabled = false;
  }
}

function announceTransition(data) {
  if (data && data.transition && data.transition.moved && data.transition.message) {
    showToast(data.transition.message, 'success');
  }
}

async function handleCandidateStepStatus(candId, stepId, newStatus) {
  hidePageError();
  try {
    const response = await fetch(
      CANDIDATES_API_BASE + candId + '/steps/' + stepId + '/status/',
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

    announceTransition(data);
    expandedCandidateIds.add(candId);
    loadAll();
  } catch (err) {
    showToast(err.message || 'Something went wrong. Please try again.', 'error');
    loadAll();
  }
}

async function handleCandidateOutcome(candId, outcome) {
  if (!outcome) {
    loadAll();
    return;
  }
  if (outcome !== 'Selected' && !confirm('Mark this candidate as ' + outcome.toLowerCase() + '? This cannot be undone.')) {
    loadAll();
    return;
  }

  hidePageError();
  try {
    const response = await fetch(CANDIDATES_API_BASE + candId + '/outcome/', {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify({ outcome: outcome })
    });

    if (handleUnauthorized(response)) {
      return;
    }

    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      throw new Error(describeApiError(data) || 'Could not update the outcome.');
    }

    announceTransition(data);
    showToast('Outcome set to ' + outcome + '.', 'success');
    loadAll();
  } catch (err) {
    showToast(err.message || 'Something went wrong. Please try again.', 'error');
    loadAll();
  }
}

async function handleDeleteCandidate(candId) {
  const confirmed = confirm('Are you sure you want to delete this candidate?');
  if (!confirmed) {
    return;
  }

  try {
    const response = await fetch(CANDIDATES_API_BASE + candId + '/', {
      method: 'DELETE',
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok && response.status !== 204) {
      throw new Error('Could not delete candidate.');
    }

    loadAll();
  } catch (err) {
    showPageError(err.message || 'Something went wrong. Please try again.');
  }
}

// ---------- Reference Checks ----------

let referenceChecksCandidateId = null;
const referenceChecksModalOverlay = document.getElementById('reference-checks-modal-overlay');
const referenceCheckForm = document.getElementById('reference-check-form');

function openReferenceChecksModal(candId) {
  referenceChecksCandidateId = candId;
  const candidate = allCandidates.find(function (c) { return c.id === candId; });
  document.getElementById('reference-checks-modal-title').textContent =
    'Reference Checks' + (candidate ? ' — ' + candidate.name : '');
  resetReferenceCheckForm();
  renderReferenceChecksModalList();
  referenceChecksModalOverlay.classList.add('open');
}

function resetReferenceCheckForm() {
  referenceCheckForm.reset();
  document.getElementById('ref-check-editing-id').value = '';
  document.getElementById('reference-check-submit-button').textContent = 'Add Reference Check';
  document.getElementById('reference-check-form-error').style.display = 'none';
}

function renderReferenceChecksModalList() {
  const listEl = document.getElementById('reference-checks-list');
  const checks = allReferenceChecks.filter(function (r) { return r.candidate_id === referenceChecksCandidateId; });

  if (checks.length === 0) {
    listEl.innerHTML = '<div class="message">No reference checks added yet.</div>';
    return;
  }

  listEl.innerHTML = checks.map(function (r) {
    return '<div class="step-row">' +
      '<div class="step-info">' +
      '<div class="step-name">' + escapeHtml(r.referee_name) + (r.relationship_to_candidate ? ' (' + escapeHtml(r.relationship_to_candidate) + ')' : '') + '</div>' +
      '<div class="step-meta">' + (r.phone ? escapeHtml(r.phone) + ' &middot; ' : '') + '<span class="chip">' + escapeHtml(r.status) + '</span>' + (r.note ? ' &middot; ' + escapeHtml(r.note) : '') + '</div>' +
      '</div>' +
      '<button type="button" class="btn-edit btn-row edit-ref-check-btn" data-id="' + escapeHtml(r.id) + '">Edit</button>' +
      '<button type="button" class="btn-delete btn-row delete-ref-check-btn" data-id="' + escapeHtml(r.id) + '">Delete</button>' +
      '</div>';
  }).join('');

  listEl.querySelectorAll('.edit-ref-check-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const check = allReferenceChecks.find(function (r) { return r.id === btn.getAttribute('data-id'); });
      if (!check) return;
      document.getElementById('ref-check-editing-id').value = check.id;
      document.getElementById('ref-referee-name').value = check.referee_name || '';
      document.getElementById('ref-relationship').value = check.relationship_to_candidate || '';
      document.getElementById('ref-phone').value = check.phone || '';
      document.getElementById('ref-status').value = check.status || 'Pending';
      document.getElementById('ref-note').value = check.note || '';
      document.getElementById('reference-check-submit-button').textContent = 'Update Reference Check';
    });
  });

  listEl.querySelectorAll('.delete-ref-check-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { handleDeleteReferenceCheck(btn.getAttribute('data-id')); });
  });
}

document.getElementById('reference-check-cancel-button').addEventListener('click', function () {
  referenceChecksModalOverlay.classList.remove('open');
});
referenceChecksModalOverlay.addEventListener('click', function (e) {
  if (e.target === referenceChecksModalOverlay) referenceChecksModalOverlay.classList.remove('open');
});

referenceCheckForm.addEventListener('submit', async function (event) {
  event.preventDefault();
  const editingId = document.getElementById('ref-check-editing-id').value;
  const payload = {
    referee_name: document.getElementById('ref-referee-name').value,
    relationship_to_candidate: document.getElementById('ref-relationship').value,
    phone: document.getElementById('ref-phone').value,
    status: document.getElementById('ref-status').value,
    note: document.getElementById('ref-note').value
  };
  if (!editingId) {
    payload.candidate_id = referenceChecksCandidateId;
  }
  const url = editingId ? REFERENCE_CHECKS_API_BASE + editingId + '/' : REFERENCE_CHECKS_API_BASE;
  try {
    const response = await fetch(url, {
      method: editingId ? 'PATCH' : 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Could not save reference check.');

    const refResponse = await fetch(REFERENCE_CHECKS_API_BASE, { headers: authHeaders(token) });
    allReferenceChecks = await refResponse.json();
    await loadAppointmentLetterEligibility();
    resetReferenceCheckForm();
    renderReferenceChecksModalList();
    renderCandidatesList();
  } catch (err) {
    const errorEl = document.getElementById('reference-check-form-error');
    errorEl.textContent = err.message;
    errorEl.style.display = 'block';
  }
});

async function handleDeleteReferenceCheck(id) {
  if (!confirm('Delete this reference check?')) return;
  const response = await fetch(REFERENCE_CHECKS_API_BASE + id + '/', {
    method: 'DELETE',
    headers: authHeaders(token)
  });
  if (handleUnauthorized(response)) return;
  allReferenceChecks = allReferenceChecks.filter(function (r) { return r.id !== id; });
  await loadAppointmentLetterEligibility();
  renderReferenceChecksModalList();
  renderCandidatesList();
}
