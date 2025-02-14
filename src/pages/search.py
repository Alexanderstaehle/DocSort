import os
import flet as ft
import shutil
from services.search_service import SearchService
import pypdfium2 as pdfium
from pathlib import Path
import tempfile


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

        self.view = ft.Column(
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
        )

    def set_loading(self, is_loading: bool):
        """Toggle loading state and disable controls"""
        if is_loading:
            self.page.overlay_service.show_loading("Searching documents...")
        else:
            self.page.overlay_service.hide_all()

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
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Error searching: {str(ex)}"),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.open(snack_bar)
        finally:
            # Hide loading overlay
            self.set_loading(False)

        self.page.update()

    def save_file_result(self, e: ft.FilePickerResultEvent):
        """Handle file save result"""
        # Use download_source instead of current_image_path if available
        source_path = getattr(self, "download_source", self.current_image_path)
        if not e.path or not source_path:
            return
        try:
            save_path = e.path
            # Append proper extension if missing
            if not any(save_path.lower().endswith(ext) for ext in [".pdf", ".png"]):
                allowed_ext = ".pdf" if source_path.endswith(".pdf") else ".png"
                save_path += allowed_ext
            shutil.copy2(source_path, save_path)
            snack_bar = ft.SnackBar(
                content=ft.Text("File saved successfully!"),
                bgcolor=ft.Colors.GREEN_700,
            )
            self.page.open(snack_bar)
        except Exception as ex:
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Error saving file: {str(ex)}"),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.open(snack_bar)
        finally:
            self.page.update()

    def _create_temp_file(self, suffix: str) -> str:
        """Create and return a temporary file path."""
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp.close()
        return temp.name

    def _process_pdf(self, file) -> tuple[str, str]:
        """
        Download PDF, render first page to PNG, and return tuple:
        (path to PNG for display, path to original PDF for download)
        """
        pdf_path = self._create_temp_file(".pdf")
        file.GetContentFile(pdf_path)
        pdf_doc = pdfium.PdfDocument(pdf_path)
        page0 = pdf_doc.get_page(0)
        bitmap = page0.render(scale=2)
        pil_image = bitmap.to_pil()
        page0.close()
        pdf_doc.close()
        png_path = self._create_temp_file(".png")
        pil_image.save(png_path, format="PNG")
        return png_path, pdf_path  # display, download_source

    def _process_image(self, file, ext: str) -> tuple[str, str]:
        """
        Download image file and return tuple:
        (path to image for display, same path for download)
        """
        image_path = self._create_temp_file(ext)
        file.GetContentFile(image_path)
        return image_path, image_path

    def view_document(self, file_id):
        """View document using Drive file ID"""
        # Show loading overlay before starting
        self.page.overlay_service.show_loading("Loading document preview...")

        try:
            file = self.page.drive_service.CreateFile({"id": file_id})
            title = file["title"]
            ext = Path(title).suffix.lower()
            if ext == ".pdf":
                display_path, download_source = self._process_pdf(file)
            else:
                display_path, download_source = self._process_image(file, ext)
            self.current_image_path = display_path
            self.download_source = download_source

            # Retrieve filename from search data
            documents = self.search_service.load_search_data(self.page.drive_service)
            doc_data = next(
                (doc for doc in documents if doc["file_id"] == file_id), None
            )
            filename = doc_data.get("filename") if doc_data else title

            def close_dialog(e):
                self.page.close(dialog)
                self.page.update()

            def download_file(e):
                allowed = ["pdf"] if ext == ".pdf" else ["png"]
                self.save_file_picker.save_file(
                    file_name=filename, allowed_extensions=allowed
                )

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Document Preview"),
                content=ft.Container(
                    content=ft.Image(
                        src=display_path, width=600, height=800, fit=ft.ImageFit.CONTAIN
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

            # Hide loading overlay before showing dialog
            self.page.overlay_service.hide_all()
            self.page.open(dialog)
            self.page.update()

        except Exception as ex:
            self.page.overlay_service.hide_all()
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Error viewing file: {str(ex)}"),
                bgcolor=ft.Colors.RED_700,
            )
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
