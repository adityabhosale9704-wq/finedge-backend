/* Shared nav + theme-toggle wiring for every FinEdge HR OS page.
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

function initSharedNav() {
  var navToggle = document.getElementById('nav-toggle');
  var navLinks = document.getElementById('nav-links');
  var sidebar = document.querySelector('.top-nav');

  // Backdrop behind the sliding sidebar on mobile — created here instead
  // of being baked into every page's HTML.
  var backdrop = document.createElement('div');
  backdrop.className = 'nav-backdrop';
  document.body.appendChild(backdrop);

  function setToggleIcon(open) {
    if (!navToggle) return;
    navToggle.innerHTML = open ? '<i class="fa-solid fa-xmark"></i>' : '<i class="fa-solid fa-bars"></i>';
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    backdrop.classList.remove('open');
    setToggleIcon(false);
  }

  function openSidebar() {
    if (sidebar) sidebar.classList.add('open');
    backdrop.classList.add('open');
    setToggleIcon(true);
  }

  if (navToggle && sidebar) {
    navToggle.addEventListener('click', function () {
      if (sidebar.classList.contains('open')) closeSidebar();
      else openSidebar();
    });
  }
  backdrop.addEventListener('click', closeSidebar);
  // Tapping a nav link closes the sidebar again on mobile.
  if (navLinks) {
    navLinks.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', closeSidebar);
    });
  }
  // Sidebar becomes fixed-but-hidden only below 720px — if the window is
  // resized back up while it was left open, make sure it doesn't stay
  // stuck mid-transition.
  window.addEventListener('resize', function () {
    if (window.innerWidth > 720) closeSidebar();
  });

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
}

document.addEventListener('DOMContentLoaded', initSharedNav);
