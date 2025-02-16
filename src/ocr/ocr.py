import os
import torch
from doctr.io import DocumentFile
from doctr.models import ocr_predictor, db_mobilenet_v3_large, crnn_mobilenet_v3_large
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor
import threading


class OCRHandler:
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    model = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(OCRHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.model = None
            # Start loading models in background
            with ThreadPoolExecutor() as executor:
                executor.submit(self._load_models)

    def _load_models(self):
        """Load OCR models from local storage"""
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            models_path = os.path.join(base_path, "storage", "data", "models", "ocr")

            # Ensure models directory exists
            os.makedirs(models_path, exist_ok=True)

            det_model_path = os.path.join(models_path, "db_mobilenet_v3_large.pt")
            reco_model_path = os.path.join(models_path, "crnn_mobilenet_v3_large.pt")

            # Initialize models
            det_model = db_mobilenet_v3_large(
                pretrained=False, pretrained_backbone=False
            )
            reco_model = crnn_mobilenet_v3_large(
                pretrained=False, pretrained_backbone=False
            )

            # Download and save models if they don't exist
            if not os.path.exists(det_model_path) or not os.path.exists(
                reco_model_path
            ):
                # Initialize a temporary predictor to get pretrained weights
                temp_predictor = ocr_predictor(
                    det_arch="db_mobilenet_v3_large",
                    reco_arch="crnn_mobilenet_v3_large",
                    pretrained=True,
                )

                # Save models
                torch.save(
                    temp_predictor.det_predictor.model.state_dict(), det_model_path
                )
                torch.save(
                    temp_predictor.reco_predictor.model.state_dict(), reco_model_path
                )
                del temp_predictor

            # Load models from local storage with weights_only=True
            det_params = torch.load(
                det_model_path, map_location="cpu", weights_only=True
            )
            det_model.load_state_dict(det_params)

            reco_params = torch.load(
                reco_model_path, map_location="cpu", weights_only=True
            )
            reco_model.load_state_dict(reco_params)

            # Create predictor
            self.model = ocr_predictor(det_model, reco_model, pretrained=False)
            print("OCR models loaded successfully")

        except Exception as e:
            print(f"Error loading OCR models: {str(e)}")
            # Fall back to loading from HuggingFace
            self.model = ocr_predictor(
                det_arch="db_mobilenet_v3_large",
                reco_arch="crnn_mobilenet_v3_large",
                pretrained=True,
            )

    def process_image(self, image):
        """Process image and extract text using DocTR"""
        # Wait for model to be loaded
        while self.model is None:
            print("Waiting for OCR model to load...")
            import time

            time.sleep(0.5)

        try:
            # Convert BGR to RGB (OpenCV uses BGR, DocTR expects RGB)
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            elif len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

            # Create document from numpy array directly
            result = self.model([image])

            # Extract text and confidence scores
            full_text = []
            words = []

            # Process first page (since we only have one image)
            page = result.pages[0]
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        # DocTR confidence is already 0-1
                        confidence = float(word.confidence) * 100

                        # Get bounding box coordinates
                        # DocTR uses relative coordinates in format [[xmin, ymin], [xmax, ymax]]
                        h, w = image.shape[:2]
                        ((xmin, ymin), (xmax, ymax)) = word.geometry

                        x = int(xmin * w)
                        y = int(ymin * h)
                        width = int((xmax - xmin) * w)
                        height = int((ymax - ymin) * h)

                        words.append(
                            {
                                "text": word.value,
                                "confidence": confidence,
                                "box": (x, y, width, height),
                            }
                        )
                        full_text.append(word.value)

            return {"full_text": " ".join(full_text), "words": words, "success": True}

        except Exception as e:
            print(f"OCR Error: {str(e)}")
            return {"full_text": "", "words": [], "success": False, "error": str(e)}
