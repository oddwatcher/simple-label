# Agent Guidelines for Image Labeling Tool

## Project Overview
Flask web application for image labeling with YOLO format support.
Backend: Python (Flask), Frontend: vanilla JavaScript.

## Commands

### Run the application
```bash
python server.py
```
The Flask dev server starts on port 5000 by default.


## Dependencies
Core dependencies: `flask`, `flask-cors`, `pillow`, `numpy`.
Optional dependency: `ultralytics` (for YOLO model inference).
There is no `requirements.txt` or `pyproject.toml`; add dependencies with `pip install <package>`.

## Code Style

### Python
- **Imports**: stdlib first, then third-party, then local. Group with blank lines between.
- **Quotes**: Use single quotes for strings and dict keys (`'key': 'value'`).
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for module-level constants.
- **Types**: Use type hints for function signatures in new code (follow `models.py` style: `def fn(x: str) -> Dict:`).
- **Error handling**: Prefer specific exceptions (`except (json.JSONDecodeError, IOError):`). Avoid bare `except:` in new code.
- **Flask routes**: Return `jsonify({'success': True, ...})` for success or `jsonify({'error': 'message'}), status_code` for errors.
- **Path handling**: Always use `pathlib.Path` instead of string paths.
- **JSON**: Use `indent=2` when writing JSON files.
- **Docstrings**: Brief imperative description (e.g., `"Load dataset metadata"`).
- **Line length**: Keep under 100 characters when possible.

### JavaScript
- **Style**: Vanilla JS (no frameworks). Use ES6 classes.
- **Naming**: `camelCase` for variables/functions, `PascalCase` for classes.
- **Semicolons**: Required.
- **Indent**: 4 spaces.
- **Quotes**: Single quotes for strings.
- **DOM**: Use `document.getElementById` / `querySelector` directly.

## Architecture
- `server.py`: Flask routes, dataset registry logic, YOLO I/O, export/import.
- `models.py`: `ModelManager` class for loading/running Ultralytics YOLO models.
- `static/app.js`: Frontend `LabelingTool` class (canvas, annotations, virtual scrolling).
- `templates/`: Jinja2 HTML templates.
- `datasets/`: Per-dataset folders with `images/`, `labels/`, and `metadata.json`.

## Conventions
- YOLO label format: `class_id x_center y_center width height` (normalized 0-1).
- Metadata stored in `metadata.json`; dataset registry in `datasets.json`.
- Registry files are reconstructed automatically if missing/corrupted.
- Keep route handlers thin; put business logic in standalone functions or class methods.
- When modifying label files, preserve existing annotations and update `annotated_count` in metadata.
- Use `datetime.now().isoformat()` for timestamps.
- Use f-strings for string formatting (`f"{value}"`).
- Prefer list comprehensions over explicit loops where readable.
- Maintain separation between backend API logic and frontend rendering logic.
- Avoid introducing new heavy dependencies; prefer stdlib or existing packages.
- When handling file uploads, validate extensions against `ALLOWED_EXTENSIONS` set.
- Ensure backward compatibility with existing YOLO datasets on disk.
- Frontend canvas operations should handle high-DPI displays properly.
- Virtual scrolling in `app.js` is used for large image lists; preserve this pattern.
- Keyboard shortcuts should be documented in UI (hover over `?` button).
- Model inference is optional (`ULTRALYTICS_AVAILABLE` flag); gracefully degrade when unavailable.
- When adding new API endpoints, prefix with `/api/` and return JSON.
- Use secure filename handling (`werkzeug.utils.secure_filename`) for uploads.
- Temporary files go in `temp/` directory; clean up after operations when possible.
- Image formats supported: `jpg`, `jpeg`, `png`, `bmp`, `gif`.
- Export formats: YOLO (native), Pascal VOC XML, COCO JSON.
- Import formats: ZIP, 7Z, TAR, RAR archives with images and optional labels.
- Do not commit secrets, API keys, or model weights to the repository.
- Keep frontend state management within the `LabelingTool` class instance.
- Use `async/await` for fetch operations in frontend; avoid callback hell.
- Maintain consistent error response format: `{success: false, error: 'message'}` or HTTP status codes.
- When updating class names, remember YOLO files store only class IDs; names live in `metadata.json`.
- Reindex class IDs when deleting labels to maintain contiguous numbering.
- Preserve existing annotations during label rename operations.
- Dataset activation is a lightweight registry update, not a file move.
- Always verify dataset exists before operating on it; return 404 if missing.
- Use `try/except/else/finally` blocks for resource cleanup when dealing with files.
- Prefer `Path.exists()` and `Path.is_dir()` over `os.path.exists()`.
- Use `json.load()` / `json.dump()` with explicit encoding (utf-8 is default).
- Keep template HTML semantic and accessible where possible.
- CSS uses a dark theme palette (`#1a1a2e`, `#16213e`, `#0f3460`, `#e94560`).
- Match existing CSS naming convention (kebab-case class names).
- When adding new frontend features, update both the toolbar and keyboard shortcuts.
- The `annotated_count` in metadata tracks images with non-empty label files.
- Empty label files (0 bytes or whitespace-only) count as non-annotated.
- Image IDs are derived from filenames without extensions (`img_file.stem`).
- Ensure cross-browser compatibility for canvas operations (Chrome, Firefox, Safari).
- Use `event.preventDefault()` and `event.stopPropagation()` judiciously in event handlers.
- Debounce rapid UI events (e.g., search input) to avoid excessive re-renders.
- When adding models, generate a sanitized ID from the name (`lower().replace(" ", "_")`).
- Model weights are stored per-model in `models/{model_id}/` directory.
- Cache loaded models in memory (`self.loaded_models`) but clear on weight updates.
- Inference results are normalized; convert to pixel coordinates only for display.
- Confidence threshold defaults to `0.25` for model inference.
- Log warnings to console rather than showing alerts for non-critical issues.
- Use `print()` sparingly in backend; prefer return values for error communication.
- Avoid modifying global state outside of route handlers and initialization blocks.
- Keep functions focused; break up large route handlers into helper functions.
- Document complex algorithms or business rules with inline comments.
- Update `updated_at` timestamps on any mutating operation.
- When creating datasets, ensure both `images/` and `labels/` subdirectories exist.
- Default dataset named `default` is created automatically if no datasets exist.
- The active dataset is tracked in `datasets.json`; UI defaults to first dataset if unset.
- When returning lists from API, sort them deterministically (e.g., by filename).
- Minimize data transfer: return filenames and IDs, not full image data, in list endpoints.
- Use `send_file()` for serving individual images, not base64 encoding.
- Base64 encoding is only used for model inference on uploaded image bytes.
- Avoid hardcoding paths; derive from `Path(__file__).parent` or config constants.
- Use environment variables sparingly; this app is configured via module-level constants.
- Maintain idempotency where possible: running an operation twice should be safe.
- When in doubt, match the style of the surrounding code.

## Testing Patterns (when adding tests)
- Place tests in `tests/` directory or `test_*.py` files at project root.
- Use `pytest` fixtures for Flask app and test client setup.
- Mock external dependencies (e.g., `ultralytics`, file I/O) to keep tests fast.
- Test API endpoints for both success and error responses.
- Use temporary directories (`tmp_path` fixture) for dataset operations.
- Verify JSON responses match the expected `{success: bool, ...}` structure.

## Common Pitfalls
- Do not assume `ultralytics` is installed; always check `ULTRALYTICS_AVAILABLE`.
- Do not return full image bytes in list endpoints; use `send_file()` for individual images.
- Remember that YOLO label files use class IDs, not names, so renaming labels does not require rewriting `.txt` files.
- Always update `updated_at` and `annotated_count` when mutating dataset state.
- Avoid bare `except:` clauses; they hide bugs and make debugging difficult.
- Do not store absolute paths in `datasets.json`; derive them from the registry location.
