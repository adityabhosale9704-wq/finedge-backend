const form = document.getElementById('login-form');
const errorMessage = document.getElementById('error-message');
const loginButton = document.getElementById('login-button');

form.addEventListener('submit', async function (event) {
  event.preventDefault();

  errorMessage.style.display = 'none';
  errorMessage.textContent = '';
  loginButton.disabled = true;

  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  try {
    const response = await fetch(API_BASE + '/auth/login/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email: email, password: password })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(describeApiError(data) || 'Login failed. Please try again.');
    }

    localStorage.setItem('authToken', data.token);
    window.location.href = 'employees.html';
  } catch (err) {
    errorMessage.textContent = err.message || 'Something went wrong. Please try again.';
    errorMessage.style.display = 'block';
  } finally {
    loginButton.disabled = false;
  }
});
