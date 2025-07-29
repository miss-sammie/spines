/**
 * BookGrid.js - Book display and management component
 * Extracted from spines v1.0 and modernized for component architecture
 */

class BookGrid {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        
        if (!this.container) {
            console.error(`BookGrid: Container ${containerId} not found`);
            return;
        }
        
        this.options = {
            booksApiUrl: '/api/books',
            enableEditing: true,
            enableSearch: true,
            enableSorting: true,
            ...options
        };
        
        this.books = [];
        this.filteredBooks = [];
        this.currentSearch = '';
        this.currentSort = 'author';
        
        this.init();
    }
    
    init() {
        this.createHTML();
        this.attachEventListeners();
        this.loadBooks();
    }
    
    createHTML() {
        this.container.innerHTML = `
            ${this.options.enableSearch ? this.createSearchHTML() : ''}
            <div class="book-grid-container"></div>
            <div class="empty-state" style="display: none;">
                <h2>no books found</h2>
                <p>Try adjusting your search or add some books to your library.</p>
            </div>
        `;
        
        this.gridContainer = this.container.querySelector('.book-grid-container');
        this.emptyState = this.container.querySelector('.empty-state');
        
        if (this.options.enableSearch) {
            this.searchInput = this.container.querySelector('#search');
            this.sortSelect = this.container.querySelector('#sort');
        }
    }
    
    createSearchHTML() {
        return `
            <div class="filters">
                <input type="text" id="search" placeholder="Search by title, author, or year...">
                ${this.options.enableSorting ? `
                <div class="sort-controls">
                    <label for="sort">sort by:</label>
                    <select id="sort">
                        <option value="author">author</option>
                        <option value="title">title</option>
                        <option value="year">year</option>
                        <option value="recent">recently added</option>
                    </select>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    attachEventListeners() {
        if (this.options.enableSearch && this.searchInput) {
            this.searchInput.addEventListener('input', this.handleSearch.bind(this));
            this.searchInput.addEventListener('keyup', this.handleSearch.bind(this));
        }
        
        if (this.options.enableSorting && this.sortSelect) {
            this.sortSelect.addEventListener('change', this.handleSort.bind(this));
        }
        
        // Global click handler for edit mode
        document.addEventListener('click', this.handleGlobalClick.bind(this));
        
        // Global key handler for escape
        document.addEventListener('keydown', this.handleGlobalKeydown.bind(this));

        // Delegated click handler for book actions and navigation
        this.container.addEventListener('click', this.handleBookGridClick.bind(this));
    }
    
    async loadBooks() {
        try {
            const response = await fetch(this.options.booksApiUrl);
            if (!response.ok) {
                throw new Error(`Failed to load books: ${response.status}`);
            }
            
            const data = await response.json();
            this.books = data.books || Object.values(data) || [];
            this.filteredBooks = [...this.books];
            
            this.sortBooks();
            this.renderBooks();
            
        } catch (error) {
            console.error('Error loading books:', error);
            this.showError('Failed to load books');
        }
    }
    
    handleSearch() {
        this.currentSearch = this.searchInput.value.toLowerCase().trim();
        this.filterBooks();
    }
    
    handleSort() {
        this.currentSort = this.sortSelect.value;
        this.sortBooks();
        this.renderBooks();
    }
    
    filterBooks() {
        if (!this.currentSearch) {
            this.filteredBooks = [...this.books];
        } else {
            this.filteredBooks = this.books.filter(book => {
                const searchTerms = [
                    book.title || '',
                    book.author || '',
                    book.year ? book.year.toString() : '',
                    book.contributor ? (Array.isArray(book.contributor) ? book.contributor.join(' ') : book.contributor) : '',
                    book.read_by ? (Array.isArray(book.read_by) ? book.read_by.join(' ') : book.read_by) : '',
                    book.tags ? (Array.isArray(book.tags) ? book.tags.join(' ') : book.tags) : ''
                ].join(' ').toLowerCase();
                
                return searchTerms.includes(this.currentSearch);
            });
        }
        
        this.sortBooks();
        this.renderBooks();
    }
    
    sortBooks() {
        const sortFunctions = {
            author: (a, b) => {
                const authorA = (a.author || '').toLowerCase();
                const authorB = (b.author || '').toLowerCase();
                if (authorA === authorB) {
                    return (a.title || '').toLowerCase().localeCompare((b.title || '').toLowerCase());
                }
                return authorA.localeCompare(authorB);
            },
            title: (a, b) => (a.title || '').toLowerCase().localeCompare((b.title || '').toLowerCase()),
            year: (a, b) => {
                const yearA = a.year || 0;
                const yearB = b.year || 0;
                return yearB - yearA; // Newest first
            },
            recent: (a, b) => {
                // Use created_at if available, fallback to date_added for legacy data
                const dateA = new Date(a.created_at || a.date_added || 0);
                const dateB = new Date(b.created_at || b.date_added || 0);
                return dateB - dateA; // Most recent first
            }
        };
        
        const sortFn = sortFunctions[this.currentSort] || sortFunctions.author;
        this.filteredBooks.sort(sortFn);
    }
    
    renderBooks() {
        if (this.filteredBooks.length === 0) {
            this.gridContainer.style.display = 'none';
            this.emptyState.style.display = 'block';
            return;
        }
        
        this.gridContainer.style.display = 'grid';
        this.emptyState.style.display = 'none';
        
        this.gridContainer.className = 'book-grid';
        this.gridContainer.innerHTML = this.filteredBooks.map(book => this.createBookCardHTML(book)).join('');
        
        // Attach event listeners to book cards
        this.attachBookCardListeners();
    }
    
    createBookCardHTML(book) {
        // Prefer using the dedicated BookCard component if present
        if (typeof BookCard !== 'undefined' && BookCard.generate) {
            return BookCard.generate(book);
        }

        // Fallback to legacy inline markup (kept for backward compatibility)
        return `
            <div class="book-card" data-book-id="${book.id}">
                <div class="book-spine">
                    ${this.createEditableField('title', book.title || 'Unknown Title', false, 'book-title')}
                    ${this.createEditableField('author', book.author || 'Unknown Author', false, 'book-author')}
                    ${this.createEditableField('year', book.year || 'click to add', false, 'book-year')}
                    ${book.isbn ? this.createEditableField('isbn', book.isbn, false, 'book-isbn') : ''}
                </div>
                
                <div class="book-meta">
                    ${book.contributor ? `<div class="contributor">contributed by: ${Array.isArray(book.contributor) ? book.contributor.join(', ') : book.contributor}</div>` : ''}
                    ${book.readers && book.readers.length > 0 ? `<div class="read-status">read by: ${book.readers.join(', ')}</div>` : ''}
                    ${book.tags && book.tags.length > 0 ? `<div class="tags">tags: ${book.tags.join(', ')}</div>` : ''}
                    ${book.related_copies && book.related_copies.length > 0 ? `<div class="related-copies">${book.related_copies.length} related cop${book.related_copies.length === 1 ? 'y' : 'ies'}</div>` : ''}
                </div>
            </div>
        `;
    }
    
    createEditableField(field, value, isEditing, className) {
        if (isEditing) {
            return `<input type="text" class="editable-input ${className}" data-field="${field}" value="${this.escapeHtml(value)}" tabindex="0">`;
        } else {
            return `<div class="${className} editable-field" data-field="${field}" tabindex="0">${this.escapeHtml(value)}</div>`;
        }
    }
    
    attachBookCardListeners() {
        // Ensure book cards show pointer cursor
        const cardEls = this.container.querySelectorAll('.book-card');

        // Create/refresh BookCard instances
        this.cardInstances = [];

        cardEls.forEach((cardEl, idx) => {
            cardEl.style.cursor = 'pointer';
            const book = this.filteredBooks[idx];
            const cardInstance = new BookCard(book, {
                element: cardEl,
                booksApiUrl: this.options.booksApiUrl,
                enableEditing: this.options.enableEditing
            });
            this.cardInstances.push(cardInstance);
        });
    }

    /* -------------------------------------------------------------
       The inline editing logic now lives inside each BookCard.
       The following wrapper/stub methods exist only for backward
       compatibility with any external calls or legacy handlers.
    ------------------------------------------------------------- */

    startFieldEdit(fieldEl) {
        const cardEl = fieldEl.closest('.book-card');
        const instance = this.cardInstances?.find(c => c.element === cardEl);
        instance?.startFieldEdit?.(fieldEl);
        console.log('oopsies!!')
    }

    saveFieldEdit(input) {
        const cardEl = input.closest('.book-card');
        const instance = this.cardInstances?.find(c => c.element === cardEl);
        return instance?.saveFieldEdit?.(input);
    }

    cancelFieldEdit(input) {
        const cardEl = input.closest('.book-card');
        const instance = this.cardInstances?.find(c => c.element === cardEl);
        instance?.cancelFieldEdit?.(input);
    }

    replaceInputWithField(input, value) {
        const cardEl = input.closest('.book-card');
        const instance = this.cardInstances?.find(c => c.element === cardEl);
        instance?.replaceInputWithField?.(input, value);
    }
    
    // Keep old methods for compatibility but simplify them
    startEdit(bookId) {
        // For backward compatibility - just focus first editable field
        const bookCard = this.container.querySelector(`[data-book-id="${bookId}"]`);
        const firstField = bookCard.querySelector('.editable-field');
        if (firstField) {
            this.startFieldEdit(firstField);
        }
    }
    
    // Legacy methods - simplified for compatibility
    async saveBook(bookId) {
        // Save any currently editing field
        const currentlyEditing = this.container.querySelector('.editable-input');
        if (currentlyEditing) {
            await this.saveFieldEdit(currentlyEditing);
        }
    }
    
    cancelEdit(bookId) {
        // Cancel any currently editing field
        const currentlyEditing = this.container.querySelector('.editable-input');
        if (currentlyEditing) {
            this.cancelFieldEdit(currentlyEditing);
        }
    }
    
    handleGlobalClick(e) {
        // Auto-save any editing field when clicking outside
        const currentlyEditing = this.container.querySelector('.editable-input');
        if (currentlyEditing && !e.target.closest('.editable-input')) {
            this.saveFieldEdit(currentlyEditing);
        }
    }
    
    handleGlobalKeydown(e) {
        // Cancel edit on escape key
        if (e.key === 'Escape') {
            const currentlyEditing = this.container.querySelector('.editable-input');
            if (currentlyEditing) {
                this.cancelFieldEdit(currentlyEditing);
            }
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    showSuccess(message) {
        this.showFeedback(message, 'success');
    }
    
    showError(message) {
        this.showFeedback(message, 'error');
    }
    
    showFeedback(message, type) {
        const feedback = document.createElement('div');
        feedback.className = `feedback ${type}`;
        feedback.textContent = message;
        
        document.body.appendChild(feedback);
        
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 3000);
    }
    
    // Public methods for external access
    refresh() {
        this.loadBooks();
    }
    
    search(query) {
        if (this.searchInput) {
            this.searchInput.value = query;
            this.handleSearch();
        }
    }
    
    // Static method to create and initialize
    static create(containerId, options) {
        return new BookGrid(containerId, options);
    }

    handleBookGridClick(e) {
        // First handle explicit action buttons within a book card
        const actionEl = e.target.closest('.js-book-action');
        if (actionEl) {
            const bookCard = actionEl.closest('.book-card');
            if (!bookCard) return;
            const bookId = bookCard.dataset.bookId;
            const action = actionEl.dataset.action;
            switch (action) {
                case 'open-file':
                    window.BookActions?.openFile(bookId);
                    break;
                case 'extract-text':
                    window.BookActions?.extractText(bookId);
                    break;
                case 'delete':
                    window.BookActions?.deleteBook(bookId, actionEl.dataset.bookTitle || '');
                    break;
                case 'replace-file':
                    window.BookActions?.replaceFile(bookId, actionEl.dataset.bookTitle || '');
                    break;
                default:
                    console.warn(`BookGrid: unknown action "${action}"`);
            }
            // Prevent the click from bubbling up to navigation
            e.stopPropagation();
            return;
        }

        // Next handle navigation when clicking anywhere on a book card (except editable areas)
        const card = e.target.closest('.book-card');
        if (!card) return;

        // Ignore clicks originating from editable fields or active inputs
        const clickedEl = e.target;
        if (clickedEl.classList?.contains('editable-field') || clickedEl.closest('.editable-input')) {
            return;
        }

        const bookId = card.dataset.bookId;
        window.location.href = `/book/${bookId}`;
    }
}

// Global instance for backwards compatibility
let bookGrid = null;

// Auto-initialize book grid
document.addEventListener('DOMContentLoaded', () => {
    const gridContainer = document.getElementById('bookGrid') || document.querySelector('.book-grid-container');
    if (gridContainer) {
        bookGrid = BookGrid.create(gridContainer.id || 'bookGrid');
        window.bookGrid = bookGrid; // Make globally accessible
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BookGrid;
} 