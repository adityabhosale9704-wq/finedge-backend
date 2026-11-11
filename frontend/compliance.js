const token = getAuthToken();
const COMPLIANCE_API_BASE = API_BASE + '/compliance/';
const BRANCHES_API_BASE = API_BASE + '/branches/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadComplianceItems();
    loadBranches();
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


let allItems = [];

async function loadComplianceItems() {
  const content = document.getElementById('items-content');
  try {
    const response = await fetch(COMPLIANCE_API_BASE, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load compliance items.');
    allItems = await response.json();
    renderItems();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message) + '</div><button type="button" class="btn-secondary" id="retry-items-button">Retry</button></div>';
    document.getElementById('retry-items-button').addEventListener('click', loadComplianceItems);
  }
}

function renderItems() {
  const content = document.getElementById('items-content');
  if (allItems.length === 0) {
    content.innerHTML = '<div class="message">No compliance items added yet.</div>';
    return;
  }
  const rows = allItems.map(function (item) {
    return '<tr><td>' + escapeHtml(item.act_name) + '</td><td>' + (item.frequency ? escapeHtml(item.frequency) : '&mdash;') + '</td>' +
      '<td>' + (item.owner ? escapeHtml(item.owner) : '&mdash;') + '</td>' +
      '<td>' + escapeHtml(item.next_due_date) + '</td>' +
      '<td><span class="status-chip ' + item.status + '">' + item.status.toUpperCase() + '</span></td>' +
      '<td><button type="button" class="btn-edit btn-row edit-item-btn" data-id="' + escapeHtml(item.id) + '">Edit</button>' +
      '<button type="button" class="btn-delete btn-row delete-item-btn" data-id="' + escapeHtml(item.id) + '">Delete</button></td></tr>';
  }).join('');
  content.innerHTML = '<table><thead><tr><th>Act Name</th><th>Frequency</th><th>Owner</th><th>Next Due Date</th><th>Status</th><th>Actions</th></tr></thead><tbody>' + rows + '</tbody></table>';

  content.querySelectorAll('.edit-item-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const item = allItems.find(function (x) { return x.id === btn.getAttribute('data-id'); });
      if (item) openItemModal('edit', item);
    });
  });
  content.querySelectorAll('.delete-item-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { handleDeleteItem(btn.getAttribute('data-id')); });
  });
}

async function handleDeleteItem(id) {
  if (!confirm('Delete this compliance item?')) return;
  const response = await fetch(COMPLIANCE_API_BASE + id + '/', { method: 'DELETE', headers: authHeaders(token) });
  if (handleUnauthorized(response)) return;
  loadComplianceItems();
}

const itemModalOverlay = document.getElementById('item-modal-overlay');
const itemForm = document.getElementById('item-form');
let editingItemId = null;

document.getElementById('add-item-button').addEventListener('click', function () { openItemModal('add', null); });
document.getElementById('item-cancel-button').addEventListener('click', closeItemModal);
itemModalOverlay.addEventListener('click', function (e) { if (e.target === itemModalOverlay) closeItemModal(); });
itemForm.addEventListener('submit', handleItemSubmit);

function openItemModal(mode, item) {
  editingItemId = mode === 'edit' && item ? item.id : null;
  document.getElementById('item-modal-title').textContent = mode === 'edit' ? 'Edit Compliance Item' : 'Add Compliance Item';
  document.getElementById('item-submit-button').textContent = mode === 'edit' ? 'Update' : 'Add';
  document.getElementById('item-act-name').value = item ? (item.act_name || '') : '';
  document.getElementById('item-frequency').value = item ? (item.frequency || '') : '';
  document.getElementById('item-owner').value = item ? (item.owner || '') : '';
  document.getElementById('item-due-date').value = item ? (item.next_due_date || '') : '';
  document.getElementById('item-modal-form-error').style.display = 'none';
  itemModalOverlay.classList.add('open');
}
function closeItemModal() {
  itemModalOverlay.classList.remove('open');
  itemForm.reset();
  editingItemId = null;
}
async function handleItemSubmit(event) {
  event.preventDefault();
  const payload = {
    act_name: document.getElementById('item-act-name').value,
    frequency: document.getElementById('item-frequency').value,
    owner: document.getElementById('item-owner').value,
    next_due_date: document.getElementById('item-due-date').value
  };
  const isEditing = editingItemId !== null;
  const url = isEditing ? COMPLIANCE_API_BASE + editingItemId + '/' : COMPLIANCE_API_BASE;
  try {
    const response = await fetch(url, {
      method: isEditing ? 'PATCH' : 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify(payload)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Could not save compliance item.');
    closeItemModal();
    loadComplianceItems();
  } catch (err) {
    const errorEl = document.getElementById('item-modal-form-error');
    errorEl.textContent = err.message;
    errorEl.style.display = 'block';
  }
}

// ---------- Branches S&E summary ----------

async function loadBranches() {
  const content = document.getElementById('branches-content');
  try {
    const response = await fetch(BRANCHES_API_BASE, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load branches.');
    const branches = await response.json();
    renderBranches(branches);
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message) + '</div></div>';
  }
}

function renderBranches(branches) {
  const content = document.getElementById('branches-content');
  if (branches.length === 0) {
    content.innerHTML = '<div class="message">No branches found.</div>';
    return;
  }
  const rows = branches.map(function (b) {
    const registered = !!b.s_and_e_number;
    return '<tr><td>' + escapeHtml(b.name) + '</td>' +
      '<td>' + (registered ? escapeHtml(b.s_and_e_number) : '&mdash;') + '</td>' +
      '<td><span class="status-chip ' + (registered ? 'green' : 'red') + '">' + (registered ? 'REGISTERED' : 'MISSING') + '</span></td></tr>';
  }).join('');
  content.innerHTML = '<table><thead><tr><th>Branch</th><th>S&amp;E Number</th><th>Status</th></tr></thead><tbody>' + rows + '</tbody></table>';
}
