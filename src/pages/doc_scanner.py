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

        # Initialize UI components
        self.setup_ui()

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
            content=ft.Stack(controls=[]),
            width=800,
            height=600,
            bgcolor=ft.Colors.BLACK12,
            border_radius=10,
        )

        self.editor_view = ft.Column(
            controls=[ft.Row([self.upload_button, self.scan_button]), self.image_stack],
            spacing=20,
            expand=True,
        )

        self.result_view = ft.Column(
            controls=[],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        )
        self.result_view.controls.append(self.classification_ui.view)

    def create_corner_dot(self, x, y, idx):
        dot = ft.Container(
            width=20,
            height=20,
            bgcolor=ft.Colors.YELLOW,
            border_radius=10,
        )

        return ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.MOVE,
            drag_interval=10,
            on_pan_update=lambda e: self.on_corner_drag(e, idx),
            content=dot,
            left=x - 10,
            top=y - 10,
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
        self.corners[idx] = (
            max(0, self.corners[idx][0] + e.delta_x),
            max(0, self.corners[idx][1] + e.delta_y),
        )
        self.corner_dots[idx].left = self.corners[idx][0] - 10
        self.corner_dots[idx].top = self.corners[idx][1] - 10
        self.corner_dots[idx].update()
        self.update_line_draggers()
        self.draw_edges()

    def on_line_drag(self, e: ft.DragUpdateEvent, idx: int):
        delta_x = e.delta_x
        delta_y = e.delta_y

        corner1_idx = idx
        corner2_idx = (idx + 1) % 4

        for i in [corner1_idx, corner2_idx]:
            self.corners[i] = (
                max(0, self.corners[i][0] + delta_x),
                max(0, self.corners[i][1] + delta_y),
            )
            self.corner_dots[i].left = self.corners[i][0] - 10
            self.corners[i].top = self.corners[i][1] - 10
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
        stack_controls = [
            c
            for c in self.image_stack.content.controls
            if isinstance(c, ft.Image) or c in self.corner_dots
        ]

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

        self.original_image = image_data["image"]
        self.display_ratio = image_data["display_ratio"]
        self.corners = image_data["corners"]

        # Reset UI components
        self.corner_dots = []
        self.line_draggers = []
        self.lines = []

        # Update UI with new image
        self.image_stack.content = ft.Stack(
            width=image_data["display_width"],
            height=image_data["display_height"],
            controls=[image_data["display_image"]],
        )

        # Create and add corner dots and draggers
        self.corner_dots = [
            self.create_corner_dot(x, y, i) for i, (x, y) in enumerate(self.corners)
        ]
        self.line_draggers = [self.create_line_dragger(i) for i in range(4)]

        # Add all controls
        self.image_stack.content.controls.extend(self.corner_dots)
        self.image_stack.content.controls.extend(self.line_draggers)

        # Update container dimensions
        self.image_stack.width = image_data["display_width"]
        self.image_stack.height = image_data["display_height"]

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

        result_data = self.image_processor.process_document(
            self.original_image, self.corners, self.display_ratio
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
        self.page.client_storage.set("processed_image_path", result_data['Final Result'])

        self.editor_view.visible = False
        self.result_view.visible = True
        self.page.update()
