(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const el = {
    thread: $('thread'), empty: $('emptyState'), form: $('composer'), question: $('question'), send: $('sendBtn'),
    users: $('userSelect'), steps: $('steps'), timing: $('timing'), timingList: $('timingList'),
    sumRoute: $('sumRoute'), sumRole: $('sumRole'), sumLatency: $('sumLatency'), sumTokens: $('sumTokens'),
    dialog: $('uploadDialog'), dept: $('departmentSelect'), access: $('accessSelect'), file: $('fileInput'),
    adminKey: $('adminKey'), uploadStatus: $('uploadStatus'), uploadBtn: $('uploadBtn'),
  };

  const ROUTES = {
    private_kb: { label: 'Company knowledge base', cls: 'status-kb' },
    web_search: { label: 'Public web', cls: 'status-web' },
    direct: { label: 'Conversation', cls: 'status-direct' },
    insufficient_evidence: { label: 'Not found · escalated', cls: 'status-stop' },
  };
  const NODES = {
    route_question: 'Route', retrieve_kb: 'Retrieve + rerank', grade_kb: 'Grade evidence', search_web: 'Web search',
    grade_web: 'Grade web', rewrite_query: 'Rewrite query', generate_from_kb: 'Write answer', generate_from_web: 'Write answer',
    direct_answer: 'Reply', insufficient: 'Escalate',
  };
  let exchangeCount = 0;
  let busy = false;

  // ------------------------------------------------------------ helpers

  const esc = (s = '') => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const roleLabel = (r = '') => r.replace('_', ' ');
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
  };

  // Inline formatting on already-escaped text: **bold**, `code`, and [n] evidence markers -> footnotes.
  function inline(text, refMap, id) {
    let html = esc(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\[(\d+)\]/g, (match, n) => {
      const k = refMap.get(Number(n));
      return k ? `<sup><a href="#src-${id}-${k}" data-src="src-${id}-${k}" aria-label="Source ${k}">${k}</a></sup>` : (refMap.size ? '' : match);
    });
    return html;
  }

  // Minimal, safe Markdown: paragraphs, bullet and numbered lists, small headings.
  function renderAnswer(text, refMap, id) {
    const out = [];
    let list = null;
    const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
    for (const raw of String(text || '').split(/\r?\n/)) {
      const line = raw.trim();
      if (!line) { close(); continue; }
      let m;
      if ((m = line.match(/^#{1,4}\s+(.*)$/))) { close(); out.push(`<h4>${inline(m[1], refMap, id)}</h4>`); }
      else if ((m = line.match(/^[-*•]\s+(.*)$/))) { if (list !== 'ul') { close(); out.push('<ul>'); list = 'ul'; } out.push(`<li>${inline(m[1], refMap, id)}</li>`); }
      else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) { if (list !== 'ol') { close(); out.push('<ol>'); list = 'ol'; } out.push(`<li>${inline(m[1], refMap, id)}</li>`); }
      else { close(); out.push(`<p>${inline(line, refMap, id)}</p>`); }
    }
    close();
    return out.join('');
  }

  function renderSources(citations, id) {
    if (!citations.length) return '';
    const items = citations.map((c, i) => {
      const k = i + 1;
      if (c.url) {
        let host = '';
        try { host = new URL(c.url).hostname.replace(/^www\./, ''); } catch { /* keep empty */ }
        return `<li id="src-${id}-${k}"><span><a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">${esc(c.title)}</a><br><span class="source-file">${esc(host)}</span></span></li>`;
      }
      const dept = c.department ? `<span class="tag tag-${esc(c.department)}">${esc(c.department)}</span> ` : '';
      const doc = c.document || c.title;
      const sections = (c.sections || []).length ? ` · ${esc(c.sections.join(', '))}` : '';
      return `<li id="src-${id}-${k}"><span>${dept}${esc(doc)}${sections}<br><span class="source-file">${esc(c.file || '')}</span></span></li>`;
    }).join('');
    return `<div class="sources"><h3>Sources</h3><ol>${items}</ol></div>`;
  }

  // ------------------------------------------------------------ conversation

  function addExchange(question, viewer) {
    if (el.empty) { el.empty.remove(); el.empty = null; }
    exchangeCount += 1;
    const node = document.createElement('article');
    node.className = 'exchange';
    node.innerHTML = `
      <p class="question"><span class="question-by">${esc(viewer)}</span>${esc(question)}</p>
      <div class="answer-slot"><div class="pending"><span class="pending-bar"></span>Routing, retrieving and checking sources…</div></div>`;
    el.thread.appendChild(node);
    node.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return { node, id: exchangeCount };
  }

  function fillExchange({ node, id }, data) {
    const route = ROUTES[data.source_used] || { label: data.source_used, cls: 'status-direct' };
    const citations = data.citations || [];
    const refMap = new Map();
    citations.forEach((c, i) => (c.refs || []).forEach((n) => refMap.set(n, i + 1)));
    const depts = (data.departments || []).map((d) => `<span class="tag tag-${esc(d)}">${esc(d)}</span>`).join(' ');
    const seconds = data.metrics ? `${(data.metrics.latency_ms / 1000).toFixed(1)} s` : '';
    node.querySelector('.answer-slot').innerHTML = `
      <div class="answer-meta"><span class="status ${route.cls}">${esc(route.label)}</span>${depts}<span>${seconds}</span></div>
      <div class="answer">${renderAnswer(data.answer, refMap, id)}</div>
      ${renderSources(citations, id)}`;
  }

  function failExchange({ node }, message) {
    node.querySelector('.answer-slot').innerHTML = `<p class="answer-error">${esc(message)}</p>`;
  }

  // ------------------------------------------------------------ trace panel

  function classifyStep(result) {
    if (/GOOD/.test(result)) return 'is-good';
    if (/WEAK|possible prompt injection/i.test(result)) return 'is-warn';
    if (/insufficient/i.test(result)) return 'is-stop';
    return '';
  }

  function renderTrace(data) {
    const route = ROUTES[data.source_used];
    el.sumRoute.textContent = route ? route.label : data.source_used;
    el.sumRole.textContent = data.user ? `${data.user.name.split(' ')[0]} · ${roleLabel(data.user.role)}` : '—';
    el.sumLatency.textContent = data.metrics ? `${(data.metrics.latency_ms / 1000).toFixed(2)} s` : '—';
    el.sumTokens.textContent = data.metrics ? data.metrics.total_tokens.toLocaleString() : '—';

    el.steps.innerHTML = (data.trace || []).map((t) => {
      const [name, ...rest] = t.split(' → ');
      const result = rest.join(' → ');
      return `<li class="${classifyStep(result)}"><span class="step-name">${esc(name)}</span><span class="step-result">${esc(result)}</span></li>`;
    }).join('') || '<li class="steps-empty">No steps recorded.</li>';

    const nodes = (data.metrics && data.metrics.nodes) || [];
    const max = Math.max(1, ...nodes.map((n) => n.ms));
    el.timingList.innerHTML = nodes.map((n) => `
      <li><span>${esc(NODES[n.node] || n.node)}</span><span class="bar"><span style="width:${Math.max(2, (n.ms / max) * 100)}%"></span></span><span class="ms">${n.ms} ms</span></li>`).join('');
    el.timing.hidden = !nodes.length;
  }

  function traceWorking() {
    el.sumRoute.textContent = 'Working…';
    el.sumLatency.textContent = '—';
    el.sumTokens.textContent = '—';
    el.steps.innerHTML = '<li class="steps-empty">Running the decision graph…</li>';
    el.timing.hidden = true;
  }

  // ------------------------------------------------------------ ask

  async function ask(question) {
    if (busy || !question.trim()) return;
    busy = true;
    el.send.disabled = true;
    const viewer = el.users.selectedOptions[0] ? el.users.selectedOptions[0].textContent : 'You';
    const ex = addExchange(question.trim(), viewer);
    traceWorking();
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-User': el.users.value || '' },
        body: JSON.stringify({ question: question.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`);
      fillExchange(ex, data);
      renderTrace(data);
    } catch (err) {
      failExchange(ex, err.message || 'Something went wrong.');
      el.sumRoute.textContent = 'Error';
      el.steps.innerHTML = '<li class="steps-empty">The request failed before a trace was returned.</li>';
    } finally {
      busy = false;
      el.send.disabled = false;
    }
  }

  const autosize = () => { el.question.style.height = 'auto'; el.question.style.height = `${el.question.scrollHeight}px`; };

  el.form.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = el.question.value;
    el.question.value = '';
    autosize();
    ask(q);
  });
  el.question.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); el.form.requestSubmit(); }
  });
  el.question.addEventListener('input', autosize);

  document.querySelectorAll('.starter, .inline-starter').forEach((b) => b.addEventListener('click', () => ask(b.textContent)));

  // Footnote click: highlight the referenced source briefly.
  el.thread.addEventListener('click', (e) => {
    const a = e.target.closest('a[data-src]');
    if (!a) return;
    const target = document.getElementById(a.dataset.src);
    if (!target) return;
    target.classList.add('is-target');
    setTimeout(() => target.classList.remove('is-target'), 1600);
  });

  // ------------------------------------------------------------ users

  fetch('/api/users').then((r) => r.json()).then((users) => {
    el.users.innerHTML = users.map((u) => `<option value="${esc(u.username)}">${esc(u.name)} (${esc(roleLabel(u.role))})</option>`).join('');
    const saved = store.get('viewer');
    if (saved && users.some((u) => u.username === saved)) el.users.value = saved;
  }).catch(() => { el.users.innerHTML = '<option value="">Default user</option>'; });
  el.users.addEventListener('change', () => store.set('viewer', el.users.value));

  // ------------------------------------------------------------ upload

  fetch('/api/departments').then((r) => r.json()).then((list) => {
    el.dept.innerHTML = list.map((d) => `<option value="${esc(d.key)}">${esc(d.label)}</option>`).join('');
  }).catch(() => { el.dept.innerHTML = '<option value="">Unavailable</option>'; });

  $('openUpload').addEventListener('click', () => { el.uploadStatus.textContent = ''; el.uploadStatus.className = 'upload-status'; el.dialog.showModal(); });
  $('closeUpload').addEventListener('click', () => el.dialog.close());

  el.uploadBtn.addEventListener('click', async () => {
    const file = el.file.files[0];
    const setStatus = (msg, cls = '') => { el.uploadStatus.textContent = msg; el.uploadStatus.className = `upload-status ${cls}`; };
    if (!file) { setStatus('Choose a file first.', 'is-error'); return; }
    const fd = new FormData();
    fd.append('file', file);
    fd.append('department', el.dept.value);
    fd.append('access', el.access.value);
    el.uploadBtn.disabled = true;
    setStatus('Scanning and indexing…');
    try {
      const res = await fetch('/api/ingest', { method: 'POST', headers: { 'X-Admin-Key': el.adminKey.value }, body: fd });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `Upload failed (${res.status})`);
      setStatus(`Indexed ${d.file}: ${d.chunks} chunks · ${d.department.toUpperCase()} · readable by ${d.access}`, 'is-ok');
      el.file.value = '';
    } catch (err) {
      setStatus(err.message, 'is-error');
    } finally {
      el.uploadBtn.disabled = false;
    }
  });
})();
