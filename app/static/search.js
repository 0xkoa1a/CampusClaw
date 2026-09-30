const searchForm = document.querySelector('#search-form');
const statusNode = document.querySelector('#search-status');
const resultNode = document.querySelector('#search-results');
const answerNode = document.querySelector('#answer-result');

async function postJSON(path, payload) {
  const response = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (response.status === 401) {
    window.location.assign('/login');
    return null;
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败');
  return data;
}

function sourceLink(hit, label) {
  const link = document.createElement('a');
  link.href = hit.source_url;
  link.textContent = label;
  return link;
}

searchForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  statusNode.textContent = '正在检索…';
  resultNode.replaceChildren();
  answerNode.replaceChildren();
  try {
    const data = await postJSON('/api/search', {
      q: searchForm.q.value, mode: searchForm.mode.value,
    });
    if (!data) return;
    statusNode.textContent = data.hits.length ? `找到 ${data.total} 个相关片段` : '资料中未找到相关内容';
    for (const hit of data.hits) {
      const article = document.createElement('article');
      article.className = 'search-hit';
      const heading = document.createElement('h3');
      heading.append(sourceLink(hit, `${hit.title} · 切片 ${hit.chunk_index + 1}`));
      const excerpt = document.createElement('p');
      excerpt.textContent = hit.excerpt;
      article.append(heading, excerpt);
      resultNode.append(article);
    }
  } catch (error) {
    statusNode.textContent = error.message;
  }
});

document.querySelector('#ask-button')?.addEventListener('click', async () => {
  const q = searchForm.q.value.trim();
  if (!q) {
    statusNode.textContent = '请先输入问题';
    return;
  }
  statusNode.textContent = '正在查找依据并生成回答…';
  answerNode.replaceChildren();
  try {
    const data = await postJSON('/api/ask', { q, history: [] });
    if (!data) return;
    statusNode.textContent = '';
    const answer = document.createElement('p');
    answer.textContent = data.answer;
    answerNode.append(answer);
    for (const citation of data.citations) {
      answerNode.append(sourceLink(citation, `[${citation.number}] ${citation.title} · 切片 ${citation.chunk_index + 1}`));
    }
  } catch (error) {
    statusNode.textContent = error.message;
  }
});

const reindexForm = document.querySelector('#reindex-form');
reindexForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const result = document.querySelector('#reindex-status');
  const button = reindexForm.querySelector('button[type="submit"]');
  button.disabled = true;
  result.textContent = '正在重建索引…';
  try {
    const values = new FormData(reindexForm);
    const data = await postJSON(`/api/materials/${reindexForm.dataset.materialId}/reindex`, {
      strategy: {
        type: values.get('type'), max_chars: Number(values.get('max_chars')),
        overlap: Number(values.get('overlap')), delimiter: values.get('delimiter'),
      },
    });
    if (!data) return;
    result.textContent = `已重建 ${data.chunk_count} 个切片。刷新页面可查看最新状态。`;
  } catch (error) {
    result.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
