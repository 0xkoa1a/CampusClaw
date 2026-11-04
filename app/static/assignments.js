(() => {
  const root = document.querySelector('.assignments-workspace');
  if (!root) return;

  const teacher = root.dataset.role === 'teacher';
  const $ = (selector) => root.querySelector(selector);
  const state = { assignments: [], controllers: new Map(), memoryKeys: new Map(), leaving: false, redirecting: false };
  const terminal = new Set(['succeeded', 'failed', 'dead']);
  const labels = { pending: '等待处理', running: '正在批改', succeeded: '批改完成', failed: '批改失败', dead: '已停止重试' };

  function appendText(parent, tag, value, className) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = value == null ? '' : String(value);
    parent.append(node);
    return node;
  }

  function setStatus(node, message, error = false) {
    if (!node) return;
    node.textContent = message;
    node.classList.toggle('is-error', error);
  }

  function stopPolling() {
    state.leaving = true;
    state.controllers.forEach((controller) => controller.abort());
    state.controllers.clear();
  }

  window.addEventListener('pagehide', stopPolling, { once: true });
  document.querySelector('#logout-form')?.addEventListener('submit', stopPolling);

  function statusError(status, detail) {
    const labelsByCode = {
      400: '提交内容不正确', 403: '没有执行此操作的权限',
      404: '作业或任务不存在，或已不可访问', 409: '提交冲突，请刷新任务后重试',
      503: '服务暂时不可用，请稍后重试',
    };
    return `${labelsByCode[status] || `请求失败（${status}）`}${detail ? `：${detail}` : ''}`;
  }

  async function request(path, options = {}, signal) {
    const response = await window.campusAuth.fetch(path, { ...options, signal: signal || options.signal });
    if (response.status === 401) {
      if (!state.redirecting && !state.leaving) {
        state.redirecting = true;
        stopPolling();
        window.location.assign('/login');
      }
      throw new Error('登录状态已失效，正在返回登录页。');
    }
    if (!response.ok) {
      let detail = '';
      try { detail = (await response.json()).error || ''; } catch (_) { /* use status text */ }
      throw new Error(statusError(response.status, detail));
    }
    return response;
  }

  async function jsonRequest(path, options = {}, signal) {
    const response = await request(path, options, signal);
    return response.status === 204 ? {} : response.json();
  }

  function makeUuid() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  async function contentFingerprint(content) {
    const bytes = new TextEncoder().encode(content);
    if (window.crypto?.subtle) {
      const digest = await window.crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
    }
    let hash = 2166136261;
    bytes.forEach((byte) => { hash = Math.imul(hash ^ byte, 16777619); });
    return `fnv-${(hash >>> 0).toString(16)}`;
  }

  async function submissionKey(assignmentId, fingerprint) {
    const memoryId = `${assignmentId}:${fingerprint}`;
    if (state.memoryKeys.has(memoryId)) return state.memoryKeys.get(memoryId);
    const storageId = `campusclaw.assignmentSubmission.${assignmentId}.${fingerprint}`;
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageId) || 'null');
      if (saved?.fingerprint === fingerprint && saved.key) {
        state.memoryKeys.set(memoryId, saved.key);
        return saved.key;
      }
    } catch (_) { /* session storage may be unavailable */ }
    const key = makeUuid();
    state.memoryKeys.set(memoryId, key);
    try { sessionStorage.setItem(storageId, JSON.stringify({ fingerprint, key })); } catch (_) { /* keep the key in memory */ }
    return key;
  }

  function clearSubmissionKey(assignmentId, fingerprint, key) {
    const memoryId = `${assignmentId}:${fingerprint}`;
    if (state.memoryKeys.get(memoryId) === key) state.memoryKeys.delete(memoryId);
    const storageId = `campusclaw.assignmentSubmission.${assignmentId}.${fingerprint}`;
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageId) || 'null');
      if (saved?.fingerprint === fingerprint && saved.key === key) sessionStorage.removeItem(storageId);
    } catch (_) { /* ignore unavailable session storage */ }
  }

  function formatDate(value) {
    if (!value) return '—';
    const normalized = typeof value === 'string' && /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)
      ? `${value.replace(' ', 'T')}Z`
      : value;
    const parsed = new Date(normalized);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('zh-CN');
  }

  async function loadAssignments() {
    const data = await jsonRequest('/api/assignments');
    state.assignments = Array.isArray(data.assignments) ? data.assignments : [];
    if (teacher) renderTeacherAssignments();
    else renderStudentAssignments();
  }

  function renderTeacherAssignments() {
    const list = $('#assignment-list');
    list.replaceChildren();
    state.assignments.forEach((assignment) => {
      const card = document.createElement('article');
      card.className = 'assignment-card';
      appendText(card, 'h3', assignment.title || `作业 #${assignment.id}`);
      appendText(card, 'p', assignment.question, 'assignment-question');
      appendText(card, 'p', `满分 ${assignment.max_score ?? '—'} 分`, 'assignment-meta');
      list.append(card);
    });
    if (!state.assignments.length) appendText(list, 'p', '还没有作业。', 'empty-state');
  }

  function renderStudentAssignments() {
    const select = $('#submission-form select[name="assignment_id"]');
    const previous = select.value;
    select.replaceChildren();
    const placeholder = appendText(select, 'option', state.assignments.length ? '请选择作业' : '当前没有可提交的作业');
    placeholder.value = '';
    state.assignments.forEach((assignment) => {
      const option = appendText(select, 'option', assignment.title || `作业 #${assignment.id}`);
      option.value = assignment.id;
    });
    if (state.assignments.some((assignment) => String(assignment.id) === previous)) select.value = previous;
    select.disabled = !state.assignments.length;
    updateAssignmentPreview();
  }

  function updateAssignmentPreview() {
    const select = $('#submission-form select[name="assignment_id"]');
    const preview = $('#assignment-preview');
    const selected = state.assignments.find((assignment) => String(assignment.id) === select.value);
    preview.hidden = !selected;
    if (!selected) return;
    $('#assignment-preview-title').textContent = selected.title || `作业 #${selected.id}`;
    $('#assignment-preview-question').textContent = selected.question || '暂无题目说明。';
    $('#assignment-preview-score').textContent = `满分 ${selected.max_score ?? '—'} 分`;
  }

  async function loadSkills() {
    const select = $('#assignment-form select[name="skill_id"]');
    if (!select) return;
    const data = await jsonRequest('/api/skills');
    (data.skills || []).forEach((skill) => {
      const option = appendText(select, 'option', skill.name || `技能 #${skill.id}`);
      option.value = skill.id;
      if (!skill.enabled) option.disabled = true;
    });
  }

  function renderTask(task) {
    const card = document.createElement('article');
    card.className = `task-card task-${task.status || 'unknown'}`;
    const heading = document.createElement('div');
    heading.className = 'task-heading';
    appendText(heading, 'h3', task.assignment_title || `作业 #${task.assignment_id}`);
    appendText(heading, 'span', labels[task.status] || task.status || '状态未知', 'task-state');
    card.append(heading);
    appendText(card, 'p', `任务 #${task.id} · 提交 #${task.submission_id} · 尝试 ${task.attempts ?? 0} 次`, 'task-meta');
    if (task.content) appendText(card, 'p', task.content, 'task-content');
    if (task.error) appendText(card, 'p', task.error, 'task-error');
    if (task.started_at || task.finished_at) {
      appendText(card, 'p', `开始：${formatDate(task.started_at)}　结束：${formatDate(task.finished_at)}`, 'task-meta');
    }
    if (task.result && typeof task.result === 'object') {
      const result = document.createElement('section');
      result.className = 'grading-result';
      appendText(result, 'h4', `得分：${task.result.score}`);
      appendText(result, 'p', task.result.feedback, 'result-feedback');
      if (task.result.source) {
        const sourceLabels = { 'test-provider': '本地测试替身', 'real-gateway': '课程网关' };
        appendText(result, 'p', `批改来源：${sourceLabels[task.result.source] || task.result.source}`, 'task-meta');
      }
      card.append(result);
    }
    return card;
  }

  function startPolling(task) {
    if (state.leaving || terminal.has(task.status) || state.controllers.has(String(task.id))) return;
    const controller = new AbortController();
    const key = String(task.id);
    state.controllers.set(key, controller);
    const poll = async () => {
      while (!state.leaving && !controller.signal.aborted) {
        try {
          await new Promise((resolve, reject) => {
            const finish = () => {
              controller.signal.removeEventListener('abort', onAbort);
              resolve();
            };
            const onAbort = () => {
              window.clearTimeout(timer);
              controller.signal.removeEventListener('abort', onAbort);
              reject(new DOMException('Polling stopped', 'AbortError'));
            };
            const timer = window.setTimeout(finish, 2000);
            controller.signal.addEventListener('abort', onAbort, { once: true });
            if (controller.signal.aborted) onAbort();
          });
          const data = await jsonRequest(`/api/tasks/${encodeURIComponent(task.id)}`, {}, controller.signal);
          const updated = data.task;
          replaceTask(updated);
          if (!updated || terminal.has(updated.status)) break;
        } catch (error) {
          if (error.name === 'AbortError' || state.leaving) break;
          setStatus($('#page-status'), `任务 #${task.id} 查询失败：${error.message}`, true);
          break;
        }
      }
      state.controllers.delete(key);
    };
    poll();
  }

  function replaceTask(task) {
    if (!task) return;
    const list = $('#task-list');
    const old = list.querySelector(`[data-task-id="${CSS.escape(String(task.id))}"]`);
    const card = renderTask(task);
    card.dataset.taskId = task.id;
    if (old) old.replaceWith(card);
    else list.prepend(card);
    const count = list.querySelectorAll('.task-card').length;
    $('#task-count').textContent = `${count} 项`;
    $('#tasks-empty').hidden = count > 0;
    startPolling(task);
  }

  async function loadTasks() {
    const data = await jsonRequest('/api/tasks');
    const tasks = Array.isArray(data.tasks) ? data.tasks : [];
    const list = $('#task-list');
    list.replaceChildren();
    tasks.forEach((task) => {
      const card = renderTask(task);
      card.dataset.taskId = task.id;
      list.append(card);
    });
    $('#task-count').textContent = `${tasks.length} 项`;
    $('#tasks-empty').hidden = tasks.length > 0;
    if (!tasks.length) $('#tasks-empty').textContent = '暂无任务。提交作业后，任务会显示在这里。';
    tasks.forEach(startPolling);
  }

  async function refresh() {
    setStatus($('#page-status'), '正在刷新…');
    try {
      await Promise.all([loadAssignments(), loadTasks()]);
      setStatus($('#page-status'), '已刷新任务与作业列表。');
    } catch (error) {
      if (error.name !== 'AbortError') setStatus($('#page-status'), error.message, true);
    }
  }

  async function createAssignment(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    const maxScore = Number(form.elements.max_score.value);
    const payload = {
      title: form.elements.title.value.trim(),
      question: form.elements.question.value.trim(),
      reference_answer: form.elements.reference_answer.value.trim(),
      rubric: form.elements.rubric.value.trim(),
      max_score: maxScore,
      skill_id: form.elements.skill_id.value ? Number(form.elements.skill_id.value) : null,
    };
    try {
      await jsonRequest('/api/assignments', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      form.reset();
      form.elements.max_score.value = '100';
      await loadAssignments();
      setStatus($('#assignment-form-status'), '作业已创建。');
    } catch (error) {
      setStatus($('#assignment-form-status'), error.message, true);
    } finally { button.disabled = false; }
  }

  async function submitAssignment(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const assignmentId = form.elements.assignment_id.value;
    const content = form.elements.content.value.trim();
    if (!assignmentId || !content) return;
    button.disabled = true;
    setStatus($('#submission-form-status'), '正在提交…');
    try {
      const fingerprint = await contentFingerprint(content);
      const key = await submissionKey(assignmentId, fingerprint);
      const response = await request(`/api/assignments/${encodeURIComponent(assignmentId)}/submissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
        body: JSON.stringify({ content }),
      });
      if (response.status !== 202) throw new Error(statusError(response.status, '提交接口未返回受理状态'));
      const data = await response.json();
      if (!data || typeof data.task_id !== 'string') throw new Error('提交回执不完整，请重试以查询原任务。');
      clearSubmissionKey(assignmentId, fingerprint, key);
      if (form.elements.content.value.trim() === content) form.elements.content.value = '';
      setStatus($('#submission-form-status'), data.replayed
        ? `已恢复原任务 #${data.task_id}（${labels[data.status] || data.status}）。`
        : `提交已接收，任务 #${data.task_id} 当前状态：${labels[data.status] || data.status}。`);
      await loadTasks();
      const current = await jsonRequest(`/api/tasks/${encodeURIComponent(data.task_id)}`);
      replaceTask(current.task);
    } catch (error) {
      setStatus($('#submission-form-status'), error.message, true);
    } finally { button.disabled = false; }
  }

  async function init() {
    $('#refresh-tasks').addEventListener('click', refresh);
    $('#assignment-form')?.addEventListener('submit', createAssignment);
    $('#submission-form')?.addEventListener('submit', submitAssignment);
    $('#submission-form select[name="assignment_id"]')?.addEventListener('change', updateAssignmentPreview);
    try {
      const jobs = [loadAssignments(), loadTasks()];
      if (teacher) jobs.push(loadSkills());
      await Promise.all(jobs);
      setStatus($('#page-status'), '');
    } catch (error) {
      if (error.name !== 'AbortError') setStatus($('#auth-status'), error.message, true);
    }
  }

  init();
})();
