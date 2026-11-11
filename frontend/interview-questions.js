const token = getAuthToken();
const QUESTIONS_API_BASE = API_BASE + '/interview-questions/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadQuestions();
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

async function loadQuestions() {
  hidePageError();
  const content = document.getElementById('questions-content');
  const department = document.getElementById('filter-department').value.trim();
  const type = document.getElementById('filter-type').value;
  const params = new URLSearchParams();
  if (department) params.set('department', department);
  if (type) params.set('type', type);
  const url = QUESTIONS_API_BASE + (params.toString() ? '?' + params.toString() : '');

  try {
    const response = await fetch(url, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load questions.');
    const questions = await response.json();
    renderQuestions(questions);
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message) + '</div><button type="button" class="btn-secondary" id="retry-questions-button">Retry</button></div>';
    document.getElementById('retry-questions-button').addEventListener('click', loadQuestions);
  }
}

function renderQuestions(questions) {
  const content = document.getElementById('questions-content');
  if (questions.length === 0) {
    content.innerHTML = '<div class="message">No questions found.</div>';
    return;
  }
  const groups = {};
  questions.forEach(function (q) {
    const key = q.type || 'Other';
    if (!groups[key]) groups[key] = [];
    groups[key].push(q);
  });

  content.innerHTML = Object.keys(groups).sort().map(function (type) {
    const rows = groups[type].map(function (q) {
      return '<div class="question-row"><span>' + escapeHtml(q.question_text) +
        (q.department ? ' <span style="color: var(--mut); font-size: 12px;">(' + escapeHtml(q.department) + ')</span>' : '') + '</span>' +
        '<button type="button" class="btn-delete btn-row delete-question-btn" data-id="' + escapeHtml(q.id) + '">Delete</button></div>';
    }).join('');
    return '<div class="question-group-title">' + escapeHtml(type) + '</div>' + rows;
  }).join('');

  content.querySelectorAll('.delete-question-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { handleDeleteQuestion(btn.getAttribute('data-id')); });
  });
}

async function handleDeleteQuestion(id) {
  if (!confirm('Delete this question?')) return;
  const response = await fetch(QUESTIONS_API_BASE + id + '/', { method: 'DELETE', headers: authHeaders(token) });
  if (handleUnauthorized(response)) return;
  loadQuestions();
}

document.getElementById('apply-filter-button').addEventListener('click', loadQuestions);
document.getElementById('clear-filter-button').addEventListener('click', function () {
  document.getElementById('filter-department').value = '';
  document.getElementById('filter-type').value = '';
  loadQuestions();
});

const questionModalOverlay = document.getElementById('question-modal-overlay');
const questionForm = document.getElementById('question-form');
document.getElementById('add-question-button').addEventListener('click', function () {
  questionForm.reset();
  document.getElementById('question-modal-form-error').style.display = 'none';
  questionModalOverlay.classList.add('open');
});
document.getElementById('question-cancel-button').addEventListener('click', function () {
  questionModalOverlay.classList.remove('open');
});
questionModalOverlay.addEventListener('click', function (e) { if (e.target === questionModalOverlay) questionModalOverlay.classList.remove('open'); });

questionForm.addEventListener('submit', async function (event) {
  event.preventDefault();
  const rawText = document.getElementById('question-texts').value;
  const question_texts = rawText.split('\n').map(function (line) { return line.trim(); }).filter(Boolean);
  if (question_texts.length === 0) {
    return;
  }
  const payload = {
    department: document.getElementById('question-department').value,
    type: document.getElementById('question-type').value,
    question_texts: question_texts
  };
  try {
    const response = await fetch(QUESTIONS_API_BASE, {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Could not add question(s).');
    questionModalOverlay.classList.remove('open');
    loadQuestions();
  } catch (err) {
    const errorEl = document.getElementById('question-modal-form-error');
    errorEl.textContent = err.message;
    errorEl.style.display = 'block';
  }
});
