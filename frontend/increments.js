const token = getAuthToken();
const STRUCTURES_API_BASE = API_BASE + '/incentive-structures/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadStructures();
  });
}

let allStructures = [];

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


async function loadStructures() {
  const content = document.getElementById('structures-content');
  hidePageError();

  try {
    const response = await fetch(STRUCTURES_API_BASE, {
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to load incentive structures.');
    }

    allStructures = await response.json();
    renderStructures();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' +
      escapeHtml(err.message || 'Could not load incentive structures.') +
      '</div><button type="button" class="btn-secondary" id="retry-structures-button">Retry</button></div>';
    document.getElementById('retry-structures-button').addEventListener('click', loadStructures);
  }
}

function findMatchingSlab(slabs, amount) {
  return slabs.find(function (slab) {
    return amount >= slab.disbursement_min && amount <= slab.disbursement_max;
  });
}

function renderStructures() {
  const content = document.getElementById('structures-content');

  if (allStructures.length === 0) {
    content.innerHTML = '<div class="message">No incentive structures added yet.</div>';
    return;
  }

  content.innerHTML = allStructures.map(function (structure) {
    const slabRows = (structure.slabs || []).map(function (slab) {
      return '<tr><td>' + escapeHtml(slab.disbursement_min) + ' &ndash; ' + escapeHtml(slab.disbursement_max) + '</td><td>' + escapeHtml(slab.payout_pct) + '%</td></tr>';
    }).join('');

    const slabsTable = (structure.slabs || []).length === 0
      ? '<div class="message" style="padding: 12px 0;">No slabs configured.</div>'
      : '<table><thead><tr><th>Disbursement Range</th><th>Payout %</th></tr></thead><tbody>' + slabRows + '</tbody></table>';

    return '<div class="structure-card">' +
      '<div class="structure-header">' +
      '<div>' +
      '<div class="structure-title">' + escapeHtml(structure.name) + '</div>' +
      '<div class="structure-sub">' + (structure.department ? escapeHtml(structure.department) : 'All departments') + ' &middot; ' + (structure.slabs || []).length + ' slab(s)' +
      (structure.bonus_amount ? ' &middot; Bonus ' + escapeHtml(structure.bonus_amount) + ' at ' + escapeHtml(structure.bonus_threshold) : '') + '</div>' +
      '</div>' +
      '<div>' +
      '<button type="button" class="btn-edit btn-row edit-structure-btn" data-id="' + escapeHtml(structure.id) + '">Edit</button>' +
      '<button type="button" class="btn-delete btn-row delete-structure-btn" data-id="' + escapeHtml(structure.id) + '">Delete</button>' +
      '</div>' +
      '</div>' +
      slabsTable +
      '<div class="calc-row">' +
      '<input type="number" step="any" placeholder="Disbursement amount" class="calc-input" data-id="' + escapeHtml(structure.id) + '" style="max-width: 220px;">' +
      '<button type="button" class="btn-secondary calc-btn" data-id="' + escapeHtml(structure.id) + '">Calculate</button>' +
      '<span class="calc-result" id="calc-result-' + escapeHtml(structure.id) + '"></span>' +
      '</div>' +
      '</div>';
  }).join('');

  content.querySelectorAll('.calc-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id = btn.getAttribute('data-id');
      const input = content.querySelector('.calc-input[data-id="' + id + '"]');
      const resultEl = document.getElementById('calc-result-' + id);
      const amount = parseFloat(input.value);
      const structure = allStructures.find(function (s) { return s.id === id; });

      if (isNaN(amount) || !structure) {
        resultEl.textContent = 'Enter a valid amount.';
        return;
      }

      const slab = findMatchingSlab(structure.slabs || [], amount);
      if (!slab) {
        resultEl.textContent = 'No matching slab for this amount.';
        return;
      }

      let payout = amount * (slab.payout_pct / 100);
      let bonusNote = '';
      if (structure.bonus_amount && amount >= structure.bonus_threshold) {
        payout += structure.bonus_amount;
        bonusNote = ' (incl. bonus of ' + structure.bonus_amount + ')';
      }

      resultEl.textContent = 'Payout: ' + payout.toFixed(2) + bonusNote;
    });
  });

  content.querySelectorAll('.edit-structure-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const structure = allStructures.find(function (s) { return s.id === btn.getAttribute('data-id'); });
      if (structure) {
        openStructureModal('edit', structure);
      }
    });
  });

  content.querySelectorAll('.delete-structure-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      handleDeleteStructure(btn.getAttribute('data-id'));
    });
  });
}

async function handleDeleteStructure(id) {
  const confirmed = confirm('Are you sure you want to delete this incentive structure?');
  if (!confirmed) {
    return;
  }

  try {
    const response = await fetch(STRUCTURES_API_BASE + id + '/', {
      method: 'DELETE',
      headers: authHeaders(token)
    });

    if (handleUnauthorized(response)) {
      return;
    }

    if (!response.ok && response.status !== 204) {
      throw new Error('Could not delete incentive structure.');
    }

    loadStructures();
  } catch (err) {
    showPageError(err.message || 'Something went wrong. Please try again.');
  }
}

// ---------- Add / Edit structure modal ----------

const structureModalOverlay = document.getElementById('structure-modal-overlay');
const structureModalTitle = document.getElementById('structure-modal-title');
const structureForm = document.getElementById('structure-form');
const structureFormError = document.getElementById('structure-form-error');
const structureSubmitButton = document.getElementById('structure-submit-button');
const structureCancelButton = document.getElementById('structure-cancel-button');
const slabsEditor = document.getElementById('slabs-editor');

let editingStructureId = null;

document.getElementById('add-structure-button').addEventListener('click', function () {
  openStructureModal('add', null);
});
document.getElementById('add-slab-row-button').addEventListener('click', function () {
  addSlabRow(null);
});
structureForm.addEventListener('submit', handleStructureSubmit);
structureCancelButton.addEventListener('click', closeStructureModal);
structureModalOverlay.addEventListener('click', function (event) {
  if (event.target === structureModalOverlay) {
    closeStructureModal();
  }
});

function addSlabRow(slab) {
  const row = document.createElement('div');
  row.className = 'slab-row';
  row.style.display = 'flex';
  row.style.gap = '6px';
  row.style.marginBottom = '6px';
  row.innerHTML =
    '<input type="number" step="any" class="slab-min" placeholder="Min" style="width: 100%;" value="' + (slab ? escapeHtml(slab.disbursement_min) : '') + '">' +
    '<input type="number" step="any" class="slab-max" placeholder="Max" style="width: 100%;" value="' + (slab ? escapeHtml(slab.disbursement_max) : '') + '">' +
    '<input type="number" step="any" class="slab-pct" placeholder="Payout %" style="width: 100%;" value="' + (slab ? escapeHtml(slab.payout_pct) : '') + '">' +
    '<button type="button" class="btn-delete remove-slab-btn" style="padding: 6px 10px;">&#10005;</button>';
  row.querySelector('.remove-slab-btn').addEventListener('click', function () {
    row.remove();
  });
  slabsEditor.appendChild(row);
}

function openStructureModal(mode, structure) {
  editingStructureId = mode === 'edit' && structure ? structure.id : null;
  structureModalTitle.textContent = mode === 'edit' ? 'Edit Structure' : 'Add Structure';
  structureSubmitButton.textContent = mode === 'edit' ? 'Update' : 'Add';

  document.getElementById('structure-name').value = structure ? (structure.name || '') : '';
  document.getElementById('structure-department').value = structure ? (structure.department || '') : '';
  document.getElementById('structure-bonus-threshold').value = structure ? (structure.bonus_threshold || 0) : 0;
  document.getElementById('structure-bonus-amount').value = structure ? (structure.bonus_amount || 0) : 0;

  slabsEditor.innerHTML = '';
  const slabs = structure && structure.slabs ? structure.slabs : [];
  if (slabs.length === 0) {
    addSlabRow(null);
  } else {
    slabs.forEach(function (slab) {
      addSlabRow(slab);
    });
  }

  structureFormError.style.display = 'none';
  structureModalOverlay.classList.add('open');
}

function closeStructureModal() {
  structureModalOverlay.classList.remove('open');
  structureForm.reset();
  slabsEditor.innerHTML = '';
  editingStructureId = null;
}

async function handleStructureSubmit(event) {
  event.preventDefault();
  structureSubmitButton.disabled = true;
  structureFormError.style.display = 'none';

  const slabs = Array.from(slabsEditor.querySelectorAll('.slab-row')).map(function (row) {
    return {
      disbursement_min: parseFloat(row.querySelector('.slab-min').value) || 0,
      disbursement_max: parseFloat(row.querySelector('.slab-max').value) || 0,
      payout_pct: parseFloat(row.querySelector('.slab-pct').value) || 0
    };
  });

  const payload = {
    name: document.getElementById('structure-name').value,
    department: document.getElementById('structure-department').value,
    bonus_threshold: parseFloat(document.getElementById('structure-bonus-threshold').value) || 0,
    bonus_amount: parseFloat(document.getElementById('structure-bonus-amount').value) || 0,
    slabs: slabs
  };

  const isEditing = editingStructureId !== null;
  const url = isEditing ? STRUCTURES_API_BASE + editingStructureId + '/' : STRUCTURES_API_BASE;
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
      throw new Error(describeApiError(data) || 'Could not save incentive structure.');
    }

    closeStructureModal();
    loadStructures();
  } catch (err) {
    structureFormError.textContent = err.message || 'Something went wrong. Please try again.';
    structureFormError.style.display = 'block';
  } finally {
    structureSubmitButton.disabled = false;
  }
}
