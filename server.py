#!/usr/bin/env python3
"""
Image Labeling Tool - Flask Web Server
Uses YOLO format as intermediate: images/*.jpg + labels/*.txt + metadata.json
"""

import os
import json
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configuration
VIEWER_PATH = Path(__file__).parent.resolve()
DATASETS_PATH = VIEWER_PATH / 'datasets'
DATASETS_REGISTRY = VIEWER_PATH / 'datasets.json'
TEMP_DIR = VIEWER_PATH / 'temp'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp', 'gif'}

# Ensure directories exist
DATASETS_PATH.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ==================== DATASET REGISTRY ====================

def load_datasets_registry():
    """Load datasets registry, reconstruct if missing"""
    if DATASETS_REGISTRY.exists():
        try:
            with open(DATASETS_REGISTRY, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # File exists but is corrupted
            pass
    
    # Registry missing or corrupted, reconstruct from datasets directory
    return reconstruct_datasets_registry()

def reconstruct_datasets_registry():
    """Reconstruct datasets.json by scanning datasets directory"""
    registry = {'datasets': {}, 'active_dataset': None, 'version': '1.0'}
    
    if not DATASETS_PATH.exists():
        DATASETS_PATH.mkdir(parents=True, exist_ok=True)
        save_datasets_registry(registry)
        return registry
    
    # Scan for existing dataset directories
    for dataset_dir in DATASETS_PATH.iterdir():
        if dataset_dir.is_dir():
            dataset_name = dataset_dir.name
            
            # Ensure images and labels directories exist
            images_dir = dataset_dir / 'images'
            labels_dir = dataset_dir / 'labels'
            images_dir.mkdir(exist_ok=True)
            labels_dir.mkdir(exist_ok=True)
            
            # Try to load or reconstruct metadata
            metadata_path = dataset_dir / 'metadata.json'
            if metadata_path.exists():
                try:
                    metadata = load_dataset_metadata({'path': str(dataset_dir)})
                except:
                    metadata = reconstruct_dataset_metadata(dataset_dir)
            else:
                metadata = reconstruct_dataset_metadata(dataset_dir)
            
            # Add to registry
            registry['datasets'][dataset_name] = {
                'name': dataset_name,
                'path': str(dataset_dir),
                'images_path': 'images',
                'labels_path': 'labels',
                'metadata_file': 'metadata.json',
                'created_at': metadata.get('created_at', datetime.now().isoformat()),
                'updated_at': metadata.get('updated_at', datetime.now().isoformat()),
                'image_count': metadata.get('image_count', 0),
                'label_count': len(metadata.get('class_names', [])),
                'annotated_count': metadata.get('annotated_count', 0)
            }
            
            # Set first dataset as active
            if not registry['active_dataset']:
                registry['active_dataset'] = dataset_name
    
    save_datasets_registry(registry)
    return registry

def reconstruct_dataset_metadata(dataset_path):
    """Reconstruct metadata.json for a dataset by scanning its contents"""
    dataset_path = Path(dataset_path)
    
    # Ensure directory structure
    images_dir = dataset_path / 'images'
    labels_dir = dataset_path / 'labels'
    images_dir.mkdir(exist_ok=True)
    labels_dir.mkdir(exist_ok=True)
    
    # Scan for images
    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        images.extend(images_dir.glob(ext))
    
    # Scan for labels and extract class IDs
    class_ids = set()
    label_count = 0
    for label_file in labels_dir.glob('*.txt'):
        label_count += 1
        try:
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_id = int(parts[0])
                        class_ids.add(class_id)
        except:
            pass
    
    # Count annotated images (images with non-empty label files)
    annotated_count = 0
    for img in images:
        label_file = labels_dir / f"{img.stem}.txt"
        if label_file.exists():
            try:
                content = label_file.read_text().strip()
                if content:
                    annotated_count += 1
            except:
                pass
    
    # Generate class names from unique IDs
    class_names = []
    if class_ids:
        sorted_ids = sorted(class_ids)
        class_names = [f'class_{i}' for i in sorted_ids]
    
    # Create metadata
    metadata = {
        'name': dataset_path.name,
        'version': '1.0',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'images_path': 'images',
        'labels_path': 'labels',
        'class_names': class_names,
        'image_count': len(images),
        'annotated_count': annotated_count
    }
    
    # Save metadata.json
    metadata_path = dataset_path / 'metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return metadata

def save_datasets_registry(registry):
    """Save datasets registry"""
    with open(DATASETS_REGISTRY, 'w') as f:
        json.dump(registry, f, indent=2)

def get_active_dataset():
    """Get currently active dataset info"""
    registry = load_datasets_registry()
    active_name = registry.get('active_dataset')
    if active_name and active_name in registry['datasets']:
        return registry['datasets'][active_name]
    if registry['datasets']:
        first_key = list(registry['datasets'].keys())[0]
        return registry['datasets'][first_key]
    return None

def set_active_dataset(dataset_name):
    """Set active dataset"""
    registry = load_datasets_registry()
    if dataset_name in registry['datasets']:
        registry['active_dataset'] = dataset_name
        save_datasets_registry(registry)
        return True
    return False

# ==================== DATASET OPERATIONS ====================

def create_dataset(dataset_name, class_names=None):
    """Create a new dataset with YOLO structure"""
    dataset_path = DATASETS_PATH / dataset_name
    
    # Create directory structure
    (dataset_path / 'images').mkdir(parents=True, exist_ok=True)
    (dataset_path / 'labels').mkdir(parents=True, exist_ok=True)
    
    # Create metadata.json (dataset info only, no annotations)
    metadata = {
        'name': dataset_name,
        'version': '1.0',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'images_path': 'images',
        'labels_path': 'labels',
        'class_names': class_names or [],
        'image_count': 0,
        'annotated_count': 0
    }
    
    with open(dataset_path / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Add to registry
    registry = load_datasets_registry()
    registry['datasets'][dataset_name] = {
        'name': dataset_name,
        'path': str(dataset_path),
        'images_path': 'images',
        'labels_path': 'labels',
        'metadata_file': 'metadata.json',
        'created_at': metadata['created_at'],
        'updated_at': metadata['updated_at'],
        'image_count': 0,
        'label_count': len(class_names) if class_names else 0
    }
    
    if not registry['active_dataset']:
        registry['active_dataset'] = dataset_name
    
    save_datasets_registry(registry)
    return registry['datasets'][dataset_name]

def load_dataset_metadata(dataset_info):
    """Load dataset metadata, reconstruct if missing"""
    metadata_path = Path(dataset_info['path']) / 'metadata.json'
    
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # File exists but is corrupted
            pass
    
    # Metadata missing or corrupted, reconstruct it
    return reconstruct_dataset_metadata(Path(dataset_info['path']))

def save_dataset_metadata(dataset_info, metadata):
    """Save dataset metadata"""
    metadata_path = Path(dataset_info['path']) / 'metadata.json'
    metadata['updated_at'] = datetime.now().isoformat()
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Update registry
    registry = load_datasets_registry()
    if dataset_info['name'] in registry['datasets']:
        registry['datasets'][dataset_info['name']]['updated_at'] = metadata['updated_at']
        registry['datasets'][dataset_info['name']]['image_count'] = metadata['image_count']
        registry['datasets'][dataset_info['name']]['annotated_count'] = metadata.get('annotated_count', 0)
        registry['datasets'][dataset_info['name']]['label_count'] = len(metadata['class_names'])
        save_datasets_registry(registry)

# ==================== YOLO FORMAT FUNCTIONS ====================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_yolo_label(label_path, img_width, img_height, class_names):
    """Parse YOLO format label file to pixel coordinates"""
    objects = []
    if not label_path.exists():
        return objects
    
    try:
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                
                class_id = int(parts[0])
                x_center = float(parts[1]) * img_width
                y_center = float(parts[2]) * img_height
                width = float(parts[3]) * img_width
                height = float(parts[4]) * img_height
                
                xmin = x_center - width / 2
                ymin = y_center - height / 2
                xmax = x_center + width / 2
                ymax = y_center + height / 2
                
                label_name = class_names[class_id] if class_id < len(class_names) else f'class_{class_id}'
                
                objects.append({
                    'label': label_name,
                    'label_id': class_id,
                    'xmin': max(0, int(xmin)),
                    'ymin': max(0, int(ymin)),
                    'xmax': min(img_width, int(xmax)),
                    'ymax': min(img_height, int(ymax))
                })
    except Exception as e:
        print(f"Error parsing {label_path}: {e}")
    
    return objects

def write_yolo_label(label_path, objects, img_width, img_height, class_names):
    """Write objects to YOLO format label file"""
    # Build class name to ID mapping
    class_to_id = {name: idx for idx, name in enumerate(class_names)}
    
    lines = []
    for obj in objects:
        label_name = obj.get('label', obj.get('label_name', 'unknown'))
        class_id = class_to_id.get(label_name, 0)
        
        # Convert to normalized coordinates
        xmin, ymin, xmax, ymax = obj['xmin'], obj['ymin'], obj['xmax'], obj['ymax']
        
        x_center = (xmin + xmax) / 2.0 / img_width
        y_center = (ymin + ymax) / 2.0 / img_height
        width = (xmax - xmin) / img_width
        height = (ymax - ymin) / img_height
        
        # Clamp to [0, 1]
        x_center = max(0, min(1, x_center))
        y_center = max(0, min(1, y_center))
        width = max(0, min(1, width))
        height = max(0, min(1, height))
        
        lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
    
    with open(label_path, 'w') as f:
        f.write('\n'.join(lines))

def get_label_color(index):
    """Get color for label based on index"""
    colors = [
        '#e94560', '#4ade80', '#fbbf24', '#60a5fa', 
        '#a78bfa', '#f472b6', '#2dd4bf', '#fb923c',
        '#f87171', '#34d399', '#818cf8', '#fbbf24'
    ]
    return colors[index % len(colors)]

def scan_dataset(dataset_info):
    """Scan dataset directory and update metadata - use only when entering dataset"""
    dataset_path = Path(dataset_info['path'])
    metadata = load_dataset_metadata(dataset_info)
    
    images_path = dataset_path / metadata['images_path']
    labels_path = dataset_path / metadata['labels_path']
    
    # Find all images
    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        images.extend(images_path.glob(ext))
    
    # Update counts - only count images with non-empty label files
    annotated_count = 0
    for img in images:
        label_file = labels_path / f"{img.stem}.txt"
        if label_file.exists():
            # Check if file has content (not empty)
            try:
                content = label_file.read_text().strip()
                if content:  # File exists and has content
                    annotated_count += 1
            except:
                pass  # Skip if can't read file
    
    metadata['image_count'] = len(images)
    metadata['annotated_count'] = annotated_count
    
    save_dataset_metadata(dataset_info, metadata)
    return metadata

def update_annotated_count_simple(dataset_info, delta=1):
    """Lightweight update to annotated_count without scanning all files.
    
    Args:
        dataset_info: Dataset info dict
        delta: +1 or -1 to adjust the count
    """
    metadata = load_dataset_metadata(dataset_info)
    current_count = metadata.get('annotated_count', 0)
    new_count = max(0, current_count + delta)
    metadata['annotated_count'] = new_count
    save_dataset_metadata(dataset_info, metadata)
    return new_count

# ==================== API ROUTES ====================

@app.route('/')
def index():
    """Dataset selection page (landing page)"""
    return render_template('select_dataset.html')

@app.route('/label')
def label_page():
    """Annotation page - requires dataset parameter"""
    dataset_name = request.args.get('dataset')
    if not dataset_name:
        # Redirect to dataset selection if no dataset specified
        return redirect('/')
    
    # Verify dataset exists
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return redirect('/')
    
    return render_template('index.html', dataset=dataset_name)

# Dataset Management
@app.route('/api/datasets')
def list_datasets():
    """List all datasets - returns cached counts without scanning"""
    registry = load_datasets_registry()
    # Return datasets with their stored counts (no scanning for performance)
    return jsonify({
        'datasets': list(registry['datasets'].values()),
        'active_dataset': registry.get('active_dataset')
    })

@app.route('/api/datasets', methods=['POST'])
def create_new_dataset():
    """Create a new dataset"""
    data = request.json
    name = data.get('name')
    class_names = data.get('class_names', [])
    
    if not name:
        return jsonify({'error': 'Dataset name required'}), 400
    
    registry = load_datasets_registry()
    if name in registry['datasets']:
        return jsonify({'error': 'Dataset already exists'}), 400
    
    dataset_info = create_dataset(name, class_names)
    return jsonify({'success': True, 'dataset': dataset_info})

@app.route('/api/datasets/<dataset_name>/activate', methods=['POST'])
def activate_dataset_route(dataset_name):
    """Activate a dataset and scan it to update counts"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    # Scan dataset to update counts when entering
    dataset_info = registry['datasets'][dataset_name]
    scan_dataset(dataset_info)
    
    # Set as active
    registry['active_dataset'] = dataset_name
    save_datasets_registry(registry)
    
    return jsonify({'success': True})

@app.route('/api/datasets/<dataset_name>', methods=['DELETE'])
def delete_dataset_route(dataset_name):
    """Delete a dataset"""
    registry = load_datasets_registry()
    
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_path = Path(registry['datasets'][dataset_name]['path'])
    if dataset_path.exists():
        shutil.rmtree(dataset_path)
    
    del registry['datasets'][dataset_name]
    
    if registry['active_dataset'] == dataset_name:
        registry['active_dataset'] = list(registry['datasets'].keys())[0] if registry['datasets'] else None
    
    save_datasets_registry(registry)
    return jsonify({'success': True})

# Image Operations
@app.route('/api/datasets/<dataset_name>/images')
def get_images(dataset_name):
    """Get list of all images in a specific dataset - returns minimal info"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    dataset_path = Path(dataset_info['path'])
    metadata = load_dataset_metadata(dataset_info)
    
    if not metadata:
        return jsonify([])
    
    images_path = dataset_path / metadata['images_path']
    labels_path = dataset_path / metadata['labels_path']
    
    # Return only filename list - minimal data transfer
    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        for img_file in images_path.glob(ext):
            label_file = labels_path / f"{img_file.stem}.txt"
            images.append({
                'id': img_file.stem,
                'filename': img_file.name,
                'has_annotation': label_file.exists()
            })
    
    return jsonify(sorted(images, key=lambda x: x['filename']))

@app.route('/api/datasets/<dataset_name>/image/<image_id>')
def get_image(dataset_name, image_id):
    """Get image file from specific dataset"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    dataset_path = Path(dataset_info['path'])
    metadata = load_dataset_metadata(dataset_info)
    images_path = dataset_path / metadata['images_path']
    
    for ext in ['.jpg', '.jpeg', '.png']:
        image_path = images_path / f"{image_id}{ext}"
        if image_path.exists():
            return send_file(image_path)
    
    return jsonify({'error': 'Image not found'}), 404

@app.route('/api/datasets/<dataset_name>/annotation/<image_id>')
def get_annotation(dataset_name, image_id):
    """Get annotation for an image from specific dataset"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    dataset_path = Path(dataset_info['path'])
    metadata = load_dataset_metadata(dataset_info)
    images_path = dataset_path / metadata['images_path']
    labels_path = dataset_path / metadata['labels_path']
    
    # Find image
    image_path = None
    for ext in ['.jpg', '.jpeg', '.png']:
        potential = images_path / f"{image_id}{ext}"
        if potential.exists():
            image_path = potential
            break
    
    if not image_path:
        return jsonify({'width': 0, 'height': 0, 'objects': []})
    
    # Get image dimensions
    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except:
        width, height = 0, 0
    
    # Parse label file
    label_path = labels_path / f"{image_id}.txt"
    objects = parse_yolo_label(label_path, width, height, metadata['class_names'])
    
    return jsonify({
        'width': width,
        'height': height,
        'objects': objects
    })

@app.route('/api/datasets/<dataset_name>/annotation/<image_id>', methods=['POST'])
def save_annotation(dataset_name, image_id):
    """Save annotation for an image in specific dataset"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    data = request.json
    width = data.get('width', 1920)
    height = data.get('height', 1080)
    objects = data.get('objects', [])
    
    dataset_path = Path(dataset_info['path'])
    metadata = load_dataset_metadata(dataset_info)
    labels_path = dataset_path / metadata['labels_path']
    
    # Validate that all labels exist in class_names
    invalid_labels = []
    for obj in objects:
        label_name = obj.get('label', obj.get('label_name', 'unknown'))
        if label_name not in metadata['class_names']:
            invalid_labels.append(label_name)
    
    if invalid_labels:
        return jsonify({
            'error': 'Invalid labels found',
            'invalid_labels': invalid_labels,
            'valid_labels': metadata['class_names']
        }), 400
    
    # Write YOLO format label file
    label_path = labels_path / f"{image_id}.txt"
    had_annotation_before = label_path.exists() and label_path.read_text().strip()
    
    if objects:
        write_yolo_label(label_path, objects, width, height, metadata['class_names'])
        has_annotation_now = True
    else:
        # Delete label file if no objects
        if label_path.exists():
            label_path.unlink()
        has_annotation_now = False
    
    # Update metadata counts - lightweight update
    if has_annotation_now and not had_annotation_before:
        update_annotated_count_simple(dataset_info, +1)
    elif not has_annotation_now and had_annotation_before:
        update_annotated_count_simple(dataset_info, -1)
    
    return jsonify({'success': True})

@app.route('/api/datasets/<dataset_name>/labels')
def get_labels(dataset_name):
    """Get all labels in a specific dataset"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    metadata = load_dataset_metadata(dataset_info)
    
    if not metadata:
        return jsonify([])
    
    # Count occurrences by scanning label files
    dataset_path = Path(dataset_info['path'])
    labels_path = dataset_path / metadata['labels_path']
    
    label_counts = {name: 0 for name in metadata['class_names']}
    
    for label_file in labels_path.glob('*.txt'):
        try:
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_id = int(parts[0])
                        if class_id < len(metadata['class_names']):
                            label_counts[metadata['class_names'][class_id]] += 1
        except:
            pass
    
    labels = [
        {
            'id': str(idx),
            'name': name,
            'color': get_label_color(idx),
            'count': label_counts.get(name, 0)
        }
        for idx, name in enumerate(metadata['class_names'])
    ]
    
    return jsonify(sorted(labels, key=lambda x: int(x['id'])))

@app.route('/api/datasets/<dataset_name>/labels', methods=['POST'])
def manage_labels(dataset_name):
    """Add new labels or update existing label names in a dataset"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    data = request.json
    
    # Handle label rename
    if 'old_name' in data and 'new_name' in data:
        return update_label_name(dataset_info, data['old_name'], data['new_name'])
    
    # Handle label delete
    if 'delete_name' in data:
        return delete_label(dataset_info, data['delete_name'])
    
    # Handle adding new labels
    if 'labels' in data:
        return add_labels(dataset_info, data['labels'])
    
    return jsonify({'error': 'Invalid request. Provide either (old_name, new_name) for rename, delete_name to delete, or labels array to add'}), 400

def add_labels(dataset_info, labels):
    """Add new labels to dataset class_names"""
    metadata = load_dataset_metadata(dataset_info)
    added = []
    existing = []
    
    for label in labels:
        label_name = label.strip() if isinstance(label, str) else label.get('name', '').strip()
        if not label_name:
            continue
            
        if label_name not in metadata['class_names']:
            metadata['class_names'].append(label_name)
            added.append(label_name)
        else:
            existing.append(label_name)
    
    if added:
        save_dataset_metadata(dataset_info, metadata)
    
    return jsonify({
        'success': True,
        'added': added,
        'existing': existing,
        'class_names': metadata['class_names']
    })

def update_label_name(dataset_info, old_name, new_name):
    """Update label name in dataset metadata only.
    
    Note: YOLO format uses class IDs (0, 1, 2...) in label files, not names.
    The names are only stored in metadata.json, so we only need to update that.
    """
    metadata = load_dataset_metadata(dataset_info)
    
    if not old_name or not new_name:
        return jsonify({'error': 'Missing label names'}), 400
    
    if old_name not in metadata['class_names']:
        return jsonify({'error': 'Label not found'}), 404
    
    # Update class_names - this is all we need to do!
    # YOLO label files only contain class IDs, not names
    idx = metadata['class_names'].index(old_name)
    metadata['class_names'][idx] = new_name
    save_dataset_metadata(dataset_info, metadata)
    
    return jsonify({'success': True})

def delete_label(dataset_info, label_name):
    """Delete a label class and remove all its annotations from the dataset.
    
    This will:
    1. Remove the label from class_names
    2. Remove all annotations with this class ID from label files
    3. Reindex remaining class IDs if necessary
    """
    metadata = load_dataset_metadata(dataset_info)
    
    if not label_name:
        return jsonify({'error': 'Missing label name'}), 400
    
    if label_name not in metadata['class_names']:
        return jsonify({'error': 'Label not found'}), 404
    
    # Get the class ID to delete
    class_id_to_delete = metadata['class_names'].index(label_name)
    
    # Remove from class_names
    metadata['class_names'].pop(class_id_to_delete)
    
    # Update all label files - remove annotations with the deleted class ID
    # and reindex remaining classes
    dataset_path = Path(dataset_info['path'])
    labels_path = dataset_path / metadata['labels_path']
    
    deleted_annotations = 0
    modified_files = 0
    
    for label_file in labels_path.glob('*.txt'):
        try:
            with open(label_file, 'r') as f:
                lines = f.readlines()
            
            # Filter out lines with the deleted class ID and reindex others
            new_lines = []
            file_modified = False
            
            for line in lines:
                parts = line.strip().split()
                if len(parts) == 5:
                    class_id = int(parts[0])
                    if class_id == class_id_to_delete:
                        # Skip this line (delete the annotation)
                        deleted_annotations += 1
                        file_modified = True
                    elif class_id > class_id_to_delete:
                        # Decrement class ID for classes after the deleted one
                        new_class_id = class_id - 1
                        new_line = f"{new_class_id} {parts[1]} {parts[2]} {parts[3]} {parts[4]}\n"
                        new_lines.append(new_line)
                        file_modified = True
                    else:
                        # Keep line as is
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            # Write back if modified
            if file_modified:
                if new_lines:
                    with open(label_file, 'w') as f:
                        f.writelines(new_lines)
                else:
                    # Delete empty label file
                    label_file.unlink()
                modified_files += 1
                
        except Exception as e:
            print(f"Error processing {label_file}: {e}")
    
    # Save updated metadata
    save_dataset_metadata(dataset_info, metadata)
    
    return jsonify({
        'success': True,
        'deleted_annotations': deleted_annotations,
        'modified_files': modified_files
    })

@app.route('/api/datasets/<dataset_name>/upload', methods=['POST'])
def upload_image(dataset_name):
    """Upload new image to specific dataset"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = f"{timestamp}_{filename.rsplit('.', 1)[0]}"
    ext = filename.rsplit('.', 1)[1].lower()
    new_filename = f"{unique_id}.{ext}"
    
    # Save to dataset images directory
    dataset_path = Path(dataset_info['path'])
    metadata = load_dataset_metadata(dataset_info)
    images_path = dataset_path / metadata['images_path']
    file_path = images_path / new_filename
    file.save(file_path)
    
    # Update image count only - lightweight
    metadata['image_count'] = metadata.get('image_count', 0) + 1
    save_dataset_metadata(dataset_info, metadata)
    
    return jsonify({
        'success': True,
        'id': unique_id,
        'filename': new_filename
    })

@app.route('/api/datasets/<dataset_name>/image/<image_id>', methods=['DELETE'])
def delete_image(dataset_name, image_id):
    """Delete image and its annotation from specific dataset"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    dataset_path = Path(dataset_info['path'])
    metadata = load_dataset_metadata(dataset_info)
    images_path = dataset_path / metadata['images_path']
    labels_path = dataset_path / metadata['labels_path']
    
    # Check if image had annotation before deleting
    label_path = labels_path / f"{image_id}.txt"
    had_annotation = label_path.exists() and label_path.read_text().strip()
    
    # Delete image file
    image_deleted = False
    for ext in ['.jpg', '.jpeg', '.png']:
        image_path = images_path / f"{image_id}{ext}"
        if image_path.exists():
            image_path.unlink()
            image_deleted = True
            break
    
    # Delete label file
    if label_path.exists():
        label_path.unlink()
    
    # Update metadata counts - lightweight
    if image_deleted:
        metadata['image_count'] = max(0, metadata.get('image_count', 0) - 1)
    if had_annotation:
        metadata['annotated_count'] = max(0, metadata.get('annotated_count', 0) - 1)
    save_dataset_metadata(dataset_info, metadata)
    
    return jsonify({'success': True})

# Import/Export
ALLOWED_ARCHIVE_EXTENSIONS = {'zip', '7z', 'tar', 'gz', 'bz2', 'rar'}

def allowed_archive(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_ARCHIVE_EXTENSIONS

@app.route('/api/import/detect', methods=['POST'])
def detect_import_format():
    """Detect format of uploaded archive - creates a new dataset from import"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_archive(file.filename):
        return jsonify({'error': 'Invalid archive format'}), 400
    
    # Save archive to temp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_path = TEMP_DIR / f"import_{timestamp}_{secure_filename(file.filename)}"
    file.save(archive_path)
    
    # Extract archive
    import subprocess
    extract_dir = TEMP_DIR / f"extracted_{timestamp}"
    extract_dir.mkdir(exist_ok=True)
    
    try:
        result = subprocess.run(
            ['7zz', 'x', str(archive_path), f'-o{extract_dir}', '-y'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            archive_path.unlink()
            shutil.rmtree(extract_dir, ignore_errors=True)
            return jsonify({'error': 'Failed to extract archive'}), 500
    except Exception as e:
        archive_path.unlink()
        shutil.rmtree(extract_dir, ignore_errors=True)
        return jsonify({'error': f'Extraction failed: {str(e)}'}), 500
    
    # Detect format with detailed info
    formats_detected = []
    
    # Check for YOLO format
    yolo_images = 0
    yolo_labels = 0
    
    if (extract_dir / 'data.yaml').exists():
        # Read class names from data.yaml
        try:
            import yaml
            with open(extract_dir / 'data.yaml', 'r') as f:
                yaml_data = yaml.safe_load(f)
                yolo_classes = yaml_data.get('names', [])
        except:
            yolo_classes = []
        
        for img_dir_name in ['train', 'valid', 'test', 'images']:
            img_dir = extract_dir / img_dir_name
            if img_dir.exists():
                yolo_images += len(list(img_dir.glob('*.jpg')) + list(img_dir.glob('*.jpeg')) + list(img_dir.glob('*.png')))
        
        label_dir = extract_dir / 'labels'
        if label_dir.exists():
            for subdir in label_dir.iterdir():
                if subdir.is_dir():
                    yolo_labels += len(list(subdir.glob('*.txt')))
                elif subdir.suffix == '.txt':
                    yolo_labels += 1
        
        formats_detected.append({
            'format': 'yolo',
            'description': 'YOLO format with images and labels directories',
            'image_count': yolo_images,
            'label_count': yolo_labels,
            'classes': yolo_classes
        })
    
    # Check for Pascal VOC
    voc_images = 0
    voc_labels = 0
    
    ann_dir = extract_dir / 'Annotations'
    img_dir = extract_dir / 'JPEGImages'
    
    if ann_dir.exists() and img_dir.exists():
        voc_labels = len(list(ann_dir.glob('*.xml')))
        voc_images = len(list(img_dir.glob('*.jpg')) + list(img_dir.glob('*.jpeg')) + list(img_dir.glob('*.png')))
        
        formats_detected.append({
            'format': 'voc',
            'description': 'Pascal VOC format with Annotations and JPEGImages',
            'image_count': voc_images,
            'label_count': voc_labels,
            'classes': []
        })
    
    # Check for COCO
    coco_images = 0
    coco_labels = 0
    coco_classes = []
    
    for json_file in extract_dir.rglob('*.json'):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if 'images' in data and 'annotations' in data and 'categories' in data:
                    coco_images = len(data['images'])
                    coco_labels = len(data['annotations'])
                    coco_classes = [cat['name'] for cat in data.get('categories', [])]
                    
                    formats_detected.append({
                        'format': 'coco',
                        'description': f"COCO format ({json_file.name})",
                        'image_count': coco_images,
                        'label_count': coco_labels,
                        'classes': coco_classes
                    })
                    break
        except:
            pass
    
    # Save import info
    import_info = {
        'archive_path': str(archive_path),
        'extract_dir': str(extract_dir),
        'detected_formats': [f['format'] for f in formats_detected]
    }
    import_info_file = TEMP_DIR / f"import_{timestamp}_info.json"
    with open(import_info_file, 'w') as f:
        json.dump(import_info, f)
    
    return jsonify({
        'success': True,
        'import_id': timestamp,
        'formats': formats_detected
    })

@app.route('/api/import/convert', methods=['POST'])
def convert_import():
    """Convert imported dataset to YOLO format and create new dataset"""
    data = request.json
    import_id = data.get('import_id')
    selected_format = data.get('format')
    dataset_name = data.get('dataset_name')
    
    if not import_id or not selected_format:
        return jsonify({'error': 'Missing import_id or format'}), 400
    
    if not dataset_name:
        # Generate dataset name from import
        dataset_name = f"imported_{import_id}"
    
    # Check if dataset name already exists
    registry = load_datasets_registry()
    if dataset_name in registry['datasets']:
        return jsonify({'error': 'Dataset name already exists'}), 400
    
    import_info_file = TEMP_DIR / f"import_{import_id}_info.json"
    if not import_info_file.exists():
        return jsonify({'error': 'Import session not found'}), 404
    
    with open(import_info_file, 'r') as f:
        import_info = json.load(f)
    
    extract_dir = Path(import_info['extract_dir'])
    if not extract_dir.exists():
        return jsonify({'error': 'Extracted files not found'}), 404
    
    # Create new dataset
    dataset_info = create_dataset(dataset_name)
    dataset_path = Path(dataset_info['path'])
    metadata = load_dataset_metadata(dataset_info)
    images_path = dataset_path / metadata['images_path']
    labels_path = dataset_path / metadata['labels_path']
    
    images_added = 0
    
    if selected_format == 'yolo':
        # Copy YOLO format files
        yaml_path = extract_dir / 'data.yaml'
        if yaml_path.exists():
            # Read class names from data.yaml
            import yaml
            with open(yaml_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
                class_names = yaml_data.get('names', [])
                if class_names:
                    metadata['class_names'] = class_names
        
        # Find and copy images and labels
        for img_dir_name in ['train', 'valid', 'test', 'images']:
            img_dir = extract_dir / img_dir_name
            if img_dir.exists():
                for img_file in img_dir.glob('*'):
                    if img_file.suffix.lower()[1:] in ALLOWED_EXTENSIONS:
                        shutil.copy2(img_file, images_path / img_file.name)
                        
                        # Copy corresponding label
                        label_file = extract_dir / 'labels' / img_dir_name / f"{img_file.stem}.txt"
                        if not label_file.exists():
                            label_file = extract_dir / 'labels' / f"{img_file.stem}.txt"
                        if label_file.exists():
                            shutil.copy2(label_file, labels_path / label_file.name)
                        
                        images_added += 1
    
    elif selected_format == 'voc':
        # Convert Pascal VOC to YOLO
        import xml.etree.ElementTree as ET
        
        ann_dirs = [extract_dir / 'Annotations', extract_dir / 'xmls']
        img_dirs = [extract_dir / 'JPEGImages', extract_dir / 'images']
        
        for ann_dir in ann_dirs:
            if not ann_dir.exists():
                continue
            for xml_file in ann_dir.glob('*.xml'):
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    # Get image info
                    filename_elem = root.find('filename')
                    if filename_elem is None:
                        continue
                    img_filename = filename_elem.text
                    
                    size = root.find('size')
                    if size is None:
                        continue
                    width = int(size.find('width').text)
                    height = int(size.find('height').text)
                    
                    # Find image file
                    img_file = None
                    for img_dir in img_dirs:
                        potential = img_dir / img_filename
                        if potential.exists():
                            img_file = potential
                            break
                    
                    if not img_file:
                        continue
                    
                    # Copy image
                    shutil.copy2(img_file, images_path / img_file.name)
                    
                    # Convert annotations to YOLO format
                    lines = []
                    for obj in root.findall('object'):
                        name_elem = obj.find('name')
                        if name_elem is None:
                            continue
                        class_name = name_elem.text
                        
                        if class_name not in metadata['class_names']:
                            metadata['class_names'].append(class_name)
                        class_id = metadata['class_names'].index(class_name)
                        
                        bbox = obj.find('bndbox')
                        if bbox is None:
                            continue
                        
                        xmin = float(bbox.find('xmin').text)
                        ymin = float(bbox.find('ymin').text)
                        xmax = float(bbox.find('xmax').text)
                        ymax = float(bbox.find('ymax').text)
                        
                        # Convert to YOLO format
                        x_center = (xmin + xmax) / 2.0 / width
                        y_center = (ymin + ymax) / 2.0 / height
                        box_width = (xmax - xmin) / width
                        box_height = (ymax - ymin) / height
                        
                        lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}")
                    
                    # Write YOLO label file
                    label_file = labels_path / f"{img_file.stem}.txt"
                    with open(label_file, 'w') as f:
                        f.write('\n'.join(lines))
                    
                    images_added += 1
                except Exception as e:
                    print(f"Error converting {xml_file}: {e}")
                    continue
    
    elif selected_format == 'coco':
        # Convert COCO to YOLO
        for json_file in extract_dir.rglob('*.json'):
            try:
                with open(json_file, 'r') as f:
                    coco_data = json.load(f)
                
                if 'images' not in coco_data or 'annotations' not in coco_data:
                    continue
                
                # Build category mapping
                categories = {cat['id']: cat['name'] for cat in coco_data.get('categories', [])}
                for cat_name in categories.values():
                    if cat_name not in metadata['class_names']:
                        metadata['class_names'].append(cat_name)
                
                # Group annotations by image
                image_annotations = {}
                for ann in coco_data['annotations']:
                    img_id = str(ann['image_id'])
                    if img_id not in image_annotations:
                        image_annotations[img_id] = []
                    image_annotations[img_id].append(ann)
                
                # Process images
                img_dir = extract_dir / 'images'
                if not img_dir.exists():
                    img_dir = json_file.parent
                
                for img_info in coco_data['images']:
                    img_id = str(img_info['id'])
                    img_filename = img_info['file_name']
                    width = img_info['width']
                    height = img_info['height']
                    
                    img_file = img_dir / img_filename
                    if not img_file.exists():
                        continue
                    
                    # Copy image
                    shutil.copy2(img_file, images_path / img_file.name)
                    
                    # Convert annotations
                    lines = []
                    for ann in image_annotations.get(img_id, []):
                        bbox = ann['bbox']  # [x, y, width, height]
                        cat_id = ann['category_id']
                        class_name = categories.get(cat_id, 'unknown')
                        class_id = metadata['class_names'].index(class_name)
                        
                        x_center = (bbox[0] + bbox[2] / 2) / width
                        y_center = (bbox[1] + bbox[3] / 2) / height
                        box_width = bbox[2] / width
                        box_height = bbox[3] / height
                        
                        lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}")
                    
                    # Write YOLO label file
                    label_file = labels_path / f"{img_file.stem}.txt"
                    with open(label_file, 'w') as f:
                        f.write('\n'.join(lines))
                    
                    images_added += 1
            except Exception as e:
                print(f"Error processing COCO file {json_file}: {e}")
                continue
    
    # Save updated metadata
    save_dataset_metadata(dataset_info, metadata)
    scan_dataset(dataset_info)
    
    # Cleanup
    archive_path = Path(import_info['archive_path'])
    if archive_path.exists():
        archive_path.unlink()
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
    import_info_file.unlink()
    
    return jsonify({
        'success': True,
        'images_added': images_added,
        'total_images': metadata['image_count'],
        'class_names': metadata['class_names']
    })

@app.route('/api/datasets/<dataset_name>/export/yolo')
def export_yolo(dataset_name):
    """Export dataset in YOLO format (it's already in YOLO format!)"""
    registry = load_datasets_registry()
    if dataset_name not in registry['datasets']:
        return jsonify({'error': 'Dataset not found'}), 404
    
    dataset_info = registry['datasets'][dataset_name]
    metadata = load_dataset_metadata(dataset_info)
    
    return jsonify({
        'dataset_name': dataset_info['name'],
        'class_names': metadata['class_names'],
        'image_count': metadata['image_count'],
        'annotated_count': metadata['annotated_count'],
        'format': 'yolo',
        'note': 'Dataset is already in YOLO format. Find it at: ' + dataset_info['path']
    })

@app.route('/api/import/local', methods=['POST'])
def import_local_dataset():
    """Import a dataset from a local folder or ZIP file"""
    data = request.json
    dataset_name = data.get('name')
    source_path = data.get('path')
    
    if not dataset_name or not source_path:
        return jsonify({'error': 'Missing dataset name or path'}), 400
    
    # Check if dataset name already exists
    registry = load_datasets_registry()
    if dataset_name in registry['datasets']:
        return jsonify({'error': 'Dataset name already exists'}), 400
    
    source_path = Path(source_path)
    
    if not source_path.exists():
        return jsonify({'error': f'Path does not exist: {source_path}'}), 404
    
    try:
        # Create new dataset
        dataset_info = create_dataset(dataset_name)
        dataset_path = Path(dataset_info['path'])
        metadata = load_dataset_metadata(dataset_info)
        images_path = dataset_path / metadata['images_path']
        labels_path = dataset_path / metadata['labels_path']
        
        # Handle ZIP file
        if source_path.is_file() and source_path.suffix.lower() in ['.zip', '.7z', '.tar', '.gz', '.bz2', '.rar']:
            # Extract archive
            import subprocess
            extract_dir = TEMP_DIR / f"local_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            extract_dir.mkdir(exist_ok=True)
            
            result = subprocess.run(
                ['7zz', 'x', str(source_path), f'-o{extract_dir}', '-y'],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                # Clean up
                if dataset_path.exists():
                    shutil.rmtree(dataset_path)
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                return jsonify({'error': 'Failed to extract archive'}), 500
            
            source_path = extract_dir
        
        # Look for images and labels directories
        images_dir = None
        labels_dir = None
        source_metadata = None
        
        # Check if source_path has images/ and labels/ directly
        if (source_path / 'images').exists() and (source_path / 'labels').exists():
            images_dir = source_path / 'images'
            labels_dir = source_path / 'labels'
            # Check for metadata.json in source
            if (source_path / 'metadata.json').exists():
                try:
                    with open(source_path / 'metadata.json', 'r') as f:
                        source_metadata = json.load(f)
                except:
                    pass
        else:
            # Look in subdirectories
            for subdir in source_path.iterdir():
                if subdir.is_dir():
                    if (subdir / 'images').exists() and (subdir / 'labels').exists():
                        images_dir = subdir / 'images'
                        labels_dir = subdir / 'labels'
                        # Check for metadata.json in subdirectory
                        if (subdir / 'metadata.json').exists():
                            try:
                                with open(subdir / 'metadata.json', 'r') as f:
                                    source_metadata = json.load(f)
                            except:
                                pass
                        break
        
        if not images_dir or not labels_dir:
            # Clean up
            if dataset_path.exists():
                shutil.rmtree(dataset_path)
            if 'extract_dir' in locals() and extract_dir.exists():
                shutil.rmtree(extract_dir)
            return jsonify({'error': 'Could not find images/ and labels/ directories'}), 400
        
        # First, scan all labels in source to extract class IDs
        class_ids = set()
        for label_file in labels_dir.glob('*.txt'):
            try:
                with open(label_file, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) == 5:
                            class_id = int(parts[0])
                            class_ids.add(class_id)
            except:
                pass
        
        # Copy images
        image_count = 0
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            for img_file in images_dir.glob(ext):
                shutil.copy2(img_file, images_path / img_file.name)
                image_count += 1
        
        # Copy labels
        label_count = 0
        for label_file in labels_dir.glob('*.txt'):
            shutil.copy2(label_file, labels_path / label_file.name)
            label_count += 1
        
        # Use class names from source metadata if available, otherwise generate default names
        if source_metadata and 'class_names' in source_metadata and source_metadata['class_names']:
            metadata['class_names'] = source_metadata['class_names']
        elif class_ids:
            # Sort unique class IDs and create names only for existing IDs
            sorted_ids = sorted(class_ids)
            metadata['class_names'] = [f'class_{i}' for i in sorted_ids]
        else:
            # No labels found, use empty class names
            metadata['class_names'] = []
        
        # Save metadata.json to ensure it's properly created
        save_dataset_metadata(dataset_info, metadata)
        
        # Update metadata
        scan_dataset(dataset_info)
        
        # Clean up temp directory if we extracted an archive
        if 'extract_dir' in locals() and extract_dir.exists():
            shutil.rmtree(extract_dir)
        
        return jsonify({
            'success': True,
            'dataset_name': dataset_name,
            'image_count': image_count,
            'label_count': label_count,
            'class_names': metadata['class_names']
        })
        
    except Exception as e:
        # Clean up on error
        if 'dataset_path' in locals() and dataset_path.exists():
            shutil.rmtree(dataset_path)
        if 'extract_dir' in locals() and extract_dir.exists():
            shutil.rmtree(extract_dir)
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

if __name__ == '__main__':
    # Create default dataset if none exists
    registry = load_datasets_registry()
    if not registry['datasets']:
        create_dataset('default')
        registry = load_datasets_registry()
        registry['active_dataset'] = 'default'
        save_datasets_registry(registry)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
