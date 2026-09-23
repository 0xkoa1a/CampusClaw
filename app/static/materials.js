const form = document.querySelector('#upload-form');
if (form) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = document.querySelector('#upload-result');
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    result.textContent = '正在上传…';
    try {
      const response = await fetch('/api/materials', { method: 'POST', body: new FormData(form) });
      if (response.status === 401) {
        window.location.assign('/login');
        return;
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '上传失败');
      window.location.assign(`/materials?id=${encodeURIComponent(data.id)}`);
    } catch (error) {
      result.textContent = error.message;
      button.disabled = false;
    }
  });
}
