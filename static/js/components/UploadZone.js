/**
 * UploadZone.js - File upload component with drag-and-drop support
 * Extracted from spines v1.0 and modernized for component architecture
 */

class UploadZone {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        
        if (!this.container) {
            console.error(`UploadZone: Container ${containerId} not found`);
            return;
        }
        
        // Determine API base dynamically (falls back to '/api')
        const apiBase = (typeof window !== 'undefined' && window.spinesApp && window.spinesApp.config && window.spinesApp.config.apiBase) || '/api';

        this.options = {
            acceptedTypes: ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv'],
            uploadUrl: `${apiBase}/files/upload`,
            onUploadStart: () => {},
            onUploadProgress: () => {},
            onUploadComplete: () => {},
            onUploadError: () => {},
            ...options
        };
        
        this.fileInput = null;
        this.progressBar = null;
        this.progressFill = null;
        this.uploadStatus = null;
        
        this.init();
    }
    
    init() {
        this.createHTML();
        this.attachEventListeners();
    }
    
    createHTML() {
        this.container.innerHTML = `
            <div class="upload-content">
                <div class="upload-icon"></div>
                <div class="upload-text">
                    <strong>Drop PDF files here to add to library</strong>
                    <br>
                    <small>or <button class="browse-button" type="button">browse files</button></small>
                </div>
                <input type="file" class="file-input" multiple accept="${this.options.acceptedTypes.join(',')}" style="display: none;">
            </div>
            <div class="upload-progress" style="display: none;">
                <div class="progress-bar">
                    <div class="progress-fill"></div>
                </div>
                <div class="upload-status">Uploading...</div>
            </div>
        `;
        
        // Get references to elements
        this.fileInput = this.container.querySelector('.file-input');
        this.browseButton = this.container.querySelector('.browse-button');
        this.uploadProgress = this.container.querySelector('.upload-progress');
        this.progressBar = this.container.querySelector('.progress-bar');
        this.progressFill = this.container.querySelector('.progress-fill');
        this.uploadStatus = this.container.querySelector('.upload-status');
    }
    
    attachEventListeners() {
        // Browse button click
        this.browseButton.addEventListener('click', () => {
            this.fileInput.click();
        });
        
        // File input change
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFiles(Array.from(e.target.files));
            }
        });
        
        // Drag and drop events
        this.container.addEventListener('dragover', this.handleDragOver.bind(this));
        this.container.addEventListener('dragenter', this.handleDragEnter.bind(this));
        this.container.addEventListener('dragleave', this.handleDragLeave.bind(this));
        this.container.addEventListener('drop', this.handleDrop.bind(this));
        
        // Prevent default drag behaviors on document
        document.addEventListener('dragover', (e) => e.preventDefault());
        document.addEventListener('drop', (e) => e.preventDefault());
    }
    
    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    handleDragEnter(e) {
        e.preventDefault();
        e.stopPropagation();
        this.container.classList.add('dragover');
    }
    
    handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // Only remove dragover if we're actually leaving the container
        if (!this.container.contains(e.relatedTarget)) {
            this.container.classList.remove('dragover');
        }
    }
    
    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        this.container.classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            this.handleFiles(files);
        }
    }
    
    handleFiles(files) {
        // Filter for supported file types
        const supportedFiles = files.filter(file => {
            const extension = '.' + file.name.split('.').pop().toLowerCase();
            return this.options.acceptedTypes.includes(extension);
        });
        
        if (supportedFiles.length === 0) {
            this.showError('No supported files found. Please upload PDF, EPUB, MOBI, AZW, or DJVU files.');
            return;
        }
        
        if (supportedFiles.length !== files.length) {
            const unsupportedCount = files.length - supportedFiles.length;
            this.showWarning(`${unsupportedCount} unsupported file(s) were skipped.`);
        }
        
        this.uploadFiles(supportedFiles);
    }
    
    async uploadFiles(files) {
        const formData = new FormData();
        
        // Add files to form data
        files.forEach(file => {
            formData.append('files', file);
        });
        
        // Add contributor if available
        const contributor = this.getContributor();
        if (contributor) {
            formData.append('contributor', contributor);
        }
        
        // Show progress
        this.showProgress();
        this.options.onUploadStart(files);
        
        try {
            await this.uploadWithProgress(formData);
        } catch (error) {
            console.error('Upload error:', error);
            this.handleUploadError(error);
        }
    }
    
    async uploadWithProgress(formData) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', this.options.uploadUrl, true);
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    this.updateProgress(percent);
                }
            };
            xhr.onreadystatechange = () => {
                if (xhr.readyState === XMLHttpRequest.DONE) {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            const result = JSON.parse(xhr.responseText);
                            this.handleUploadSuccess(result);
                            resolve(result);
                        } catch (err) {
                            reject(err);
                        }
                    } else {
                        reject(new Error(`Upload failed: ${xhr.status}`));
                    }
                }
            };
            xhr.onerror = () => reject(new Error('Network error'));
            xhr.send(formData);
        });
    }
    
    getContributor() {
        // Try to get contributor from localStorage or input field
        const savedContributor = localStorage.getItem('spines_contributor');
        if (savedContributor && savedContributor.trim()) {
            return savedContributor.trim();
        }
        
        // Try to get from header input if it exists
        const headerInput = document.querySelector('.header-right input');
        if (headerInput && headerInput.value.trim()) {
            return headerInput.value.trim();
        }
        
        return 'anonymous';
    }
    
    showProgress() {
        this.uploadProgress.style.display = 'block';
        this.progressFill.style.width = '0%';
        this.uploadStatus.textContent = 'Uploading...';
    }
    
    hideProgress() {
        setTimeout(() => {
            this.uploadProgress.style.display = 'none';
            this.progressFill.style.width = '0%';
        }, 2000);
    }
    
    updateProgress(percent) {
        this.progressFill.style.width = `${percent}%`;
    }
    
    handleUploadSuccess(result) {
        this.updateProgress(100);
        
        let message = `✅ Uploaded ${result.uploaded_count} file(s)`;
        if (result.processed_count > 0) {
            message += `, ${result.processed_count} processed automatically`;
        }
        if (result.review_queue_count > 0) {
            message += `, ${result.review_queue_count} added to review queue`;
        }
        
        this.uploadStatus.textContent = message;
        this.showSuccess(message);
        this.hideProgress();
        
        // Reset file input
        this.fileInput.value = '';
        
        // Mark that metadata has been updated (for cache invalidation)
        localStorage.setItem('spines_metadata_updated', 'true');
        
        this.options.onUploadComplete(result);
        
        // Automatically trigger ProcessingQueue to show real-time processing progress
        try {
            if (window.spinesApp && typeof window.spinesApp.getComponent === 'function') {
                const pq = window.spinesApp.getComponent('processingQueue');
                if (pq && typeof pq.startProcessing === 'function' && !pq.isProcessing) {
                    // If autoStart flag exists, honour it, otherwise start immediately
                    pq.startProcessing();
                }
            }
        } catch (err) {
            console.warn('ProcessingQueue auto-start failed:', err);
        }
        
        // Don't auto-redirect when background processing is active
        // Let the user choose when to navigate to review queue via the notice
        if (result.processed_count > 0 && result.review_queue_count === 0) {
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    }
    
    handleUploadError(error) {
        this.uploadStatus.textContent = '❌ Upload failed';
        this.showError(`Upload failed: ${error.message}`);
        this.hideProgress();
        
        this.options.onUploadError(error);
    }
    
    showSuccess(message) {
        this.showFeedback(message, 'success');
    }
    
    showError(message) {
        this.showFeedback(message, 'error');
    }
    
    showWarning(message) {
        this.showFeedback(message, 'info');
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
        }, 5000);
    }
    
    // Static method to create and initialize
    static create(containerId, options) {
        return new UploadZone(containerId, options);
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UploadZone;
} 