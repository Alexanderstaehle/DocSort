import cv2
import numpy as np
from scan import scan_document
import os

def draw_corners(image, corners):
    """Draw corners and edges on the image"""
    # Create a copy for visualization
    display = image.copy()
    
    # Draw corners
    for corner in corners:
        x, y = corner.astype(int)
        cv2.circle(display, (x, y), 15, (0, 255, 0), -1)
        cv2.circle(display, (x, y), 17, (255, 255, 255), 2)
    
    # Draw edges
    for i in range(4):
        pt1 = tuple(corners[i].astype(int))
        pt2 = tuple(corners[(i + 1) % 4].astype(int))
        cv2.line(display, pt1, pt2, (0, 255, 0), 3)
        cv2.line(display, pt1, pt2, (255, 255, 255), 1)
    
    return display

def resize_image_for_display(image, max_width=1200, max_height=800):
    """Resize image to fit within max dimensions while maintaining aspect ratio"""
    height, width = image.shape[:2]
    
    # Calculate scaling ratio
    width_ratio = max_width / width
    height_ratio = max_height / height
    scale_ratio = min(width_ratio, height_ratio)
    
    # Only resize if image is too large
    if scale_ratio < 1:
        new_width = int(width * scale_ratio)
        new_height = int(height * scale_ratio)
        return cv2.resize(image, (new_width, new_height))
    return image

def main():
    # Get the path to the example image
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    image_path = os.path.join(parent_dir, "example_images", "cell_pic.jpg")

    # Read image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image at {image_path}")
        return

    # Get original image and corners
    image, corners = scan_document(image)
    
    # Create visualization
    display_image = draw_corners(image, corners)
    
    # Resize for display while ensuring entire image is visible
    display_image = resize_image_for_display(display_image)

    # Create named window that can be resized by user
    cv2.namedWindow("Detected Document Corners", cv2.WINDOW_NORMAL)
    cv2.imshow("Detected Document Corners", display_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
