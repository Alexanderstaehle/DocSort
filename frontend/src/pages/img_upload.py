import cv2
import numpy as np
import os
import tempfile
import time
import flet as ft

from scanner.scan import scan_document, four_point_transform


class ImageProcessor:
    def __init__(self):
        self.temp_files = []

    def load_image(self, image_path):
        """Load and prepare image for display"""
        original_image = cv2.imread(image_path)
        if original_image is None:
            return None

        # Find corners
        _, detected_corners = scan_document(original_image)

        # Calculate display scaling
        height, width = original_image.shape[:2]
        max_dimension = 800
        display_ratio = max_dimension / max(width, height)
        display_width = int(width * display_ratio)
        display_height = int(height * display_ratio)

        # Scale corners to display size
        corners = [(x * display_ratio, y * display_ratio) for x, y in detected_corners]

        # Prepare display image
        image_rgb = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(image_rgb, (display_width, display_height))

        # Save temporary image
        temp_path = self._save_temp_image(cv2.cvtColor(resized, cv2.COLOR_RGB2BGR))

        return {
            "image": original_image,
            "display_ratio": display_ratio,
            "corners": corners,
            "display_width": display_width,
            "display_height": display_height,
            "display_image": ft.Image(
                src=temp_path,
                width=display_width,
                height=display_height,
                fit=ft.ImageFit.CONTAIN,
            ),
        }

    def process_document(self, original_image, corners, display_ratio):
        """Process document and return paths to processed images"""
        # Convert corners back to original image coordinates
        corners_array = np.array(corners, dtype=np.float32) / display_ratio

        # Apply perspective transform
        warped = four_point_transform(original_image, corners_array)

        # Process images
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        sharpen = cv2.GaussianBlur(gray, (0, 0), 3)
        sharpen = cv2.addWeighted(gray, 1.5, sharpen, -0.5, 0)
        thresh = cv2.adaptiveThreshold(
            sharpen, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 15
        )

        # Save processed images
        return {
            "Original Scan": self._save_temp_image(warped),
            "Grayscale + Sharpened": self._save_temp_image(sharpen),
            "Final Result": self._save_temp_image(thresh),
        }

    def _save_temp_image(self, image):
        """Save image to temporary file and return path"""
        temp_path = os.path.join(
            tempfile.gettempdir(),
            f"scan_result_{int(time.time())}_{np.random.randint(0, 10000)}.png",
        )
        cv2.imwrite(temp_path, image)
        self.temp_files.append(temp_path)
        return temp_path

    def __del__(self):
        """Cleanup temporary files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
