const token = getAuthToken();
const EMPLOYEES_API_BASE = API_BASE + '/employees/';
const CANDIDATES_API_BASE = API_BASE + '/candidates/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadEmployees();
    loadCandidates();
  });
}

let allEmployees = [];
let allCandidates = [];
let searchTerm = '';
const expandedIds = new Set();

function escapeHtml(value) {
  if (value === undefined || value === null) return '';
  const div = document.createElement('div');
  div.textContent = String(value);
  return div.innerHTML;
}


function showPageError(message) {
  const el = document.getElementById('page-error');
  el.textContent = message;
  el.style.display = 'block';
}

document.querySelectorAll('#docs-tabs .tab').forEach(function (tab) {
  tab.addEventListener('click', function () {
    document.querySelectorAll('#docs-tabs .tab').forEach(function (t) { t.classList.remove('active'); });
    document.querySelectorAll('.docs-panel').forEach(function (p) { p.classList.remove('active'); });
    tab.classList.add('active');
    document.getElementById('panel-' + tab.getAttribute('data-panel')).classList.add('active');
  });
});

document.getElementById('docs-search-input').addEventListener('input', function (event) {
  searchTerm = event.target.value.trim().toLowerCase();
  renderEmployeesPanels();
  renderCandidatesPanel();
});

async function loadEmployees() {
  try {
    const response = await fetch(EMPLOYEES_API_BASE, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load employees.');
    allEmployees = await response.json();
    renderEmployeesPanels();
  } catch (err) {
    showPageError(err.message);
  }
}

async function loadCandidates() {
  try {
    const response = await fetch(CANDIDATES_API_BASE, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load candidates.');
    allCandidates = await response.json();
    renderCandidatesPanel();
  } catch (err) {
    showPageError(err.message);
  }
}

const candidateChecklistCache = {};

function renderPersonList(containerId, people, idPrefix, getDocsFn) {
  const container = document.getElementById(containerId);
  const filtered = searchTerm
    ? people.filter(function (p) { return (p.name || '').toLowerCase().indexOf(searchTerm) !== -1; })
    : people;

  if (filtered.length === 0) {
    container.innerHTML = '<div class="message">No matches.</div>';
    return;
  }

  container.innerHTML = filtered.map(function (person) {
    const rowId = idPrefix + person.id;
    const isExpanded = expandedIds.has(rowId);
    const docs = getDocsFn(person);
    // Candidate doc-checklist entries need the dedicated endpoint for
    // absolute file URLs (the bulk /candidates/ list only has relative
    // storage paths) — cached per candidate once fetched, used only for
    // the expanded detail view's links, not the count badge above.
    const detailDocs = idPrefix === 'cand-' ? (candidateChecklistCache[person.id] || docs) : docs;
    let detailHtml = '';
    if (isExpanded) {
      if (detailDocs.length === 0) {
        detailHtml = '<div class="doc-vault-detail message" style="padding: 10px 0;">No documents on file.</div>';
      } else {
        detailHtml = '<div class="doc-vault-detail">' + detailDocs.map(function (d) {
          // Employee doc-vault entries store their absolute URL under
          // file_path (see employees/views.py::serialize_employee);
          // candidate doc-checklist entries use file_url instead.
          const url = d.file_path || d.file_url;
          return '<div class="step-row"><div class="step-info"><div class="step-name">' + escapeHtml(d.name || d.doc_name) + '</div>' +
            '<div class="step-meta">' + escapeHtml(d.status || d.category || '') + '</div></div>' +
            (url ? '<a href="' + escapeHtml(url) + '" target="_blank" class="btn-view">View</a>' : '<span class="chip chip-gray">Not uploaded</span>') +
            '</div>';
        }).join('') + '</div>';
      }
    }
    return '<div class="doc-vault-row-wrap">' +
      '<div class="doc-vault-row" data-row-id="' + escapeHtml(rowId) + '">' +
      '<span><strong>' + escapeHtml(person.name) + '</strong></span>' +
      '<span class="chip chip-navy">' + (idPrefix === 'cand-' ? docs.filter(function (d) { return !!d.file_url; }).length + '/' + docs.length + ' uploaded' : docs.length + ' document(s)') + '</span>' +
      '</div>' +
      detailHtml +
      '</div>';
  }).join('');

  container.querySelectorAll('.doc-vault-row').forEach(function (row) {
    row.addEventListener('click', async function () {
      const id = row.getAttribute('data-row-id');
      if (expandedIds.has(id)) {
        expandedIds.delete(id);
      } else {
        expandedIds.add(id);
        if (id.indexOf('cand-') === 0) {
          const candId = id.slice('cand-'.length);
          if (!candidateChecklistCache[candId]) {
            try {
              const response = await fetch(CANDIDATES_API_BASE + candId + '/doc-checklist/', { headers: authHeaders(token) });
              if (response.ok) {
                const data = await response.json();
                candidateChecklistCache[candId] = data.doc_checklist;
              }
            } catch (err) {
              // Non-fatal — detail view just shows nothing for this candidate.
            }
          }
        }
      }
      renderEmployeesPanels();
      renderCandidatesPanel();
    });
  });
}

function renderEmployeesPanels() {
  const employees = allEmployees.filter(function (e) { return e.status !== 'Leaver'; });
  const leavers = allEmployees.filter(function (e) { return e.status === 'Leaver'; });
  renderPersonList('employees-list', employees, 'emp-', function (e) { return e.docs || []; });
  renderPersonList('leavers-list', leavers, 'lvr-', function (e) { return e.docs || []; });
}

function renderCandidatesPanel() {
  const inPipeline = allCandidates.filter(function (c) {
    // Joined candidates stay listed: their joining documents remain on file here
    // after they move to Onboarding.
    return ['Rejected', 'Withdrawn'].indexOf(c.stage) === -1 && (c.doc_checklist || []).length > 0;
  });
  renderPersonList('candidates-list', inPipeline, 'cand-', function (c) { return c.doc_checklist || []; });
}
