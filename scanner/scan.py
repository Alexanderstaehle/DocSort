import cv2
import numpy as np
from scipy.spatial import distance as dist


def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 75, 200)
    return edges


def order_points(pts):
    # Sort points based on x-coordinates
    xSorted = pts[np.argsort(pts[:, 0]), :]

    # Get left-most and right-most points
    leftMost = xSorted[:2, :]
    rightMost = xSorted[2:, :]

    # Sort left-most by y-coordinate
    leftMost = leftMost[np.argsort(leftMost[:, 1]), :]
    (tl, bl) = leftMost

    # Use pythagorean theorem to identify bottom-right point
    D = dist.cdist(tl[np.newaxis], rightMost, "euclidean")[0]
    (br, tr) = rightMost[np.argsort(D)[::-1], :]

    return np.array([tl, tr, br, bl], dtype="float32")


def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # Compute width of new image
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # Compute height of new image
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    # Define destination points for "birds eye view"
    dst = np.array(
        [[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]],
        dtype="float32",
    )

    # Compute perspective transform and apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    return warped


def find_document_corners(image):
    """Returns the corners of the document in the image"""
    orig_h, orig_w = image.shape[:2]
    
    # Resize image while maintaining aspect ratio
    target_height = 500.0
    ratio = target_height / orig_h
    resized = cv2.resize(image, (int(orig_w * ratio), int(target_height)))
    
    # Convert to grayscale and blur
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection and dilation
    edges = cv2.Canny(blur, 75, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    dilated = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    
    # Find the document contour
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        
        if len(approx) == 4:
            # Scale corners back to original image size
            corners = approx.reshape(4, 2)
            corners = corners / ratio  # Scale back to original size
            return corners.astype(np.float32)
    
    # If no document found, return corners of the full image
    return np.float32([[0, 0], [orig_w, 0], [orig_w, orig_h], [0, orig_h]])


def scan_document(image):
    """Returns original image and detected corners"""
    orig = image.copy()
    corners = find_document_corners(image)
    return orig, corners
