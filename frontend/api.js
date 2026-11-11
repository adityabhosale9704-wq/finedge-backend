/* Shared API/auth behavior; public upload and login requests stay unauthenticated. */
function getAuthToken() {
  return localStorage.getItem('authToken');
}

function authHeaders(token, json) {
  var headers = { 'Authorization': 'Bearer ' + token };
  if (json) headers['Content-Type'] = 'application/json';
  return headers;
}

function logout() {
  localStorage.removeItem('authToken');
  window.location.href = 'login.html';
}

function handleUnauthorized(response) {
  if (response.status === 401) {
    logout();
    return true;
  }
  return false;
}

function describeApiError(data) {
  if (!data) return '';
  if (typeof data === 'string') return data;
  if (data.detail) return String(data.detail);
  return Object.keys(data).map(function (field) {
    var value = data[field];
    return field + ': ' + (Array.isArray(value) ? value.join(' ') : String(value));
  }).join(' | ');
}
