const token = getAuthToken();
const EMPLOYEES_API_BASE = API_BASE + '/employees/';
const REQUISITIONS_API_BASE = API_BASE + '/requisitions/';
const CANDIDATES_API_BASE = API_BASE + '/candidates/';
const TASKS_API_BASE = API_BASE + '/tasks/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    renderGreeting();
    loadAll();
    initGlobalBranchFilter('global-branch-filter-container', function () { loadAll(); });
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


function renderGreeting() {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good Morning' : (hour < 17 ? 'Good Afternoon' : 'Good Evening');
  document.getElementById('greeting-heading').textContent = greeting;
  document.getElementById('greeting-date').textContent = new Date().toLocaleDateString('en-IN', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

async function loadAll() {
  try {
    const branchQuery = getGlobalBranchFilter() ? '?branch=' + encodeURIComponent(getGlobalBranchFilter()) : '';
    const [empRes, reqRes, candRes, taskRes] = await Promise.all([
      fetch(EMPLOYEES_API_BASE + branchQuery, { headers: authHeaders(token) }),
      fetch(REQUISITIONS_API_BASE, { headers: authHeaders(token) }),
      fetch(CANDIDATES_API_BASE, { headers: authHeaders(token) }),
      fetch(TASKS_API_BASE + branchQuery, { headers: authHeaders(token) })
    ]);

    if ([empRes, reqRes, candRes, taskRes].some(handleUnauthorized)) {
      return;
    }

    if (!empRes.ok || !reqRes.ok || !candRes.ok || !taskRes.ok) {
      throw new Error('Failed to load dashboard data.');
    }

    const employees = await empRes.json();
    const requisitions = await reqRes.json();
    const candidates = await candRes.json();
    const tasks = await taskRes.json();

    renderKpis(employees, requisitions, candidates, tasks);
    renderScoreboard(tasks);
    renderAttention(requisitions, candidates, tasks);
    renderCelebrations(employees);
  } catch (err) {
    const retryHtml = '<div class="error-state"><div>' +
      escapeHtml(err.message || 'Could not load dashboard data.') +
      '</div><button type="button" class="btn-secondary retry-dashboard-button">Retry</button></div>';
    document.getElementById('attention-content').innerHTML = retryHtml;
    document.getElementById('celebrations-content').innerHTML = retryHtml;
    document.querySelectorAll('.retry-dashboard-button').forEach(function (btn) {
      btn.addEventListener('click', loadAll);
    });
  }
}

function renderKpis(employees, requisitions, candidates, tasks) {
  const activeEmployees = employees.filter(function (e) {
    return String(e.status || '').toLowerCase() === 'active';
  }).length;
  document.getElementById('kpi-active-employees').textContent = activeEmployees;

  const openRequisitions = requisitions.filter(function (r) { return r.stage !== 'Closed'; });
  const totalOpenings = openRequisitions.reduce(function (sum, r) { return sum + (r.openings || 0); }, 0);
  document.getElementById('kpi-open-requisitions').textContent = openRequisitions.length;
  document.getElementById('kpi-open-requisitions-sub').textContent = totalOpenings + ' openings';

  const inPipeline = candidates.filter(function (c) {
    return ['Joined', 'Rejected', 'Withdrawn'].indexOf(c.stage) === -1;
  }).length;
  document.getElementById('kpi-in-pipeline').textContent = inPipeline;

  const overdueTasks = tasks.filter(function (t) { return t.status === 'Overdue'; }).length;
  document.getElementById('kpi-overdue-tasks').textContent = overdueTasks;
}

function renderScoreboard(tasks) {
  const countByStatus = function (statusName) {
    return tasks.filter(function (t) { return t.status === statusName; }).length;
  };
  document.getElementById('score-early').textContent = countByStatus('Early');
  document.getElementById('score-ontime').textContent = countByStatus('On Time');
  document.getElementById('score-delayed').textContent = countByStatus('Delayed');
  document.getElementById('score-overdue').textContent = countByStatus('Overdue');
  document.getElementById('score-open').textContent = countByStatus('Open');
}

function daysBetween(dateA, dateB) {
  const msPerDay = 1000 * 60 * 60 * 24;
  return Math.round((dateA - dateB) / msPerDay);
}

function renderAttention(requisitions, candidates, tasks) {
  const content = document.getElementById('attention-content');
  const today = new Date();
  const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());

  const items = [];

  tasks.filter(function (t) { return t.status === 'Overdue'; }).forEach(function (t) {
    const due = new Date(t.due_date + 'T00:00:00');
    const daysOverdue = daysBetween(todayMidnight, due) * -1;
    items.push({
      tag: 'tag-task',
      tagLabel: 'Task',
      text: escapeHtml(t.title) + ' &mdash; ' + escapeHtml(t.assigned_to_name) + ' (' + daysOverdue + 'd overdue)',
      link: 'tasks.html'
    });
  });

  requisitions.filter(function (r) {
    if (r.approved_by || r.stage === 'Closed') {
      return false;
    }
    const raised = new Date(r.raised_date + 'T00:00:00');
    const daysElapsed = daysBetween(todayMidnight, raised) * -1;
    const tatDays = r.tat_days || 30;
    return (daysElapsed / tatDays) >= 0.8;
  }).forEach(function (r) {
    items.push({
      tag: 'tag-requisition',
      tagLabel: 'Requisition',
      text: escapeHtml(r.role) + ' &mdash; ' + escapeHtml(r.branch) + ' (unapproved, aging)',
      link: 'recruitment.html'
    });
  });

  candidates.filter(function (c) { return c.stage === 'Documents Pending'; }).forEach(function (c) {
    items.push({
      tag: 'tag-candidate',
      tagLabel: 'Candidate',
      text: escapeHtml(c.name) + ' &mdash; Documents Pending',
      link: 'recruitment.html'
    });
  });

  const capped = items.slice(0, 8);

  if (capped.length === 0) {
    content.innerHTML = '<div class="message">All caught up &#127881;</div>';
    return;
  }

  content.innerHTML = '<ul class="attention-list">' + capped.map(function (item) {
    return '<li>' +
      '<span class="attention-text"><span class="attention-tag ' + item.tag + '">' + item.tagLabel + '</span>' + item.text + '</span>' +
      '<a href="' + item.link + '" class="btn-view">View</a>' +
      '</li>';
  }).join('') + '</ul>';
}

function nextOccurrence(dateStr, todayMidnight) {
  if (!dateStr) {
    return null;
  }
  const original = new Date(dateStr + 'T00:00:00');
  if (isNaN(original.getTime())) {
    return null;
  }

  let next = new Date(todayMidnight.getFullYear(), original.getMonth(), original.getDate());
  if (next < todayMidnight) {
    next = new Date(todayMidnight.getFullYear() + 1, original.getMonth(), original.getDate());
  }
  return next;
}

function formatDaysAway(diffDays) {
  if (diffDays === 0) {
    return 'Today';
  }
  if (diffDays === 1) {
    return 'Tomorrow';
  }
  return 'in ' + diffDays + ' days';
}

function renderCelebrations(employees) {
  const content = document.getElementById('celebrations-content');
  const today = new Date();
  const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());

  const items = [];

  employees.forEach(function (emp) {
    const anniversary = nextOccurrence(emp.date_of_joining, todayMidnight);
    if (anniversary) {
      const diffDays = daysBetween(anniversary, todayMidnight) * -1;
      if (diffDays >= 0 && diffDays <= 14) {
        items.push({
          name: emp.name,
          type: 'Work Anniversary',
          date: anniversary,
          diffDays: diffDays
        });
      }
    }

    const birthday = nextOccurrence(emp.dob, todayMidnight);
    if (birthday) {
      const diffDays = daysBetween(birthday, todayMidnight) * -1;
      if (diffDays >= 0 && diffDays <= 14) {
        items.push({
          name: emp.name,
          type: 'Birthday',
          date: birthday,
          diffDays: diffDays
        });
      }
    }
  });

  items.sort(function (a, b) { return a.diffDays - b.diffDays; });

  if (items.length === 0) {
    content.innerHTML = '<div class="message">No upcoming celebrations in the next 2 weeks</div>';
    return;
  }

  content.innerHTML = '<ul class="celebration-list">' + items.map(function (item) {
    const dateLabel = item.date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
    return '<li>' +
      '<span><span class="celebration-badge">' + item.type + '</span>' + escapeHtml(item.name) + '</span>' +
      '<span>' + dateLabel + ' (' + formatDaysAway(item.diffDays) + ')</span>' +
      '</li>';
  }).join('') + '</ul>';
}
