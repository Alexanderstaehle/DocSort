from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import numpy as np
import cv2


class OCRHandler:
    def __init__(self):
        # Initialize DocTR model with default recognition model
        self.model = ocr_predictor(
            det_arch="db_mobilenet_v3_large",
            reco_arch="crnn_mobilenet_v3_large",
            pretrained=True,
        )

    def process_image(self, image):
        """Process image and extract text using DocTR"""
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

                        words.append({
                            "text": word.value,
                            "confidence": confidence,
                            "box": (x, y, width, height),
                        })
                        full_text.append(word.value)

            return {
                "full_text": " ".join(full_text),
                "words": words,
                "success": True
            }

        except Exception as e:
            print(f"OCR Error: {str(e)}")  # Add debug print
            return {
                "full_text": "",
                "words": [],
                "success": False,
                "error": str(e)
            }
