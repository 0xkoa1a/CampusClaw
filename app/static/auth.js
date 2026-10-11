const TOKEN_SLOT = 'campusclaw.accessToken';

function clearAccessToken() {
  sessionStorage.removeItem(TOKEN_SLOT);
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = sessionStorage.getItem(TOKEN_SLOT);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) clearAccessToken();
  return response;
}

window.campusAuth = { fetch: apiFetch, clear: clearAccessToken };

const loginForm = document.querySelector('#login-form');
if (loginForm) {
  clearAccessToken();
  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = loginForm.querySelector('button[type="submit"]');
    const result = document.querySelector('#login-result');
    button.disabled = true;
    result.textContent = '';
    try {
      const response = await fetch('/api/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: loginForm.username.value.trim(),
          password: loginForm.password.value, auth_mode: 'bearer',
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '登录失败');
      sessionStorage.setItem(TOKEN_SLOT, data.access_token);
      window.location.assign('/materials');
    } catch (error) {
      result.textContent = error.message;
      button.disabled = false;
    }
  });
}

document.querySelector('#logout-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const result = document.querySelector('#auth-status');
  try {
    const response = await apiFetch('/api/logout', { method: 'POST' });
    if (!response.ok && response.status !== 401) throw new Error('退出失败，请重试');
    clearAccessToken();
    window.location.assign('/login');
  } catch (error) {
    if (result) result.textContent = error.message;
  }
});

if (document.querySelector('#auth-status')) {
  window.campusAuth.fetch('/api/materials').then((response) => {
    if (response.status === 401) window.location.assign('/login');
    else if (!response.ok) document.querySelector('#auth-status').textContent = '材料服务暂时不可用';
  }).catch(() => {
    document.querySelector('#auth-status').textContent = '网络连接失败';
  });
}
