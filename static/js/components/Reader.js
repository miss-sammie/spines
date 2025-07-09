/**
 * Reader.js - A file-agnostic reading component for Spines
 * Handles PDF, EPUB, and TXT files with a consistent, beautiful UI.
 */
class Reader {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Reader: Container #${containerId} not found.`);
            return;
        }
        this.options = { isInline: false, ...options };
        this.bookId = null;
        this.files = [];
        this.activeViewer = null;

        this.init();
    }

    init() {
        if (this.options.isInline) {
            this.container.innerHTML = `
                <div class="reader-toolbar"></div>
                <div class="reader-main-view"></div>
            `;
            this.mainView = this.container.querySelector('.reader-main-view');
            this.toolbar = this.container.querySelector('.reader-toolbar');
        } else {
            this.container.innerHTML = `
                <div class="reader-modal" style="display: none;">
                    <div class="reader-overlay"></div>
                    <div class="reader-content">
                        <button class="reader-close-btn">&times;</button>
                        <div class="reader-toolbar"></div>
                        <div class="reader-main-view"></div>
                    </div>
                </div>
            `;
            this.modal = this.container.querySelector('.reader-modal');
            this.mainView = this.container.querySelector('.reader-main-view');
            this.toolbar = this.container.querySelector('.reader-toolbar');
            
            this.container.querySelector('.reader-close-btn').addEventListener('click', () => this.hide());
            this.container.querySelector('.reader-overlay').addEventListener('click', () => this.hide());
        }
        
        // Handle keyboard shortcuts
        window.addEventListener('keydown', (e) => {
            if (!this.isOpen()) return;
            if (e.key === 'Escape' && !this.options.isInline) this.hide();
            if (e.key === 'ArrowLeft') this.prevPage();
            if (e.key === 'ArrowRight') this.nextPage();
        });
    }

    isOpen() {
        if (this.options.isInline) {
            return this.container.style.display !== 'none';
        }
        return this.modal && this.modal.style.display !== 'none';
    }

    async show(bookId) {
        this.bookId = bookId;
        if (!this.options.isInline) {
            this.modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        this.toolbar.innerHTML = '';
        this.mainView.innerHTML = '<div class="reader-loading">Loading files...</div>';

        try {
            const response = await fetch(`/api/books/${this.bookId}/files`);
            if (!response.ok) throw new Error('Failed to load file list.');
            this.files = await response.json();
            this.renderFileSelection();
        } catch (error) {
            this.mainView.innerHTML = `<div class="reader-error">${error.message}</div>`;
        }
    }

    hide() {
        if (this.options.isInline) return; // Cannot hide inline reader

        this.modal.style.display = 'none';
        document.body.style.overflow = '';
        this.mainView.innerHTML = '';
        this.toolbar.innerHTML = '';
        // Clean up mode classes
        this.mainView.classList.remove('txt-active');
        this.bookId = null;
        this.files = [];
        if (this.activeViewer && this.activeViewer.destroy) {
            this.activeViewer.destroy();
        }

        this.activeViewer = null;
    }

    renderFileSelection() {
        if (this.files.length === 0) {
            this.mainView.innerHTML = '<div class="reader-error">No readable files found for this book.</div>';
            return;
        }

        if (this.files.length === 1) {
            this.loadFile(this.files[0].name, this.files[0].type);
            return;
        }

        const filesHTML = this.files.map(file => `
            <li class="file-item" data-filename="${file.name}" data-filetype="${file.type}">
                <span class="file-icon">${this.getIconForType(file.type)}</span>
                <span class="file-name">${file.name}</span>
            </li>
        `).join('');

        this.mainView.innerHTML = `
            <div class="file-selector">
                <h3>Select a file to read:</h3>
                <ul>${filesHTML}</ul>
            </div>
        `;

        this.mainView.querySelectorAll('.file-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const target = e.currentTarget;
                this.loadFile(target.dataset.filename, target.dataset.filetype);
            });
        });
    }
    
    getIconForType(type) {
        switch(type) {
            case 'pdf': return '📄';
            case 'epub': return '📖';
            case 'txt': return '📝';
            default: return '📁';
        }
    }

    loadFile(filename, filetype) {
        this.mainView.innerHTML = `<div class="reader-loading">Loading ${filename}...</div>`;
        this.toolbar.innerHTML = '';
        // Remove any previous mode classes
        this.mainView.classList.remove('txt-active');
        switch(filetype) {
            case 'pdf':
                this.loadPdfViewer(filename);
                break;
            case 'epub':
                this.loadEpubViewer(filename);
                break;
            case 'txt':
                this.loadTxtViewer(filename);
                break;
            default:
                this.mainView.innerHTML = `<div class="reader-error">Unsupported file type: ${filetype}</div>`;
        }
    }

    async loadPdfViewer(filename) {
        const url = `/api/books/${this.bookId}/file?filename=${encodeURIComponent(filename)}`;
        this.mainView.innerHTML = `<div id="pdf-viewer-container"></div>`;
        const container = this.mainView.querySelector('#pdf-viewer-container');

        try {
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
            const loadingTask = pdfjsLib.getDocument(url);
            const pdf = await loadingTask.promise;

            for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
                const page = await pdf.getPage(pageNum);
                const canvas = document.createElement('canvas');
                const context = canvas.getContext('2d');
                
                const viewport = page.getViewport({ scale: 1.5 });
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                canvas.style.maxWidth = '100%';
                canvas.style.height = 'auto';
                canvas.className = 'pdf-page';
                container.appendChild(canvas);

                const renderContext = { canvasContext: context, viewport: viewport };
                await page.render(renderContext).promise;
            }
        } catch (error) {
            console.error('PDF loading error:', error);
            this.mainView.innerHTML = `<div class="reader-error">Failed to load PDF: ${error.message}</div>`;
        }
    }
    
    async loadEpubViewer(filename) {
        const url = `/api/books/${this.bookId}/file?filename=${encodeURIComponent(filename)}`;
        this.mainView.innerHTML = `<div id="epub-viewer-container"></div>`;
        this.toolbar.innerHTML = `
            <button id="prev-page">‹ Prev</button>
            <button id="next-page">Next ›</button>
            <label>Size: <input type="range" id="font-size" min="80" max="150" value="100" step="10"></label>
        `;

        try {
            const book = ePub(url);
            
            // Let ePub.js handle responsive layout automatically
            const rendition = book.renderTo("epub-viewer-container", {
                width: "100%",
                height: "100%"
            });

            // Apply font size changes
            const fontSlider = this.toolbar.querySelector('#font-size');
            fontSlider.addEventListener('input', (e) => {
                const size = e.target.value + '%';
                rendition.themes.fontSize(size);
            });

            await rendition.display();
            
            // Auto-fit container height to first page
            rendition.on('rendered', () => {
                const iframe = this.mainView.querySelector('iframe');
                if (iframe && iframe.contentWindow) {
                    try {
                        const doc = iframe.contentWindow.document;
                        const height = doc.documentElement.scrollHeight;
                        const container = this.mainView.querySelector('#epub-viewer-container');
                        if (container && height > 0) {
                            container.style.height = `${height}px`;
                        }
                    } catch (e) {
                        // Cross-origin or other access issues, use default
                        console.debug('Could not access iframe content for height calc');
                    }
                }
            });
            
            this.activeViewer = rendition;

            // Wire up navigation
            this.toolbar.querySelector('#prev-page').addEventListener('click', () => {
                rendition.prev();
            });
            this.toolbar.querySelector('#next-page').addEventListener('click', () => {
                rendition.next();
            });

            // Keyboard navigation
            rendition.on('keyup', (e) => {
                if (e.key === 'ArrowLeft') rendition.prev();
                if (e.key === 'ArrowRight') rendition.next();
            });

        } catch (error) {
            console.error('EPUB loading error:', error);
            this.mainView.innerHTML = `<div class="reader-error">Failed to load EPUB: ${error.message}</div>`;
        }
    }
    
    async loadTxtViewer(filename) {
        const url = `/api/books/${this.bookId}/file?filename=${encodeURIComponent(filename)}`;
        this.toolbar.innerHTML = `<button id="save-txt">Save</button>`;
        this.mainView.classList.add('txt-active');
        
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch text file.');
            const text = await response.text();

            this.mainView.innerHTML = `
                <div class="txt-viewer-container">
                    <textarea class="txt-viewer">${text}</textarea>
                </div>
            `;
            
            const textarea = this.mainView.querySelector('.txt-viewer');
            const resizeTextarea = () => {
                textarea.style.height = 'auto';
                textarea.style.height = (textarea.scrollHeight) + 'px';
            };
            textarea.addEventListener('input', resizeTextarea);
            setTimeout(resizeTextarea, 0); // Initial resize

            this.toolbar.querySelector('#save-txt').addEventListener('click', async () => {
                const newText = textarea.value;
                await this.saveTxtFile(filename, newText);
            });

        } catch (error) {
            console.error('TXT loading error:', error);
            this.mainView.innerHTML = `<div class="reader-error">Failed to load text file: ${error.message}</div>`;
        }
    }
    
    async saveTxtFile(filename, content) {
        const saveButton = this.toolbar.querySelector('#save-txt');
        saveButton.textContent = 'Saving...';
        saveButton.disabled = true;

        try {
            const url = `/api/books/${this.bookId}/file?filename=${encodeURIComponent(filename)}`;
            const response = await fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': 'text/plain' },
                body: content
            });
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || 'Failed to save.');
            }
            saveButton.textContent = 'Saved!';
            setTimeout(() => { saveButton.textContent = 'Save'; }, 2000);
        } catch (error) {
            console.error('TXT saving error:', error);
            saveButton.textContent = 'Error!';
             setTimeout(() => { saveButton.textContent = 'Save'; }, 2000);
        } finally {
            saveButton.disabled = false;
        }
    }
    
    prevPage() {
        if (this.activeViewer && this.activeViewer.prev) {
            this.activeViewer.prev();
        }
    }

    nextPage() {
        if (this.activeViewer && this.activeViewer.next) {
            this.activeViewer.next();
        }
    }
} 