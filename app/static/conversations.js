(() => {
  const root = document.querySelector('.conversation-workspace');
  if (!root) return;
  const teacher = root.dataset.role === 'teacher';
  const $ = (selector) => document.querySelector(selector);
  const els = {
    authStatus: $('#auth-status'), listStatus: $('#conversation-list-status'),
    convList: $('#conversation-list'), newConv: $('#new-conversation-form'), newAgent: $('#new-agent'),
    title: $('#conversation-title'), lockedAgent: $('#locked-agent'), deleteConv: $('#delete-conversation'),
    chatStatus: $('#chat-status'), messages: $('#message-list'), messageForm: $('#message-form'),
    message: $('#message-content'), send: $('#message-form button[type="submit"]'),
  };
  const state = { agents: [], skills: [], materials: [], conversations: [], activeId: null, streaming: false };

  function escapeText(value) { return value == null ? '' : String(value); }
  function appendText(parent, tag, value, className) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = escapeText(value);
    parent.append(node);
    return node;
  }
  function jsonHeaders() { return { 'Content-Type': 'application/json' }; }
  async function request(path, options = {}) {
    const response = await window.campusAuth.fetch(path, options);
    if (response.status === 401) {
      window.location.assign('/login');
      throw new Error('登录状态已失效，正在返回登录页。');
    }
    if (!response.ok) {
      let detail = '';
      try { detail = (await response.json()).error || ''; } catch (_) { /* use status text */ }
      const labels = { 400: '请求内容不正确', 403: '没有执行此操作的权限', 404: '目标不存在或已不可访问', 409: '会话正在处理，请稍后再试', 503: '服务暂时不可用' };
      throw new Error(`${labels[response.status] || `请求失败（${response.status}）`}${detail ? `：${detail}` : ''}`);
    }
    return response;
  }
  async function jsonRequest(path, options = {}) {
    const response = await request(path, { ...options, headers: { ...jsonHeaders(), ...(options.headers || {}) } });
    if (response.status === 204) return {};
    return response.json();
  }
  function setStatus(node, message, isError = false) {
    node.textContent = message;
    node.classList.toggle('is-error', isError);
  }
  function agentById(id) { return state.agents.find((item) => String(item.id) === String(id)); }
  function renderAgents() {
    els.newAgent.replaceChildren();
    const enabled = state.agents.filter((agent) => agent.enabled);
    if (!enabled.length) appendText(els.newAgent, 'option', '暂无可用智能体').disabled = true;
    enabled.forEach((agent) => {
      const option = appendText(els.newAgent, 'option', agent.name);
      option.value = agent.id;
    });
    if (teacher) renderAgentConfig();
  }
  function renderSkills() {
    if (!teacher) return;
    const list = $('#skill-list');
    list.replaceChildren();
    state.skills.forEach((skill) => {
      const item = document.createElement('li');
      const button = appendText(item, 'button', `${skill.name}${skill.enabled ? '' : '（已停用）'}`);
      button.type = 'button';
      button.addEventListener('click', () => editSkill(skill));
      list.append(item);
    });
    renderAgentConfig();
  }
  function renderAgentConfig() {
    const skills = $('#agent-skills');
    const materials = $('#agent-materials');
    if (!skills || !materials) return;
    skills.replaceChildren(); materials.replaceChildren();
    state.skills.forEach((skill) => addCheckbox(skills, 'skill_ids', skill.id, `${skill.name}${skill.enabled ? '' : '（已停用）'}`));
    state.materials.forEach((material) => addCheckbox(materials, 'material_ids', material.id, material.title));
    const list = $('#agent-list');
    list.replaceChildren();
    state.agents.forEach((agent) => {
      const item = document.createElement('li');
      const button = appendText(item, 'button', `${agent.name}${agent.enabled ? '' : '（已停用）'}`);
      button.type = 'button';
      button.addEventListener('click', () => editAgent(agent));
      list.append(item);
    });
  }
  function addCheckbox(container, name, value, label) {
    const wrap = document.createElement('label'); wrap.className = 'choice-option';
    const input = document.createElement('input'); input.type = 'checkbox'; input.name = name; input.value = value;
    wrap.append(input, document.createTextNode(label)); container.append(wrap);
  }
  function renderConversations() {
    els.convList.replaceChildren();
    state.conversations.forEach((conversation) => {
      const item = document.createElement('li'); item.className = 'conversation-item';
      const button = document.createElement('button'); button.type = 'button'; button.className = 'conversation-open';
      button.setAttribute('aria-current', String(conversation.id) === String(state.activeId) ? 'true' : 'false');
      appendText(button, 'span', conversation.title || '新会话');
      appendText(button, 'small', formatDate(conversation.updated_at));
      button.addEventListener('click', () => loadConversation(conversation.id));
      item.append(button);
      const remove = appendText(item, 'button', '删除', 'mini-delete'); remove.type = 'button'; remove.setAttribute('aria-label', `删除会话：${conversation.title || '新会话'}`);
      remove.addEventListener('click', () => deleteConversation(conversation.id));
      els.convList.append(item);
    });
  }
  function formatDate(value) {
    if (!value) return '';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
  function citationLink(citation) {
    const source = citation.source_url;
    if (typeof source !== 'string' || !source.startsWith('/materials?')) return null;
    try {
      const url = new URL(source, window.location.origin);
      return url.origin === window.location.origin && url.pathname === '/materials' ? `${url.pathname}${url.search}${url.hash}` : null;
    } catch (_) { return null; }
  }
  function renderMessage(message) {
    const article = document.createElement('article'); article.className = `message ${message.role === 'user' ? 'user' : 'assistant'}`;
    appendText(article, 'div', message.role === 'user' ? '你' : '助手', 'message-role');
    appendText(article, 'p', message.content, 'message-content');
    if (message.role !== 'user') {
      const meta = [message.skill_name, message.status === 'partial' ? '回答未完整生成' : ''].filter(Boolean).join(' · ');
      if (meta) appendText(article, 'div', meta, 'message-meta');
      if (Array.isArray(message.citations) && message.citations.length) {
        const list = document.createElement('ol'); list.className = 'citations';
        message.citations.forEach((citation) => {
          const item = document.createElement('li');
          const href = citationLink(citation);
          if (href) { const link = appendText(item, 'a', citation.title || '查看资料'); link.href = href; }
          else appendText(item, 'span', citation.title || '资料引用');
          if (citation.chunk_index != null) appendText(item, 'span', ` · 切片 ${citation.chunk_index + 1}`);
          list.append(item);
        });
        article.append(list);
      }
    }
    els.messages.append(article);
    els.messages.scrollTop = els.messages.scrollHeight;
    return article;
  }
  function setActive(conversation) {
    state.activeId = conversation ? conversation.id : null;
    window.history.replaceState(null, '', conversation ? `/conversations?id=${encodeURIComponent(conversation.id)}` : '/conversations');
    els.title.textContent = conversation ? (conversation.title || '新会话') : '选择或新建一个会话';
    const agent = conversation && agentById(conversation.agent_id);
    els.lockedAgent.textContent = conversation ? `固定智能体：${agent ? agent.name : `#${conversation.agent_id}`} · 会话创建后不能更换` : '会话创建后会固定使用所选智能体。';
    els.deleteConv.disabled = !conversation || state.streaming;
    els.message.disabled = !conversation || state.streaming;
    els.send.disabled = !conversation || state.streaming;
    renderConversations();
  }
  async function reloadConversations(selectId = state.activeId) {
    const data = await jsonRequest('/api/conversations');
    state.conversations = data.conversations || [];
    if (selectId == null && state.conversations.length) selectId = state.conversations[0].id;
    renderConversations();
    if (selectId != null && state.conversations.some((item) => String(item.id) === String(selectId))) await loadConversation(selectId);
  }
  async function loadConversation(id) {
    if (state.streaming) return;
    setStatus(els.chatStatus, '正在加载会话…');
    try {
      const data = await jsonRequest(`/api/conversations/${encodeURIComponent(id)}`);
      setActive(data.conversation);
      els.messages.replaceChildren();
      (data.messages || []).forEach(renderMessage);
      setStatus(els.chatStatus, '');
    } catch (error) { setStatus(els.chatStatus, error.message, true); }
  }
  async function deleteConversation(id) {
    if (state.streaming) return;
    try {
      await jsonRequest(`/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' });
      if (String(state.activeId) === String(id)) { setActive(null); els.messages.replaceChildren(); }
      const requestedId = new URLSearchParams(window.location.search).get('id');
      await reloadConversations(requestedId && /^\d+$/.test(requestedId) ? Number(requestedId) : null);
      setStatus(els.chatStatus, '会话已删除。');
    } catch (error) { setStatus(els.chatStatus, error.message, true); }
  }
  async function createConversation(event) {
    event.preventDefault();
    const agentId = els.newAgent.value;
    if (!agentId) return;
    const button = els.newConv.querySelector('button[type="submit"]'); button.disabled = true;
    try {
      const data = await jsonRequest('/api/conversations', { method: 'POST', body: JSON.stringify({ agent_id: Number(agentId) }) });
      await reloadConversations(data.conversation.id);
      setStatus(els.chatStatus, '会话已创建。');
    } catch (error) { setStatus(els.chatStatus, error.message, true); }
    finally { button.disabled = false; }
  }
  function processSSEBlock(block, onEvent) {
    let event = 'message'; const data = [];
    block.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').forEach((line) => {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
    });
    if (data.length) {
      try { onEvent(event, JSON.parse(data.join('\n'))); }
      catch (_) { onEvent('parse_error', {}); }
    }
  }
  async function sendMessage(event) {
    event.preventDefault();
    const content = els.message.value.trim();
    if (!state.activeId || !content || state.streaming) return;
    state.streaming = true; setActive(state.conversations.find((item) => String(item.id) === String(state.activeId)) || { id: state.activeId, title: els.title.textContent });
    els.message.value = ''; setStatus(els.chatStatus, '正在连接解题助手…');
    renderMessage({ role: 'user', content });
    const assistant = renderMessage({ role: 'assistant', content: '正在生成…' });
    const contentNode = assistant.querySelector('.message-content'); contentNode.textContent = '';
    let meta = null; let finalError = null; let gotDone = false;
    try {
      const response = await request(`/api/conversations/${encodeURIComponent(state.activeId)}/messages`, { method: 'POST', headers: jsonHeaders(), body: JSON.stringify({ content }) });
      if (!response.body) throw new Error('浏览器无法读取流式响应。');
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      const onEvent = (name, data) => {
        if (name === 'meta') {
          meta = data;
          setStatus(els.chatStatus, data.status === 'grounded' ? '已找到相关资料，正在生成回答。' : '暂未找到相关资料，正在生成回答。');
        } else if (name === 'delta') {
          contentNode.textContent += escapeText(data.text);
          els.messages.scrollTop = els.messages.scrollHeight;
        } else if (name === 'done') {
          gotDone = true;
        } else if (name === 'error') {
          finalError = new Error(data.error || '生成过程中发生错误。');
        } else if (name === 'parse_error') finalError = new Error('收到无法解析的流式数据。');
      };
      while (true) {
        const chunk = await reader.read();
        buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
        const separator = /(?:\r\n\r\n|\n\n|\r\r)/;
        let boundary;
        while ((boundary = separator.exec(buffer)) !== null) {
          processSSEBlock(buffer.slice(0, boundary.index), onEvent);
          buffer = buffer.slice(boundary.index + boundary[0].length);
          if (finalError) break;
        }
        if (finalError || chunk.done) break;
      }
      if (buffer.trim() && !finalError) processSSEBlock(buffer, onEvent);
      if (finalError) await reader.cancel();
      if (finalError) throw finalError;
      if (!gotDone) throw new Error('连接提前结束，已生成内容可能已保存为未完成回答。');
      if (meta) {
        if (meta.skill_name) appendText(assistant, 'div', meta.skill_name, 'message-meta');
        if (Array.isArray(meta.citations) && meta.citations.length) {
          const list = document.createElement('ol'); list.className = 'citations';
          meta.citations.forEach((citation) => {
            const li = document.createElement('li'); const href = citationLink(citation);
            if (href) { const link = appendText(li, 'a', citation.title || `引用 ${citation.number}`); link.href = href; }
            else appendText(li, 'span', citation.title || `引用 ${citation.number}`);
            if (citation.chunk_index != null) appendText(li, 'span', ` · 切片 ${citation.chunk_index + 1}`);
            list.append(li);
          });
          assistant.append(list);
        }
      }
      setStatus(els.chatStatus, '回答已保存。');
    } catch (error) {
      if (!contentNode.textContent) contentNode.textContent = '本轮未能完成。';
      appendText(assistant, 'div', `${error.message} 可检查历史记录中的已保存内容；请确认后再决定是否重试。`, 'message-meta');
      setStatus(els.chatStatus, error.message, true);
    } finally {
      state.streaming = false;
      setActive(state.conversations.find((item) => String(item.id) === String(state.activeId)) || { id: state.activeId, title: els.title.textContent });
      const previousStatus = els.chatStatus.textContent;
      const previousError = els.chatStatus.classList.contains('is-error');
      try { await reloadConversations(state.activeId); } catch (_) { /* keep the generated turn visible */ }
      setStatus(els.chatStatus, previousStatus, previousError);
    }
  }

  function editSkill(skill) {
    const form = $('#skill-form'); form.elements.id.value = skill.id; form.elements.name.value = skill.name || '';
    form.elements.source.value = skill.source_text || ''; form.elements.enabled.checked = Boolean(skill.enabled);
    $('#skill-delete').disabled = false; setStatus($('#skill-status'), `正在编辑：${skill.name}`);
  }
  function resetSkill() {
    $('#skill-form').reset(); $('#skill-form').elements.id.value = ''; $('#skill-form').elements.enabled.checked = true;
    $('#skill-delete').disabled = true; setStatus($('#skill-status'), '');
  }
  async function saveSkill(event) {
    event.preventDefault(); const form = event.currentTarget;
    let source = form.elements.source.value;
    const name = form.elements.name.value.trim();
    if (!name) return;
    // Skill writes accept only the source document; synchronize form fields in its Chinese header.
    source = setSourceField(source, '名称', name);
    source = setSourceField(source, '启用', form.elements.enabled.checked ? '是' : '否');
    const id = form.elements.id.value;
    try {
      const data = await jsonRequest(id ? `/api/skills/${encodeURIComponent(id)}` : '/api/skills', { method: id ? 'PUT' : 'POST', body: JSON.stringify({ source }) });
      await loadConfig(); resetSkill(); setStatus($('#skill-status'), `技能“${data.skill?.name || name}”已保存。`);
    } catch (error) { setStatus($('#skill-status'), error.message, true); }
  }
  function setSourceField(source, field, value) {
    const lines = source.split(/\r?\n/);
    const pattern = new RegExp(`^\\s*${field}\\s*[：:]`);
    const index = lines.findIndex((line) => pattern.test(line));
    if (index >= 0) lines[index] = `${field}：${value}`;
    else lines.unshift(`${field}：${value}`);
    return lines.join('\n');
  }
  async function deleteSkill() {
    const id = $('#skill-form').elements.id.value; if (!id) return;
    try { await jsonRequest(`/api/skills/${encodeURIComponent(id)}`, { method: 'DELETE' }); await loadConfig(); resetSkill(); setStatus($('#skill-status'), '技能已删除。'); }
    catch (error) { setStatus($('#skill-status'), error.message, true); }
  }
  function editAgent(agent) {
    const form = $('#agent-form'); form.elements.id.value = agent.id; form.elements.name.value = agent.name || '';
    form.elements.role_prompt.value = agent.role_prompt || ''; form.elements.enabled.checked = Boolean(agent.enabled);
    form.querySelectorAll('[name=skill_ids]').forEach((input) => { input.checked = (agent.skill_ids || []).map(String).includes(input.value); });
    form.querySelectorAll('[name=material_ids]').forEach((input) => { input.checked = (agent.material_ids || []).map(String).includes(input.value); });
    setStatus($('#agent-status'), `正在编辑：${agent.name}`);
  }
  function resetAgent() {
    const form = $('#agent-form'); form.reset(); form.elements.id.value = ''; form.elements.enabled.checked = true;
    setStatus($('#agent-status'), '');
  }
  async function saveAgent(event) {
    event.preventDefault(); const form = event.currentTarget; const id = form.elements.id.value;
    const payload = {
      name: form.elements.name.value.trim(), role_prompt: form.elements.role_prompt.value,
      enabled: form.elements.enabled.checked,
      skill_ids: Array.from(form.querySelectorAll('[name=skill_ids]:checked'), (input) => Number(input.value)),
      material_ids: Array.from(form.querySelectorAll('[name=material_ids]:checked'), (input) => Number(input.value)),
    };
    try {
      const data = await jsonRequest(id ? `/api/agents/${encodeURIComponent(id)}` : '/api/agents', { method: id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      await loadConfig(); resetAgent(); setStatus($('#agent-status'), `智能体“${data.agent?.name || payload.name}”已保存。`);
    } catch (error) { setStatus($('#agent-status'), error.message, true); }
  }
  async function importSkillFile(event) {
    const file = event.currentTarget.files[0]; if (!file) return;
    try {
      const source = await file.text(); $('#skill-source').value = source;
      const nameField = source.match(/^\s*名称\s*[：:]\s*(.+?)\s*$/m);
      $('#skill-name').value = nameField ? nameField[1] : file.name.replace(/\.(txt|md)$/i, '').slice(0, 32);
      const enabledField = source.match(/^\s*启用\s*[：:]\s*(.+?)\s*$/m);
      if (enabledField) $('#skill-form').elements.enabled.checked = !/^(否|false|no|0)$/i.test(enabledField[1]);
      setStatus($('#skill-status'), `已导入 ${file.name}，检查后保存即可。`);
    } catch (_) { setStatus($('#skill-status'), '无法读取所选文件。', true); }
  }
  async function loadConfig() {
    const [agentsData, skillsData, materialsData] = await Promise.all([
      jsonRequest('/api/agents'), jsonRequest('/api/skills'), jsonRequest('/api/materials'),
    ]);
    state.agents = agentsData.agents || []; state.skills = skillsData.skills || []; state.materials = materialsData.materials || [];
    renderAgents(); renderSkills();
  }
  function bindTeacherForms() {
    $('#skill-form').addEventListener('submit', saveSkill); $('#skill-reset').addEventListener('click', resetSkill); $('#skill-delete').addEventListener('click', deleteSkill);
    $('#skill-file').addEventListener('change', importSkillFile);
    $('#agent-form').addEventListener('submit', saveAgent); $('#agent-reset').addEventListener('click', resetAgent);
  }
  async function init() {
    try {
      if (teacher) bindTeacherForms();
      els.newConv.addEventListener('submit', createConversation);
      els.messageForm.addEventListener('submit', sendMessage);
      els.deleteConv.addEventListener('click', () => state.activeId != null && deleteConversation(state.activeId));
      if (teacher) await loadConfig();
      else {
        const [agentsData, materialsData] = await Promise.all([jsonRequest('/api/agents'), jsonRequest('/api/materials')]);
        state.agents = agentsData.agents || []; state.materials = materialsData.materials || []; renderAgents();
      }
      const requestedId = new URLSearchParams(window.location.search).get('id');
      await reloadConversations(requestedId && /^\d+$/.test(requestedId) ? Number(requestedId) : null);
      if (!els.newAgent.value) setStatus(els.listStatus, '目前没有启用的智能体。');
    } catch (error) { setStatus(els.authStatus, error.message, true); }
  }
  init();
})();
