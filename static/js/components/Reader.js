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
        if (this._epubResizeHandler) {
            window.removeEventListener('resize', this._epubResizeHandler);
            this._epubResizeHandler = null;
        }
        if (this._epubOverlay && this._epubOverlay.parentNode) {
            this._epubOverlay.parentNode.removeChild(this._epubOverlay);
            this._epubOverlay = null;
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
            console.log('EPUB book loaded:', book);
            
            const rendition = book.renderTo("epub-viewer-container", {
                width: "100%",
                height: "100%"
            });
            console.log('EPUB rendition created:', rendition);

            // Responsive spread – single page on portrait, spread on landscape
            const updateSpread = () => {
                const w = this.mainView.clientWidth;
                const h = this.mainView.clientHeight;
                console.log('Container dimensions:', w, h);
                if (w === 0 || h === 0) return;
                if (w > h) {
                    rendition.spread("auto"); // allow two-page
                } else {
                    rendition.spread("none"); // force single page
                }
            };

            // Font size slider
            const fontSlider = this.toolbar.querySelector('#font-size');
            fontSlider.addEventListener('input', (e) => {
                const size = e.target.value + '%';
                rendition.themes.fontSize(size);
            });

            await rendition.display();
            console.log('EPUB display complete');
            
            // Check if content actually rendered
            setTimeout(() => {
                const iframe = this.mainView.querySelector('#epub-viewer-container iframe');
                console.log('EPUB iframe found:', !!iframe);
                if (iframe) {
                    console.log('EPUB iframe src:', iframe.src);
                    console.log('EPUB iframe content loaded:', iframe.contentDocument ? 'yes' : 'no');
                    console.log('EPUB iframe dimensions:', iframe.offsetWidth, 'x', iframe.offsetHeight);
                    console.log('EPUB iframe style:', iframe.style.cssText);
                    
                    // Try to inspect iframe content
                    try {
                        const doc = iframe.contentDocument || iframe.contentWindow.document;
                        console.log('EPUB iframe body height:', doc.body ? doc.body.scrollHeight : 'no body');
                        console.log('EPUB iframe body content:', doc.body ? doc.body.innerHTML.substring(0, 100) : 'no body');
                    } catch (e) {
                        console.log('Cannot access iframe content:', e.message);
                    }
                }
            }, 200);
            
            // Now set up spread and overlay AFTER display
            
            // Check layout and force reflow if needed
            console.log('EPUB layout:', rendition._layout.name);
            if (rendition._layout.name === 'pre-paginated') {
                console.log('Pre-paginated layout detected - keeping as fixed pages');
                // Just resize to fit container properly
                rendition.resize('100%', '100%');
            } else {
                console.log('Reflowable EPUB - setting up responsive spread');
                // Only do spread logic for reflowable books
                updateSpread();
            }
            
            window.addEventListener('resize', updateSpread);
            this._epubResizeHandler = updateSpread;

            // Tap / click navigation overlay - add AFTER epub is rendered
            setTimeout(() => {
                const container = this.mainView.querySelector('#epub-viewer-container');
                if (container) {
                    const overlay = document.createElement('div');
                    overlay.className = 'epub-nav-overlay';
                    container.appendChild(overlay);
                    
                    const handleNav = (clientX) => {
                        const rect = overlay.getBoundingClientRect();
                        const relX = clientX - rect.left;
                        const ratio = relX / rect.width;
                        console.log('Nav click at ratio:', ratio);
                        if (ratio < 0.33) rendition.prev();
                        else if (ratio > 0.66) rendition.next();
                    };
                    
                    overlay.addEventListener('click', (e) => {
                        e.stopPropagation();
                        handleNav(e.clientX);
                    });
                    overlay.addEventListener('touchstart', (e) => {
                        e.preventDefault();
                        if (e.touches && e.touches.length) {
                            handleNav(e.touches[0].clientX);
                        }
                    });
                    overlay.style.touchAction = 'manipulation';
                    this._epubOverlay = overlay;
                    console.log('Navigation overlay added');
                }
            }, 100);

            this.activeViewer = rendition;

            // Wire up toolbar buttons
            this.toolbar.querySelector('#prev-page').addEventListener('click', () => {
                console.log('Prev button clicked');
                rendition.prev();
            });
            this.toolbar.querySelector('#next-page').addEventListener('click', () => {
                console.log('Next button clicked');
                rendition.next();
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