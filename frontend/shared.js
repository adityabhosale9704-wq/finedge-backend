/* Shared nav + theme-toggle wiring for every FinEdge HR OS page.
   Loaded synchronously in <head> (after shared.css) so the saved
   theme is applied before first paint, avoiding a flash of the
   wrong theme. */

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
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', function () {
      navLinks.classList.toggle('open');
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
}

document.addEventListener('DOMContentLoaded', initSharedNav);
