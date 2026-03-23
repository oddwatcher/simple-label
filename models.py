"""
Model Manager for Image Labeling Tool
Handles model loading, inference, and management using Ultralytics
"""

import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
from PIL import Image
import io
import base64

# Ultralytics imports
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    print("Warning: ultralytics not installed. Model inference will not be available.")


class ModelManager:
    """Manages AI models for automated annotation"""
    
    def __init__(self, models_path: str = "./models"):
        self.models_path = Path(models_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.models_path / "models.json"
        self.loaded_models = {}  # Cache for loaded models
        
    def load_registry(self) -> Dict:
        """Load models registry"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"models": {}, "version": "1.0"}
    
    def save_registry(self, registry: Dict):
        """Save models registry"""
        with open(self.registry_file, 'w') as f:
            json.dump(registry, f, indent=2)
    
    def list_models(self) -> List[Dict]:
        """List all available models"""
        registry = self.load_registry()
        models = []
        
        for model_id, model_info in registry.get("models", {}).items():
            model_path = self.models_path / model_id
            if model_path.exists():
                # Check if weights file exists
                weights_file = model_path / model_info.get("weights_file", "")
                model_info["available"] = weights_file.exists()
                models.append(model_info)
        
        return sorted(models, key=lambda x: x.get("name", ""))
    
    def detect_model_type(self, filename: str) -> str:
        """Detect model type from filename"""
        filename_lower = filename.lower()
        if "rtdetr" in filename_lower:
            return "rtdetr"
        elif "yolo" in filename_lower or any(x in filename_lower for x in ['yolov8', 'yolov9', 'yolov10', 'yolo11']):
            return "yolo"
        else:
            # Default to yolo for .pt files
            return "yolo"
    
    def add_model(self, name: str, description: str = "") -> Dict:
        """Add a new model entry to registry"""
        registry = self.load_registry()
        
        # Create model ID from name (sanitize)
        model_id = "".join(c if c.isalnum() or c in ['_', '-'] else '_' for c in name.lower().replace(" ", "_"))
        
        if model_id in registry["models"]:
            raise ValueError(f"Model '{name}' already exists")
        
        # Create model directory
        model_dir = self.models_path / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        
        model_info = {
            "id": model_id,
            "name": name,
            "description": description,
            "type": "unknown",  # Will be set when weights are uploaded
            "weights_file": None,
            "created_at": self._get_timestamp(),
            "available": False
        }
        
        registry["models"][model_id] = model_info
        self.save_registry(registry)
        
        return model_info
    
    def upload_weights(self, model_id: str, file_path: str, filename: str) -> Dict:
        """Upload model weights file"""
        registry = self.load_registry()
        
        if model_id not in registry["models"]:
            raise ValueError(f"Model '{model_id}' not found")
        
        model_info = registry["models"][model_id]
        model_dir = self.models_path / model_id
        
        # Detect model type from filename
        model_type = self.detect_model_type(filename)
        
        # Copy weights file
        dest_path = model_dir / filename
        shutil.copy2(file_path, dest_path)
        
        # Update registry
        model_info["weights_file"] = filename
        model_info["type"] = model_type
        model_info["available"] = True
        model_info["updated_at"] = self._get_timestamp()
        
        self.save_registry(registry)
        
        # Clear cache if model was loaded
        if model_id in self.loaded_models:
            del self.loaded_models[model_id]
        
        return model_info
    
    def delete_model(self, model_id: str):
        """Delete a model"""
        registry = self.load_registry()
        
        if model_id not in registry["models"]:
            raise ValueError(f"Model '{model_id}' not found")
        
        # Remove from cache
        if model_id in self.loaded_models:
            del self.loaded_models[model_id]
        
        # Delete directory
        model_dir = self.models_path / model_id
        if model_dir.exists():
            shutil.rmtree(model_dir)
        
        # Remove from registry
        del registry["models"][model_id]
        self.save_registry(registry)
    
    def load_model(self, model_id: str):
        """Load a model (with caching)"""
        if not ULTRALYTICS_AVAILABLE:
            raise RuntimeError("Ultralytics not installed. Cannot load models.")
        
        # Return cached model if available
        if model_id in self.loaded_models:
            return self.loaded_models[model_id]
        
        registry = self.load_registry()
        if model_id not in registry["models"]:
            raise ValueError(f"Model '{model_id}' not found")
        
        model_info = registry["models"][model_id]
        model_dir = self.models_path / model_id
        weights_file = model_dir / model_info["weights_file"]
        
        if not weights_file.exists():
            raise ValueError(f"Weights file not found for model '{model_id}'")
        
        # Load model using Ultralytics
        model_type = model_info.get("type", "yolo")
        
        if model_type == "rtdetr":
            # RTDETR models are loaded with YOLO class in ultralytics
            model = YOLO(str(weights_file))
        else:
            # YOLO models
            model = YOLO(str(weights_file))
        
        # Cache the model
        self.loaded_models[model_id] = model
        
        return model
    
    def run_inference(self, model_id: str, image_path: str, conf_threshold: float = 0.25) -> List[Dict]:
        """
        Run inference on an image
        
        Returns list of detections with normalized coordinates: [{xmin, ymin, xmax, ymax, confidence, class_id, class_name, x_center, y_center, width, height}]
        All coordinates are normalized to [0, 1] range
        """
        if not ULTRALYTICS_AVAILABLE:
            raise RuntimeError("Ultralytics not installed. Cannot run inference.")
        
        # Load model
        model = self.load_model(model_id)
        
        # Run inference
        results = model(image_path, conf=conf_threshold)
        
        # Parse results
        detections = []
        
        for result in results:
            if result.boxes is not None:
                # Get image dimensions from result (no need to read image again!)
                # result.orig_shape is (height, width)
                img_height, img_width = result.orig_shape
                
                boxes = result.boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2 in pixels
                confidences = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy().astype(int)
                
                # Get class names from model
                names = result.names if hasattr(result, 'names') else {}
                
                for i, (box, conf, cls_id) in enumerate(zip(boxes, confidences, class_ids)):
                    # Pixel coordinates
                    xmin_px = float(box[0])
                    ymin_px = float(box[1])
                    xmax_px = float(box[2])
                    ymax_px = float(box[3])
                    
                    # Calculate normalized coordinates
                    x_center = (xmin_px + xmax_px) / 2.0 / img_width
                    y_center = (ymin_px + ymax_px) / 2.0 / img_height
                    width = (xmax_px - xmin_px) / img_width
                    height = (ymax_px - ymin_px) / img_height
                    
                    # Clamp to [0, 1]
                    x_center = max(0, min(1, x_center))
                    y_center = max(0, min(1, y_center))
                    width = max(0, min(1, width))
                    height = max(0, min(1, height))
                    
                    detection = {
                        "xmin": xmin_px / img_width,  # Normalized
                        "ymin": ymin_px / img_height,  # Normalized
                        "xmax": xmax_px / img_width,  # Normalized
                        "ymax": ymax_px / img_height,  # Normalized
                        "x_center": x_center,  # Normalized center
                        "y_center": y_center,  # Normalized center
                        "width": width,  # Normalized width
                        "height": height,  # Normalized height
                        "confidence": float(conf),
                        "class_id": int(cls_id),
                        "class_name": names.get(int(cls_id), f"class_{cls_id}"),
                        "img_width": img_width,
                        "img_height": img_height
                    }
                    detections.append(detection)
        
        return detections
    
    def run_inference_on_image_data(self, model_id: str, image_data: bytes, conf_threshold: float = 0.25) -> List[Dict]:
        """Run inference on image bytes"""
        if not ULTRALYTICS_AVAILABLE:
            raise RuntimeError("Ultralytics not installed. Cannot run inference.")
        
        # Load image from bytes
        image = Image.open(io.BytesIO(image_data))
        
        # Load model
        model = self.load_model(model_id)
        
        # Run inference
        results = model(image, conf=conf_threshold)
        
        # Parse results
        detections = []
        
        for result in results:
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()
                confidences = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy().astype(int)
                
                names = result.names if hasattr(result, 'names') else {}
                
                for box, conf, cls_id in zip(boxes, confidences, class_ids):
                    detection = {
                        "xmin": float(box[0]),
                        "ymin": float(box[1]),
                        "xmax": float(box[2]),
                        "ymax": float(box[3]),
                        "confidence": float(conf),
                        "class_id": int(cls_id),
                        "class_name": names.get(int(cls_id), f"class_{cls_id}")
                    }
                    detections.append(detection)
        
        return detections
    
    def get_model_info(self, model_id: str) -> Dict:
        """Get model information"""
        registry = self.load_registry()
        if model_id not in registry["models"]:
            raise ValueError(f"Model '{model_id}' not found")
        return registry["models"][model_id]
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()


# Global model manager instance
model_manager = ModelManager()
