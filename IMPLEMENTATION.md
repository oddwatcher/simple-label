# Image Labeling Tool - Implementation Document

## Overview
A web-based image labeling tool for object detection datasets with support for multiple datasets, standard YOLO format, and various import/export formats.

## Architecture

### Directory Structure
```
/root/viewer/
├── datasets.json              # Registry of all datasets
├── datasets/                  # All datasets stored here
│   ├── dataset_name/
│   │   ├── images/           # Image files (*.jpg, *.png)
│   │   ├── labels/           # YOLO format labels (*.txt)
│   │   └── metadata.json     # Dataset metadata (class names, counts)
│   └── ...
├── temp/                     # Temporary files for imports
├── static/
│   └── app.js               # Frontend application
├── templates/
│   ├── index.html           # Main annotation UI
│   └── select_dataset.html  # Dataset selection page
└── server.py                # Flask backend
```

## Data Formats

### 1. datasets.json (Registry)
Location: `/root/viewer/datasets.json`

Tracks all datasets:
```json
{
  "datasets": {
    "dataset_name": {
      "name": "dataset_name",
      "path": "/root/viewer/datasets/dataset_name",
      "images_path": "images",
      "labels_path": "labels",
      "metadata_file": "metadata.json",
      "created_at": "ISO timestamp",
      "updated_at": "ISO timestamp",
      "image_count": 1000,
      "annotated_count": 950,
      "label_count": 10
    }
  },
  "active_dataset": "dataset_name",
  "version": "1.0"
}
```

### 2. metadata.json (Per Dataset)
Location: `datasets/dataset_name/metadata.json`

Contains dataset-level information:
```json
{
  "name": "dataset_name",
  "version": "1.0",
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp",
  "images_path": "images",
  "labels_path": "labels",
  "class_names": ["r_head", "l_head", "person", "car"],
  "image_count": 1000,
  "annotated_count": 950
}
```

### 3. YOLO Label Format
Location: `datasets/dataset_name/labels/*.txt`

Each image has a corresponding `.txt` file:
```
0 0.453125 0.623456 0.234375 0.123456
1 0.234567 0.345678 0.156789 0.098765
```

Format: `class_id x_center y_center width height`
- All values normalized to [0, 1]
- One line per bounding box
- Empty files count as non-annotated

## Application Flow

### 1. Dataset Selection Page (`/`)
- Landing page showing all datasets
- Create new datasets with initial class names
- Import datasets from ZIP/7Z/TAR/RAR archives
- Export datasets in YOLO/VOC/COCO formats
- Click dataset to open annotation page

### 2. Annotation Page (`/label?dataset=name`)
- Three-panel layout: Image list | Canvas | Labels & Annotations
- Virtual scrolling for large image lists (11,000+ images)
- Draw/Select modes for bounding box editing
- Label management panel with id:name(count) format
- Keyboard shortcuts (hover over ? button to see)

## API Endpoints

### Dataset Management
- `GET /api/datasets` - List all datasets with current counts
- `POST /api/datasets` - Create new dataset
  - Body: `{"name": "dataset_name", "class_names": ["class1", "class2"]}`
- `POST /api/datasets/<name>/activate` - Set active dataset
- `DELETE /api/datasets/<name>` - Delete dataset

### Dataset-Specific Operations
- `GET /api/datasets/<name>/images` - List images (minimal data: id, filename, has_annotation)
- `GET /api/datasets/<name>/image/<id>` - Get image file
- `GET /api/datasets/<name>/annotation/<id>` - Get annotations
- `POST /api/datasets/<name>/annotation/<id>` - Save annotations
  - Validates all labels exist in dataset class_names
  - Returns error if invalid labels found
- `DELETE /api/datasets/<name>/image/<id>` - Delete image
- `POST /api/datasets/<name>/upload` - Upload image(s)

### Label Management
- `GET /api/datasets/<name>/labels` - Get all labels sorted by ID
  - Returns: `[{"id": "0", "name": "person", "color": "#e94560", "count": 5}]`
- `POST /api/datasets/<name>/labels` - Add or rename labels
  - Add: `{"labels": ["class1", "class2"]}`
  - Rename: `{"old_name": "old", "new_name": "new"}`

### Import/Export
- `POST /api/import/detect` - Detect format of uploaded archive
- `POST /api/import/convert` - Convert and import dataset
- `GET /api/datasets/<name>/export/<format>` - Export dataset
  - Formats: `yolo`, `voc`, `coco`

## Features

### Core Features
1. **Multi-dataset support** - Dataset selection page with create/import/export
2. **Standard YOLO format** - Native compatibility with YOLO tools
3. **Virtual scrolling** - Handle 10,000+ images efficiently
4. **Label consistency** - All labels validated against dataset class_names
5. **Bounding box editing** - Draw, resize, move boxes with visual handles
6. **Dataset-level labels** - Labels defined per-dataset, not per-image

### UI Features
1. **Dataset cards** - Show image count, annotated count, dates
2. **Export dropdown** - On dataset cards and annotation toolbar
3. **Image browser** - Virtual scrolling list with search/filter
4. **Canvas editor** - Pixel-perfect bounding box editing
5. **Label panel** - Shows `id:name(count)` format, sorted by ID
6. **Keyboard shortcuts** - Hidden ? button, shows on hover
7. **Mode buttons** - Draw/Select modes, disabled when no image selected

### Performance Optimizations
1. **Virtual scrolling** - Only render visible image list items
2. **Debounced search** - 300ms delay on image search
3. **Lazy loading** - Images loaded on-demand
4. **Minimal API responses** - Image list returns only essential data

## Backend Functions

### Dataset Registry
- `load_datasets_registry()` - Load datasets.json
- `save_datasets_registry()` - Save datasets.json
- `create_dataset(name, class_names)` - Create new dataset
- `scan_dataset(dataset_info)` - Update image/annotation counts

### YOLO Format
- `parse_yolo_label(path, width, height, class_names)` - Parse .txt to objects
- `write_yolo_label(path, objects, width, height, class_names)` - Write objects to .txt
- Label validation: Only allows labels from dataset class_names

### Import/Export
- `detect_import_format()` - Detect format of uploaded archive
- `convert_import()` - Convert and import dataset
- Support: YOLO, Pascal VOC, COCO formats

## Frontend Structure

### Main Components
1. **DatasetSelector** - Dataset selection page logic
2. **LabelingTool** - Main annotation tool class
3. **Virtual scrolling** - Efficient image list rendering
4. **Canvas editor** - Bounding box drawing and editing

### State Management
- `datasetName` - Current dataset from URL
- `images` - List of all images
- `currentImage` - Currently selected image
- `annotations` - Current image's boxes
- `labels` - Dataset class names with id, color, count
- `selectedLabel` - Currently selected class for drawing
- `mode` - 'draw' or 'select' (only when image selected)

### Keyboard Shortcuts
Accessible via ? button (bottom-right, hover to show):
- `←/→` - Previous/Next image
- `D` - Draw mode (only when image selected)
- `S` - Select mode (only when image selected)
- `Delete` - Delete selected box or image
- `Escape` - Cancel drawing/selection

**Note:** Annotations are auto-saved when you:
- Finish drawing a box
- Finish moving/resizing a box
- Change a label
- Switch to another image

### Mode Behavior
- **Two modes only**: Draw or Select
- **Mode disabled** when no image selected (buttons grayed out)
- **Auto-reset** to Select mode when switching images
- **Draw mode**: Click and drag to create boxes
- **Select mode**: Click to select, drag to move, handles to resize

## File Requirements

### Required Files
1. `server.py` - Flask backend with all API endpoints
2. `templates/index.html` - Annotation page UI
3. `templates/select_dataset.html` - Dataset selection page
4. `static/app.js` - Frontend JavaScript
5. `datasets.json` - Dataset registry (auto-created)

### Auto-Created on First Run
1. `datasets/default/` - Default dataset directory
2. `datasets/default/metadata.json` - Default metadata
3. `datasets/default/images/` - Images folder
4. `datasets/default/labels/` - Labels folder

## Dependencies
- Python 3.7+
- Flask
- Flask-CORS
- Pillow (PIL)
- Werkzeug
- PyYAML (for import)

## Security Considerations
1. File upload validation (image types only)
2. Secure filename handling
3. Path traversal protection
4. CORS enabled for development
5. Label validation on save (prevents invalid labels)

## Recent Changes

### Performance Improvements
- Virtual scrolling for image lists
- Debounced search input
- Lazy image loading
- Dataset-specific API endpoints

### UI Improvements
- Dataset selection page with export functionality
- Compact keyboard shortcuts (? button)
- Single Export button with dropdown menu
- Label display: `id:name(count)` format
- Mode buttons disabled when no image selected

### Data Integrity
- Labels must be pre-defined in dataset
- Validation on annotation save
- Consistent label IDs across all images
- Proper annotated count (checks file content, not just existence)

### Robustness & Auto-Recovery
The system automatically reconstructs missing files:

#### 1. Missing datasets.json
**Trigger:** File deleted or corrupted
**Action:** Scans `/root/viewer/datasets/` directory
**Reconstruction:**
- Finds all dataset directories
- Creates `images/` and `labels/` folders if missing
- Reconstructs `metadata.json` for each dataset
- Generates class names from label files
- Updates counts (images, annotations)
- Saves new `datasets.json`

#### 2. Missing metadata.json
**Trigger:** Accessing a dataset without metadata
**Action:** Scans dataset directory
**Reconstruction:**
- Counts all images
- Reads all label files
- Extracts unique class IDs
- Generates class names: `['class_0', 'class_2', ...]`
- Counts annotated images
- Creates and saves `metadata.json`

#### 3. Import with Missing Metadata
When importing a local dataset without `metadata.json`:
- Scans source directory before copying
- Extracts class IDs from all labels
- Creates metadata with discovered classes
- Copies files
- Saves complete metadata.json

This ensures the system is resilient to accidental file deletions and can recover from corrupted state.

## Future Enhancements
1. User authentication
2. Dataset versioning
3. Collaborative editing
4. AI-assisted labeling
5. Video annotation support
6. Batch operations (delete, label rename)
7. Image preprocessing options
