import flet as ft
import numpy as np
import cv2
from pages.img_upload import ImageProcessor
from pages.classification import ClassificationUI


class DocumentScannerUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.corners = []
        self.corner_dots = []
        self.line_draggers = []
        self.lines = []
        self.original_image = None
        self.display_ratio = 1.0
        self.image_processor = ImageProcessor()
        self.classification_ui = ClassificationUI(page)
        self.max_display_height = 0.7  # 70% of screen height
        self.max_display_width = 0.9  # 90% of screen width
        self.current_display_width = 0
        self.current_display_height = 0
        self.padding = 20
        self.base_container = None

        # Initialize UI components
        self.setup_ui()
        self.page.on_route_change = lambda e: self.handle_route_change(e.route)

    def setup_ui(self):
        self.file_picker = ft.FilePicker(on_result=self.on_upload_result)
        self.page.overlay.append(self.file_picker)

        self.upload_button = ft.ElevatedButton(
            "Upload Image",
            on_click=lambda _: self.file_picker.pick_files(
                allowed_extensions=["png", "jpg", "jpeg"]
            ),
        )

        self.scan_button = ft.ElevatedButton(
            "Apply Cutout", on_click=self.cutout_document, visible=False
        )

        self.image_stack = ft.Container(
            content=ft.Stack(controls=[], clip_behavior=ft.ClipBehavior.NONE),
            bgcolor=ft.Colors.BLACK12,
            border_radius=10,
            alignment=ft.alignment.center,
            clip_behavior=ft.ClipBehavior.NONE,
        )

        self.editor_view = ft.Column(
            controls=[
                ft.Row(
                    [self.upload_button, self.scan_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=self.image_stack,
                    alignment=ft.alignment.center,
                ),
            ],
            spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.result_view = ft.Column(
            controls=[],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        )
        self.result_view.controls.append(self.classification_ui.view)

    def calculate_display_dimensions(self, image_width, image_height):
        """Calculate display dimensions based on screen size and image aspect ratio"""
        # Get available screen dimensions (account for padding)
        available_width = (self.page.window_width * self.max_display_width) - (
            2 * self.padding
        )
        available_height = (self.page.window_height * self.max_display_height) - (
            2 * self.padding
        )

        # Calculate aspect ratio
        aspect_ratio = image_width / image_height

        # Calculate display dimensions maintaining aspect ratio
        if image_width > image_height:
            # Landscape orientation
            display_width = min(available_width, image_width)
            display_height = display_width / aspect_ratio
            if display_height > available_height:
                display_height = available_height
                display_width = display_height * aspect_ratio
        else:
            # Portrait orientation
            display_height = min(available_height, image_height)
            display_width = display_height * aspect_ratio
            if display_width > available_width:
                display_width = available_width
                display_height = display_width / aspect_ratio

        return display_width, display_height

    def constrain_corner(self, x, y):
        """Constrain corner coordinates to valid image area including padding"""
        x = max(self.padding, min(x, self.current_display_width + self.padding))
        y = max(self.padding, min(y, self.current_display_height + self.padding))
        return (x, y)

    def check_corner_constraints(self, new_x, new_y, idx):
        """Check if the new position maintains a valid rectangle"""
        # corners order: [top-left, top-right, bottom-right, bottom-left]
        if idx == 0:  # top-left
            max_x = self.corners[1][0] - 10  # can't go past top-right
            max_y = self.corners[3][1] - 10  # can't go past bottom-left
            new_x = max(self.padding, min(new_x, max_x))
            new_y = max(self.padding, min(new_y, max_y))
        elif idx == 1:  # top-right
            min_x = self.corners[0][0] + 10  # can't go past top-left
            max_y = self.corners[2][1] - 10  # can't go past bottom-right
            new_x = max(min_x, min(new_x, self.current_display_width + self.padding))
            new_y = max(self.padding, min(new_y, max_y))
        elif idx == 2:  # bottom-right
            min_x = self.corners[3][0] + 10  # can't go past bottom-left
            min_y = self.corners[1][1] + 10  # can't go past top-right
            new_x = max(min_x, min(new_x, self.current_display_width + self.padding))
            new_y = max(min_y, min(new_y, self.current_display_height + self.padding))
        else:  # bottom-left (idx == 3)
            max_x = self.corners[2][0] - 10  # can't go past bottom-right
            min_y = self.corners[0][1] + 10  # can't go past top-left
            new_x = max(self.padding, min(new_x, max_x))
            new_y = max(min_y, min(new_y, self.current_display_height + self.padding))

        return new_x, new_y

    def create_corner_dot(self, x, y, idx):
        """Create a corner dot with size relative to current display dimensions"""
        dot_size = min(
            max(
                (
                    self.current_display_width * 0.025
                    if self.current_display_width
                    else 10
                ),
                10,
            ),
            20,
        )

        # Define Colors for each corner for better visibility
        corner_Colors = {
            0: ft.Colors.RED,  # Top-left
            1: ft.Colors.GREEN,  # Top-right
            2: ft.Colors.BLUE,  # Bottom-right
            3: ft.Colors.YELLOW,  # Bottom-left
        }

        corner_labels = {
            0: "TL",  # Top-left
            1: "TR",  # Top-right
            2: "BR",  # Bottom-right
            3: "BL",  # Bottom-left
        }

        dot = ft.Container(
            width=dot_size,
            height=dot_size,
            bgcolor=corner_Colors[idx],
            border_radius=dot_size / 2,
            tooltip=corner_labels[idx],
        )

        return ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.MOVE,
            drag_interval=10,
            on_pan_update=lambda e: self.on_corner_drag(e, idx),
            content=dot,
            left=x - dot_size / 2,
            top=y - dot_size / 2,
        )

    def create_line_dragger(self, idx):
        return ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.MOVE,
            drag_interval=10,
            on_pan_update=lambda e: self.on_line_drag(e, idx),
            content=ft.Container(
                bgcolor=ft.Colors.TRANSPARENT,
                width=40,
                height=40,
            ),
        )

    def create_line_segments(self, start, end, idx):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = int(np.sqrt(dx**2 + dy**2))
        num_segments = min(length // 16, 50)
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

    def on_corner_drag(self, e: ft.DragUpdateEvent, idx: int):
        new_x = self.corners[idx][0] + e.delta_x
        new_y = self.corners[idx][1] + e.delta_y

        # Apply both rectangle and boundary constraints
        new_x, new_y = self.check_corner_constraints(new_x, new_y, idx)

        self.corners[idx] = (new_x, new_y)

        # Calculate dot size for proper centering
        dot_size = min(
            max(
                (
                    self.current_display_width * 0.025
                    if self.current_display_width
                    else 10
                ),
                10,
            ),
            20,
        )
        self.corner_dots[idx].left = new_x - dot_size / 2
        self.corner_dots[idx].top = new_y - dot_size / 2
        self.corner_dots[idx].update()

        self.update_line_draggers()
        self.draw_edges()

    def on_line_drag(self, e: ft.DragUpdateEvent, idx: int):
        delta_x = e.delta_x
        delta_y = e.delta_y

        corner1_idx = idx
        corner2_idx = (idx + 1) % 4

        # Try moving both corners
        for i in [corner1_idx, corner2_idx]:
            new_x = self.corners[i][0] + delta_x
            new_y = self.corners[i][1] + delta_y

            # Apply both rectangle and boundary constraints
            new_x, new_y = self.check_corner_constraints(new_x, new_y, i)
            self.corners[i] = (new_x, new_y)

            # Calculate dot size for proper centering
            dot_size = min(
                max(
                    (
                        self.current_display_width * 0.025
                        if self.current_display_width
                        else 10
                    ),
                    10,
                ),
                20,
            )
            self.corner_dots[i].left = new_x - dot_size / 2
            self.corner_dots[i].top = new_y - dot_size / 2
            self.corner_dots[i].update()

        self.draw_edges()

    def update_line_draggers(self):
        for i in range(len(self.corners)):
            start = self.corners[i]
            end = self.corners[(i + 1) % 4]
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            self.line_draggers[i].left = mid_x - 20
            self.line_draggers[i].top = mid_y - 20

    def draw_edges(self):
        """Update method to include base container in stack controls"""
        stack_controls = [
            c
            for c in self.image_stack.content.controls
            if isinstance(c, ft.Container) and c.content == self.base_container
        ]
        stack_controls.extend(self.corner_dots)

        for i in range(len(self.corner_dots)):
            start = self.corners[i]
            end = self.corners[(i + 1) % 4]
            segments = self.create_line_segments(start, end, i)
            stack_controls.extend(segments)

        self.image_stack.content.controls = stack_controls
        self.page.update()

    def on_upload_result(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return

        image_data = self.image_processor.load_image(e.files[0].path)
        if image_data is None:
            return

        # Calculate display dimensions
        self.current_display_width, self.current_display_height = (
            self.calculate_display_dimensions(
                image_data["display_width"], image_data["display_height"]
            )
        )

        # Update display ratio
        original_display_ratio = image_data["display_ratio"]
        new_display_ratio = self.current_display_width / image_data["display_width"]
        self.display_ratio = original_display_ratio * new_display_ratio

        # Scale corners according to new display ratio
        self.corners = [
            (x * new_display_ratio, y * new_display_ratio)
            for x, y in image_data["corners"]
        ]
        self.original_image = image_data["image"]

        # Reset UI components
        self.corner_dots = []
        self.line_draggers = []
        self.lines = []

        # Create the base container with padding
        self.base_container = ft.Container(
            width=self.current_display_width,
            height=self.current_display_height,
            content=ft.Image(
                src=e.files[0].path,
                width=self.current_display_width,
                height=self.current_display_height,
                fit=ft.ImageFit.CONTAIN,
            ),
        )

        # Update UI with new image with padding
        self.image_stack.content = ft.Stack(
            width=self.current_display_width + (2 * self.padding),
            height=self.current_display_height + (2 * self.padding),
            controls=[
                ft.Container(
                    content=self.base_container,
                    margin=self.padding,
                )
            ],
            clip_behavior=ft.ClipBehavior.NONE,  # Allow interaction outside bounds
        )

        # Adjust corners for padding
        self.corners = [(x + self.padding, y + self.padding) for x, y in self.corners]

        # Create and add corner dots and draggers
        self.corner_dots = [
            self.create_corner_dot(x, y, i) for i, (x, y) in enumerate(self.corners)
        ]
        self.line_draggers = [self.create_line_dragger(i) for i in range(4)]

        # Add all controls
        self.image_stack.content.controls.extend(self.corner_dots)
        self.image_stack.content.controls.extend(self.line_draggers)

        # Explicitly set container dimensions
        self.image_stack.width = self.current_display_width + (2 * self.padding)
        self.image_stack.height = self.current_display_height + (2 * self.padding)

        self.update_line_draggers()
        self.draw_edges()
        self.scan_button.visible = True
        self.page.update()

    def go_back_to_editor(self, _):
        self.result_view.visible = False
        self.editor_view.visible = True
        self.page.update()

    def cutout_document(self, _):
        if self.original_image is None or not self.corners:
            return

        # Remove padding from corners before processing
        adjusted_corners = [
            (x - self.padding, y - self.padding) for x, y in self.corners
        ]

        result_data = self.image_processor.process_document(
            self.original_image, adjusted_corners, self.display_ratio
        )

        if result_data is None:
            return

        # Create tabs with processed images
        tabs = ft.Tabs(
            selected_index=2,
            animation_duration=300,
            expand=True,
            tabs=[
                ft.Tab(
                    text=title,
                    content=ft.Container(
                        content=ft.Image(
                            src=path,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        padding=20,
                        expand=True,
                    ),
                )
                for title, path in result_data.items()
            ],
        )

        # Next button to go to classification
        next_button = ft.FilledButton(
            "Next →",
            on_click=lambda _: self.page.go("/classify"),
        )

        # Update result view
        self.result_view.controls = [
            ft.Container(
                content=ft.Row(
                    [
                        ft.FilledButton(
                            "← Back to Editor",
                            on_click=self.go_back_to_editor,
                        ),
                        next_button,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=10,
            ),
            tabs,
        ]

        # Store the processed image path in page data for classification
        self.page.client_storage.set(
            "processed_image_path", result_data["Final Result"]
        )

        self.editor_view.visible = False
        self.result_view.visible = True
        self.page.update()

    def reset_ui(self):
        """Reset UI to initial state"""
        self.corners = []
        self.corner_dots = []
        self.line_draggers = []
        self.lines = []
        self.original_image = None
        self.scan_button.visible = False
        self.base_container = None  # Reset base container

        # Reset image stack
        self.image_stack.content = ft.Stack(
            controls=[], clip_behavior=ft.ClipBehavior.NONE
        )
        self.image_stack.width = None
        self.image_stack.height = None

        # Clear result view
        self.result_view.controls = []
        self.result_view.controls.append(self.classification_ui.view)

    def handle_route_change(self, route):
        """Handle route changes"""
        if route == "/" and (self.editor_view.visible or self.result_view.visible):
            if not self.page.client_storage.get("processed_image_path"):
                self.reset_ui()
                self.editor_view.visible = True
                self.result_view.visible = False
                self.page.update()
