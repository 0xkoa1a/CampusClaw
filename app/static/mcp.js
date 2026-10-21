(() => {
  const form = document.querySelector('#server-form');
  if (!form) return;

  const list = document.querySelector('#server-list');
  const pageStatus = document.querySelector('#page-status');
  const auditStatus = document.querySelector('#audit-status');
  const saveButton = document.querySelector('#save-server');
  const cancelButton = document.querySelector('#cancel-edit');
  let editingId = null;

  function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.textContent = value || '';
  }

  async function api(path, options = {}) {
    const response = await window.campusAuth.fetch(path, options);
    if (response.status === 401) {
      window.location.assign('/login');
      throw new Error('登录已失效');
    }
    let data = {};
    try {
      data = await response.json();
    } catch (_error) {
      data = {};
    }
    if (!response.ok) {
      if (response.status === 403) throw new Error('需要教师权限');
      throw new Error(data.error || `请求失败（${response.status}）`);
    }
    return data;
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function jsonRequest(method, body) {
    return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  }

  function resetForm() {
    editingId = null;
    form.reset();
    form.elements.token_env.value = 'MCP_AUTH_TOKEN';
    setText('#server-form-title', '登记 MCP 服务器');
    setText('#save-server', '登记服务器');
    cancelButton.hidden = true;
  }

  function startEdit(server) {
    editingId = server.id;
    form.elements.name.value = server.name;
    form.elements.base_url.value = server.base_url;
    form.elements.token_env.value = server.token_env;
    setText('#server-form-title', `编辑服务器 · ${server.name}`);
    setText('#save-server', '保存修改');
    cancelButton.hidden = false;
    form.scrollIntoView({ behavior: 'smooth', block: 'center' });
    form.elements.name.focus();
  }

  function renderTool(tool) {
    const card = element('article', 'tool-card');
    const heading = element('div', 'tool-heading');
    heading.append(element('h4', '', tool.name || '未命名工具'));
    heading.append(element('span', 'tool-tag', 'MCP 工具'));
    card.append(heading);
    if (tool.description) card.append(element('p', 'tool-description', tool.description));
    const details = element('details', 'schema-details');
    details.append(element('summary', '', '查看 inputSchema'));
    const schema = element('pre', 'schema-code');
    try {
      schema.textContent = JSON.stringify(tool.inputSchema || {}, null, 2);
    } catch (_error) {
      schema.textContent = '参数结构无法显示';
    }
    details.append(schema);
    card.append(details);
    return card;
  }

  function actionButton(label, style, action) {
    const button = element('button', style, label);
    button.type = 'button';
    button.addEventListener('click', action);
    return button;
  }

  function renderServer(server) {
    const card = element('article', 'server-card');
    const header = element('div', 'server-card-heading');
    const identity = element('div', 'server-identity');
    identity.append(element('h3', '', server.name));
    identity.append(element('p', 'server-url', server.base_url));
    header.append(identity);
    header.append(element('span', `connection-state ${server.connected ? 'is-connected' : 'is-disconnected'}`, server.connected ? '已连接' : '未连接'));
    card.append(header);

    const facts = element('dl', 'server-facts');
    facts.append(element('dt', '', '令牌配置'));
    facts.append(element('dd', '', server.token_configured ? `已配置 · ${server.token_env}` : `未配置 · ${server.token_env}`));
    facts.append(element('dt', '', '发现工具'));
    facts.append(element('dd', '', String((server.tools || []).length)));
    card.append(facts);

    if (server.last_error) card.append(element('p', 'server-error', server.last_error));
    const actions = element('div', 'server-actions');
    actions.append(actionButton('编辑', 'secondary-button', () => startEdit(server)));
    actions.append(actionButton(server.connected ? '断开' : '连接并发现', server.connected ? 'secondary-button' : 'primary-button', () => toggleConnection(server)));
    actions.append(actionButton('删除', 'danger-button', () => deleteServer(server)));
    card.append(actions);

    const tools = Array.isArray(server.tools) ? server.tools : [];
    const toolsHeading = element('div', 'tools-heading');
    toolsHeading.append(element('h4', '', '发现的工具'));
    toolsHeading.append(element('span', 'tool-count', `${tools.length} 项`));
    card.append(toolsHeading);
    if (!tools.length) {
      card.append(element('p', 'tools-empty', server.connected ? '服务未返回工具。' : '连接服务器后可读取工具清单。'));
    } else {
      const grid = element('div', 'tool-grid');
      tools.forEach((tool) => grid.append(renderTool(tool)));
      card.append(grid);
    }
    return card;
  }

  async function loadServers() {
    const data = await api('/api/mcp/servers');
    const servers = Array.isArray(data.servers) ? data.servers : [];
    list.replaceChildren(...servers.map(renderServer));
    setText('#server-count', `${servers.length} 台`);
    document.querySelector('#servers-empty').hidden = servers.length > 0;
  }

  function renderAuditRow(call) {
    const row = document.createElement('tr');
    [call.tool_ref, call.status, `#${call.user_id}`, call.conversation_id ? `#${call.conversation_id}` : '—', String(call.round), call.summary, call.created_at]
      .forEach((value, index) => {
        const cell = document.createElement('td');
        cell.textContent = value == null ? '' : String(value);
        if (index === 5) cell.className = 'audit-summary';
        row.append(cell);
      });
    return row;
  }

  async function loadAudit() {
    const data = await api('/api/mcp/tool-calls');
    const calls = Array.isArray(data.tool_calls) ? data.tool_calls : [];
    const rows = document.querySelector('#audit-rows');
    rows.replaceChildren(...calls.map(renderAuditRow));
    document.querySelector('#audit-empty').hidden = calls.length > 0;
  }

  async function refreshAll() {
    setText('#page-status', '正在刷新服务器和审计记录…');
    try {
      await Promise.all([loadServers(), loadAudit()]);
      setText('#page-status', '数据已更新');
    } catch (error) {
      setText('#page-status', error.message);
    }
  }

  async function refreshAudit() {
    setText('#audit-status', '正在读取调用记录…');
    try {
      await loadAudit();
      setText('#audit-status', '调用记录已更新');
    } catch (error) {
      setText('#audit-status', error.message);
    }
  }

  async function toggleConnection(server) {
    const operation = server.connected ? 'disconnect' : 'connect';
    setText('#page-status', `${server.connected ? '正在断开' : '正在连接并发现'} ${server.name}…`);
    try {
      await api(`/api/mcp/servers/${encodeURIComponent(server.id)}/${operation}`, { method: 'POST' });
      await Promise.all([loadServers(), loadAudit()]);
      setText('#page-status', server.connected ? '服务器已断开，工具缓存已清除' : '服务器已连接，发现清单已更新');
    } catch (error) {
      setText('#page-status', error.message);
      if (operation === 'connect') await loadServers().catch(() => {});
    }
  }

  async function deleteServer(server) {
    if (!window.confirm(`删除服务器“${server.name}”？已有审计记录会保留。`)) return;
    setText('#page-status', `正在删除 ${server.name}…`);
    try {
      await api(`/api/mcp/servers/${encodeURIComponent(server.id)}`, { method: 'DELETE' });
      if (editingId === server.id) resetForm();
      await Promise.all([loadServers(), loadAudit()]);
      setText('#page-status', '服务器已删除，调用审计保留');
    } catch (error) {
      setText('#page-status', error.message);
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const wasEditing = editingId !== null;
    const payload = {
      name: form.elements.name.value.trim(),
      base_url: form.elements.base_url.value.trim(),
      token_env: form.elements.token_env.value.trim(),
    };
    saveButton.disabled = true;
    setText('#page-status', wasEditing ? '正在保存服务器修改…' : '正在登记服务器…');
    try {
      const path = wasEditing ? `/api/mcp/servers/${encodeURIComponent(editingId)}` : '/api/mcp/servers';
      await api(path, jsonRequest(wasEditing ? 'PUT' : 'POST', payload));
      resetForm();
      await loadServers();
      setText('#page-status', wasEditing ? '服务器修改已保存' : '服务器已登记');
    } catch (error) {
      setText('#page-status', error.message);
    } finally {
      saveButton.disabled = false;
    }
  });

  cancelButton.addEventListener('click', resetForm);
  document.querySelector('#refresh-all').addEventListener('click', refreshAll);
  document.querySelector('#refresh-audit').addEventListener('click', refreshAudit);
  refreshAll();
})();
