const token = getAuthToken();
const DONE_BOARD_API = API_BASE + '/done-board/';
const CANDIDATES_API_BASE = API_BASE + '/candidates/';
const EMPLOYEES_API_BASE = API_BASE + '/employees/';
const SEPARATIONS_API_BASE = API_BASE + '/separations/';

const MODULE_LABELS = {
  recruitment: 'Recruitment',
  onboarding: 'Onboarding',
  exit: 'Exit'
};

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadBoard();
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


function showPageError(message) {
  const el = document.getElementById('page-error');
  el.textContent = message;
  el.style.display = 'block';
}
function hidePageError() {
  const el = document.getElementById('page-error');
  el.textContent = '';
  el.style.display = 'none';
}

async function loadBoard() {
  hidePageError();
  const content = document.getElementById('board-content');
  try {
    const response = await fetch(DONE_BOARD_API, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load done board.');
    const items = await response.json();
    renderBoard(items);
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message) + '</div><button type="button" class="btn-secondary" id="retry-board-button">Retry</button></div>';
    document.getElementById('retry-board-button').addEventListener('click', loadBoard);
  }
}

function renderBoard(items) {
  const content = document.getElementById('board-content');
  if (items.length === 0) {
    content.innerHTML = '<div class="message">Nothing pending. All caught up.</div>';
    return;
  }
  content.innerHTML = items.map(function (item, index) {
    return '<div class="step-row">' +
      '<div class="step-info">' +
      '<span class="module-chip">' + escapeHtml(MODULE_LABELS[item.module] || item.module) + '</span>' +
      '<span class="step-name">' + escapeHtml(item.person_name) + '</span>' +
      '<div class="step-meta">' + escapeHtml(item.step_name) + (item.who ? ' &middot; ' + escapeHtml(item.who) : '') + ' &middot; ' + escapeHtml(item.record_id) + '</div>' +
      '</div>' +
      '<button type="button" class="btn-primary btn-row done-btn" data-index="' + index + '">&#10003; Done</button>' +
      '</div>';
  }).join('');

  content.querySelectorAll('.done-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const item = items[parseInt(btn.getAttribute('data-index'), 10)];
      handleMarkDone(item, btn);
    });
  });
}

function endpointForModule(item) {
  if (item.module === 'recruitment') {
    return CANDIDATES_API_BASE + item.record_id + '/steps/' + item.step_id + '/done/';
  }
  if (item.module === 'onboarding') {
    return EMPLOYEES_API_BASE + item.record_id + '/onboarding-steps/' + item.step_id + '/done/';
  }
  if (item.module === 'exit') {
    return SEPARATIONS_API_BASE + item.record_id + '/steps/' + item.step_id + '/done/';
  }
  return null;
}

async function handleMarkDone(item, btn) {
  const url = endpointForModule(item);
  if (!url) return;
  btn.disabled = true;
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders(token)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Could not mark step as done.');
    loadBoard();
  } catch (err) {
    showPageError(err.message);
    btn.disabled = false;
  }
}
