/**
 * Main.js - Application initialization and coordination
 * Coordinates all spines components and handles global functionality
 */

class SpinesApp {
    constructor() {
        this.components = {};
        this.config = {
            apiBase: '/api',
            enableCloudSky: true,
            enableAutoSave: true,
            contributorKey: 'spines_contributor'
        };
        
        this.init();
    }
    
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeApp());
        } else {
            this.initializeApp();
        }
    }
    
    initializeApp() {
        console.log('🌟 Initializing Spines 2.0...');
        
        // Initialize components in order
        this.initializeCloudSky();
        this.initializeContributorHandling();
        this.initializeUploadZone();
        this.initializeBookGrid();
        this.initializeProcessingQueue();
        this.initializeNotifications();
        this.initializeGlobalHandlers();
        
        console.log('✨ Spines 2.0 initialized successfully!');
    }
    
    initializeCloudSky() {
        if (this.config.enableCloudSky && document.getElementById('cloudSky')) {
            try {
                this.components.cloudSky = new CloudSky('cloudSky');
                console.log('☁️ CloudSky initialized');
            } catch (error) {
                console.warn('CloudSky initialization failed:', error);
            }
        }
    }
    
    initializeContributorHandling() {
        // Handle contributor input in header
        const contributorInput = document.querySelector('.header-right input');
        if (contributorInput) {
            // Load saved contributor
            const savedContributor = localStorage.getItem(this.config.contributorKey);
            if (savedContributor && savedContributor.trim()) {
                contributorInput.value = savedContributor;
            }
            
            // Save contributor on change
            contributorInput.addEventListener('blur', () => {
                const contributor = contributorInput.value.trim();
                if (contributor) {
                    localStorage.setItem(this.config.contributorKey, contributor);
                }
            });
            
            // Save on enter
            contributorInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    contributorInput.blur();
                }
            });
        }
    }
    
    initializeUploadZone() {
        const uploadZone = document.getElementById('uploadZone') || document.querySelector('.upload-zone');
        if (uploadZone) {
            try {
                this.components.uploadZone = new UploadZone(uploadZone.id || 'uploadZone', {
                    uploadUrl: `${this.config.apiBase}/files/upload`,
                    onUploadComplete: (result) => {
                        // Refresh book grid if it exists
                        if (this.components.bookGrid) {
                            setTimeout(() => this.components.bookGrid.refresh(), 1000);
                        }
                    }
                });
                console.log('📤 UploadZone initialized');
            } catch (error) {
                console.warn('UploadZone initialization failed:', error);
            }
        }
    }
    
    initializeBookGrid() {
        const bookGrid = document.getElementById('bookGrid') || document.querySelector('.book-grid-container');
        if (bookGrid) {
            try {
                this.components.bookGrid = new BookGrid(bookGrid.id || 'bookGrid', {
                    booksApiUrl: `${this.config.apiBase}/books`
                });
                
                // Make globally accessible for backwards compatibility
                window.bookGrid = this.components.bookGrid;
                
                console.log('📚 BookGrid initialized');
            } catch (error) {
                console.warn('BookGrid initialization failed:', error);
            }
        }
    }
    
    initializeProcessingQueue() {
        const processingQueue = document.getElementById('processingQueue') || document.querySelector('.processing-queue');
        if (processingQueue) {
            try {
                this.components.processingQueue = new ProcessingQueue(processingQueue.id || 'processingQueue', {
                    processUrl: `${this.config.apiBase}/files/process`,
                    streamUrl: `${this.config.apiBase}/files/process-stream`
                });
                console.log('⚙️ ProcessingQueue initialized');
            } catch (error) {
                console.warn('ProcessingQueue initialization failed:', error);
            }
        }
    }
    
    initializeNotifications() {
        // Check for pending changes notice
        this.checkForChanges();
        
        // Check for review queue items
        this.checkReviewQueue();
        
        // Initialize background processing monitor
        this.initializeBackgroundProcessing();
        
        // Handle cache invalidation
        this.handleCacheInvalidation();
    }
    
    async checkForChanges() {
        try {
            // This would be implemented by checking file system changes
            // For now, we'll skip this as it requires server-side implementation
        } catch (error) {
            console.warn('Failed to check for changes:', error);
        }
    }
    
    async checkReviewQueue() {
        try {
            const response = await fetch(`${this.config.apiBase}/review-queue`);
            if (response.ok) {
                const data = await response.json();
                const pendingCount = data.summary?.pending_review || 0;
                
                if (pendingCount > 0) {
                    this.showReviewNotice(pendingCount);
                }
            }
        } catch (error) {
            console.warn('Failed to check review queue:', error);
        }
    }
    
    showReviewNotice(count) {
        const existingNotice = document.querySelector('.review-notice');
        
        if (existingNotice) {
            // Update existing notice with new count
            const countElement = existingNotice.querySelector('strong');
            if (countElement) {
                countElement.innerHTML = `📋 ${count} book${count !== 1 ? 's' : ''} need manual review`;
            }
            return;
        }
        
        // Create new notice
        const notice = document.createElement('div');
        notice.className = 'review-notice';
        notice.innerHTML = `
            <strong>📋 ${count} book${count !== 1 ? 's' : ''} need manual review</strong>
            <br>
            <a href="/admin/review-queue" class="review-link">review metadata →</a>
        `;
        
        // Insert after header
        const header = document.querySelector('header');
        if (header) {
            header.insertAdjacentElement('afterend', notice);
        }
    }
    
    initializeBackgroundProcessing() {
        // Check if there's an active processing session
        const savedState = localStorage.getItem('spines_processing_state');
        if (!savedState) return;
        
        try {
            const state = JSON.parse(savedState);
            
            // Check if state is recent (within last 10 minutes)
            const maxAge = 10 * 60 * 1000; // 10 minutes
            if (Date.now() - state.timestamp > maxAge) {
                localStorage.removeItem('spines_processing_state');
                return;
            }
            
            if (state.isProcessing) {
                // Create a background processing monitor
                this.backgroundProcessingMonitor = new BackgroundProcessingMonitor(state);
                console.log('🔄 Background processing detected, monitoring stream...');
            }
        } catch (error) {
            console.warn('Failed to initialize background processing:', error);
            localStorage.removeItem('spines_processing_state');
        }
    }
    
    handleCacheInvalidation() {
        // Check if metadata was updated and refresh if needed
        const metadataUpdated = localStorage.getItem('spines_metadata_updated');
        if (metadataUpdated === 'true') {
            localStorage.removeItem('spines_metadata_updated');
            
            // Refresh book grid if it exists
            if (this.components.bookGrid) {
                setTimeout(() => this.components.bookGrid.refresh(), 500);
            }
        }
    }
    
    initializeGlobalHandlers() {
        // Handle navigation with cache busting
        this.setupNavigationHandlers();
        
        // Handle keyboard shortcuts
        this.setupKeyboardShortcuts();
        
        // Handle window events
        this.setupWindowHandlers();
    }
    
    setupNavigationHandlers() {
        // Cache busting for navigation links
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[href="/"]');
            if (link) {
                e.preventDefault();
                const timestamp = new Date().getTime();
                window.location.href = `/?t=${timestamp}`;
            }
        });
    }
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K for search focus
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.getElementById('search');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }
            
            // Escape to clear search
            if (e.key === 'Escape') {
                const searchInput = document.getElementById('search');
                if (searchInput && searchInput === document.activeElement) {
                    searchInput.value = '';
                    searchInput.blur();
                    if (this.components.bookGrid) {
                        this.components.bookGrid.handleSearch();
                    }
                }
            }
        });
    }
    
    setupWindowHandlers() {
        // Handle beforeunload for unsaved changes
        window.addEventListener('beforeunload', (e) => {
            if (this.components.processingQueue?.isProcessing) {
                e.preventDefault();
                e.returnValue = 'File processing is in progress. Are you sure you want to leave?';
                return e.returnValue;
            }
        });
        
        // Handle visibility change to pause/resume components
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // Page is hidden - could pause non-essential animations
                console.log('🌙 Page hidden - pausing non-essential features');
            } else {
                // Page is visible - resume normal operation
                console.log('☀️ Page visible - resuming normal operation');
            }
        });
    }
    
    // Public API methods
    getComponent(name) {
        return this.components[name];
    }
    
    refreshAll() {
        Object.values(this.components).forEach(component => {
            if (component.refresh) {
                component.refresh();
            }
        });
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `feedback ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
}

/**
 * Background Processing Monitor
 * Monitors processing streams across page navigation
 */
class BackgroundProcessingMonitor {
    constructor(state) {
        this.state = state;
        this.reviewCount = state.reviewCount || 0;
        this.eventSource = null;
        
        this.connectToStream();
    }
    
    connectToStream() {
        const apiBase = window.spinesApp?.config?.apiBase || '/api';
        const streamUrl = `${apiBase}/process-files-stream?contributor=${encodeURIComponent(this.state.contributor)}`;
        
        this.eventSource = new EventSource(streamUrl);
        
        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleStreamEvent(data);
            } catch (error) {
                console.error('Error parsing background stream data:', error);
            }
        };
        
        this.eventSource.onerror = (error) => {
            console.error('Background EventSource error:', error);
            this.cleanup();
        };
    }
    
    handleStreamEvent(data) {
        switch (data.type) {
            case 'file_complete':
                if (data.status === 'review') {
                    this.reviewCount++;
                    this.updateReviewNotice();
                    this.triggerReviewQueueUpdate();
                }
                this.updateState();
                break;
                
            case 'complete':
                console.log('🎉 Background processing completed');
                this.cleanup();
                
                // Trigger final review notice update
                if (data.review_queue_count > 0) {
                    this.reviewCount = data.review_queue_count;
                    this.updateReviewNotice();
                    this.triggerReviewQueueUpdate();
                }
                
                // Mark metadata as updated for cache invalidation
                localStorage.setItem('spines_metadata_updated', 'true');
                break;
                
            case 'error':
                console.error('Background processing error:', data.error);
                this.cleanup();
                break;
        }
    }
    
    updateReviewNotice() {
        if (this.reviewCount > 0 && window.spinesApp) {
            window.spinesApp.showReviewNotice(this.reviewCount);
        }
    }
    
    updateState() {
        // Update the stored state
        this.state.reviewCount = this.reviewCount;
        this.state.timestamp = Date.now();
        localStorage.setItem('spines_processing_state', JSON.stringify(this.state));
    }
    
    triggerReviewQueueUpdate() {
        // Trigger review queue page update if it exists
        if (window.location.pathname.includes('review-queue') && typeof window.loadReviewQueue === 'function') {
            console.log('🔄 Triggering review queue update');
            window.loadReviewQueue();
        }
    }
    
    cleanup() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        localStorage.removeItem('spines_processing_state');
        
        // Remove from app
        if (window.spinesApp?.backgroundProcessingMonitor === this) {
            window.spinesApp.backgroundProcessingMonitor = null;
        }
    }
}

// Initialize the app
const spinesApp = new SpinesApp();

// Make globally accessible
window.spinesApp = spinesApp;

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SpinesApp;
}