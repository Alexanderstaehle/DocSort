import flet as ft
import threading
from services.classification_service import ClassificationService


class ClassificationUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.classification_service = (
            ClassificationService()
        )  # Remove preferred_language parameter
        self._setup_state()
        self.setup_ui()
        self.page.on_route_change = self.handle_route_change

    def _setup_state(self):
        """Initialize state variables"""
        self.detected_company_name = None
        self.last_ocr_result = None
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(""),
            action="OK",
            bgcolor=ft.Colors.GREEN_700,
        )

    def handle_route_change(self, e):
        if e.route == "/classify" and self.view.visible:
            threading.Thread(target=self.start_processing, daemon=True).start()

    def setup_ui(self):
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
                ft.Column(  # Make this Column scrollable instead of the Container
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
                    scroll=ft.ScrollMode.AUTO,  # Add scroll here
                    expand=True,  # Make sure it expands to take available space
                ),
            ],
            expand=True,
        )

        self.view = ft.Container(
            content=self.content,
            expand=True,
            visible=False,
        )

    def toggle_new_category_input(self, e):
        self.new_category_input.visible = not self.new_category_input.visible
        self.add_category_button.visible = not self.add_category_button.visible
        self.page.update()

    def add_new_category(self, e):
        if self.new_category_input.value:
            if self.classification_service.add_category(self.new_category_input.value):
                self.update_category_dropdown()
                self.category_dropdown.value = self.new_category_input.value
                self.new_category_input.value = ""
                self.toggle_new_category_input(None)
            self.page.update()

    def update_category_dropdown(self):
        """Update category dropdown with user categories"""
        # Get categories in the folder language
        categories = self.classification_service.get_categories(
            self.classification_service.folder_language
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
            (
                self.page.overlay_service.show_saving("Saving document...")
                if is_loading
                else self.page.overlay_service.hide_all()
            )
        else:
            (
                self.page.overlay_service.show_loading("Processing document...")
                if is_loading
                else self.page.overlay_service.hide_all()
            )

        # Disable/enable controls
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
            if self.classification_service.add_company(self.new_company_input.value):
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
            self._show_error("Please enter a filename")
            return

        self.set_loading(True, is_save=True)
        try:
            # Get final company name and add to permanent list if it's from detected field
            company_name = self._get_final_company_name()
            if (
                self.detected_company_field.visible
                and self.detected_company_field.value == company_name
            ):
                self.classification_service.add_company(company_name)

            # Prepare document data
            document_data = {
                "category": self.category_dropdown.value,
                "company": company_name,
                "filename": f"{self.filename_input.value}.png",
                "image_path": self.page.client_storage.get("processed_image_path"),
                "ocr_text": self.last_ocr_result["full_text"],
            }

            # Save document
            success, message = self.classification_service.save_document(
                self.page.drive_service, document_data
            )

            if success:
                self._handle_successful_save(
                    document_data["category"], document_data["company"]
                )
            else:
                self._show_error(message)

        finally:
            self.set_loading(False, is_save=True)

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
        """Process the document"""
        self.set_loading(True)
        try:
            image_path = self.page.client_storage.get("processed_image_path")
            if image_path:
                result = self.classification_service.process_document(image_path)
                if result["success"]:
                    self.last_ocr_result = result["ocr_result"]
                    self._handle_processing_result(result)
                else:
                    self.category_message.value = f"Error: {result['error']}"
        finally:
            self.set_loading(False)

    def _handle_processing_result(self, result):
        """Handle successful processing result"""
        # Update company information
        if result["detected_companies"]:
            first_detected = result["detected_companies"][0]
            if first_detected not in result["existing_companies"]:
                self._show_detected_company(first_detected)
            else:
                self._select_existing_company(first_detected)

        self._update_company_dropdown(result["existing_companies"])

        # Update category information
        if result["classification"]["labels"]:
            self.update_category_dropdown()
            print("Category:", result["classification"]["labels"][0])
            self.category_dropdown.value = result["classification"]["labels"][0]

    def _show_detected_company(self, company_name: str):
        """Show detected company in UI"""
        self.detected_company_name = company_name
        self.detected_company_field.value = company_name
        self.detected_company_message.visible = True
        self.detected_company_field.visible = True

    def _select_existing_company(self, company_name: str):
        """Select existing company in dropdown"""
        self.company_dropdown.value = company_name
        self.detected_company_message.visible = False
        self.detected_company_field.visible = False

    def _update_company_dropdown(self, companies: list):
        """Update company dropdown with options"""
        self.company_dropdown.options = [
            ft.dropdown.Option(company) for company in companies
        ]

    def _get_final_company_name(self) -> str:
        """Get final company name from either dropdown or detected field"""
        if self.company_dropdown.value:
            return self.company_dropdown.value
        elif self.detected_company_field.visible and self.detected_company_field.value:
            return self.detected_company_field.value
        return ""

    def _show_error(self, message: str):
        """Show error message in snackbar"""
        self.page.snack_bar.bgcolor = ft.Colors.RED_700
        self.page.snack_bar.content.value = message
        self.page.open(self.page.snack_bar)
        self.page.update()

    def _handle_successful_save(self, folder_path: str, company: str):
        """Handle successful document save"""
        self.page.snack_bar.bgcolor = ft.Colors.GREEN_700
        self.page.snack_bar.content.value = "Document saved to Google Drive!"
        self.page.open(self.page.snack_bar)

        # Clear temporary data
        self.page.client_storage.remove("processed_image_path")
        folder_path = f"{folder_path}/{company}" if company else folder_path
        self.page.client_storage.set("success_folder_path", folder_path)
        self.page.client_storage.set("success_filename", self.filename_input.value)

        # Navigate to success page
        self.page.go("/success")

    def update_language(self, new_language: str):
        """Update UI language and refresh classification if needed"""
        self.preferred_language = new_language
        # No need to create new service instance as it handles folder language internally
        if self.last_ocr_result:
            threading.Thread(target=self.start_processing, daemon=True).start()
        self.page.update()
