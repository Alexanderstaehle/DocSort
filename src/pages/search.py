import os
import flet as ft
import json
import shutil
from services.search_service import SearchService


class SearchUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.search_service = SearchService()
        self.setup_ui()

        self.save_file_picker = ft.FilePicker(
            on_result=self.save_file_result,
        )
        self.page.overlay.append(self.save_file_picker)
        self.current_image_path = None
        self.temp_file = None

    def setup_ui(self):
        # Create loading overlay first
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
                            ft.Text("Searching documents...", color=ft.Colors.WHITE),
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

        self.search_field = ft.TextField(
            label="Search documents",
            hint_text="Enter your search query...",
            width=400,
            on_submit=self.handle_search,
        )

        self.search_button = ft.FilledButton(
            "Search",
            on_click=self.handle_search,
        )

        self.results_list = ft.ListView(
            expand=1,
            spacing=10,
            padding=20,
        )

        # Update main view to include overlay
        self.view = ft.Stack(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Search Documents", size=32, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [self.search_field, self.search_button],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        self.results_list,
                    ],
                    spacing=20,
                    expand=True,
                ),
                self.loading_overlay,
            ],
            expand=True,
        )

    def set_loading(self, is_loading: bool):
        """Toggle loading state and disable controls"""
        self.loading_overlay.visible = is_loading
        self.search_field.disabled = is_loading
        self.search_button.disabled = is_loading
        self.page.update()

    def handle_search(self, e):
        query = self.search_field.value
        if not query or not self.page.drive_service:
            return

        # Show loading overlay
        self.set_loading(True)

        try:
            # Load documents from Drive
            documents = self.search_service.load_search_data(self.page.drive_service)
            if not documents:
                self.results_list.controls = [
                    ft.Text("No documents found", color=ft.Colors.GREY_400)
                ]
                self.page.update()
                return

            # Perform search
            results = self.search_service.search(query, documents)

            # Clear previous results
            self.results_list.controls.clear()

            # Create result cards
            for doc, score in results:
                # Get filename or use default text
                filename = doc.get("filename", "Unnamed document")
                company = doc.get("company", "")

                # Create a closure to capture the correct file_id
                def create_click_handler(file_id):
                    return lambda _: self.view_document(file_id)

                card = ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.ListTile(
                                    leading=ft.Icon(ft.Icons.FOLDER),
                                    title=ft.Text(
                                        f"Category: {doc['category']}",
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    subtitle=ft.Column(
                                        controls=[
                                            ft.Text(f"Company: {company}"),
                                            ft.Text(
                                                f"Filename: {filename}",
                                                style=ft.TextStyle(italic=True),
                                            ),
                                        ],
                                        spacing=5,
                                    ),
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        (
                                            doc["text"][:200] + "..."
                                            if len(doc["text"]) > 200
                                            else doc["text"]
                                        ),
                                        size=12,
                                    ),
                                    padding=ft.padding.only(
                                        left=16, right=16, bottom=8
                                    ),
                                ),
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.Text(f"Match: {score:.2%}", size=12),
                                            ft.FilledButton(
                                                "View Document",
                                                on_click=create_click_handler(
                                                    doc["file_id"]
                                                ),
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    padding=ft.padding.only(
                                        left=16, right=16, bottom=8
                                    ),
                                ),
                            ],
                        ),
                        padding=10,
                    )
                )
                self.results_list.controls.append(card)

        except Exception as ex:
            # Show error message
            snack_bar = ft.SnackBar(content=ft.Text(f"Error searching: {str(ex)}"))
            self.page.open(snack_bar)
        finally:
            # Hide loading overlay
            self.set_loading(False)

        self.page.update()

    def save_file_result(self, e: ft.FilePickerResultEvent):
        """Handle file save result"""
        if not e.path or not self.current_image_path:
            return

        try:
            # Ensure the path has the correct extension
            save_path = e.path
            if not save_path.lower().endswith(".png"):
                save_path += ".png"

            # Copy the image to the selected location
            shutil.copy2(self.current_image_path, save_path)
            # Show success message
            snack_bar = ft.SnackBar(content=ft.Text("File saved successfully!"))
            self.page.open(snack_bar)
        except Exception as ex:
            # Show error message
            snack_bar = ft.SnackBar(content=ft.Text(f"Error saving file: {str(ex)}"))
            self.page.open(snack_bar)
        finally:
            self.page.update()

    def view_document(self, file_id):
        """View document using Drive file ID"""
        try:
            # Get file from Drive
            file = self.page.drive_service.CreateFile({"id": file_id})

            # Create temporary file
            import tempfile
            import os

            if self.temp_file:
                try:
                    os.remove(self.temp_file)
                except:
                    pass

            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp.close()
            self.temp_file = temp.name

            # Download file
            file.GetContentFile(self.temp_file)

            # Show dialog with image
            self.current_image_path = self.temp_file

            # Get filename from Drive search data
            documents = self.search_service.load_search_data(self.page.drive_service)
            doc_data = next(
                (doc for doc in documents if doc["file_id"] == file_id), None
            )
            filename = doc_data.get("filename") if doc_data else file["title"]

            def close_dialog(e):
                self.page.close(dialog)
                self.page.update()

            def download_file(e):
                self.save_file_picker.save_file(
                    file_name=filename, allowed_extensions=["png"]
                )

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Document Preview"),
                content=ft.Container(
                    content=ft.Image(
                        src=self.temp_file,
                        width=600,
                        height=800,
                        fit=ft.ImageFit.CONTAIN,
                    ),
                    padding=10,
                ),
                actions=[
                    ft.FilledButton(
                        "Download", icon=ft.Icons.DOWNLOAD, on_click=download_file
                    ),
                    ft.TextButton("Close", on_click=close_dialog),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            self.page.open(dialog)
            self.page.update()
        except Exception as ex:
            # Show error message
            snack_bar = ft.SnackBar(content=ft.Text(f"Error viewing file: {str(ex)}"))
            self.page.open(snack_bar)
        finally:
            self.page.update()

    def __del__(self):
        """Cleanup temporary files"""
        if self.temp_file:
            try:
                os.remove(self.temp_file)
            except:
                pass
