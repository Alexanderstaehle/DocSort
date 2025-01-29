import flet as ft
import cv2
import numpy as np
import os
import tempfile
import sys
import time  # Add this with other imports at the top

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from scanner.scan import scan_document, four_point_transform


def main(page: ft.Page):
    page.title = "Document Scanner"
    page.padding = 20
    page.window_width = 1000
    page.window_height = 800
    page.auto_scroll = True

    # State variables
    corners = []
    original_image = None
    display_ratio = 1.0

    def on_corner_drag(e: ft.DragUpdateEvent, idx: int):
        # Update corner position based on drag
        corners[idx] = (
            max(0, corners[idx][0] + e.delta_x),
            max(0, corners[idx][1] + e.delta_y),
        )
        # Update visual position of corner dot
        corner_dots[idx].left = corners[idx][0] - 10
        corner_dots[idx].top = corners[idx][1] - 10
        corner_dots[idx].update()
        # Redraw connecting lines
        update_line_draggers()
        draw_edges()

    def create_corner_dot(x, y, idx):
        # Create the yellow dot container
        dot = ft.Container(
            width=20,
            height=20,
            bgcolor=ft.Colors.YELLOW,
            border_radius=10,
        )

        # Wrap in GestureDetector for dragging
        return ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.MOVE,
            drag_interval=10,
            on_pan_update=lambda e: on_corner_drag(e, idx),
            content=dot,
            left=x - 10,
            top=y - 10,
        )

    def create_line_segment(x, y, index):
        """Create a small segment of a line"""
        return ft.Container(
            width=2,
            height=2,
            bgcolor=ft.Colors.YELLOW,
            left=x,
            top=y,
        )

    def on_line_drag(e: ft.DragUpdateEvent, idx: int):
        """Handle line dragging by moving connected corners together"""
        delta_x = e.delta_x
        delta_y = e.delta_y

        # Move both connected corners
        corner1_idx = idx
        corner2_idx = (idx + 1) % 4

        for i in [corner1_idx, corner2_idx]:
            corners[i] = (
                max(0, corners[i][0] + delta_x),
                max(0, corners[i][1] + delta_y),
            )
            # Update corner dot position
            corner_dots[i].left = corners[i][0] - 10
            corner_dots[i].top = corners[i][1] - 10
            corner_dots[i].update()

        draw_edges()

    def create_line_segments(start, end, idx):
        """Create optimized line segments between two points"""
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = int(np.sqrt(dx**2 + dy**2))

        # Use fewer segments for better performance
        num_segments = min(length // 16, 50)  # Limit number of segments
        if num_segments < 2:
            num_segments = 2

        segments = []
        for j in range(num_segments):
            t = j / (num_segments - 1)
            x = start[0] + dx * t
            y = start[1] + dy * t
            segment = ft.Container(
                width=2,
                height=2,
                bgcolor=ft.Colors.YELLOW,
                left=x,
                top=y,
            )
            segments.append(segment)
        return segments

    def draw_edges():
        """Draw optimized lines between corner points"""
        # Store existing corners and image
        stack_controls = [
            c
            for c in image_stack.content.controls
            if isinstance(c, ft.Image) or c in corner_dots
        ]

        # Draw new line segments between corners
        for i in range(len(corner_dots)):
            start = corners[i]
            end = corners[(i + 1) % 4]
            segments = create_line_segments(start, end, i)
            stack_controls.extend(segments)

        image_stack.content.controls = stack_controls
        page.update()

    def create_line_dragger(idx):
        """Create an invisible draggable container for the line"""
        return ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.MOVE,
            drag_interval=10,
            on_pan_update=lambda e: on_line_drag(e, idx),
            content=ft.Container(
                bgcolor=ft.Colors.TRANSPARENT,
                width=40,  # Wider hit area
                height=40,
            ),
        )

    def update_line_draggers():
        """Update position of line drag handlers"""
        for i in range(len(corners)):
            start = corners[i]
            end = corners[(i + 1) % 4]

            # Position dragger at midpoint of line
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2

            line_draggers[i].left = mid_x - 20  # Center the hit area
            line_draggers[i].top = mid_y - 20

    def on_upload_result(e: ft.FilePickerResultEvent):
        if not e.files:
            return

        nonlocal original_image, display_ratio, corners, corner_dots, lines, line_draggers

        # Clear previous state
        corner_dots = []
        line_draggers = []
        lines = []

        # Load image and find corners
        image_path = e.files[0].path
        original_image = cv2.imread(image_path)
        _, detected_corners = scan_document(original_image)

        # Calculate display scaling
        height, width = original_image.shape[:2]
        max_dimension = 800
        display_ratio = max_dimension / max(width, height)
        display_width = int(width * display_ratio)
        display_height = int(height * display_ratio)

        # Scale corners to display size
        corners = [(x * display_ratio, y * display_ratio) for x, y in detected_corners]

        # Convert BGR to RGB for proper display
        image_rgb = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(image_rgb, (display_width, display_height))

        # Save temporary image
        temp_path = os.path.join(
            tempfile.gettempdir(), f"temp_scan_{int(time.time())}.png"
        )
        cv2.imwrite(temp_path, cv2.cvtColor(resized, cv2.COLOR_RGB2BGR))

        # Create fresh Stack instance
        image_stack.content = ft.Stack(
            width=display_width, height=display_height, controls=[]
        )

        # Add image with absolute path
        display_image = ft.Image(
            src=os.path.abspath(temp_path),
            width=display_width,
            height=display_height,
            fit=ft.ImageFit.CONTAIN,
        )

        # Add image first
        image_stack.content.controls.append(display_image)

        # Create and add corner dots and draggers
        corner_dots = [create_corner_dot(x, y, i) for i, (x, y) in enumerate(corners)]
        line_draggers = [create_line_dragger(i) for i in range(4)]

        # Add all controls in correct order
        image_stack.content.controls.extend(corner_dots)
        image_stack.content.controls.extend(line_draggers)

        # Update container dimensions
        image_stack.width = display_width
        image_stack.height = display_height

        # Update positions and redraw
        update_line_draggers()
        draw_edges()
        scan_button.visible = True
        page.update()

    def go_back_to_editor(_):
        """Return to the editor view"""
        result_view.visible = False
        editor_view.visible = True
        page.update()

    def cutout_document(_):
        if original_image is None or not corners:
            return

        # Convert corners back to original image coordinates
        corners_array = np.array(corners, dtype=np.float32) / display_ratio

        # Apply perspective transform
        warped = four_point_transform(original_image, corners_array)

        # Post-processing steps
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        sharpen = cv2.GaussianBlur(gray, (0, 0), 3)
        sharpen = cv2.addWeighted(gray, 1.5, sharpen, -0.5, 0)
        thresh = cv2.adaptiveThreshold(
            sharpen, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 15
        )

        # Save all processed images first
        original_path = save_temp_image(warped)
        sharpen_path = save_temp_image(sharpen)
        thresh_path = save_temp_image(thresh)

        # Create tabs with images
        tabs = ft.Tabs(
            selected_index=2,
            animation_duration=300,
            expand=True,
            tabs=[
                ft.Tab(
                    text="Original Scan",
                    content=ft.Container(
                        content=ft.Image(
                            src=original_path,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        padding=20,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Grayscale + Sharpened",
                    content=ft.Container(
                        content=ft.Image(
                            src=sharpen_path,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        padding=20,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Final Result",
                    content=ft.Container(
                        content=ft.Image(
                            src=thresh_path,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        padding=20,
                        expand=True,
                    ),
                ),
            ],
        )

        # Update result view with back button at top-left
        result_view.controls = [
            ft.Container(
                content=ft.FilledButton(
                    "← Back to Editor",  # Added arrow for better UX
                    on_click=go_back_to_editor,
                ),
                alignment=ft.alignment.center_left,  # Changed to left alignment
                padding=10,
            ),
            tabs,
        ]

        # Switch views
        editor_view.visible = False
        result_view.visible = True
        page.update()

    def save_temp_image(image):
        """Helper function to save image to temp file and return path"""
        temp_path = os.path.join(
            tempfile.gettempdir(), f"scan_result_{np.random.randint(0, 10000)}.png"
        )
        cv2.imwrite(temp_path, image)
        return temp_path

    # Initialize UI components
    corner_dots = []
    line_draggers = []
    lines = []
    file_picker = ft.FilePicker(on_result=on_upload_result)
    page.overlay.append(file_picker)

    upload_button = ft.ElevatedButton(
        "Upload Image",
        on_click=lambda _: file_picker.pick_files(
            allowed_extensions=["png", "jpg", "jpeg"]
        ),
    )

    scan_button = ft.ElevatedButton(
        "Apply Cutout", on_click=cutout_document, visible=False
    )

    # Main image stack needs to be set as a relative position container
    image_stack = ft.Container(
        content=ft.Stack(
            controls=[],
        ),
        width=800,
        height=600,
        bgcolor=ft.Colors.BLACK12,
        border_radius=10,
    )

    editor_view = ft.Column(
        controls=[ft.Row([upload_button, scan_button]), image_stack],
        spacing=20,
        expand=True,
    )

    result_view = ft.Column(
        controls=[],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,  # Reduced spacing
        expand=True,
    )

    page.add(editor_view, result_view)


if __name__ == "__main__":
    ft.app(target=main)
