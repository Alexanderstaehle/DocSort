import flet as ft
from ocr.ocr import OCRHandler
import cv2
import threading

class ClassificationUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.ocr_handler = OCRHandler()
        self.setup_ui()
        self.page.on_route_change = self.handle_route_change

    def handle_route_change(self, e):
        if e.route == "/classify" and self.view.visible:
            # Start processing in a separate thread
            threading.Thread(target=self.start_processing, daemon=True).start()

    def setup_ui(self):
        # Create loading indicator
        self.loading_indicator = ft.ProgressRing(visible=False)

        # Create text display area
        self.text_display = ft.TextField(
            multiline=True,
            read_only=True,
            min_lines=10,
            max_lines=20,
            width=600,
            bgcolor=ft.Colors.INVERSE_SURFACE,
            color=ft.Colors.BLACK,
        )

        # Create confidence indicator
        self.confidence_display = ft.Text(
            size=16,
            color=ft.Colors.BLUE,
        )

        self.view = ft.Column(
            controls=[
                ft.Container(
                    content=ft.FilledButton(
                        "← Back to Scanner",
                        on_click=lambda _: self.page.go("/"),
                    ),
                    padding=10,
                ),
                ft.Column(
                    controls=[
                        ft.Text("Document Text", size=24, weight=ft.FontWeight.BOLD),
                        self.loading_indicator,
                        self.confidence_display,
                        self.text_display,
                    ],
                    spacing=20,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            expand=True,
            visible=False,
        )

    def start_processing(self):
        """Process the document with OCR"""
        # Reset previous results
        self.text_display.value = ""
        self.confidence_display.value = ""
        self.loading_indicator.visible = True
        self.page.update()

        try:
            # Get the image path from client storage
            image_path = self.page.client_storage.get("processed_image_path")
            if image_path:
                # Load and process the image
                image = cv2.imread(image_path)
                if image is not None:
                    result = self.ocr_handler.process_image(image)
                    
                    if result['success']:
                        self.text_display.value = result['full_text']
                        if result['words']:
                            avg_confidence = sum(word['confidence'] for word in result['words']) / len(result['words'])
                            self.confidence_display.value = f"Average confidence: {avg_confidence:.1f}%"
                        else:
                            self.confidence_display.value = "No text detected"
                    else:
                        self.text_display.value = "Error processing document"
                        self.confidence_display.value = f"Error: {result.get('error', 'Unknown error')}"
                else:
                    self.text_display.value = "Could not load image"
                    self.confidence_display.value = "Error: Image loading failed"
        except Exception as e:
            self.text_display.value = f"An error occurred: {str(e)}"
            self.confidence_display.value = "Error: Processing failed"
        finally:
            self.loading_indicator.visible = False
            self.page.update()
