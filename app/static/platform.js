/* Catalog templates are copied to editable fields; trace display is owner-only. */
(() => {
  async function json(path) {
    const response = await window.campusAuth.fetch(path);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '请求失败');
    return data;
  }
  const template = document.querySelector('#prompt-template');
  document.querySelector('#install-apps')?.addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try {
      const response = await window.campusAuth.fetch('/api/platform/install', {method:'POST'});
      if (!response.ok) throw new Error('内置应用安装失败');
      window.location.reload();
    } catch (error) { document.querySelector('#auth-status').textContent = error.message; event.currentTarget.disabled = false; }
  });
  if (template) json('/api/platform/catalog').then((catalog) => {
    for (const [selector, items, apply] of [
      [template, catalog.prompt_templates, (item) => { document.querySelector('#agent-prompt').value = item.content; }],
      [document.querySelector('#builtin-skill'), catalog.skills, (item) => {
        document.querySelector('#skill-reset').click();
        document.querySelector('#skill-name').value = item.name;
        document.querySelector('#skill-source').value = item.source;
      }],
    ]) {
      items.forEach((item, index) => { const option = document.createElement('option'); option.value = String(index); option.textContent = item.name; selector.append(option); });
      selector.addEventListener('change', () => { if (selector.value !== '') apply(items[Number(selector.value)]); });
    }
  }).catch((error) => { document.querySelector('#auth-status').textContent = error.message; });
  document.querySelector('#load-traces')?.addEventListener('click', async () => {
    const output = document.querySelector('#call-traces');
    const id = new URLSearchParams(window.location.search).get('id');
    if (!id) { output.textContent = '请先选择会话'; return; }
    try { output.textContent = JSON.stringify(await json(`/api/conversations/${encodeURIComponent(id)}/traces`), null, 2); }
    catch (error) { output.textContent = error.message; }
  });
})();
