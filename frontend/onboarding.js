const token = getAuthToken();
const EMPLOYEES_API_BASE = API_BASE + '/employees/';
const ONBOARDING_LIST_API = EMPLOYEES_API_BASE + 'onboarding/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadOnboarding();
  });
}

let allOnboarding = [];
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


const AVATAR_PALETTE = ['#a5314a', '#c97a3d', '#2a5db0', '#1e7e34', '#8a3ab2', '#b7472a', '#0f766e'];

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

async function loadOnboarding() {
  const content = document.getElementById('onboarding-content');
  hidePageError();

  try {
    const response = await fetch(ONBOARDING_LIST_API, {
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to load onboarding employees.');
    }

    allOnboarding = await response.json();
    renderOnboarding();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' +
      escapeHtml(err.message || 'Could not load onboarding employees.') +
      '</div><button type="button" class="btn-secondary" id="retry-onboarding-button">Retry</button></div>';
    document.getElementById('retry-onboarding-button').addEventListener('click', loadOnboarding);
  }
}

function renderOnboarding() {
  const content = document.getElementById('onboarding-content');

  if (allOnboarding.length === 0) {
    content.innerHTML = '<div class="message">No employees currently onboarding.</div>';
    return;
  }

  content.innerHTML = allOnboarding.map(function (emp) {
    const steps = emp.onboarding_steps || [];
    const doneCount = steps.filter(function (s) { return s.done; }).length;
    const totalCount = steps.length;
    const pct = (emp.onboarding_progress_pct !== undefined) ? emp.onboarding_progress_pct : (totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0);
    const cur = emp.onboarding_current_step;
    const currentLabel = cur ? ('Current: ' + escapeHtml(cur.step_no) + '. ' + escapeHtml(cur.how)) : (totalCount > 0 ? 'All steps completed' : '');
    const isExpanded = expandedIds.has(emp.id);
    const allStepsDone = !!emp.onboarding_all_required_completed;
    const waitingNote = (allStepsDone && !emp.policy_accepted)
      ? '<div class="candidate-meta"><span class="chip chip-amber">All steps done. Waiting for the policy handbook to be accepted; the employee is activated automatically once it is.</span></div>'
      : '';

    let bodyHtml = '';
    if (isExpanded) {
      const stepsHtml = steps.length === 0
        ? '<div class="message" style="padding: 12px 0;">No onboarding steps configured.</div>'
        : steps.map(function (step) {
          const options = ['Pending', 'In Progress', 'Completed'].map(function (st) {
            return '<option value="' + st + '"' + (step.status === st ? ' selected' : '') + '>' + st + '</option>';
          }).join('');
          return '<div class="step-row">' +
            '<div class="step-info">' +
            '<div class="step-name' + (step.done ? ' step-done' : '') + '">' + escapeHtml(step.step_no) + '. ' + escapeHtml(step.how || step.step_name) +
            (step.required === false ? ' <span class="chip chip-navy">Optional</span>' : '') + '</div>' +
            '<div class="step-meta"><b>Who:</b> ' + (step.who ? escapeHtml(step.who) : 'Unassigned') +
            (step.when ? ' &middot; <b>When:</b> ' + escapeHtml(step.when) : '') +
            (step.completed_at ? ' &middot; completed ' + escapeHtml(String(step.completed_at).slice(0, 10)) + (step.completed_by ? ' by ' + escapeHtml(step.completed_by) : '') : '') + '</div>' +
            '</div>' +
            '<select class="onboard-step-status" data-emp-id="' + escapeHtml(emp.id) + '" data-step-id="' + escapeHtml(step.id) + '">' + options + '</select>' +
            '</div>';
        }).join('');

      bodyHtml = '<div class="onboarding-body">' +
        '<div class="progress-track"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="progress-label">' + doneCount + '/' + totalCount + ' steps &middot; ' + pct + '% &middot; ' + currentLabel + '</div>' +
        stepsHtml +
        '<div class="policy-row">' +
        '<input type="checkbox" id="policy-' + escapeHtml(emp.id) + '" class="policy-checkbox" data-emp-id="' + escapeHtml(emp.id) + '"' + (emp.policy_accepted ? ' checked' : '') + '>' +
        '<label for="policy-' + escapeHtml(emp.id) + '" style="margin: 0;">Policy handbook accepted</label>' +
        '</div>' +
        waitingNote +
        '<div class="audit-box" data-entity="employee" data-entity-id="' + escapeHtml(emp.id) + '"></div>' +
        '</div>';
    } else {
      bodyHtml = '<div class="progress-track" style="margin-top: 10px;"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="progress-label">' + doneCount + '/' + totalCount + ' steps &middot; ' + pct + '% &middot; ' + currentLabel + ' &mdash; click to expand</div>';
    }

    return '<div class="onboarding-card">' +
      '<div class="onboarding-header onboarding-toggle" data-emp-id="' + escapeHtml(emp.id) + '">' +
      '<span class="onboarding-identity">' +
      '<span class="avatar avatar-small" style="background:' + getAvatarColor(emp.name) + '">' + escapeHtml(getInitials(emp.name)) + '</span>' +
      '<span>' +
      '<div class="onboarding-name">' + escapeHtml(emp.name) + '</div>' +
      '<div class="onboarding-meta">' + escapeHtml(emp.designation) + (emp.department ? ' &middot; ' + escapeHtml(emp.department) : '') + (emp.branch ? ' &middot; ' + escapeHtml(emp.branch) : '') + '</div>' +
      '</span>' +
      '</span>' +
      '<span class="chip chip-amber">Onboarding</span>' +
      '</div>' +
      bodyHtml +
      '</div>';
  }).join('');

  content.querySelectorAll('.onboarding-toggle').forEach(function (header) {
    header.addEventListener('click', function () {
      const id = header.getAttribute('data-emp-id');
      if (expandedIds.has(id)) {
        expandedIds.delete(id);
      } else {
        expandedIds.add(id);
      }
      renderOnboarding();
    });
  });

  content.querySelectorAll('.onboard-step-status').forEach(function (select) {
    select.addEventListener('click', function (event) { event.stopPropagation(); });
    select.addEventListener('change', function () {
      handleStepStatus(select.getAttribute('data-emp-id'), select.getAttribute('data-step-id'), select.value);
    });
  });

  content.querySelectorAll('.audit-box').forEach(function (box) {
    renderAuditHistory(box, box.getAttribute('data-entity'), box.getAttribute('data-entity-id'));
  });

  content.querySelectorAll('.policy-checkbox').forEach(function (checkbox) {
    checkbox.addEventListener('click', function (event) {
      event.stopPropagation();
    });
    checkbox.addEventListener('change', function () {
      handlePolicyToggle(checkbox.getAttribute('data-emp-id'), checkbox.checked);
    });
  });

}

function announce(data) {
  if (data && data.transition && data.transition.moved && data.transition.message) {
    showToast(data.transition.message, 'success');
  } else if (data && data.transition && data.transition.reason &&
             data.transition.reason.indexOf('policy') !== -1) {
    showToast(data.transition.reason, 'info');
  }
}

async function handleStepStatus(empId, stepId, newStatus) {
  hidePageError();
  try {
    const response = await fetch(
      EMPLOYEES_API_BASE + empId + '/onboarding-steps/' + stepId + '/status/',
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

    announce(data);
    expandedIds.add(empId);
    loadOnboarding();
  } catch (err) {
    showToast(err.message || 'Something went wrong. Please try again.', 'error');
    loadOnboarding();
  }
}

async function handlePolicyToggle(empId, checked) {
  hidePageError();
  try {
    const response = await fetch(EMPLOYEES_API_BASE + empId + '/', {
      method: 'PATCH',
      headers: authHeaders(token, true),
      body: JSON.stringify({ policy_accepted: checked })
    });

    if (handleUnauthorized(response)) {
      return;
    }

    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      throw new Error('Could not update policy acceptance.');
    }

    announce(data);
    expandedIds.add(empId);
    loadOnboarding();
  } catch (err) {
    showPageError(err.message || 'Something went wrong. Please try again.');
  }
}
