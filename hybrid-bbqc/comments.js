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
  const submitButton = form?.querySelector('button[type="submit"]');
  const cancelButton = document.createElement('button');
  cancelButton.type = 'button';
  cancelButton.className = 'comment-cancel';
  cancelButton.textContent = 'Cancel edit';
  cancelButton.hidden = true;
  form?.querySelector('.comments-actions')?.insertBefore(cancelButton, message);
  let editingId = null;
  const fmt = (ts) => new Date(ts * 1000).toLocaleString();
  const esc = (s) => String(s || '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function api(path, opts) {
    const res = await fetch(path, Object.assign({headers: {'Content-Type': 'application/json'}}, opts || {}));
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `${res.status} ${res.statusText}`);
    return res.json();
  }
  function resetEdit() {
    editingId = null;
    if (submitButton) submitButton.textContent = 'Save comment';
    cancelButton.hidden = true;
    message.textContent = '';
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
  function renderComment(r) {
    const edited = r.updated_at && r.updated_at !== r.created_at ? ` · edited ${fmt(r.updated_at)}` : '';
    const edit = r.can_edit ? `<button type="button" class="comment-edit" data-edit-id="${r.id}" data-edit-status="${esc(r.status)}" data-edit-body="${esc(r.body)}">Edit</button>` : '';
    return `<article class="comment-card"><div class="comment-head"><span><strong>${esc(r.status)}</strong> · ${esc(r.author_display)} · ${fmt(r.created_at)}${edited}</span>${edit}</div><p>${esc(r.body).replace(/\n/g,'<br>')}</p></article>`;
  }
  async function loadComments() {
    try {
      const rows = await api(`/api/comments?target=${encodeURIComponent(target)}`);
      list.innerHTML = rows.length ? rows.map(renderComment).join('') : '<p class="muted">No comments yet.</p>';
    } catch (e) {
      list.innerHTML = `<p class="muted">Could not load comments: ${esc(e.message)}</p>`;
    }
  }
  list?.addEventListener('click', (ev) => {
    const btn = ev.target.closest('[data-edit-id]');
    if (!btn) return;
    editingId = Number(btn.dataset.editId);
    status.value = btn.dataset.editStatus || 'review';
    body.value = btn.dataset.editBody || '';
    if (submitButton) submitButton.textContent = 'Update comment';
    cancelButton.hidden = false;
    message.textContent = `Editing comment #${editingId}`;
    body.focus();
  });
  cancelButton.addEventListener('click', () => {
    body.value = '';
    resetEdit();
  });
  form?.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    message.textContent = editingId ? 'Updating...' : 'Saving...';
    try {
      const payload = JSON.stringify({target, status: status.value, body: body.value});
      if (editingId) {
        await api(`/api/comments/${editingId}`, {method:'PATCH', body: payload});
      } else {
        await api('/api/comments', {method:'POST', body: payload});
      }
      body.value = '';
      message.textContent = editingId ? 'Updated.' : 'Saved.';
      resetEdit();
      await loadComments();
    } catch (e) {
      message.textContent = e.message;
    }
  });
  loadMe();
  loadComments();
})();
