// utils/BookActions.js
/* Centralised reusable book actions for Spines UI  */
(() => {
  function toast(msg, type = 'info') {
    const fb = document.createElement('div');
    fb.className = `feedback ${type}`;
    fb.textContent = msg;
    document.body.appendChild(fb);
    setTimeout(() => fb.remove(), 4000);
  }

  async function extractText(bookId) {
    toast('🔍 extracting text...', 'info');
    try {
      const res = await fetch(`/api/books/${bookId}/extract-text`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      toast(`✅ text extracted (${data.word_count || '--'} words)`, 'success');
    } catch (e) {
      toast(`❌ ${e.message}`, 'error');
    }
  }

  async function deleteBook(bookId, title = '') {
    if (!confirm(`Delete "${title}" and all associated files?`)) return;
    toast('🗑️ deleting...', 'info');
    try {
      const res = await fetch(`/api/books/${bookId}`, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      toast('✅ book deleted', 'success');
      setTimeout(() => (window.location.href = '/'), 1500);
    } catch (e) {
      toast(`❌ ${e.message}`, 'error');
    }
  }

  function openFile(bookId) {
    window.open(`/api/books/${bookId}/file`, '_blank');
  }

  // Expose globally so templates can call directly
  window.openFile = openFile;
  window.extractText = extractText;
  window.deleteBook = deleteBook;
  // Also namespace for modules
  window.BookActions = { openFile, extractText, deleteBook };

  // Delegated click handler for buttons that declare a book action via data attributes
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.js-book-action');
    if (!btn) return;

    const { action } = btn.dataset;
    const bookId = btn.dataset.bookId;
    switch (action) {
      case 'open-file':
        openFile(bookId);
        break;
      case 'extract-text':
        extractText(bookId);
        break;
      case 'delete':
        deleteBook(bookId, btn.dataset.bookTitle || '');
        break;
      default:
        console.warn(`BookActions: unknown action "${action}"`);
    }
  });
})(); 