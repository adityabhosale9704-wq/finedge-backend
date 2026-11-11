/* Public browser configuration. This file must never contain credentials.
   Set apiBase to an HTTPS /api/v1 URL for a separately hosted backend.
   An empty value uses local Django in development or the same origin in deployment. */
window.HR_OS_CONFIG = Object.assign({ apiBase: '' }, window.HR_OS_CONFIG || {});
var localDevelopment = ['localhost', '127.0.0.1', '[::1]'].indexOf(window.location.hostname) !== -1;
window.API_BASE = (window.HR_OS_CONFIG.apiBase ||
  (localDevelopment ? 'http://127.0.0.1:8000/api/v1' : window.location.origin + '/api/v1')).replace(/\/+$/, '');
