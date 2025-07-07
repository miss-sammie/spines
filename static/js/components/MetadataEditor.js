/**
 * MetadataEditor.js - Reusable inline metadata editing component
 * Handles JSON field editing with automatic saving and validation
 */

class MetadataEditor {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        
        if (!this.container) {
            console.error(`MetadataEditor: Container ${containerId} not found`);
            return;
        }
        
        this.options = {
            apiEndpoint: '/api/books',
            autoSave: true,
            saveDelay: 1000,
            fields: {},
            onSave: null,
            onError: null,
            ...options
        };
        
        this.currentEdit = null;
        this.saveTimeout = null;
        this.originalValues = {};
        
        this.init();
    }
    
    init() {
        this.attachEventListeners();
        this.makeFieldsEditable();
    }
    
    attachEventListeners() {
        // Global click handler for edit mode
        document.addEventListener('click', this.handleGlobalClick.bind(this));
        
        // Global key handler for escape
        document.addEventListener('keydown', this.handleGlobalKeydown.bind(this));
    }
    
    makeFieldsEditable() {
        // Find all editable metadata fields
        const editableFields = this.container.querySelectorAll('.metadata-value[data-field]');
        
        editableFields.forEach(field => {
            const fieldName = field.dataset.field;
            const fieldType = field.dataset.type || 'text';
            
            // Skip if field is marked as readonly
            if (field.classList.contains('readonly')) return;
            
            // Add click handler for editing
            field.addEventListener('click', (e) => {
                e.stopPropagation();
                this.startEdit(field, fieldName, fieldType);
            });
            
            // Add visual indicator that field is editable
            field.classList.add('editable');
            field.title = `Click to edit ${fieldName}`;
        });
    }
    
    startEdit(fieldElement, fieldName, fieldType) {
        // Cancel any existing edit
        if (this.currentEdit) {
            this.cancelEdit();
        }
        
        const currentValue = this.extractFieldValue(fieldElement, fieldType);
        this.originalValues[fieldName] = currentValue;
        
        // Create input based on field type
        const input = this.createInput(fieldType, currentValue, fieldName);
        
        // Replace field with input
        fieldElement.style.display = 'none';
        fieldElement.parentNode.insertBefore(input, fieldElement.nextSibling);
        
        // Focus and select
        input.focus();
        if (input.select) input.select();
        
        // Track current edit
        this.currentEdit = {
            fieldElement,
            input,
            fieldName,
            fieldType,
            originalValue: currentValue
        };
        
        // Attach input event listeners
        this.attachInputListeners(input);
    }
    
    createInput(fieldType, currentValue, fieldName) {
        let input;
        
        switch (fieldType) {
            case 'textarea':
                input = document.createElement('textarea');
                input.value = currentValue || '';
                input.rows = 3;
                break;
                
            case 'array':
                input = document.createElement('input');
                input.type = 'text';
                input.value = Array.isArray(currentValue) ? currentValue.join(', ') : (currentValue || '');
                input.placeholder = 'Enter comma-separated values';
                break;
                
            case 'number':
                input = document.createElement('input');
                input.type = 'number';
                input.value = currentValue || '';
                break;
                
            default: // text
                input = document.createElement('input');
                input.type = 'text';
                input.value = currentValue || '';
                break;
        }
        
        input.className = 'metadata-input';
        input.dataset.field = fieldName;
        input.dataset.type = fieldType;
        
        return input;
    }
    
    extractFieldValue(fieldElement, fieldType) {
        const text = fieldElement.textContent.trim();
        
        // Handle placeholder text
        if (text.startsWith('click to add')) {
            return fieldType === 'array' ? [] : '';
        }
        
        switch (fieldType) {
            case 'array':
                return text ? text.split(',').map(s => s.trim()).filter(s => s) : [];
            case 'number':
                return text ? parseFloat(text) : null;
            default:
                return text;
        }
    }
    
    attachInputListeners(input) {
        // Enhanced keyboard handling
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && input.tagName !== 'TEXTAREA') {
                e.preventDefault();
                this.saveEdit();
            } else if (e.key === 'Tab') {
                e.preventDefault();
                // Don't save on tab, just navigate
                this.navigateToNextField(e.shiftKey);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.cancelEdit();
            }
        });
        
        // Save on blur (when leaving field)
        input.addEventListener('blur', () => {
            // Small delay to allow tab navigation to work
            setTimeout(() => {
                if (this.currentEdit && this.currentEdit.input === input) {
                    this.saveEdit();
                }
            }, 100);
        });
        
        // Auto-save on input (debounced)
        if (this.options.autoSave) {
            input.addEventListener('input', () => {
                this.debouncedSave();
            });
        }
    }
    
    navigateToNextField(reverse = false) {
        const editableFields = Array.from(this.container.querySelectorAll('.metadata-value[data-field]:not(.readonly)'));
        const currentFieldName = this.currentEdit?.fieldName;
        const currentIndex = editableFields.findIndex(field => 
            field.dataset.field === currentFieldName
        );
        
        let nextIndex;
        if (reverse) {
            nextIndex = currentIndex > 0 ? currentIndex - 1 : editableFields.length - 1;
        } else {
            nextIndex = currentIndex < editableFields.length - 1 ? currentIndex + 1 : 0;
        }
        
        const nextField = editableFields[nextIndex];
        if (nextField) {
            const fieldName = nextField.dataset.field;
            const fieldType = nextField.dataset.type || 'text';
            
            // Cancel current edit without saving
            this.cancelEdit();
            
            // Start editing next field
            setTimeout(() => {
                this.startEdit(nextField, fieldName, fieldType);
            }, 10);
        }
    }
    
    debouncedSave() {
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }
        
        this.saveTimeout = setTimeout(() => {
            this.saveEdit();
        }, this.options.saveDelay);
    }
    
    async saveEdit() {
        if (!this.currentEdit) return Promise.resolve();
        
        const { fieldElement, input, fieldName, fieldType, originalValue } = this.currentEdit;
        const newValue = this.parseInputValue(input.value, fieldType);
        
        // Check if value actually changed
        if (this.valuesEqual(originalValue, newValue)) {
            this.cancelEdit();
            return Promise.resolve();
        }
        
        try {
            // Show saving indicator
            this.showSavingIndicator(fieldElement);
            
            // Make API call
            const response = await this.saveToAPI(fieldName, newValue);
            
            // Update field display
            this.updateFieldDisplay(fieldElement, newValue, fieldType);
            
            // Clean up edit state
            this.finishEdit();
            
            // Show success
            this.showSuccess();
            
            // Call callback
            if (this.options.onSave) {
                this.options.onSave(fieldName, newValue, originalValue);
            }
            
            return Promise.resolve(response);
            
        } catch (error) {
            console.error('Save error:', error);
            this.showError(error.message);
            
            // Call error callback
            if (this.options.onError) {
                this.options.onError(fieldName, error);
            }
            
            // Keep edit active for retry
            return Promise.reject(error);
        }
    }
    
    parseInputValue(inputValue, fieldType) {
        switch (fieldType) {
            case 'array':
                return inputValue ? inputValue.split(',').map(s => s.trim()).filter(s => s) : [];
            case 'number':
                return inputValue ? parseFloat(inputValue) : null;
            default:
                return inputValue.trim();
        }
    }
    
    valuesEqual(a, b) {
        if (Array.isArray(a) && Array.isArray(b)) {
            return a.length === b.length && a.every((val, i) => val === b[i]);
        }
        return a === b;
    }
    
    updateFieldDisplay(fieldElement, newValue, fieldType) {
        let displayValue;
        
        switch (fieldType) {
            case 'array':
                displayValue = Array.isArray(newValue) && newValue.length > 0 
                    ? newValue.join(', ') 
                    : 'click to add';
                break;
            default:
                displayValue = newValue || 'click to add';
                break;
        }
        
        fieldElement.textContent = displayValue;
    }
    
    async saveToAPI(fieldName, newValue) {
        const bookId = this.getBookId();
        const url = `${this.options.apiEndpoint}/${bookId}`;
        
        const response = await fetch(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                [fieldName]: newValue
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Check if response indicates success
        if (data.success === false) {
            throw new Error(data.error || 'Save failed');
        }
        
        return data;
    }
    
    getBookId() {
        // Extract book ID from URL or data attribute
        const bookIdElement = this.container.querySelector('[data-book-id]');
        if (bookIdElement) {
            return bookIdElement.dataset.bookId;
        }
        
        // Fallback: extract from URL
        const pathMatch = window.location.pathname.match(/\/book\/([^\/]+)/);
        return pathMatch ? pathMatch[1] : null;
    }
    
    cancelEdit() {
        if (!this.currentEdit) return;
        
        const { fieldElement, input } = this.currentEdit;
        
        // Remove input
        if (input.parentNode) {
            input.parentNode.removeChild(input);
        }
        
        // Show field again
        fieldElement.style.display = '';
        
        // Clear edit state
        this.currentEdit = null;
        
        // Clear save timeout
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
            this.saveTimeout = null;
        }
    }
    
    finishEdit() {
        if (!this.currentEdit) return;
        
        const { fieldElement, input } = this.currentEdit;
        
        // Remove input
        if (input.parentNode) {
            input.parentNode.removeChild(input);
        }
        
        // Show field again
        fieldElement.style.display = '';
        
        // Clear edit state
        this.currentEdit = null;
    }
    
    handleGlobalClick(e) {
        // Cancel edit if clicking outside
        if (this.currentEdit && !this.currentEdit.input.contains(e.target)) {
            this.saveEdit();
        }
    }
    
    handleGlobalKeydown(e) {
        if (e.key === 'Escape' && this.currentEdit) {
            this.cancelEdit();
        }
    }
    
    showSavingIndicator(fieldElement) {
        fieldElement.classList.add('saving');
    }
    
    showSuccess() {
        this.showFeedback('Saved', 'success');
    }
    
    showError(message) {
        this.showFeedback(`Error: ${message}`, 'error');
    }
    
    showFeedback(message, type = 'info') {
        // Create or update feedback element
        let feedback = document.getElementById('metadata-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.id = 'metadata-feedback';
            feedback.className = 'metadata-feedback';
            document.body.appendChild(feedback);
        }
        
        feedback.textContent = message;
        feedback.className = `metadata-feedback ${type}`;
        feedback.style.display = 'block';
        
        // Auto-hide after 3 seconds
        setTimeout(() => {
            feedback.style.display = 'none';
        }, 3000);
    }
    
    // Static factory method
    static create(containerId, options) {
        return new MetadataEditor(containerId, options);
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MetadataEditor;
} 