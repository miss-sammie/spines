class BookCard {
    constructor(book, options = {}) {
        this.book = book || {};
        this.options = {
            element: null,            // DOM element representing this card (optional – can be attached later)
            booksApiUrl: '/api/books',
            enableEditing: true,      // inline editable fields (title, author, …). Ignored for variant 'full'
            variant: 'spine',         // 'icon' | 'spine' | 'full'
            actions: [                // actions rendered in functions section for 'full' variant
                { key: 'open-file', label: '📖 open file' },
                { key: 'extract-text',
                  label: (b)=> b.text_extracted ? '🔄 re-extract text' : '🔍 extract text' },
                { key: 'replace-file', label: '📂 replace file' },
                { key: 'delete', label: '🗑️ delete book', classes:'delete' }
            ],
            ...options
        };
        // Normalize variant string
        this.options.variant = this.options.variant || 'spine';

        // If we were passed a DOM element, keep a reference and wire events immediately
        if (this.options.element) {
            this.element = this.options.element;
            if (this.options.enableEditing && this.options.variant !== 'full') {
                this.attachEditingListeners();
            }
        }
    }

    /* Utility: escape potentially unsafe HTML */
    escapeHtml(text = '') {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /* Helper to create editable field markup – mirrors BookGrid implementation */
    createEditableField(field, value, isEditing = false, className = '') {
        if (isEditing) {
            return `<input type="text" class="editable-input ${className}" data-field="${field}" value="${this.escapeHtml(value)}" tabindex="0">`;
        }
        return `<div class="${className} editable-field" data-field="${field}" tabindex="0">${this.escapeHtml(value)}</div>`;
    }

    /* Render the complete HTML for the book card */
    render() {
        const v = this.options.variant;
        if (v === 'full') {
            return this.renderFull();
        }
        if (v === 'review') {
            return this.renderReview();
        }
        // default 'spine' / 'icon' (icon currently same as spine minus meta)
        return this.renderSpine();

    }3

    renderSpine() {
        const b = this.book;
        return `
            <div class="book-card" data-book-id="${b.id}">
                <div class="book-spine">
                    ${this.createEditableField('title', b.title || 'Unknown Title', false, 'book-title')}
                    ${this.createEditableField('author', b.author || 'Unknown Author', false, 'book-author')}
                    ${this.createEditableField('year', b.year || 'click to add', false, 'book-year')}
                    ${b.isbn ? this.createEditableField('isbn', b.isbn, false, 'book-isbn') : ''}
                </div>
                <div class="book-meta">
                    ${b.contributor ? `<div class="contributor">contributed by: ${Array.isArray(b.contributor) ? b.contributor.join(', ') : b.contributor}</div>` : ''}
                    ${b.readers && b.readers.length > 0 ? `<div class="read-status">read by: ${b.readers.join(', ')}</div>` : ''}
                    ${b.tags && b.tags.length > 0 ? `<div class="tags">tags: ${b.tags.join(', ')}</div>` : ''}
                    ${b.related_copies && b.related_copies.length > 0 ? `<div class="related-copies">${b.related_copies.length} related cop${b.related_copies.length === 1 ? 'y' : 'ies'}</div>` : ''}
                </div>
            </div>`;
    }

    /* renderFull – rich detail variant */
    renderFull() {
        const b = this.book;
        const formatArr = (arr)=> Array.isArray(arr)? arr.join(', '): (arr||'');
        const metaRow = (label, field, value, type='text', editable=true)=>{
            if(value===undefined||value===null||value==='') value = editable? 'click to add' : 'unknown';
            const valHtml = editable
                ? `<div class="metadata-value" data-field="${field}" data-type="${type}">${this.escapeHtml(value.toString())}</div>`
                : `<div class="readonly">${this.escapeHtml(value.toString())}</div>`;
            return `
                <div class="metadata-label">${label}:</div>
                ${valHtml}`;
        };

        // compute dynamic action buttons markup
        const actionBtns = this.options.actions.map(a=>{
            const label = typeof a.label === 'function' ? a.label(b) : a.label;
            const extraCls = a.classes||'';
            return `<button class="function-button ${extraCls} js-book-action" data-action="${a.key}" data-book-id="${b.id}" data-book-title="${this.escapeHtml(b.title||'')}">${label}</button>`;
        }).join('');

        // collapse toggle inline handler for simplicity
        const collapseToggle = `onclick="const d=this.closest('.book-detail');const c=d.classList.toggle('collapsed');this.textContent=c?'+':'–';"`;

        return `
        <div class="book-detail book-card" data-book-id="${b.id}">
            <div class="collapse-toggle" ${collapseToggle}>–</div>
            <h2>${this.escapeHtml(b.title||'Untitled')}</h2>

            <div class="metadata-content">
                <div class="metadata-grid">
                    ${metaRow('author','author',b.author)}
                    ${metaRow('year','year',b.year,'number')}
                    ${b.isbn? metaRow('isbn','isbn',b.isbn):''}
                    ${metaRow('publisher','publisher',b.publisher)}
                    ${metaRow('media type','media_type',b.media_type,'select')}
                    ${metaRow('contributors','contributor',formatArr(b.contributor),'array')}
                    ${metaRow('read by','read_by',formatArr(b.readers||b.read_by),'array')}
                    ${metaRow('tags','tags',formatArr(b.tags),'array')}
                    ${metaRow('notes','notes',b.notes,'textarea')}
                    ${b.pages? metaRow('pages','',b.pages,'text',false):''}
                    ${b.file_size? metaRow('file size','',`${(b.file_size/1024/1024).toFixed(1)} MB`,'text',false):''}
                    ${b.file_type? metaRow('file type','',b.file_type,'text',false):''}
                    ${b.related_copies? metaRow('related copies','',`${b.related_copies.length} related cop${b.related_copies.length===1?'y':'ies'}`,'text',false):''}
                    ${metaRow('added','', b.date_added? b.date_added.slice(0,10):'unknown','text',false)}
                    ${b.migrated_from_v1? metaRow('migrated','',`from spines v1.0 on ${b.migration_date?b.migration_date.slice(0,10):'unknown'}`,'text',false):''}
                </div>
            </div>

            <div class="functions-section">
                <h3 class="section-title">functions</h3>
                <div class="function-buttons">
                    ${actionBtns}
                </div>
            </div>
        </div>`;
    }

    /* renderReview – variant for review queue proto-books */
    renderReview() {
        const item = this.book; // contains queue item fields
        const m = item.extracted_metadata || {};
        const arrToStr = (arr)=> Array.isArray(arr)? arr.join(', '): (arr||'');

        return `
        <div class="review-item" id="item-${item.id}">
            <div class="review-header">
                <div>
                    <div class="review-title">${this.escapeHtml(item.filename)}</div>
                    <div class="review-meta">confidence: ${(item.extraction_confidence*100).toFixed(0)}% • method: ${this.escapeHtml(item.extraction_method)} • isbn: ${item.isbn_found?'✅':'❌'} • reason: ${this.escapeHtml(item.reason||'')}
                    </div>
                </div>
                <div class="review-actions"><button class="btn" onclick="previewPdf('${item.id}')">📄 preview</button></div>
            </div>
            <iframe class="pdf-preview" id="preview-${item.id}" style="display:none;"></iframe>
            <div class="metadata-editor" id="editor-${item.id}">
                <div class="metadata-label">media type:</div>
                <select class="metadata-input" data-field="media_type" onchange="updateReviewFields('${item.id}')">
                    <option value="book" ${(m.media_type||'book')==='book'?'selected':''}>book</option>
                    <option value="article" ${(m.media_type)==='article'?'selected':''}>article</option>
                    <option value="web" ${(m.media_type||'')==='web'?'selected':''}>web</option>
                    <option value="unknown" ${(m.media_type||'')==='unknown'?'selected':''}>unknown</option>
                </select>
                <div class="metadata-label">title:</div><input type="text" class="metadata-input" data-field="title" value="${this.escapeHtml(m.title||'')}" />
                <div class="metadata-label">author:</div><input type="text" class="metadata-input" data-field="author" value="${this.escapeHtml(m.author||'')}" />
                <div class="metadata-label">year:</div><input type="number" class="metadata-input" data-field="year" value="${this.escapeHtml(m.year||'')}" />
                <div class="metadata-label">publisher:</div><input type="text" class="metadata-input" data-field="publisher" value="${this.escapeHtml(m.publisher||'')}" />
                <div class="metadata-label">read by:</div><input type="text" class="metadata-input" data-field="read_by" value="${this.escapeHtml(arrToStr(m.read_by))}" placeholder="comma-separated" />
                <div class="metadata-label">tags:</div><input type="text" class="metadata-input" data-field="tags" value="${this.escapeHtml(arrToStr(m.tags))}" placeholder="comma-separated" />
                <div class="metadata-label">notes:</div><textarea rows="2" class="metadata-input" data-field="notes">${this.escapeHtml(m.notes||'')}</textarea>
                <div class="metadata-label isbn-field">isbn:</div>
                <div class="isbn-field" style="display:flex;gap:5px;align-items:center;">
                    <input type="text" class="metadata-input" data-field="isbn" value="${this.escapeHtml(m.isbn||'')}" onkeypress="if(event.key==='Enter') recheckIsbn('${item.id}')" />
                    <button class="btn" onclick="recheckIsbn('${item.id}')" title="Recheck ISBN">🔍</button>
                </div>
                <div class="metadata-label url-field" style="display:none;">url:</div>
                <input type="url" class="metadata-input url-field" data-field="url" value="${this.escapeHtml(m.url||'')}" style="display:none;" />
            </div>
            <div class="process-controls">
                <div><label>contributor:</label><input type="text" class="contributor-input" value="anonymous" /></div>
                <div class="action-buttons"><button class="reject-btn" onclick="rejectItem('${item.id}')">🗑️ reject</button><button class="process-btn" onclick="approveItem('${item.id}')">✅ approve & process</button></div>
            </div>
        </div>`;
    }

    /* Convenience static generator */
    static generate(book, options = {}) {
        return new BookCard(book, options).render();
    }

    /* ------------  EDITING LOGIC (ported from BookGrid) ------------- */

    attachEditingListeners() {
        if (!this.element) return;

        // Handle clicks on editable fields to start editing
        const editableFields = this.element.querySelectorAll('.editable-field');
        editableFields.forEach(field => {
            field.addEventListener('click', (e) => {
                e.stopPropagation();
                this.startFieldEdit(field);
            });

            // Visual cue
            field.style.cursor = 'text';
        });

        // Handle keyboard events on any pre-existing inputs (e.g., when re-attaching)
        const editableInputs = this.element.querySelectorAll('.editable-input');
        editableInputs.forEach(input => this.attachInputListeners(input));

        // Ensure entire card shows pointer for navigation (unless over text fields)
        this.element.style.cursor = 'pointer';
    }

    startFieldEdit(fieldElement) {
        if (!this.element) return;

        // Save any other editing field within this card first
        const currentlyEditing = this.element.querySelector('.editable-input');
        if (currentlyEditing && currentlyEditing !== fieldElement) {
            this.saveFieldEdit(currentlyEditing);
        }

        // Replace the field with an input
        const currentValue = fieldElement.textContent;
        const fieldName = fieldElement.dataset.field;
        const className = fieldElement.className.replace('editable-field', '').trim();

        const input = document.createElement('input');
        input.type = 'text';
        input.className = `editable-input ${className}`;
        input.dataset.field = fieldName;
        input.dataset.originalValue = currentValue;
        input.value = currentValue;
        input.tabIndex = 0;

        // Replace the field with the input
        fieldElement.parentNode.replaceChild(input, fieldElement);

        // Focus/select
        input.focus();
        input.select();

        // Wire listeners
        this.attachInputListeners(input);
    }

    attachInputListeners(input) {
        // Save on Enter, blur, Tab; cancel on Esc
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.saveFieldEdit(input);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.cancelFieldEdit(input);
            } else if (e.key === 'Tab') {
                this.saveFieldEdit(input); // commit then let tab move on
            }
        });

        input.addEventListener('blur', () => {
            // small delay so Tab navigation still works
            setTimeout(() => {
                if (document.activeElement !== input) {
                    this.saveFieldEdit(input);
                }
            }, 50);
        });
    }

    async saveFieldEdit(input) {
        if (!input.parentNode) return; // Already handled, do nothing.

        const fieldName = input.dataset.field;
        const newValueRaw = input.value.trim();
        const originalValue = input.dataset.originalValue;

        // No change? cancel
        if (newValueRaw === originalValue) {
            this.cancelFieldEdit(input);
            return;
        }

        // Prepare update payload
        let value = newValueRaw || null;
        if (fieldName === 'year' && value) {
            value = parseInt(value) || null;
        }

        const updates = { [fieldName]: value };

        try {
            // Persist to server
            const resp = await fetch(`${this.options.booksApiUrl}/${this.book.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });

            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            // Update local copy
            Object.assign(this.book, updates);

            // Swap back to display element
            this.replaceInputWithField(input, newValueRaw || 'click to add');

            this.showSuccess('Book updated');
        } catch (err) {
            console.error('BookCard save error', err);
            this.showError('Failed to update');
            // Revert UI
            this.replaceInputWithField(input, originalValue);
        }
    }

    cancelFieldEdit(input) {
        if (!input.parentNode) return; // Already handled, do nothing.
        const originalValue = input.dataset.originalValue;
        this.replaceInputWithField(input, originalValue);
    }

    replaceInputWithField(input, value) {
        const fieldName = input.dataset.field;
        const className = input.className.replace('editable-input', '').trim();

        const field = document.createElement('div');
        field.className = `${className} editable-field`;
        field.dataset.field = fieldName;
        field.tabIndex = 0;
        field.textContent = value;
        field.style.cursor = 'text';

        input.parentNode.replaceChild(field, input);

        // Re-attach click to enable further editing
        field.addEventListener('click', (e) => {
            e.stopPropagation();
            this.startFieldEdit(field);
        });
    }

    /* ---------- feedback helpers (copied) ------------- */

    showSuccess(msg) { this.showFeedback(msg, 'success'); }
    showError(msg)   { this.showFeedback(msg, 'error');   }

    showFeedback(message, type = 'info') {
        const fb = document.createElement('div');
        fb.className = `feedback ${type}`;
        fb.textContent = message;
        document.body.appendChild(fb);
        setTimeout(() => fb.remove(), 3000);
    }

    /* ---------- Static helper to mount into an existing element ---------- */
    static mount(targetElement, book, options = {}) {
        if (!targetElement) {
            console.error('BookCard.mount: target element not provided');
            return null;
        }
        // Render first
        const instance = new BookCard(book, options);
        targetElement.innerHTML = instance.render();
        instance.element = targetElement.firstElementChild;

        // Attach editing listeners if applicable
        if (instance.options.enableEditing && instance.options.variant !== 'full') {
            instance.attachEditingListeners();
        }

        // For full variant, initialize MetadataEditor if available
        if (instance.options.variant === 'full' && typeof MetadataEditor !== 'undefined') {
            const containerId = targetElement.id || 'bookDetail';
            try {
                new MetadataEditor(containerId, { 
                    apiEndpoint: instance.options.booksApiUrl,
                    autoSave: false  // disable debounced autosave, only save on blur/enter/tab
                });
            } catch (err) {
                console.warn('BookCard: failed to init MetadataEditor', err);
            }
        }

        return instance;
    }
}

// Export for script-tag usage (attach to window) and CommonJS environments alike
if (typeof window !== 'undefined') {
    window.BookCard = BookCard;
}
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BookCard;
} 