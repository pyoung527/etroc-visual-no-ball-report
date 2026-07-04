(() => {
  const root = document.querySelector('[data-comments-target]');
  if (!root) return;
  const target = root.dataset.commentsTarget;
  const list = root.querySelector('[data-comments-list]');
  const form = root.querySelector('[data-comments-form]');
  const body = root.querySelector('[data-comments-body]');
  const status = root.querySelector('[data-comments-status]');
  const message = root.querySelector('[data-comments-message]');
  const meBox = root.querySelector('[data-comments-me]');
  const fmt = (ts) => new Date(ts * 1000).toLocaleString();
  const esc = (s) => String(s || '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function api(path, opts) {
    const res = await fetch(path, Object.assign({headers: {'Content-Type': 'application/json'}}, opts || {}));
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `${res.status} ${res.statusText}`);
    return res.json();
  }
  async function loadMe() {
    try {
      const me = await api('/api/me');
      if (me.authenticated) {
        meBox.textContent = `Signed in as ${me.user.display || me.user.user}`;
        form.hidden = false;
      } else {
        meBox.textContent = 'CERN SSO login required to add comments.';
        form.hidden = true;
      }
    } catch (e) {
      meBox.textContent = 'Comment API unavailable.';
      form.hidden = true;
    }
  }
  async function loadComments() {
    try {
      const rows = await api(`/api/comments?target=${encodeURIComponent(target)}`);
      list.innerHTML = rows.length ? rows.map((r) => `<article class="comment-card"><div><strong>${esc(r.status)}</strong> · ${esc(r.author_display)} · ${fmt(r.created_at)}</div><p>${esc(r.body).replace(/\n/g,'<br>')}</p></article>`).join('') : '<p class="muted">No comments yet.</p>';
    } catch (e) {
      list.innerHTML = `<p class="muted">Could not load comments: ${esc(e.message)}</p>`;
    }
  }
  form?.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    message.textContent = 'Saving...';
    try {
      await api('/api/comments', {method:'POST', body: JSON.stringify({target, status: status.value, body: body.value})});
      body.value = '';
      message.textContent = 'Saved.';
      await loadComments();
    } catch (e) {
      message.textContent = e.message;
    }
  });
  loadMe();
  loadComments();
})();
