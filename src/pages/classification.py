from timeit import Timer
import flet as ft
from ocr.ocr import OCRHandler
from classification.zero_shot import DocumentClassifier
from classification.company_detection import CompanyDetector
import cv2
import threading
import time


class ClassificationUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.ocr_handler = OCRHandler()
        self.doc_classifier = DocumentClassifier()
        self.company_detector = CompanyDetector()
        
        # Initialize the snackbar at page level
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(""),
            action="OK",
        )
        
        self.setup_ui()
        self.page.on_route_change = self.handle_route_change

    def handle_route_change(self, e):
        if e.route == "/classify" and self.view.visible:
            # Start processing in a separate thread
            threading.Thread(target=self.start_processing, daemon=True).start()

    def setup_ui(self):
        # Create loading overlay
        self.loading_overlay = ft.Stack(
            controls=[
                ft.Container(
                    bgcolor=ft.Colors.BLACK,
                    opacity=0.7,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.ProgressRing(),
                            ft.Text("Detecting category...", color=ft.Colors.WHITE),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                ),
            ],
            expand=True,
            visible=False,
        )

        # Create category dropdown
        self.category_dropdown = ft.Dropdown(
            label="Select category",
            width=300,
        )

        # Create new category input
        self.new_category_input = ft.TextField(
            label="Add new category", width=300, visible=False
        )

        # Create add category button
        self.add_category_button = ft.FilledButton(
            "Add Category", on_click=self.add_new_category, visible=False
        )

        # Create toggle for new category input
        self.show_new_category = ft.IconButton(
            icon=ft.Icons.ADD,
            tooltip="Add new category",
            on_click=self.toggle_new_category_input,
        )

        self.category_message = ft.Text(
            "We think this document should belong in the following folder:",
            size=16,
        )

        # Create company dropdown
        self.company_dropdown = ft.Dropdown(
            label="Select company",
            width=300,
        )

        # Create new company input
        self.new_company_input = ft.TextField(
            label="Add new company", width=300, visible=False
        )

        # Create add company button
        self.add_company_button = ft.FilledButton(
            "Add Company", on_click=self.add_new_company, visible=False
        )

        # Create toggle for new company input
        self.show_new_company = ft.IconButton(
            icon=ft.Icons.BUSINESS,
            tooltip="Add new company",
            on_click=self.toggle_new_company_input,
        )

        # Create save button
        self.save_button = ft.FilledButton(
            "Save Changes",
            on_click=self.save_changes,
        )

        # Create content container
        self.content = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.FilledButton(
                                "← Back to Scanner",
                                on_click=lambda _: self.page.go("/"),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=10,
                ),
                ft.Column(
                    controls=[
                        self.category_message,
                        ft.Row(
                            controls=[
                                self.category_dropdown,
                                self.show_new_category,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            controls=[
                                self.new_category_input,
                                self.add_category_button,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        ft.Text("Detected Company:", size=16),
                        ft.Row(
                            controls=[
                                self.company_dropdown,
                                self.show_new_company,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            controls=[
                                self.new_company_input,
                                self.add_company_button,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        self.save_button,
                    ],
                    spacing=20,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
        )

        # Main view with stack for overlay
        self.view = ft.Stack(
            controls=[
                self.content,
                self.loading_overlay,
            ],
            expand=True,
            visible=False,
        )

    def toggle_new_category_input(self, e):
        self.new_category_input.visible = not self.new_category_input.visible
        self.add_category_button.visible = not self.add_category_button.visible
        self.page.update()

    def add_new_category(self, e):
        if self.new_category_input.value:
            if self.doc_classifier.add_new_category(self.new_category_input.value):
                # Update dropdown options
                self.update_category_dropdown()
                # Select the new category
                self.category_dropdown.value = self.new_category_input.value
                # Clear and hide the input
                self.new_category_input.value = ""
                self.toggle_new_category_input(None)
            self.page.update()

    def update_category_dropdown(self):
        categories = self.doc_classifier.get_categories_in_language(
            self.doc_classifier.preferred_language
        )
        self.category_dropdown.options = [ft.dropdown.Option(cat) for cat in categories]
        self.page.update()

    def on_language_change(self, e):
        """Handle language preference change"""
        if self.doc_classifier.set_preferred_language(e.data):
            # Reclassify text if there's any
            if self.text_display.value:
                threading.Thread(target=self.start_processing, daemon=True).start()

    def set_loading(self, is_loading: bool):
        """Toggle loading state and disable/enable controls"""
        self.loading_overlay.visible = is_loading
        self.category_dropdown.disabled = is_loading
        self.new_category_input.disabled = is_loading
        self.add_category_button.disabled = is_loading
        self.show_new_category.disabled = is_loading
        self.company_dropdown.disabled = is_loading
        self.new_company_input.disabled = is_loading
        self.add_company_button.disabled = is_loading
        self.show_new_company.disabled = is_loading
        self.save_button.disabled = is_loading
        self.page.update()

    def toggle_new_company_input(self, e):
        self.new_company_input.visible = not self.new_company_input.visible
        self.add_company_button.visible = not self.add_company_button.visible
        self.page.update()

    def add_new_company(self, e):
        if self.new_company_input.value:
            if self.company_detector.add_company(self.new_company_input.value):
                self.update_company_dropdown()
                self.company_dropdown.value = self.new_company_input.value
                self.new_company_input.value = ""
                self.toggle_new_company_input(None)
            self.page.update()

    def update_company_dropdown(self):
        companies = self.company_detector.get_companies()
        self.company_dropdown.options = [
            ft.dropdown.Option(company) for company in companies
        ]
        self.page.update()

    def save_changes(self, e):
        if self.category_dropdown.value:
            self.doc_classifier.add_new_category(self.category_dropdown.value)
        if self.company_dropdown.value:
            self.company_detector.add_company(self.company_dropdown.value)
        
        # Update the snackbar content and show it
        self.page.snack_bar.content.value = "Changes saved successfully!"
        self.page.snack_bar.open = True
        
        # Clear the stored image path
        self.page.client_storage.remove("processed_image_path")
        
        def navigate_back():
            self.page.go("/")
            # Reset UI elements
            self.category_dropdown.value = None
            self.company_dropdown.value = None
            self.page.update()
            
        threading.Timer(1.0, navigate_back).start()
        self.page.update()

    def start_processing(self):
        """Process the document with OCR and classification"""
        self.set_loading(True)

        try:
            # Get the image path from client storage
            image_path = self.page.client_storage.get("processed_image_path")
            if image_path:
                # Load and process the image
                image = cv2.imread(image_path)
                if image is not None:
                    result = self.ocr_handler.process_image(image)

                    if result["success"]:
                        # Print text to console
                        print("Document Text:")
                        print(result["full_text"])

                        # Detect companies
                        companies = self.company_detector.detect_companies(
                            result["full_text"]
                        )
                        # Update company dropdown
                        self.update_company_dropdown()
                        if companies:
                            self.company_dropdown.value = companies[0]

                        # Classify document
                        doc_type = self.doc_classifier.classify_text(
                            result["full_text"]
                        )

                        if not doc_type["error"] and doc_type["labels"]:
                            # Update dropdown with all categories
                            self.update_category_dropdown()
                            # Set the predicted category
                            self.category_dropdown.value = doc_type["labels"][0]
                        else:
                            self.category_message.value = f"Error: {doc_type['error']}"
                    else:
                        self.category_message.value = (
                            f"Error: {result.get('error', 'Unknown error')}"
                        )
                else:
                    self.category_message.value = "Could not load image"
        except Exception as e:
            self.category_message.value = f"An error occurred: {str(e)}"
        finally:
            self.set_loading(False)
