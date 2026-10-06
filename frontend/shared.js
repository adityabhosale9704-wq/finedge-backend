/* Shared sidebar + theme-toggle wiring for every FinEdge HR OS page.
   Loaded synchronously in <head> (after shared.css) so the saved
   theme is applied before first paint, avoiding a flash of the
   wrong theme. */

/* Single place every page's API_BASE-prefixed fetch calls point at.
   Local dev (Django on your own machine): leave this as-is.
   After hosting the backend on AWS: change ONLY this one line to your
   server's address (e.g. 'https://api.yourdomain.com/api/v1' or
   'http://<your-ec2-ip>:8000/api/v1') and every page picks it up —
   no need to touch the 17 HTML files individually again. */
window.API_BASE = 'http://16.170.98.44/api/v1';

(function () {
  var savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'dark' || savedTheme === 'light') {
    document.documentElement.setAttribute('data-theme', savedTheme);
  }
})();

function getCurrentTheme() {
  var explicit = document.documentElement.getAttribute('data-theme');
  if (explicit === 'dark' || explicit === 'light') {
    return explicit;
  }
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function updateThemeToggleIcon() {
  var themeToggle = document.getElementById('theme-toggle');
  if (!themeToggle) {
    return;
  }
  var isDark = getCurrentTheme() === 'dark';
  themeToggle.innerHTML = isDark ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
  themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
}

/* ---------- Sidebar config ----------
   One source of truth for every page's nav entry. Add/remove/reorder
   pages here only — every page's sidebar is generated from this, so
   there is nothing left to keep in sync by hand across HTML files. */

var NAV_CONFIG = [
  { href: 'dashboard.html', icon: 'fa-gauge-high', label: 'Dashboard' },
  {
    key: 'hr-management',
    label: 'HR Management',
    icon: 'fa-users',
    items: [
      { href: 'employees.html', icon: 'fa-users', label: 'Employees' },
      { href: 'positions.html', icon: 'fa-id-badge', label: 'Employee IDs' },
      { href: 'recruitment.html', icon: 'fa-user-plus', label: 'Recruitment' },
      { href: 'onboarding.html', icon: 'fa-clipboard-check', label: 'Onboarding' },
      { href: 'tasks.html', icon: 'fa-list-check', label: 'Tasks' }
    ]
  },
  {
    key: 'operations',
    label: 'Operations',
    icon: 'fa-sliders',
    items: [
      { href: 'salary-structure.html', icon: 'fa-sack-dollar', label: 'Salary Structure' },
      { href: 'increments.html', icon: 'fa-chart-line', label: 'Increments' },
      { href: 'exit.html', icon: 'fa-door-open', label: 'Exit' },
      { href: 'engagement.html', icon: 'fa-heart', label: 'Engagement' },
      { href: 'compliance.html', icon: 'fa-shield-halved', label: 'Compliance' }
    ]
  },
  {
    key: 'reports-tools',
    label: 'Reports & Tools',
    icon: 'fa-chart-pie',
    items: [
      { href: 'done-board.html', icon: 'fa-square-check', label: 'Done Board' },
      { href: 'interview-questions.html', icon: 'fa-circle-question', label: 'Interview Questions' }
    ]
  },
  {
    key: 'settings',
    label: 'Settings',
    icon: 'fa-gear',
    items: [
      { href: 'admin.html', icon: 'fa-building', label: 'Admin Studio' },
      { href: 'workindia.html', icon: 'fa-file-import', label: 'WorkIndia Import' }
    ]
  }
];

function buildSidebarHtml(currentPage) {
  var openGroups = {};
  try {
    openGroups = JSON.parse(localStorage.getItem('navOpenGroups') || '{}');
  } catch (err) {
    openGroups = {};
  }

  var html = '';
  html += '<div class="nav-bar">';
  html += '  <div class="nav-header">';
  html += '    <a href="dashboard.html" class="nav-logo"><span class="nav-logo-badge"><i class="fa-solid fa-building-columns"></i></span><span>HR OS</span></a>';
  html += '    <button type="button" class="nav-collapse-toggle" id="nav-collapse-toggle" aria-label="Collapse sidebar"><i class="fa-solid fa-chevron-left"></i></button>';
  html += '  </div>';

  html += '  <div class="nav-search">';
  html += '    <i class="fa-solid fa-magnifying-glass"></i>';
  html += '    <input type="text" id="nav-search-input" placeholder="Search menu...">';
  html += '    <span class="nav-search-kbd">⌘K</span>';
  html += '  </div>';

  html += '  <div class="nav-links" id="nav-links">';

  NAV_CONFIG.forEach(function (entry) {
    if (!entry.items) {
      var isActive = entry.href === currentPage;
      html += '<a href="' + entry.href + '" class="nav-link' + (isActive ? ' active' : '') + '" data-nav-label="' + entry.label.toLowerCase() + '">' +
        '<i class="fa-solid ' + entry.icon + '"></i><span>' + entry.label + '</span></a>';
      return;
    }

    var groupHasActive = entry.items.some(function (item) { return item.href === currentPage; });
    var isOpen = groupHasActive || openGroups[entry.key] === true;

    html += '<div class="nav-group' + (isOpen ? ' open' : '') + '" data-group="' + entry.key + '">';
    html += '  <button type="button" class="nav-group-header">' +
      '<i class="fa-solid ' + entry.icon + '"></i><span>' + entry.label + '</span>' +
      '<i class="fa-solid fa-chevron-down nav-group-chevron"></i></button>';
    html += '  <div class="nav-group-items">';
    entry.items.forEach(function (item) {
      var isActive = item.href === currentPage;
      html += '<a href="' + item.href + '" class="nav-link nav-sublink' + (isActive ? ' active' : '') + '" data-nav-label="' + item.label.toLowerCase() + '">' +
        '<i class="fa-solid ' + item.icon + '"></i><span>' + item.label + '</span></a>';
    });
    html += '  </div>';
    html += '</div>';
  });

  html += '  </div>';

  html += '  <button type="button" class="theme-toggle" id="theme-toggle" aria-label="Toggle theme"><i class="fa-solid fa-moon"></i></button>';

  html += '  <div class="nav-profile" id="nav-profile">';
  html += '    <span class="nav-profile-avatar" id="nav-profile-avatar">…</span>';
  html += '    <span class="nav-profile-info">';
  html += '      <span class="nav-profile-name" id="nav-profile-name">Loading…</span>';
  html += '      <span class="nav-profile-role" id="nav-profile-role">&nbsp;</span>';
  html += '    </span>';
  html += '    <i class="fa-solid fa-chevron-right"></i>';
  html += '  </div>';

  html += '</div>';
  return html;
}

var ROLE_LABELS = {
  admin: 'HR Admin',
  hr: 'HR Executive',
  manager: 'Manager'
};

function loadNavProfile() {
  var nameEl = document.getElementById('nav-profile-name');
  var roleEl = document.getElementById('nav-profile-role');
  var avatarEl = document.getElementById('nav-profile-avatar');
  if (!nameEl) {
    return;
  }

  var token = localStorage.getItem('authToken');
  if (!token) {
    return;
  }

  fetch(window.API_BASE + '/auth/me/', { headers: { 'Authorization': 'Bearer ' + token } })
    .then(function (response) { return response.ok ? response.json() : null; })
    .then(function (data) {
      if (!data) {
        return;
      }
      var name = data.name || (data.email ? data.email.split('@')[0] : 'User');
      nameEl.textContent = name;
      roleEl.textContent = ROLE_LABELS[data.role] || data.role || 'User';
      var initials = name
        .split(/\s+/)
        .slice(0, 2)
        .map(function (part) { return part.charAt(0).toUpperCase(); })
        .join('');
      avatarEl.textContent = initials || 'U';
    })
    .catch(function () {
      nameEl.textContent = 'User';
      roleEl.textContent = '';
    });
}

function initSidebarInteractions() {
  var sidebar = document.querySelector('.top-nav');
  var navToggle = document.getElementById('nav-toggle');
  var navLinks = document.getElementById('nav-links');

  var backdrop = document.createElement('div');
  backdrop.className = 'nav-backdrop';
  document.body.appendChild(backdrop);

  function setToggleIcon(open) {
    if (!navToggle) return;
    navToggle.innerHTML = open ? '<i class="fa-solid fa-xmark"></i>' : '<i class="fa-solid fa-bars"></i>';
  }

  function closeMobileSidebar() {
    if (sidebar) sidebar.classList.remove('mobile-open');
    backdrop.classList.remove('open');
    setToggleIcon(false);
  }

  function openMobileSidebar() {
    if (sidebar) sidebar.classList.add('mobile-open');
    backdrop.classList.add('open');
    setToggleIcon(true);
  }

  if (navToggle && sidebar) {
    navToggle.addEventListener('click', function () {
      if (sidebar.classList.contains('mobile-open')) closeMobileSidebar();
      else openMobileSidebar();
    });
  }
  backdrop.addEventListener('click', closeMobileSidebar);
  if (navLinks) {
    navLinks.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', closeMobileSidebar);
    });
  }
  window.addEventListener('resize', function () {
    if (window.innerWidth > 720) closeMobileSidebar();
  });

  // Collapsible groups, state persisted so it survives the full page
  // reload every nav click causes in this multi-page app.
  document.querySelectorAll('.nav-group-header').forEach(function (header) {
    header.addEventListener('click', function () {
      var group = header.closest('.nav-group');
      var isOpen = group.classList.toggle('open');
      var key = group.getAttribute('data-group');
      var openGroups = {};
      try {
        openGroups = JSON.parse(localStorage.getItem('navOpenGroups') || '{}');
      } catch (err) {
        openGroups = {};
      }
      openGroups[key] = isOpen;
      localStorage.setItem('navOpenGroups', JSON.stringify(openGroups));
    });
  });

  // Collapse-to-icon-rail toggle. body.sidebar-collapsed shrinks the
  // content area's left margin to match (see shared.css).
  var collapseToggle = document.getElementById('nav-collapse-toggle');
  if (collapseToggle && sidebar) {
    if (localStorage.getItem('navCollapsed') === 'true') {
      sidebar.classList.add('collapsed');
      document.body.classList.add('sidebar-collapsed');
    }
    collapseToggle.addEventListener('click', function () {
      var collapsed = sidebar.classList.toggle('collapsed');
      document.body.classList.toggle('sidebar-collapsed', collapsed);
      localStorage.setItem('navCollapsed', collapsed ? 'true' : 'false');
    });
  }

  // Search filters visible nav items by label, auto-opening any group
  // that has a match so the result is actually visible.
  var searchInput = document.getElementById('nav-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      var term = searchInput.value.trim().toLowerCase();
      document.querySelectorAll('#nav-links > a, .nav-group').forEach(function (el) {
        if (el.matches('.nav-group')) {
          var matches = Array.prototype.slice.call(el.querySelectorAll('[data-nav-label]'))
            .some(function (link) { return link.getAttribute('data-nav-label').indexOf(term) !== -1; });
          el.style.display = term && !matches ? 'none' : '';
          if (term && matches) el.classList.add('open');
        } else {
          var label = el.getAttribute('data-nav-label') || '';
          el.style.display = term && label.indexOf(term) === -1 ? 'none' : '';
        }
      });
    });

    window.addEventListener('keydown', function (event) {
      var isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
      if (isShortcut) {
        event.preventDefault();
        searchInput.focus();
      }
    });
  }

  var themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    updateThemeToggleIcon();
    themeToggle.addEventListener('click', function () {
      var next = getCurrentTheme() === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      updateThemeToggleIcon();
    });
  }

  loadNavProfile();
}

function initSharedNav() {
  var mount = document.getElementById('app-sidebar');
  if (!mount) {
    // Pages with no sidebar (login) just skip all of this.
    return;
  }

  var currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';

  // Mobile hamburger button lives outside the sidebar markup itself so it
  // stays visible even while the sidebar is off-screen.
  var navToggle = document.createElement('button');
  navToggle.type = 'button';
  navToggle.id = 'nav-toggle';
  navToggle.className = 'nav-toggle';
  navToggle.setAttribute('aria-label', 'Toggle navigation');
  navToggle.innerHTML = '<i class="fa-solid fa-bars"></i>';
  document.body.insertBefore(navToggle, document.body.firstChild);

  mount.innerHTML = buildSidebarHtml(currentPage);
  initSidebarInteractions();
}

document.addEventListener('DOMContentLoaded', initSharedNav);
