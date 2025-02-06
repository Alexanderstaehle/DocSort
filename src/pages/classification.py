import flet as ft
from ocr.ocr import OCRHandler
from classification.zero_shot import DocumentClassifier
from classification.company_detection import CompanyDetector
import cv2
import threading
import json
import os
import pandas as pd
from services.search_service import SearchService


class ClassificationUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.ocr_handler = OCRHandler()
        self.doc_classifier = DocumentClassifier(self.page.preferred_language)
        self.company_detector = CompanyDetector()
        self.search_service = SearchService()
        self.detected_company_name = None
        self.last_ocr_result = None

        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(""),
            action="OK",
            bgcolor=ft.Colors.GREEN_700,
        )

        self.setup_ui()
        self.page.on_route_change = self.handle_route_change

    def handle_route_change(self, e):
        if e.route == "/classify" and self.view.visible:
            threading.Thread(target=self.start_processing, daemon=True).start()

    def setup_ui(self):
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

        self.category_dropdown = ft.Dropdown(
            label="Select category",
            width=300,
        )

        self.new_category_input = ft.TextField(
            label="Add new category", width=300, visible=False
        )

        self.add_category_button = ft.FilledButton(
            "Add Category", on_click=self.add_new_category, visible=False
        )

        self.show_new_category = ft.IconButton(
            icon=ft.Icons.ADD,
            tooltip="Add new category",
            on_click=self.toggle_new_category_input,
        )

        self.category_message = ft.Text(
            "We think this document should belong in the following folder:",
            size=16,
        )

        self.company_dropdown = ft.Dropdown(
            label="Select company",
            width=300,
        )

        self.new_company_input = ft.TextField(
            label="Add new company", width=300, visible=False
        )

        self.add_company_button = ft.FilledButton(
            "Add Company", on_click=self.add_new_company, visible=False
        )

        self.show_new_company = ft.IconButton(
            icon=ft.Icons.BUSINESS,
            tooltip="Add new company",
            on_click=self.toggle_new_company_input,
        )

        self.save_button = ft.FilledButton(
            "Save Changes",
            on_click=self.save_changes,
        )

        self.filename_input = ft.TextField(
            label="Filename (automatically adds .png)",
            width=300,
            hint_text="Enter filename",
            suffix_text=".png",
            suffix_style=ft.TextStyle(color=ft.Colors.GREY_500),
        )

        self.detected_company_message = ft.Text(
            "We detected a new company. Is this spelling correct?",
            size=14,
            color=ft.Colors.BLUE,
            visible=False,
        )

        self.detected_company_field = ft.TextField(
            label="Detected company name", width=300, visible=False
        )

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
                        self.detected_company_message,
                        self.detected_company_field,
                        ft.Row(
                            controls=[
                                self.new_company_input,
                                self.add_company_button,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        ft.Text("Filename:", size=16),
                        self.filename_input,
                        self.save_button,
                    ],
                    spacing=20,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
        )

        self.save_overlay = ft.Stack(
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
                            ft.Text("Saving document...", color=ft.Colors.WHITE),
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

        self.view = ft.Stack(
            controls=[
                self.content,
                self.loading_overlay,
                self.save_overlay,
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
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            user_file = os.path.join(
                base_path, "storage", "data", "user_categories.csv"
            )

            if not os.path.exists(user_file):
                df = pd.read_csv("storage/data/category_mapping.csv")
                df.to_csv(user_file, index=False)
                self.doc_classifier.category_mapping = df

            if self.doc_classifier.add_new_category(self.new_category_input.value):
                self.doc_classifier.category_mapping.to_csv(user_file, index=False)
                self.update_category_dropdown()
                self.category_dropdown.value = self.new_category_input.value
                self.new_category_input.value = ""
                self.toggle_new_category_input(None)
            self.page.update()

    def update_category_dropdown(self):
        """Update category dropdown with user categories if available"""
        # Force reload of category mapping to ensure we have latest user categories
        self.doc_classifier.category_mapping = (
            self.doc_classifier.load_category_mapping()
        )
        categories = self.doc_classifier.get_categories_in_language(
            self.doc_classifier.preferred_language
        )
        self.category_dropdown.options = [ft.dropdown.Option(cat) for cat in categories]
        self.page.update()

    def on_language_change(self, e):
        """Handle language preference change"""
        if self.doc_classifier.set_preferred_language(e.data):
            if self.text_display.value:
                threading.Thread(target=self.start_processing, daemon=True).start()

    def set_loading(self, is_loading: bool, is_save=False):
        """Toggle loading state and disable/enable controls"""
        if is_save:
            self.save_overlay.visible = is_loading
        else:
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
        if not self.filename_input.value:
            self.page.snack_bar.bgcolor = ft.Colors.RED_700
            self.page.snack_bar.content.value = "Please enter a filename"
            self.page.open(self.page.snack_bar)
            self.page.update()
            return

        self.set_loading(True, is_save=True)

        try:
            # Get final company name - either from dropdown or detected field
            company_name = None
            if self.company_dropdown.value:
                company_name = self.company_dropdown.value
            elif (
                self.detected_company_field.visible
                and self.detected_company_field.value
            ):
                company_name = self.detected_company_field.value
                self.company_detector.add_company(company_name)

            # Get Drive service
            drive_service = self.page.drive_service
            if not drive_service:
                self.page.snack_bar.bgcolor = ft.Colors.RED_700
                self.page.snack_bar.content.value = "Google Drive not connected"
                self.page.open(self.page.snack_bar)
                self.page.update()
                return

            category = self.category_dropdown.value
            filename = f"{self.filename_input.value}.png"

            folder_path = category
            if company_name:
                folder_path = f"{category}/{company_name}"

            # Upload file to Drive first to get file ID
            folder_id = self._ensure_folder_path(drive_service, folder_path)
            image_path = self.page.client_storage.get("processed_image_path")

            if image_path and self.last_ocr_result and self.last_ocr_result["success"]:
                file = drive_service.CreateFile(
                    {"title": filename, "parents": [{"id": folder_id}]}
                )
                file.SetContentFile(image_path)
                file.Upload()

                # Add search indexing using file ID
                search_data = self.search_service.prepare_document_data(
                    text=self.last_ocr_result["full_text"],
                    category=self.category_dropdown.value,
                    company=company_name or "",
                    file_id=file["id"],
                    filename=filename,
                )

                # Load existing documents from Drive
                documents = self.search_service.load_search_data(drive_service)
                documents.append(search_data)

                # Save back to Drive
                self.search_service.save_search_data(drive_service, documents)

                self.page.snack_bar.bgcolor = ft.Colors.GREEN_700
                self.page.snack_bar.content.value = "Document saved to Google Drive!"
                self.page.open(self.page.snack_bar)

                self.page.client_storage.remove("processed_image_path")
                self.page.client_storage.set("success_folder_path", folder_path)
                self.page.client_storage.set("success_filename", filename)

                self.page.go("/success")

        except Exception as e:
            self.page.snack_bar.bgcolor = ft.Colors.RED_700
            self.page.snack_bar.content.value = f"Error saving to Drive: {str(e)}"
            self.page.open(self.page.snack_bar)
        finally:
            self.set_loading(False, is_save=True)
            self.company_detector.clear_temp_companies()

        self.page.update()

    def _ensure_folder_path(self, drive, folder_path):
        """Create folder hierarchy and return final folder ID"""
        # First ensure DocSort folder exists at root
        file_list = drive.ListFile(
            {
                "q": f"title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            }
        ).GetList()

        if not file_list:
            # Create DocSort folder if it doesn't exist
            docsort = drive.CreateFile(
                {
                    "title": "DocSort",
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [{"id": "root"}],
                }
            )
            docsort.Upload()
            parent_id = docsort["id"]
        else:
            parent_id = file_list[0]["id"]

        for folder_name in folder_path.split("/"):
            file_list = drive.ListFile(
                {
                    "q": f"title='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            if not file_list:
                folder = drive.CreateFile(
                    {
                        "title": folder_name,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [{"id": parent_id}],
                    }
                )
                folder.Upload()
                parent_id = folder["id"]
            else:
                parent_id = file_list[0]["id"]

        return parent_id

    def _upload_file(self, drive, local_path, filename, parent_id):
        """Upload file to Google Drive"""
        file = drive.CreateFile({"title": filename, "parents": [{"id": parent_id}]})
        file.SetContentFile(local_path)
        file.Upload()

    def start_processing(self):
        """Process the document with OCR and classification"""
        self.set_loading(True)

        try:
            image_path = self.page.client_storage.get("processed_image_path")
            if image_path:
                image = cv2.imread(image_path)
                if image is not None:
                    result = self.ocr_handler.process_image(image)
                    self.last_ocr_result = result

                    if result["success"]:
                        print("Document Text:")
                        print(result["full_text"])

                        detected_companies = self.company_detector.detect_companies(
                            result["full_text"]
                        )
                        existing_companies = (
                            self.company_detector.get_permanent_companies()
                        )

                        if detected_companies:
                            first_detected = detected_companies[0]
                            if first_detected not in existing_companies:
                                self.detected_company_name = first_detected
                                self.detected_company_field.value = first_detected
                                self.detected_company_message.visible = True
                                self.detected_company_field.visible = True
                            else:
                                self.company_dropdown.value = first_detected
                                self.detected_company_message.visible = False
                                self.detected_company_field.visible = False

                        self.company_dropdown.options = [
                            ft.dropdown.Option(company)
                            for company in existing_companies
                        ]

                        doc_type = self.doc_classifier.classify_text(
                            result["full_text"]
                        )

                        if not doc_type["error"] and doc_type["labels"]:
                            self.update_category_dropdown()
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
