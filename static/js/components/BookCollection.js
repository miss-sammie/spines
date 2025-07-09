class BookCollection {
    /**
     * Construct a BookCollection widget.
     * @param {string} containerId – element id where collection will mount.
     * @param {object} options – { id: <collectionId>, view: 'grid'|'index'|'spine' }
     */
    constructor(containerId, options = {}) {
        if (!options.id) {
            throw new Error('BookCollection requires an `id` option');
        }
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container #${containerId} not found`);
        }
        this.options = Object.assign({ view: 'grid' }, options);
        this.collection = null;
        this.books = [];
    }

    async init() {
        try {
            await this.loadCollection();
            this.render();
        } catch (err) {
            console.error('Failed to initialise collection', err);
            this.container.innerHTML = `<div class="feedback error">Failed to load collection</div>`;
        }
    }

    async loadCollection() {
        const res = await fetch(`/api/collections/${this.options.id}?resolve=1`);
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        this.collection = data.collection || data;
        this.books = data.books || [];
    }

    render() {
        const { view } = this.options;
        this.container.classList.add('book-collection');
        // Header
        const headerHTML = `
            <header class="collection-header">
                <h2>${this.escapeHtml(this.collection.name)}</h2>
                ${this.collection.description ? `<p>${this.escapeHtml(this.collection.description)}</p>` : ''}
            </header>
        `;

        let bodyHTML = '';
        if (view === 'index') {
            bodyHTML = this.renderIndex();
        } else if (view === 'spine') {
            bodyHTML = this.renderSpine();
        } else {
            bodyHTML = this.renderGrid();
        }

        this.container.innerHTML = headerHTML + bodyHTML;
    }

    renderGrid() {
        if (!this.books.length) {
            return '<div class="empty-state"><h3>(no books)</h3></div>';
        }
        const cards = this.books.map(b => typeof BookCard !== 'undefined' ? BookCard.generate(b) : `<div>${this.escapeHtml(b.title)}</div>`).join('');
        return `<div class="book-grid">${cards}</div>`;
    }

    renderIndex() {
        if (!this.books.length) {
            return '<div class="empty-state"><h3>(no books)</h3></div>';
        }
        const items = this.books.map(b => `<li>${this.escapeHtml(b.author || '?')} — <em>${this.escapeHtml(b.title || '?')}</em> ${b.year ? '(' + b.year + ')' : ''}</li>`).join('');
        return `<ol class="book-index">${items}</ol>`;
    }

    renderSpine() {
        if (!this.books.length) {
            return '<div class="empty-state"><h3>(no books)</h3></div>';
        }
        const cards = this.books.map(b => typeof BookCard !== 'undefined' ? BookCard.generate(b) : `<div class="book-spine">${this.escapeHtml(b.title)}</div>`).join('');
        return `<div class="spine-shelf" style="display:flex;gap:4px;overflow-x:auto;">${cards}</div>`;
    }

    escapeHtml(text = '') {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    static async create(containerId, options) {
        const inst = new BookCollection(containerId, options);
        await inst.init();
        return inst;
    }
} 