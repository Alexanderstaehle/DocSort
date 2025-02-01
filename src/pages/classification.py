import flet as ft
from ocr.ocr import OCRHandler
from classification.zero_shot import DocumentClassifier
import cv2
import threading

class ClassificationUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.ocr_handler = OCRHandler()
        self.doc_classifier = DocumentClassifier()
        self.setup_ui()
        self.page.on_route_change = self.handle_route_change

    def handle_route_change(self, e):
        if e.route == "/classify" and self.view.visible:
            # Start processing in a separate thread
            threading.Thread(target=self.start_processing, daemon=True).start()

    def setup_ui(self):
        # Add language selector dropdown
        self.language_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(lang) for lang in self.doc_classifier.get_supported_languages()
            ],
            value=self.doc_classifier.preferred_language,
            label="Preferred Language",
            on_change=self.on_language_change,
            width=200
        )

        # Add detected language display
        self.detected_lang_display = ft.Text(
            size=16,
            color=ft.Colors.BLUE,
        )

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

        # Create document type display
        self.doc_type_display = ft.Column(
            controls=[
                ft.Text("Document Type", size=20, weight=ft.FontWeight.BOLD),
                ft.Column(controls=[], spacing=5)
            ],
            spacing=10,
        )

        self.view = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.FilledButton(
                                "← Back to Scanner",
                                on_click=lambda _: self.page.go("/"),
                            ),
                            self.language_dropdown,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    padding=10,
                ),
                ft.Column(
                    controls=[
                        ft.Text("Document Text", size=24, weight=ft.FontWeight.BOLD),
                        self.loading_indicator,
                        self.detected_lang_display,
                        self.confidence_display,
                        self.doc_type_display,
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

    def on_language_change(self, e):
        """Handle language preference change"""
        if self.doc_classifier.set_preferred_language(e.data):
            # Reclassify text if there's any
            if self.text_display.value:
                threading.Thread(target=self.start_processing, daemon=True).start()

    def start_processing(self):
        """Process the document with OCR and classification"""
        # Reset previous results
        self.text_display.value = ""
        self.confidence_display.value = ""
        self.detected_lang_display.value = ""
        self.doc_type_display.controls[1].controls = []
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

                            # Classify document
                            doc_type = self.doc_classifier.classify_text(result['full_text'])
                            
                            if doc_type['error']:
                                self.confidence_display.value = f"Classification error: {doc_type['error']}"
                            else:
                                # Display detected language
                                self.detected_lang_display.value = f"Detected language: {doc_type['language']}"
                                
                                # Display classification results
                                self.doc_type_display.controls[1].controls = [
                                    ft.Text(
                                        f"{label} ({score:.1%})",
                                        color=ft.Colors.BLUE if idx == 0 else ft.Colors.GREY_700,
                                        size=16 if idx == 0 else 14
                                    )
                                    for idx, (label, score) in enumerate(zip(doc_type['labels'], doc_type['scores']))
                                ]
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
