/**
 * ProcessingQueue.js - File processing progress tracking component
 * Extracted from spines v1.0 and modernized for component architecture
 */

class ProcessingQueue {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        
        if (!this.container) {
            console.error(`ProcessingQueue: Container ${containerId} not found`);
            return;
        }
        
        // Determine API base dynamically (falls back to '/api')
        const apiBase = (typeof window !== 'undefined' && window.spinesApp && window.spinesApp.config && window.spinesApp.config.apiBase) || '/api';

        this.options = {
            processUrl: `${apiBase}/files/process`,
            streamUrl: `${apiBase}/files/process-stream`,
            enableStreaming: true,
            autoStart: false,
            ...options
        };
        
        this.isProcessing = false;
        this.eventSource = null;
        this.processButton = null;
        this.progressBar = null;
        this.progressFill = null;
        this.progressDetails = null;
        this.fileList = null;
        this.reviewCount = 0; // Track items flagged for review
        
        this.init();
        this.restoreState(); // Restore processing state if it exists
    }
    
    init() {
        this.createHTML();
        this.attachEventListeners();
    }
    
    createHTML() {
        this.container.innerHTML = `
            <div class="process-controls">
                <button class="process-button" type="button">
                    📚 process files
                </button>
                <span class="process-status"></span>
            </div>
            <div class="process-progress" style="display: none;">
                <div class="progress-bar">
                    <div class="progress-fill"></div>
                </div>
                <div class="progress-details"></div>
                <div class="file-list"></div>
            </div>
        `;
        
        // Get references to elements
        this.processButton = this.container.querySelector('.process-button');
        this.processStatus = this.container.querySelector('.process-status');
        this.processProgress = this.container.querySelector('.process-progress');
        this.progressBar = this.container.querySelector('.progress-bar');
        this.progressFill = this.container.querySelector('.progress-fill');
        this.progressDetails = this.container.querySelector('.progress-details');
        this.fileList = this.container.querySelector('.file-list');
    }
    
    attachEventListeners() {
        this.processButton.addEventListener('click', this.startProcessing.bind(this));
    }
    
    async startProcessing() {
        if (this.isProcessing) {
            return;
        }
        
        this.isProcessing = true;
        this.processButton.disabled = true;
        this.processButton.textContent = '⏳ processing...';
        this.processStatus.textContent = '';
        
        // Show progress container
        this.processProgress.style.display = 'block';
        this.progressFill.style.width = '0%';
        this.progressDetails.textContent = 'Initializing...';
        this.fileList.innerHTML = '';
        this.reviewCount = 0; // Reset review count
        
        try {
            if (this.options.enableStreaming) {
                await this.processWithStreaming();
            } else {
                await this.processWithoutStreaming();
            }
        } catch (error) {
            console.error('Processing error:', error);
            this.handleError(error);
        }
    }
    
    async processWithStreaming(contributor = null) {
        contributor = contributor || this.getContributor();
        const streamUrl = `${this.options.streamUrl}?contributor=${encodeURIComponent(contributor)}`;
        
        // Save state when starting processing
        this.saveState();
        
        return new Promise((resolve, reject) => {
            this.eventSource = new EventSource(streamUrl);
            
            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleStreamEvent(data);
                    
                    if (data.type === 'complete' || data.type === 'error') {
                        this.eventSource.close();
                        this.eventSource = null;
                        
                        if (data.type === 'complete') {
                            resolve(data);
                        } else {
                            reject(new Error(data.error || 'Processing failed'));
                        }
                    }
                } catch (error) {
                    console.error('Error parsing stream data:', error);
                }
            };
            
            this.eventSource.onerror = (error) => {
                console.error('EventSource error:', error);
                this.eventSource.close();
                this.eventSource = null;
                reject(new Error('Stream connection failed'));
            };
            
            // Timeout after 5 minutes
            setTimeout(() => {
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                    reject(new Error('Processing timeout'));
                }
            }, 300000);
        });
    }
    
    async processWithoutStreaming() {
        const contributor = this.getContributor();
        
        const response = await fetch(this.options.processUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ contributor })
        });
        
        if (!response.ok) {
            throw new Error(`Processing failed: ${response.status} ${response.statusText}`);
        }
        
        const result = await response.json();
        
        // Simulate progress for non-streaming
        this.progressFill.style.width = '100%';
        this.progressDetails.textContent = `Processed ${result.processed_count} files`;
        
        this.handleComplete(result);
    }
    
    handleStreamEvent(data) {
        switch (data.type) {
            case 'ping':
                this.progressDetails.textContent = 'Connected...';
                break;
                
            case 'start':
                this.progressDetails.textContent = `Processing ${data.total_files} files...`;
                this.populateFileList(data.filenames || []);
                break;
                
            case 'progress':
                const percent = (data.current_file / data.total_files) * 100;
                this.progressFill.style.width = `${percent}%`;
                this.progressDetails.textContent = `Processing ${data.current_file}/${data.total_files}: ${data.filename}`;
                break;
                
            case 'detail':
                this.updateFileSubStatus(data.filename, data.detail);
                break;
                
            case 'file_complete':
                this.updateFileStatus(data);
                // Check if this file was flagged for review
                if (data.status === 'review') {
                    this.reviewCount++;
                    this.updateReviewNotice();
                }
                // Save updated state
                this.saveState();
                break;
                
            case 'complete':
                this.progressFill.style.width = '100%';
                this.progressDetails.textContent = `✅ Completed! Processed ${data.processed_count} files`;
                this.handleComplete(data);
                break;
                
            case 'error':
                this.handleError(new Error(data.error));
                break;
        }
    }
    
    populateFileList(filenames) {
        this.fileList.innerHTML = ''; // Clear previous list
        filenames.forEach(filename => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            // Use a data attribute to easily find the element later
            fileItem.dataset.filename = filename;
            
            fileItem.innerHTML = `
                <span class="file-name">${this.escapeHtml(filename)}</span>
                <span class="file-sub-status"></span>
                <span class="file-status pending">pending...</span>
            `;
            this.fileList.appendChild(fileItem);
        });
    }

    updateFileSubStatus(filename, detail) {
        const fileItem = this.fileList.querySelector(`[data-filename="${filename}"]`);
        if (!fileItem) return;

        const subStatusSpan = fileItem.querySelector('.file-sub-status');
        let detailText = detail.replace(/_/g, ' ');
        subStatusSpan.textContent = `(${detailText})`;
    }

    updateFileStatus(fileData) {
        const fileItem = this.fileList.querySelector(`[data-filename="${fileData.filename}"]`);
        if (!fileItem) return;

        let statusClass = 'unknown';
        let statusIcon = '🤔';
        
        switch (fileData.status) {
            case 'success':
                statusClass = 'success';
                statusIcon = '✅ Processed';
                break;
            case 'review':
                statusClass = 'review';
                statusIcon = '📋 To Review';
                break;
            case 'failed':
                statusClass = 'failed';
                statusIcon = '❌ Failed';
                break;
            case 'error':
                statusClass = 'error';
                statusIcon = '⚠️ Error';
                break;
        }

        const statusSpan = fileItem.querySelector('.file-status');
        statusSpan.className = `file-status ${statusClass}`;
        statusSpan.textContent = statusIcon;

        // Clear sub-status on completion
        const subStatusSpan = fileItem.querySelector('.file-sub-status');
        if (subStatusSpan) subStatusSpan.textContent = '';
    }
    
    updateReviewNotice() {
        // Update the review notice in real-time
        if (this.reviewCount > 0 && window.spinesApp) {
            window.spinesApp.showReviewNotice(this.reviewCount);
        }
    }
    
    saveState() {
        // Save processing state to localStorage
        const state = {
            isProcessing: this.isProcessing,
            reviewCount: this.reviewCount,
            contributor: this.getContributor(),
            timestamp: Date.now()
        };
        localStorage.setItem('spines_processing_state', JSON.stringify(state));
    }
    
    restoreState() {
        // Restore processing state from localStorage
        const savedState = localStorage.getItem('spines_processing_state');
        if (!savedState) return;
        
        try {
            const state = JSON.parse(savedState);
            
            // Check if state is recent (within last 10 minutes)
            const maxAge = 10 * 60 * 1000; // 10 minutes
            if (Date.now() - state.timestamp > maxAge) {
                this.clearState();
                return;
            }
            
            if (state.isProcessing) {
                this.reviewCount = state.reviewCount || 0;
                
                // Check if background processing is already active
                if (window.spinesApp?.backgroundProcessingMonitor) {
                    // Just update UI state, don't create duplicate stream
                    this.isProcessing = true;
                    this.processButton.disabled = true;
                    this.processButton.textContent = '⏳ processing...';
                    this.processProgress.style.display = 'block';
                    this.progressDetails.textContent = 'Processing in background...';
                } else {
                    this.reconnectToStream(state.contributor);
                }
            }
        } catch (error) {
            console.warn('Failed to restore processing state:', error);
            this.clearState();
        }
    }
    
    clearState() {
        localStorage.removeItem('spines_processing_state');
    }
    
    reconnectToStream(contributor) {
        // Reconnect to the processing stream
        this.isProcessing = true;
        this.processButton.disabled = true;
        this.processButton.textContent = '⏳ processing...';
        this.processProgress.style.display = 'block';
        this.progressDetails.textContent = 'Reconnecting to processing stream...';
        
        this.processWithStreaming(contributor).catch(error => {
            console.error('Failed to reconnect to stream:', error);
            this.handleError(error);
        });
    }
    
    addFileToList(fileData) {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        
        const statusClass = fileData.status === 'success' ? 'success' : 
                           fileData.status === 'failed' ? 'failed' : 
                           fileData.status === 'error' ? 'error' : 'processing';
        
        const statusIcon = fileData.status === 'success' ? '✅' : 
                          fileData.status === 'failed' ? '❌' : 
                          fileData.status === 'error' ? '⚠️' : '⏳';
        
        fileItem.innerHTML = `
            <span class="file-name">${fileData.filename}</span>
            <span class="file-status ${statusClass}">${statusIcon}</span>
        `;
        
        this.fileList.appendChild(fileItem);
        
        // Scroll to bottom of file list
        this.fileList.scrollTop = this.fileList.scrollHeight;
    }
    
    handleComplete(result) {
        this.isProcessing = false;
        this.processButton.disabled = false;
        this.processButton.textContent = '📚 process files';
        
        // Clear processing state when complete
        this.clearState();
        
        if (result.processed_count > 0 || result.review_queue_count > 0) {
            const message = `✅ Processed ${result.processed_count || 0}, with ${result.review_queue_count || 0} for review.`;
            this.processStatus.textContent = message;
            this.showSuccess(message);
            
            // Update final review count if it differs from our tracked count
            if (result.review_queue_count > 0 && result.review_queue_count !== this.reviewCount) {
                this.reviewCount = result.review_queue_count;
                this.updateReviewNotice();
            }
            
                    // Mark that metadata has been updated
        localStorage.setItem('spines_metadata_updated', 'true');
        
        // Only auto-reload if there are no review items (let user decide when to review)
        if (result.review_queue_count === 0 && result.processed_count > 0) {
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        }
        } else {
            this.processStatus.textContent = 'ℹ️ No new files were processed';
            this.showInfo('No new files were processed');
        }
        
        // Hide progress after delay
        setTimeout(() => {
            this.processProgress.style.display = 'none';
        }, 5000);
    }
    
    handleError(error) {
        this.isProcessing = false;
        this.processButton.disabled = false;
        this.processButton.textContent = '📚 process files';
        this.processStatus.textContent = '❌ Processing failed';
        
        // Clear processing state on error
        this.clearState();
        
        this.progressDetails.textContent = `Error: ${error.message}`;
        this.showError(`Processing failed: ${error.message}`);
        
        // Hide progress after delay
        setTimeout(() => {
            this.processProgress.style.display = 'none';
        }, 5000);
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
    
    showInfo(message) {
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
    
    // Public methods
    stop() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        
        this.isProcessing = false;
        this.processButton.disabled = false;
        this.processButton.textContent = '📚 process files';
        this.processStatus.textContent = '⏹️ Stopped';
    }
    
    // Static method to create and initialize
    static create(containerId, options) {
        return new ProcessingQueue(containerId, options);
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProcessingQueue;
} 