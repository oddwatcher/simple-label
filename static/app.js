/**
 * Image Labeling Tool - Main Application
 */

class LabelingTool {
    constructor() {
        this.images = [];
        this.currentImageIndex = -1;
        this.currentImage = null;
        this.annotations = [];
        this.labels = [];
        this.selectedLabel = null;
        this.selectedAnnotation = null;
        this.datasetName = null;
        
        // Canvas state
        this.canvas = document.getElementById('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.canvasContainer = document.getElementById('canvasContainer');
        this.isDrawing = false;
        this.isDragging = false;
        this.dragStart = { x: 0, y: 0 };
        this.currentBox = null;
        this.mode = 'select'; // 'draw' or 'select'
        this.dragOffset = { x: 0, y: 0 };
        this.resizeHandle = null;
        this.handleSize = 8;
        
        // Colors for labels
        this.labelColors = [
            '#e94560', '#4ade80', '#fbbf24', '#60a5fa', 
            '#a78bfa', '#f472b6', '#2dd4bf', '#fb923c'
        ];
        this.labelColorMap = {};
        this.hiddenLabels = new Set(); // Track hidden label names
        
        this.init();
    }
    
    async init() {
        // Get dataset name from URL
        const urlParams = new URLSearchParams(window.location.search);
        this.datasetName = urlParams.get('dataset');
        
        if (!this.datasetName) {
            // Redirect to dataset selection if no dataset specified
            window.location.href = '/';
            return;
        }
        
        this.setupEventListeners();
        await this.loadImages();
        await this.loadLabels();
        this.setupKeyboardShortcuts();
        this.updateModeButtonsState(); // Initialize button states (disabled since no image selected)
    }
    
    setupEventListeners() {
        // Toolbar buttons
        document.getElementById('prevBtn').addEventListener('click', () => this.prevImage());
        document.getElementById('nextBtn').addEventListener('click', () => this.nextImage());
        document.getElementById('drawBtn').addEventListener('click', () => this.setMode('draw'));
        document.getElementById('selectBtn').addEventListener('click', () => this.setMode('select'));
        document.getElementById('uploadBtn').addEventListener('click', () => this.showUploadModal());
        document.getElementById('backToDatasetsBtn').addEventListener('click', () => {
            window.location.href = '/';
        });
        document.getElementById('deleteBtn').addEventListener('click', () => this.deleteCurrentImage());
        
        // Export dropdown
        const exportBtn = document.getElementById('exportBtn');
        const exportMenu = document.getElementById('exportMenu');
        if (exportBtn && exportMenu) {
            exportBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                exportMenu.classList.toggle('show');
            });
            
            // Close menu when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.export-dropdown')) {
                    exportMenu.classList.remove('show');
                }
            });
            
            // Handle export format selection
            exportMenu.querySelectorAll('.export-item').forEach(item => {
                item.addEventListener('click', () => {
                    const format = item.getAttribute('data-format');
                    this.exportDataset(format);
                    exportMenu.classList.remove('show');
                });
            });
        }
        
        // Label management
        document.getElementById('addLabelBtn').addEventListener('click', () => this.addNewLabel());
        document.getElementById('newLabelInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addNewLabel();
        });
        
        // Search
        document.getElementById('searchBox').addEventListener('input', (e) => this.filterImages(e.target.value));
        
        // Canvas events
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.canvas.addEventListener('dblclick', (e) => this.handleDoubleClick(e));
        
        // Upload modal
        document.getElementById('closeUploadBtn').addEventListener('click', () => this.hideUploadModal());
        document.getElementById('dropZone').addEventListener('click', () => document.getElementById('fileInput').click());
        document.getElementById('fileInput').addEventListener('change', (e) => this.handleFileSelect(e));
        
        // Drag and drop
        const dropZone = document.getElementById('dropZone');
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            this.handleFiles(e.dataTransfer.files);
        });
        
        // Window resize
        window.addEventListener('resize', () => {
            this.resizeCanvas();
            // Update virtual scroll on resize
            if (this.images.length > 0) {
                const container = document.getElementById('imageList');
                if (container) {
                    this.containerHeight = container.clientHeight;
                    this.visibleCount = Math.ceil(this.containerHeight / this.itemHeight) + 5;
                    this.renderVisibleImages();
                }
            }
        });
    }
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input
            if (e.target.tagName === 'INPUT') return;
            
            switch(e.key) {
                case 'ArrowLeft':
                    e.preventDefault();
                    this.prevImage();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    this.nextImage();
                    break;
                case 'd':
                case 'D':
                    this.setMode('draw');
                    break;
                case 's':
                case 'S':
                    this.setMode('select');
                    break;
                case 'Delete':
                    if (this.selectedAnnotation !== null) {
                        const ann = this.annotations[this.selectedAnnotation];
                        const labelName = ann.label || ann.label_name || 'unknown';
                        // Only delete if not hidden
                        if (!this.hiddenLabels.has(labelName)) {
                            this.deleteAnnotation(this.selectedAnnotation);
                        }
                    } else {
                        this.deleteCurrentImage();
                    }
                    break;
                case 'Escape':
                    this.selectedAnnotation = null;
                    this.isDrawing = false;
                    this.currentBox = null;
                    this.render();
                    break;
            }
            

        });
    }
    
    async loadImages() {
        try {
            const response = await fetch(`/api/datasets/${this.datasetName}/images`);
            this.images = await response.json();
            this.renderImageList();
        } catch (error) {
            console.error('Failed to load images:', error);
        }
    }
    
    async loadLabels() {
        try {
            const response = await fetch(`/api/datasets/${this.datasetName}/labels?t=${Date.now()}`);
            const labelsData = await response.json();
            // Store full label objects with id, name, color, count
            this.labels = labelsData;
            this.labelMap = {}; // Map label name to label object
            labelsData.forEach(label => {
                this.labelMap[label.name] = label;
            });
            this.renderLabelList();
        } catch (error) {
            console.error('Failed to load labels:', error);
        }
    }
    
    getLabelColor(labelName) {
        if (this.labelMap && this.labelMap[labelName]) {
            return this.labelMap[labelName].color;
        }
        // Fallback color
        return '#e94560';
    }
    
    getLabelByName(name) {
        return this.labelMap ? this.labelMap[name] : null;
    }
    
    // Virtual scrolling configuration
    initVirtualScroll() {
        this.itemHeight = 45; // Height of each image item including margin
        this.containerHeight = 0;
        this.visibleCount = 0;
        this.scrollTop = 0;
        this.filteredImages = [...this.images]; // For search filtering
        
        const container = document.getElementById('imageList');
        this.containerHeight = container.clientHeight;
        this.visibleCount = Math.ceil(this.containerHeight / this.itemHeight) + 5; // Buffer of 5 items
        
        // Create spacer for total height
        this.totalHeight = this.filteredImages.length * this.itemHeight;
        
        container.addEventListener('scroll', (e) => {
            this.scrollTop = e.target.scrollTop;
            this.renderVisibleImages();
        });
        
        // Initial render
        this.renderVisibleImages();
    }
    
    renderVisibleImages() {
        const container = document.getElementById('imageList');
        const startIndex = Math.floor(this.scrollTop / this.itemHeight);
        const endIndex = Math.min(startIndex + this.visibleCount, this.filteredImages.length);
        
        // Clear container but keep scroll position
        const scrollPos = container.scrollTop;
        container.innerHTML = '';
        
        // Add top spacer
        const topSpacer = document.createElement('div');
        topSpacer.style.height = `${startIndex * this.itemHeight}px`;
        container.appendChild(topSpacer);
        
        // Render only visible items
        for (let i = startIndex; i < endIndex; i++) {
            const img = this.filteredImages[i];
            const originalIndex = this.images.indexOf(img);
            
            const item = document.createElement('div');
            item.className = `image-item ${img.has_annotation ? 'has-annotation' : 'no-annotation'} ${originalIndex === this.currentImageIndex ? 'active' : ''}`;
            item.style.height = `${this.itemHeight - 5}px`; // Account for margin
            item.innerHTML = `<span class="image-name">${img.filename}</span>`;
            item.addEventListener('click', () => this.selectImage(originalIndex));
            container.appendChild(item);
        }
        
        // Add bottom spacer
        const bottomSpacer = document.createElement('div');
        bottomSpacer.style.height = `${(this.filteredImages.length - endIndex) * this.itemHeight}px`;
        container.appendChild(bottomSpacer);
        
        // Restore scroll position if needed
        if (scrollPos !== this.scrollTop) {
            container.scrollTop = this.scrollTop;
        }
    }
    
    renderImageList() {
        // Use virtual scrolling instead of rendering all items
        this.filteredImages = [...this.images];
        this.initVirtualScroll();
    }
    
    renderLabelList() {
        const container = document.getElementById('labelList');
        container.innerHTML = '';

        this.labels.forEach((labelObj) => {
            const isHidden = this.hiddenLabels.has(labelObj.name);
            const item = document.createElement('div');
            item.className = `label-item ${labelObj.name === this.selectedLabel ? 'selected' : ''} ${isHidden ? 'hidden-label' : ''}`;
            item.innerHTML = `
                <div class="label-color" style="background: ${isHidden ? '#666' : labelObj.color}"></div>
                <span class="label-name" style="opacity: ${isHidden ? '0.5' : '1'}">${labelObj.id}:${labelObj.name} (${labelObj.count})</span>
                <button class="icon-btn visibility-label-btn" title="${isHidden ? 'Show' : 'Hide'} Label">${isHidden ? '👁' : '👁'}</button>
                <button class="icon-btn rename-label-btn" title="Rename Label">✎</button>
                <button class="icon-btn delete-label-btn" title="Delete Label">🗑</button>
            `;
            
            // Add click handler for the label item (selecting the label)
            item.addEventListener('click', (e) => {
                // Don't trigger if clicking action buttons
                if (e.target.classList.contains('rename-label-btn') || 
                    e.target.classList.contains('delete-label-btn') ||
                    e.target.classList.contains('visibility-label-btn')) return;
                
                this.selectedLabel = labelObj.name;
                this.renderLabelList();
                if (this.mode === 'draw' && this.selectedAnnotation !== null) {
                    // Change label of selected annotation
                    this.annotations[this.selectedAnnotation].label = labelObj.name;
                    this.saveAnnotations();
                    this.render();
                }
            });
            
            // Add click handler for the visibility button
            const visibilityBtn = item.querySelector('.visibility-label-btn');
            visibilityBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleLabelVisibility(labelObj.name);
            });
            
            // Add click handler for the rename button
            const renameBtn = item.querySelector('.rename-label-btn');
            renameBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.renameLabel(labelObj.name);
            });
            
            // Add click handler for the delete button
            const deleteBtn = item.querySelector('.delete-label-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteLabel(labelObj.name);
            });
            
            container.appendChild(item);
        });
    }
    
    toggleLabelVisibility(labelName) {
        if (this.hiddenLabels.has(labelName)) {
            this.hiddenLabels.delete(labelName);
        } else {
            this.hiddenLabels.add(labelName);
        }
        this.renderLabelList();
        this.render();
    }
    
    async renameLabel(oldName) {
        const newName = prompt(`Rename label "${oldName}" to:`, oldName);
        if (!newName || newName === oldName) return;
        
        try {
            const response = await fetch(`/api/datasets/${this.datasetName}/labels`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    old_name: oldName,
                    new_name: newName
                })
            });
            
            if (response.ok) {
                // Update selected label if it was the renamed one
                if (this.selectedLabel === oldName) {
                    this.selectedLabel = newName;
                }
                
                // Update annotations that use this label
                this.annotations.forEach(ann => {
                    if (ann.label === oldName) {
                        ann.label = newName;
                    }
                });
                
                // Reload labels (this also calls renderLabelList) and refresh UI
                await this.loadLabels();
                this.render();
                this.renderAnnotationsList();
            } else {
                const error = await response.json();
                alert('Failed to rename label: ' + (error.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Failed to rename label:', error);
            alert('Failed to rename label');
        }
    }
    
    async deleteLabel(labelName) {
        if (!confirm(`Are you sure you want to delete the label "${labelName}"?\n\nThis will remove ALL annotations with this label from the dataset. This action cannot be undone.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/datasets/${this.datasetName}/labels`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    delete_name: labelName
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                
                // Clear selected label if it was the deleted one
                if (this.selectedLabel === labelName) {
                    this.selectedLabel = null;
                }
                
                // Remove annotations with this label from current image
                this.annotations = this.annotations.filter(ann => ann.label !== labelName);
                this.selectedAnnotation = null;
                
                // Reload labels and refresh UI
                await this.loadLabels();
                this.render();
                this.renderAnnotationsList();
                
                alert(`Label "${labelName}" deleted.\nRemoved ${result.deleted_annotations} annotations from ${result.modified_files} files.`);
            } else {
                const error = await response.json();
                alert('Failed to delete label: ' + (error.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Failed to delete label:', error);
            alert('Failed to delete label');
        }
    }
    
    renderAnnotationsList() {
        const container = document.getElementById('annotationsList');
        container.innerHTML = '';
        
        this.annotations.forEach((ann, index) => {
            const labelName = ann.label || ann.label_name || 'unknown';
            const isHidden = this.hiddenLabels.has(labelName);
            const item = document.createElement('div');
            item.className = `annotation-item ${index === this.selectedAnnotation ? 'selected' : ''} ${isHidden ? 'hidden-annotation' : ''}`;
            item.innerHTML = `
                <div class="annotation-info">
                    <div class="annotation-label" style="color: ${isHidden ? '#666' : this.getLabelColor(labelName)}; opacity: ${isHidden ? '0.5' : '1'}">${labelName} ${isHidden ? '(hidden)' : ''}</div>
                    <div class="annotation-coords">
                        [${Math.round(ann.xmin)}, ${Math.round(ann.ymin)}] - [${Math.round(ann.xmax)}, ${Math.round(ann.ymax)}]
                    </div>
                </div>
                <div class="annotation-actions">
                    <button class="icon-btn" title="Edit Label" onclick="event.stopPropagation(); tool.changeAnnotationLabel(${index})">✎</button>
                    <button class="icon-btn" title="Delete" onclick="event.stopPropagation(); tool.deleteAnnotation(${index})">🗑</button>
                </div>
            `;
            item.addEventListener('click', () => {
                this.selectedAnnotation = index;
                this.render();
                this.renderAnnotationsList();
            });
            container.appendChild(item);
        });
        
        // Update info panel
        document.getElementById('infoAnnotationCount').textContent = this.annotations.length;
    }
    
    async selectImage(index) {
        if (index < 0 || index >= this.images.length) return;
        
        // Save current annotations before switching
        if (this.currentImageIndex !== -1) {
            await this.saveAnnotations();
        }
        
        this.currentImageIndex = index;
        this.currentImage = this.images[index];
        this.selectedAnnotation = null;
        this.annotations = [];
        
        // Update UI
        this.renderVisibleImages(); // Re-render to update active state
        document.getElementById('infoImageName').textContent = this.currentImage.filename;
        
        // Scroll selected image into view
        this.scrollToImage(index);
        
        // Load image
        await this.loadCurrentImage();
        
        // Load annotations
        await this.loadAnnotations();
        
        // Update status
        const status = this.currentImage.has_annotation ? 'Annotated' : 'Not Annotated';
        document.getElementById('infoStatus').textContent = status;
        
        // Reset to select mode and update button states
        this.setMode('select');
        this.updateModeButtonsState();
    }
    
    scrollToImage(index) {
        // Check if image is in filtered list
        const filteredIndex = this.filteredImages.indexOf(this.images[index]);
        if (filteredIndex === -1) return;
        
        const container = document.getElementById('imageList');
        const itemTop = filteredIndex * this.itemHeight;
        const itemBottom = itemTop + this.itemHeight;
        const containerTop = container.scrollTop;
        const containerBottom = containerTop + container.clientHeight;
        
        // Scroll if item is not fully visible
        if (itemTop < containerTop) {
            container.scrollTop = itemTop;
            this.scrollTop = itemTop;
        } else if (itemBottom > containerBottom) {
            container.scrollTop = itemBottom - container.clientHeight;
            this.scrollTop = container.scrollTop;
        }
    }
    
    async loadCurrentImage() {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                this.canvas.width = img.width;
                this.canvas.height = img.height;
                this.canvas.style.display = 'block';
                document.querySelector('.canvas-placeholder').style.display = 'none';
                
                document.getElementById('infoDimensions').textContent = `${img.width} × ${img.height}`;
                
                this.currentImageData = img;
                this.render();
                resolve();
            };
            img.onerror = reject;
            img.src = `/api/datasets/${this.datasetName}/image/${this.currentImage.id}`;
        });
    }
    
    async loadAnnotations() {
        try {
            const response = await fetch(`/api/datasets/${this.datasetName}/annotation/${this.currentImage.id}`);
            const data = await response.json();
            
            this.annotations = data.objects || [];
            this.render();
            this.renderAnnotationsList();
        } catch (error) {
            console.error('Failed to load annotations:', error);
        }
    }
    
    async saveAnnotations() {
        if (!this.currentImage) return;
        
        try {
            const response = await fetch(`/api/datasets/${this.datasetName}/annotation/${this.currentImage.id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    width: this.canvas.width,
                    height: this.canvas.height,
                    objects: this.annotations
                })
            });
            
            if (response.ok) {
                // Update has_annotation status
                this.currentImage.has_annotation = this.annotations.length > 0;
                this.renderImageList();
                document.getElementById('infoStatus').textContent = 
                    this.annotations.length > 0 ? 'Annotated' : 'Not Annotated';
            } else {
                const error = await response.json();
                if (error.error === 'Invalid labels found') {
                    alert(`Error: Invalid labels found: ${error.invalid_labels.join(', ')}\n\nValid labels are: ${error.valid_labels.join(', ')}`);
                } else {
                    alert('Failed to save annotations: ' + (error.error || 'Unknown error'));
                }
            }
        } catch (error) {
            console.error('Failed to save annotations:', error);
        }
    }
    
    render() {
        if (!this.currentImageData) return;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw image
        this.ctx.drawImage(this.currentImageData, 0, 0);
        
        // Draw annotations (skip hidden labels)
        this.annotations.forEach((ann, index) => {
            const isSelected = index === this.selectedAnnotation;
            const labelName = ann.label || ann.label_name || 'unknown';
            
            // Skip if this label is hidden
            if (this.hiddenLabels.has(labelName)) return;
            
            const color = this.getLabelColor(labelName);
            
            // Draw box
            this.ctx.strokeStyle = color;
            this.ctx.lineWidth = isSelected ? 3 : 2;
            this.ctx.strokeRect(ann.xmin, ann.ymin, ann.xmax - ann.xmin, ann.ymax - ann.ymin);
            
            // Fill with transparency
            this.ctx.fillStyle = color + '20';
            this.ctx.fillRect(ann.xmin, ann.ymin, ann.xmax - ann.xmin, ann.ymax - ann.ymin);
            
            // Draw label
            this.ctx.fillStyle = color;
            this.ctx.font = 'bold 14px sans-serif';
            const text = labelName;
            const textWidth = this.ctx.measureText(text).width;
            this.ctx.fillRect(ann.xmin, ann.ymin - 20, textWidth + 10, 20);
            this.ctx.fillStyle = '#fff';
            this.ctx.fillText(text, ann.xmin + 5, ann.ymin - 5);
            
            // Draw resize handles if selected
            if (isSelected) {
                this.drawResizeHandles(ann);
            }
        });
        
        // Draw current box being created
        if (this.currentBox) {
            this.ctx.strokeStyle = this.selectedLabel ? this.getLabelColor(this.selectedLabel) : '#e94560';
            this.ctx.lineWidth = 2;
            this.ctx.setLineDash([5, 5]);
            this.ctx.strokeRect(
                this.currentBox.xmin,
                this.currentBox.ymin,
                this.currentBox.xmax - this.currentBox.xmin,
                this.currentBox.ymax - this.currentBox.ymin
            );
            this.ctx.setLineDash([]);
        }
    }
    
    drawResizeHandles(ann) {
        const handles = [
            { x: ann.xmin, y: ann.ymin, cursor: 'nw-resize' },
            { x: (ann.xmin + ann.xmax) / 2, y: ann.ymin, cursor: 'n-resize' },
            { x: ann.xmax, y: ann.ymin, cursor: 'ne-resize' },
            { x: ann.xmax, y: (ann.ymin + ann.ymax) / 2, cursor: 'e-resize' },
            { x: ann.xmax, y: ann.ymax, cursor: 'se-resize' },
            { x: (ann.xmin + ann.xmax) / 2, y: ann.ymax, cursor: 's-resize' },
            { x: ann.xmin, y: ann.ymax, cursor: 'sw-resize' },
            { x: ann.xmin, y: (ann.ymin + ann.ymax) / 2, cursor: 'w-resize' }
        ];
        
        this.ctx.fillStyle = '#fff';
        this.ctx.strokeStyle = '#e94560';
        this.ctx.lineWidth = 1;
        
        handles.forEach(handle => {
            this.ctx.fillRect(handle.x - 4, handle.y - 4, 8, 8);
            this.ctx.strokeRect(handle.x - 4, handle.y - 4, 8, 8);
        });
    }
    
    getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }
    
    getResizeHandle(pos, ann) {
        const handles = [
            { x: ann.xmin, y: ann.ymin, idx: 0 },
            { x: (ann.xmin + ann.xmax) / 2, y: ann.ymin, idx: 1 },
            { x: ann.xmax, y: ann.ymin, idx: 2 },
            { x: ann.xmax, y: (ann.ymin + ann.ymax) / 2, idx: 3 },
            { x: ann.xmax, y: ann.ymax, idx: 4 },
            { x: (ann.xmin + ann.xmax) / 2, y: ann.ymax, idx: 5 },
            { x: ann.xmin, y: ann.ymax, idx: 6 },
            { x: ann.xmin, y: (ann.ymin + ann.ymax) / 2, idx: 7 }
        ];
        
        for (const handle of handles) {
            const dist = Math.sqrt(Math.pow(pos.x - handle.x, 2) + Math.pow(pos.y - handle.y, 2));
            if (dist <= this.handleSize) {
                return handle.idx;
            }
        }
        return null;
    }
    
    isInsideBox(pos, ann) {
        return pos.x >= ann.xmin && pos.x <= ann.xmax && pos.y >= ann.ymin && pos.y <= ann.ymax;
    }
    
    handleMouseDown(e) {
        if (!this.currentImage) return;
        
        const pos = this.getMousePos(e);
        
        if (this.mode === 'draw') {
            // Start drawing new box
            this.isDrawing = true;
            this.dragStart = pos;
            this.currentBox = {
                xmin: pos.x,
                ymin: pos.y,
                xmax: pos.x,
                ymax: pos.y
            };
        } else {
            // Select mode
            // Check if clicking on a resize handle of selected annotation (skip if hidden)
            if (this.selectedAnnotation !== null) {
                const ann = this.annotations[this.selectedAnnotation];
                const labelName = ann.label || ann.label_name || 'unknown';
                if (!this.hiddenLabels.has(labelName)) {
                    const handle = this.getResizeHandle(pos, ann);
                    if (handle !== null) {
                        this.isDragging = true;
                        this.resizeHandle = handle;
                        this.dragStart = pos;
                        return;
                    }
                }
            }
            
            // Check if clicking inside any box (skip hidden labels)
            let clickedAnnotation = null;
            for (let i = this.annotations.length - 1; i >= 0; i--) {
                const ann = this.annotations[i];
                const labelName = ann.label || ann.label_name || 'unknown';
                // Skip hidden labels
                if (this.hiddenLabels.has(labelName)) continue;
                
                if (this.isInsideBox(pos, ann)) {
                    clickedAnnotation = i;
                    break;
                }
            }
            
            if (clickedAnnotation !== null) {
                this.selectedAnnotation = clickedAnnotation;
                this.isDragging = true;
                this.resizeHandle = null;
                this.dragStart = pos;
                this.dragOffset = {
                    x: pos.x - this.annotations[clickedAnnotation].xmin,
                    y: pos.y - this.annotations[clickedAnnotation].ymin
                };
            } else {
                this.selectedAnnotation = null;
            }
            
            this.render();
            this.renderAnnotationsList();
        }
    }
    
    handleMouseMove(e) {
        if (!this.currentImage) return;
        
        const pos = this.getMousePos(e);
        
        if (this.isDrawing && this.currentBox) {
            this.currentBox.xmax = pos.x;
            this.currentBox.ymax = pos.y;
            this.render();
        } else if (this.isDragging && this.selectedAnnotation !== null) {
            const ann = this.annotations[this.selectedAnnotation];
            const labelName = ann.label || ann.label_name || 'unknown';
            
            // Don't drag hidden annotations
            if (this.hiddenLabels.has(labelName)) {
                this.isDragging = false;
                this.selectedAnnotation = null;
                return;
            }
            
            if (this.resizeHandle !== null) {
                // Resizing
                switch(this.resizeHandle) {
                    case 0: // Top-left
                        ann.xmin = Math.min(pos.x, ann.xmax - 10);
                        ann.ymin = Math.min(pos.y, ann.ymax - 10);
                        break;
                    case 1: // Top
                        ann.ymin = Math.min(pos.y, ann.ymax - 10);
                        break;
                    case 2: // Top-right
                        ann.xmax = Math.max(pos.x, ann.xmin + 10);
                        ann.ymin = Math.min(pos.y, ann.ymax - 10);
                        break;
                    case 3: // Right
                        ann.xmax = Math.max(pos.x, ann.xmin + 10);
                        break;
                    case 4: // Bottom-right
                        ann.xmax = Math.max(pos.x, ann.xmin + 10);
                        ann.ymax = Math.max(pos.y, ann.ymin + 10);
                        break;
                    case 5: // Bottom
                        ann.ymax = Math.max(pos.y, ann.ymin + 10);
                        break;
                    case 6: // Bottom-left
                        ann.xmin = Math.min(pos.x, ann.xmax - 10);
                        ann.ymax = Math.max(pos.y, ann.ymin + 10);
                        break;
                    case 7: // Left
                        ann.xmin = Math.min(pos.x, ann.xmax - 10);
                        break;
                }
            } else {
                // Moving
                const width = ann.xmax - ann.xmin;
                const height = ann.ymax - ann.ymin;
                ann.xmin = pos.x - this.dragOffset.x;
                ann.ymin = pos.y - this.dragOffset.y;
                ann.xmax = ann.xmin + width;
                ann.ymax = ann.ymin + height;
            }
            
            // Clamp to canvas
            ann.xmin = Math.max(0, Math.min(this.canvas.width - 10, ann.xmin));
            ann.ymin = Math.max(0, Math.min(this.canvas.height - 10, ann.ymin));
            ann.xmax = Math.max(ann.xmin + 10, Math.min(this.canvas.width, ann.xmax));
            ann.ymax = Math.max(ann.ymin + 10, Math.min(this.canvas.height, ann.ymax));
            
            this.render();
            this.renderAnnotationsList();
        } else if (this.mode === 'select' && this.selectedAnnotation !== null) {
            // Update cursor (skip if hidden)
            const ann = this.annotations[this.selectedAnnotation];
            const labelName = ann.label || ann.label_name || 'unknown';
            if (this.hiddenLabels.has(labelName)) {
                this.canvas.style.cursor = 'default';
                return;
            }
            const handle = this.getResizeHandle(pos, ann);
            if (handle !== null) {
                const cursors = ['nw-resize', 'n-resize', 'ne-resize', 'e-resize', 
                               'se-resize', 's-resize', 'sw-resize', 'w-resize'];
                this.canvas.style.cursor = cursors[handle];
            } else if (this.isInsideBox(pos, ann)) {
                this.canvas.style.cursor = 'move';
            } else {
                this.canvas.style.cursor = 'default';
            }
        }
    }
    
    handleMouseUp(e) {
        if (this.isDrawing && this.currentBox) {
            // Finish drawing
            const width = Math.abs(this.currentBox.xmax - this.currentBox.xmin);
            const height = Math.abs(this.currentBox.ymax - this.currentBox.ymin);
            
            if (width > 10 && height > 10) {
                // Normalize box coordinates
                // Ensure we use a valid label from the dataset
                let labelName = this.selectedLabel;
                if (!labelName || !this.labels.find(l => l.name === labelName)) {
                    // If no valid label selected, use the first available label
                    labelName = this.labels[0] && this.labels[0].name;
                }
                
                if (!labelName) {
                    alert('No labels defined in this dataset. Please add a label first.');
                    this.isDrawing = false;
                    this.currentBox = null;
                    this.render();
                    return;
                }
                
                const newBox = {
                    label: labelName,
                    xmin: Math.min(this.currentBox.xmin, this.currentBox.xmax),
                    ymin: Math.min(this.currentBox.ymin, this.currentBox.ymax),
                    xmax: Math.max(this.currentBox.xmin, this.currentBox.xmax),
                    ymax: Math.max(this.currentBox.ymin, this.currentBox.ymax)
                };
                
                this.annotations.push(newBox);
                this.selectedAnnotation = this.annotations.length - 1;
                this.saveAnnotations();
                this.renderAnnotationsList();
            }
            
            this.isDrawing = false;
            this.currentBox = null;
            this.render();
        } else if (this.isDragging) {
            this.isDragging = false;
            this.resizeHandle = null;
            this.saveAnnotations();
        }
    }
    
    handleDoubleClick(e) {
        if (this.selectedAnnotation !== null) {
            this.changeAnnotationLabel(this.selectedAnnotation);
        }
    }
    
    changeAnnotationLabel(index) {
        const ann = this.annotations[index];
        const currentLabel = ann.label || ann.label_name || 'unknown';
        const currentLabelObj = this.labels.find(l => l.name === currentLabel);
        const currentId = currentLabelObj ? currentLabelObj.id : '0';
        
        // Show available labels with IDs
        const labelList = this.labels.map(l => `${l.id}:${l.name}`).join(', ');
        const newLabelId = prompt(`Available labels (ID:Name):\n${labelList}\n\nEnter label ID:`, currentId);
        
        if (newLabelId && newLabelId.trim()) {
            const trimmedId = newLabelId.trim();
            
            // Find label by ID
            const existingLabel = this.labels.find(l => l.id === trimmedId);
            if (!existingLabel) {
                alert(`Label ID "${trimmedId}" does not exist in this dataset. Available IDs: ${this.labels.map(l => l.id).join(', ')}`);
                return;
            }
            
            ann.label = existingLabel.name;
            this.saveAnnotations();
            this.render();
            this.renderAnnotationsList();
        }
    }
    
    async addNewLabel() {
        const input = document.getElementById('newLabelInput');
        const labelName = input.value.trim();
        
        if (!labelName) return;
        
        if (this.labels.find(l => l.name === labelName)) {
            alert(`Label "${labelName}" already exists`);
            return;
        }
        
        try {
            // Add label to server
            const response = await fetch(`/api/datasets/${this.datasetName}/labels`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ labels: [labelName] })
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.added.length > 0) {
                    // Reload labels from server to get proper IDs and counts
                    await this.loadLabels();
                    input.value = '';
                }
            } else {
                const error = await response.json();
                alert('Failed to add label: ' + (error.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Failed to add label:', error);
            alert('Failed to add label');
        }
    }
    
    deleteAnnotation(index) {
        this.annotations.splice(index, 1);
        if (this.selectedAnnotation === index) {
            this.selectedAnnotation = null;
        } else if (this.selectedAnnotation > index) {
            this.selectedAnnotation--;
        }
        this.saveAnnotations();
        this.render();
        this.renderAnnotationsList();
    }
    
    setMode(mode) {
        // Only allow mode change if an image is selected
        if (!this.currentImage) {
            return;
        }
        
        this.mode = mode;
        this.isDrawing = false;
        this.currentBox = null;
        
        document.getElementById('drawBtn').classList.toggle('btn-primary', mode === 'draw');
        document.getElementById('drawBtn').classList.toggle('btn-secondary', mode !== 'draw');
        document.getElementById('selectBtn').classList.toggle('btn-primary', mode === 'select');
        document.getElementById('selectBtn').classList.toggle('btn-secondary', mode !== 'select');
        
        this.canvas.style.cursor = mode === 'draw' ? 'crosshair' : 'default';
    }
    
    updateModeButtonsState() {
        const drawBtn = document.getElementById('drawBtn');
        const selectBtn = document.getElementById('selectBtn');
        
        if (!this.currentImage) {
            // Disable buttons when no image is selected
            drawBtn.disabled = true;
            selectBtn.disabled = true;
            drawBtn.style.opacity = '0.5';
            selectBtn.style.opacity = '0.5';
            drawBtn.style.cursor = 'not-allowed';
            selectBtn.style.cursor = 'not-allowed';
        } else {
            // Enable buttons when an image is selected
            drawBtn.disabled = false;
            selectBtn.disabled = false;
            drawBtn.style.opacity = '1';
            selectBtn.style.opacity = '1';
            drawBtn.style.cursor = 'pointer';
            selectBtn.style.cursor = 'pointer';
        }
    }
    
    prevImage() {
        if (this.currentImageIndex > 0) {
            this.selectImage(this.currentImageIndex - 1);
        }
    }
    
    nextImage() {
        if (this.currentImageIndex < this.images.length - 1) {
            this.selectImage(this.currentImageIndex + 1);
        }
    }
    
    filterImages(query) {
        // Debounce search
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        this.searchTimeout = setTimeout(() => {
            const lowerQuery = query.toLowerCase();
            if (!lowerQuery) {
                this.filteredImages = [...this.images];
            } else {
                this.filteredImages = this.images.filter(img => 
                    img.filename.toLowerCase().includes(lowerQuery)
                );
            }
            // Reset scroll and re-render
            this.scrollTop = 0;
            const container = document.getElementById('imageList');
            if (container) {
                container.scrollTop = 0;
            }
            this.renderVisibleImages();
        }, 300); // 300ms debounce
    }
    
    async deleteCurrentImage() {
        if (!this.currentImage) return;
        
        if (confirm(`Delete image "${this.currentImage.filename}"?`)) {
            try {
                const response = await fetch(`/api/datasets/${this.datasetName}/image/${this.currentImage.id}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    this.images.splice(this.currentImageIndex, 1);
                    this.currentImage = null;
                    this.currentImageIndex = -1;
                    this.annotations = [];
                    this.canvas.style.display = 'none';
                    document.querySelector('.canvas-placeholder').style.display = 'block';
                    this.renderImageList();
                    this.renderAnnotationsList();
                    this.updateModeButtonsState();
                }
            } catch (error) {
                console.error('Failed to delete image:', error);
            }
        }
    }
    
    showUploadModal() {
        document.getElementById('uploadModal').classList.add('active');
    }
    
    hideUploadModal() {
        document.getElementById('uploadModal').classList.remove('active');
    }
    
    handleFileSelect(e) {
        this.handleFiles(e.target.files);
    }
    
    async handleFiles(files) {
        const imageFiles = Array.from(files).filter(file => file.type.startsWith('image/'));
        
        for (const file of imageFiles) {
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch(`/api/datasets/${this.datasetName}/upload`, {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const result = await response.json();
                    this.images.push({
                        id: result.id,
                        filename: result.filename,
                        has_annotation: false
                    });
                }
            } catch (error) {
                console.error('Failed to upload file:', error);
            }
        }

        this.renderImageList();
        this.hideUploadModal();

        // Select the first newly uploaded image
        if (imageFiles.length > 0) {
            this.selectImage(this.images.length - imageFiles.length);
        }
    }
    
    async exportDataset(format) {
        try {
            const response = await fetch(`/api/datasets/${this.datasetName}/export/${format}`);
            if (response.ok) {
                const result = await response.json();
                alert(`Export info:\n${result.note || 'Dataset exported'}`);
            }
        } catch (error) {
            console.error('Failed to export dataset:', error);
        }
    }
    
    resizeCanvas() {
        // Canvas is sized to image dimensions, but we can adjust the display size
        if (this.currentImageData) {
            this.render();
        }
    }
    
}

// Initialize tool
const tool = new LabelingTool();
