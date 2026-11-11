const token = getAuthToken();
const CANDIDATES_API_BASE = API_BASE + '/candidates/';

if (!token) {
  window.location.href = 'login.html';
} else {
  // Start loading only after the whole script has been evaluated: the loaders use
  // consts declared further down (error banners, state), which would otherwise be
  // in their temporal dead zone and throw before anything renders.
  document.addEventListener('DOMContentLoaded', function () {
    loadCandidates();
  });
}

let allCandidates = [];
const checklistCache = {};
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
function hidePageError() {
  const el = document.getElementById('page-error');
  el.textContent = '';
  el.style.display = 'none';
}

async function loadCandidates() {
  hidePageError();
  const content = document.getElementById('candidates-content');
  try {
    const response = await fetch(CANDIDATES_API_BASE, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Failed to load candidates.');
    const candidates = await response.json();
    allCandidates = candidates.filter(function (c) { return c.stage === 'Documents Pending'; });
    await Promise.all(allCandidates.map(function (c) { return loadChecklistFor(c.id); }));
    renderCandidates();
  } catch (err) {
    content.innerHTML = '<div class="error-state"><div>' + escapeHtml(err.message) + '</div><button type="button" class="btn-secondary" id="retry-button">Retry</button></div>';
    document.getElementById('retry-button').addEventListener('click', loadCandidates);
  }
}

const checklistErrors = {};

async function loadChecklistFor(candId) {
  delete checklistErrors[candId];
  try {
    const response = await fetch(CANDIDATES_API_BASE + candId + '/doc-checklist/', { headers: authHeaders(token) });
    if (response.ok) {
      checklistCache[candId] = await response.json();
    } else {
      checklistErrors[candId] = 'The document checklist could not be loaded (server returned ' + response.status + ').';
    }
  } catch (err) {
    checklistErrors[candId] = 'The document checklist could not be loaded. Check your connection and try again.';
  }
}

function renderCandidates() {
  const content = document.getElementById('candidates-content');
  if (allCandidates.length === 0) {
    content.innerHTML = '<div class="message">No candidates in Documents Pending.</div>';
    return;
  }

  content.innerHTML = allCandidates.map(function (cand) {
    const checklist = checklistCache[cand.id];
    const isExpanded = expandedIds.has(cand.id);
    const requiredItems = checklist ? (checklist.doc_checklist || []).filter(function (i) { return i.required !== false; }) : [];
    const totalCount = requiredItems.length;
    const verifiedCount = requiredItems.filter(function (i) { return i.file_url && i.status !== 'Rejected'; }).length;
    const allVerified = totalCount > 0 && verifiedCount === totalCount;

    let bodyHtml = '';
    if (isExpanded && checklist) {
      const categories = {};
      checklist.doc_checklist.forEach(function (item) {
        categories[item.category] = categories[item.category] || [];
        categories[item.category].push(item);
      });

      const categoriesHtml = Object.keys(categories).map(function (cat) {
        const itemsHtml = categories[cat].map(function (item) {
          const hasFile = !!item.file_url;
          const statusLabel = !hasFile ? 'Not uploaded' : (item.status === 'Pending' ? 'Uploaded' : item.status);
          const statusChip = item.status === 'Verified' ? 'chip-green' : (item.status === 'Rejected' ? 'chip-red' : (hasFile ? 'chip-navy' : 'chip-amber'));
          const uploadBtn = '<label class="btn-secondary btn-row upload-label" style="cursor: pointer; display: inline-block;">' +
            (hasFile ? 'Replace' : 'Upload') +
            '<input type="file" class="doc-upload-input" style="display: none;" data-cand-id="' + escapeHtml(cand.id) + '" data-item-id="' + escapeHtml(item.id) + '"></label>';
          const reviewBtns = hasFile
            ? '<button type="button" class="btn-done btn-row verify-doc-btn" data-cand-id="' + escapeHtml(cand.id) + '" data-item-id="' + escapeHtml(item.id) + '">Verify</button>' +
              '<button type="button" class="btn-delete btn-row reject-doc-btn" data-cand-id="' + escapeHtml(cand.id) + '" data-item-id="' + escapeHtml(item.id) + '">Reject</button>'
            : '';
          return '<div class="doc-item-row">' +
            '<span>' + escapeHtml(item.doc_name) +
            (item.file_url ? ' &middot; <a href="' + escapeHtml(item.file_url) + '" target="_blank">View file</a>' : ' &middot; <span style="color: var(--mut);">not uploaded</span>') +
            (item.rejection_reason ? '<div class="step-meta">Rejected: ' + escapeHtml(item.rejection_reason) + '</div>' : '') +
            '</span>' +
            '<span><span class="chip ' + statusChip + '" style="margin-right: 8px;">' + escapeHtml(statusLabel) + '</span>' +
            uploadBtn + reviewBtns + '</span>' +
            '</div>';
        }).join('');
        return '<div class="doc-category-title">' + escapeHtml(cat) + '</div>' + itemsHtml;
      }).join('');

      const additional = checklist.additional_docs;
      const nomineeHtml = (additional.nominee_docs || []).map(function (n) {
        return '<div class="doc-item-row"><span>' + escapeHtml(n.doc_name) + '</span>' +
          (n.file_url ? '<a href="' + escapeHtml(n.file_url) + '" target="_blank">View file</a>' : '<span style="color: var(--mut);">not uploaded</span>') +
          '</div>';
      }).join('');

      bodyHtml = '<div style="margin-top: 12px;">' +
        '<div class="progress-track"><div class="progress-fill" style="width:' + (totalCount ? Math.round(verifiedCount / totalCount * 100) : 0) + '%"></div></div>' +
        '<div class="progress-label">' + verifiedCount + '/' + totalCount + ' required documents uploaded</div>' +
        categoriesHtml +
        '<div class="doc-category-title">Additional Documents</div>' +
        '<div class="doc-item-row"><span>UAN Number</span><span>' + (additional.uan_number ? escapeHtml(additional.uan_number) : '&mdash;') + '</span></div>' +
        '<div class="doc-item-row"><span>Marital Status</span><span>' + (additional.marital_status ? escapeHtml(additional.marital_status) : '&mdash;') + '</span></div>' +
        (nomineeHtml || '<div class="message" style="padding: 8px 0;">No nominee documents submitted yet.</div>') +
        '<div class="form-actions" style="margin-top: 14px;">' +
        '<button type="button" class="btn-secondary send-link-btn" data-cand-id="' + escapeHtml(cand.id) + '" data-phone="' + escapeHtml(cand.phone || '') + '">Send Link</button>' +
        '<button type="button" class="btn-primary extract-review-btn" data-cand-id="' + escapeHtml(cand.id) + '"' + (checklist.ready_for_onboarding === true ? '' : ' disabled') + '>Move to Onboarding &rarr;</button>' +
        '</div>' +
        (checklist.ready_for_onboarding === true ? '' : '<div class="step-meta" style="margin-top: 8px;">' + escapeHtml(checklist.onboarding_blocked_reason || (checklist.ready_for_onboarding === undefined ? 'The server needs to be updated to the latest backend before candidates can be moved to Onboarding.' : '')) + '</div>') +
        '</div>';
    } else if (isExpanded) {
      bodyHtml = '<div class="form-error" style="display: block; margin-top: 12px;">' +
        escapeHtml(checklistErrors[cand.id] || 'No document checklist was found for this candidate.') +
        ' <button type="button" class="btn-secondary btn-row retry-checklist-btn" data-cand-id="' + escapeHtml(cand.id) + '" style="margin-left: 8px;">Retry</button></div>';
    } else {
      bodyHtml = '<div class="progress-label" style="margin-top: 8px;">' + verifiedCount + '/' + totalCount + ' required documents uploaded</div>' +
        '<div class="form-actions" style="margin-top: 10px;">' +
        '<button type="button" class="btn-primary open-docs-btn" data-cand-id="' + escapeHtml(cand.id) + '">Upload Documents</button></div>';
    }

    return '<div class="candidate-dp-card">' +
      '<div class="candidate-dp-header dp-toggle" data-cand-id="' + escapeHtml(cand.id) + '">' +
      '<span><strong>' + escapeHtml(cand.name) + '</strong><div class="step-meta">' + escapeHtml(cand.id) + (cand.requisition_role ? ' &middot; ' + escapeHtml(cand.requisition_role) : '') + '</div></span>' +
      '<span class="chip ' + (allVerified ? 'chip-green' : 'chip-amber') + '">' + verifiedCount + '/' + totalCount + ' uploaded</span>' +
      '</div>' +
      bodyHtml +
      '</div>';
  }).join('');

  content.querySelectorAll('.dp-toggle').forEach(function (header) {
    header.addEventListener('click', function () {
      const id = header.getAttribute('data-cand-id');
      if (expandedIds.has(id)) expandedIds.delete(id); else expandedIds.add(id);
      renderCandidates();
    });
  });

  content.querySelectorAll('.verify-doc-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      handleVerifyDoc(btn.getAttribute('data-cand-id'), btn.getAttribute('data-item-id'));
    });
  });

  content.querySelectorAll('.open-docs-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      expandedIds.add(btn.getAttribute('data-cand-id'));
      renderCandidates();
    });
  });

  content.querySelectorAll('.retry-checklist-btn').forEach(function (btn) {
    btn.addEventListener('click', async function (e) {
      e.stopPropagation();
      await loadChecklistFor(btn.getAttribute('data-cand-id'));
      renderCandidates();
    });
  });

  content.querySelectorAll('.upload-label').forEach(function (label) {
    label.addEventListener('click', function (e) { e.stopPropagation(); });
  });

  content.querySelectorAll('.doc-upload-input').forEach(function (input) {
    input.addEventListener('change', function () {
      if (input.files && input.files[0]) {
        handleUploadDoc(input.getAttribute('data-cand-id'), input.getAttribute('data-item-id'), input.files[0]);
      }
    });
  });

  content.querySelectorAll('.reject-doc-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      openRejectModal(btn.getAttribute('data-cand-id'), btn.getAttribute('data-item-id'));
    });
  });

  content.querySelectorAll('.send-link-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      handleSendLink(btn.getAttribute('data-cand-id'), btn.getAttribute('data-phone'));
    });
  });

  content.querySelectorAll('.extract-review-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      openReviewModal(btn.getAttribute('data-cand-id'), false);
    });
  });
}

async function handleUploadDoc(candId, itemId, file) {
  hidePageError();
  const body = new FormData();
  body.append('file', file);
  try {
    const response = await fetch(CANDIDATES_API_BASE + candId + '/doc-checklist/' + itemId + '/upload/', {
      method: 'POST',
      headers: authHeaders(token),
      body: body
    });
    if (handleUnauthorized(response)) return;
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(describeApiError(data) || 'Could not upload the document.');
    checklistCache[candId] = data;
    showToast('Document uploaded. It is stored in the Docs tab.', 'success');
    renderCandidates();
  } catch (err) {
    showToast(err.message || 'Upload failed.', 'error');
  }
}

async function handleVerifyDoc(candId, itemId) {
  hidePageError();
  try {
    const response = await fetch(CANDIDATES_API_BASE + candId + '/doc-checklist/' + itemId + '/verify/', {
      method: 'POST',
      headers: authHeaders(token)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Could not verify document.');
    checklistCache[candId] = await response.json();
    renderCandidates();
  } catch (err) {
    showPageError(err.message);
  }
}

let rejectingCandId = null;
let rejectingItemId = null;
const rejectModalOverlay = document.getElementById('reject-modal-overlay');
const rejectForm = document.getElementById('reject-form');

function openRejectModal(candId, itemId) {
  rejectingCandId = candId;
  rejectingItemId = itemId;
  rejectForm.reset();
  document.getElementById('reject-form-error').style.display = 'none';
  rejectModalOverlay.classList.add('open');
}
document.getElementById('reject-cancel-button').addEventListener('click', function () {
  rejectModalOverlay.classList.remove('open');
});
rejectModalOverlay.addEventListener('click', function (e) { if (e.target === rejectModalOverlay) rejectModalOverlay.classList.remove('open'); });

rejectForm.addEventListener('submit', async function (event) {
  event.preventDefault();
  try {
    const response = await fetch(CANDIDATES_API_BASE + rejectingCandId + '/doc-checklist/' + rejectingItemId + '/reject/', {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify({ reason: document.getElementById('reject-reason').value })
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Could not reject document.');
    checklistCache[rejectingCandId] = await response.json();
    rejectModalOverlay.classList.remove('open');
    renderCandidates();
  } catch (err) {
    const errorEl = document.getElementById('reject-form-error');
    errorEl.textContent = err.message;
    errorEl.style.display = 'block';
  }
});

async function handleSendLink(candId, phone) {
  hidePageError();
  try {
    const response = await fetch(CANDIDATES_API_BASE + candId + '/send-doc-link/', {
      method: 'POST',
      headers: authHeaders(token)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) throw new Error('Could not generate upload link.');
    const data = await response.json();
    const uploadUrl = window.location.origin + '/doc-upload.html?candidate=' + encodeURIComponent(candId) + '&token=' + encodeURIComponent(data.upload_token);
    const message = 'Hi, please upload your joining documents using this secure link: ' + uploadUrl;
    const digitsOnly = (phone || '').replace(/\D/g, '');
    window.open('https://wa.me/' + digitsOnly + '?text=' + encodeURIComponent(message), '_blank');
  } catch (err) {
    showPageError(err.message);
  }
}

const reviewModalOverlay = document.getElementById('review-modal-overlay');
let reviewingCandId = null;
let reviewingMoveAnywayNeeded = false;

function openReviewModal(candId, moveAnywayNeeded) {
  reviewingCandId = candId;
  reviewingMoveAnywayNeeded = moveAnywayNeeded;
  const cand = allCandidates.find(function (c) { return c.id === candId; });
  const checklist = checklistCache[candId];
  document.getElementById('review-form-error').style.display = 'none';
  document.getElementById('review-summary').innerHTML =
    '<div class="step-row"><span>Name</span><strong>' + escapeHtml(cand.name) + '</strong></div>' +
    '<div class="step-row"><span>Role</span><strong>' + escapeHtml(cand.requisition_role || '&mdash;') + '</strong></div>' +
    '<div class="step-row"><span>Branch</span><strong>' + escapeHtml(cand.requisition_branch || '&mdash;') + '</strong></div>' +
    '<div class="step-row"><span>Required documents uploaded</span><strong>' + checklist.required_uploaded_count + '/' + checklist.required_total_count + '</strong></div>' +
    '<div class="step-row"><span>Outcome</span><strong>' + escapeHtml(checklist.outcome || '') + '</strong></div>';
  reviewModalOverlay.classList.add('open');
}
document.getElementById('review-cancel-button').addEventListener('click', function () {
  reviewModalOverlay.classList.remove('open');
});
reviewModalOverlay.addEventListener('click', function (e) { if (e.target === reviewModalOverlay) reviewModalOverlay.classList.remove('open'); });

document.getElementById('review-confirm-button').addEventListener('click', async function () {
  try {
    const response = await fetch(CANDIDATES_API_BASE + reviewingCandId + '/create-employee/', {
      method: 'POST',
      headers: authHeaders(token, true),
      body: JSON.stringify({})
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(describeApiError(data) || 'Could not create employee.');
    }
    const created = await response.json().catch(function () { return {}; });
    reviewModalOverlay.classList.remove('open');
    showToast(created.message || 'Candidate successfully moved to Onboarding.', 'success');
    loadCandidates();
  } catch (err) {
    const errorEl = document.getElementById('review-form-error');
    errorEl.textContent = err.message;
    errorEl.style.display = 'block';
  }
});
