import flet as ft
from pathlib import Path
import tempfile
import shutil
import os
from typing import Optional, Dict


class FolderExplorerUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_folder_id = None
        self.folder_stack = []  # Stack to track navigation history
        self.current_path = []  # Track current path for display
        self.search_data = {}  # Cache for search index data
        self.setup_ui()

        # Setup file picker for downloads
        self.save_file_picker = ft.FilePicker(
            on_result=self.save_file_result,
        )
        self.page.overlay.append(self.save_file_picker)
        self.current_image_path = None
        self.temp_file = None

    def setup_ui(self):
        # Breadcrumb navigation
        self.breadcrumb = ft.Row(
            controls=[
                ft.TextButton(text="Root", on_click=lambda _: self.navigate_to_root())
            ],
            scroll=ft.ScrollMode.AUTO,
        )

        # Folder contents - update GridView settings
        self.contents_grid = ft.GridView(
            expand=True,
            runs_count=5,
            max_extent=150,  # Increase max_extent
            spacing=10,
            run_spacing=10,
            padding=20,
        )

        # Refresh button
        self.refresh_button = ft.IconButton(
            icon=ft.icons.REFRESH,
            tooltip="Refresh",
            on_click=lambda _: self.load_current_folder(),
        )

        self.view = ft.Column(
            controls=[
                ft.Row(
                    [
                        ft.Text("Folder Explorer", size=32, weight=ft.FontWeight.BOLD),
                        self.refresh_button,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.breadcrumb,
                self.contents_grid,
            ],
            spacing=20,
            expand=True,
        )

    def load_current_folder(self):
        """Load contents of current folder"""
        self.page.overlay_service.show_loading("Loading folder contents...")

        try:
            # Get root folder on first load
            if self.current_folder_id is None:
                docsort_list = self.page.drive_service.ListFile(
                    {
                        "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                    }
                ).GetList()
                if not docsort_list:
                    raise Exception("DocSort folder not found")
                self.current_folder_id = docsort_list[0]["id"]

            # Load search index data for sync status
            search_data = self.page.search_service.load_search_data(
                self.page.drive_service
            )
            self.search_data = {doc["file_id"]: doc for doc in search_data}

            # List current folder contents
            query = f"'{self.current_folder_id}' in parents and trashed=false"
            file_list = self.page.drive_service.ListFile({"q": query}).GetList()

            # Filter out search_data.json from file list
            file_list = [f for f in file_list if f["title"] != "search_data.json"]

            # Clear current view
            self.contents_grid.controls.clear()

            # Add items to grid
            for item in sorted(
                file_list,
                key=lambda x: (
                    x["mimeType"] != "application/vnd.google-apps.folder",
                    x["title"],
                ),
            ):
                is_folder = item["mimeType"] == "application/vnd.google-apps.folder"
                is_synced = item["id"] in self.search_data

                card = self.create_item_card(item, is_folder, is_synced)
                self.contents_grid.controls.append(card)

        except Exception as e:
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Error loading folder: {str(e)}"),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.open(snack_bar)
        finally:
            self.page.overlay_service.hide_all()
            self.page.update()

    def create_item_card(self, item: Dict, is_folder: bool, is_synced: bool) -> ft.Card:
        """Create a card for a folder or file item"""
        icon = ft.icons.FOLDER if is_folder else ft.icons.DESCRIPTION
        icon_color = ft.colors.BLUE if is_folder else (ft.colors.GREEN if is_synced else ft.colors.ORANGE)

        def handle_click(e):
            if is_folder:
                self.navigate_to_folder(item["id"], item["title"])
            else:
                self.view_document(item["id"])

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(  # Add container for icon
                            content=ft.Icon(
                                icon,
                                color=icon_color,
                                size=32,
                            ),
                            alignment=ft.alignment.center,
                            margin=ft.margin.only(top=5),
                        ),
                        ft.Container(  # Add container for text
                            content=ft.Text(
                                item["title"],
                                size=12,
                                weight=ft.FontWeight.W_500,
                                text_align=ft.TextAlign.CENTER,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            alignment=ft.alignment.center,
                            margin=ft.margin.symmetric(horizontal=5),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,  # Center vertically
                    spacing=5,
                ),
                padding=10,  # Increase padding
                on_click=handle_click,
                width=130,  # Fixed width
                height=100,  # Fixed height
            ),
        )

    def navigate_to_folder(self, folder_id: str, folder_name: str):
        """Navigate into a folder"""
        self.folder_stack.append(self.current_folder_id)
        self.current_path.append(folder_name)
        self.current_folder_id = folder_id
        self.update_breadcrumb()
        self.load_current_folder()

    def navigate_to_root(self):
        """Navigate back to root"""
        self.folder_stack = []
        self.current_path = []
        self.current_folder_id = None
        self.update_breadcrumb()
        self.load_current_folder()

    def navigate_up(self):
        """Navigate up one level"""
        if self.folder_stack:
            self.current_folder_id = self.folder_stack.pop()
            self.current_path.pop()
            self.update_breadcrumb()
            self.load_current_folder()

    def update_breadcrumb(self):
        """Update breadcrumb navigation"""
        self.breadcrumb.controls = [
            ft.TextButton(text="Root", on_click=lambda _: self.navigate_to_root())
        ]

        for i, name in enumerate(self.current_path):
            self.breadcrumb.controls.append(ft.Text(" / "))
            self.breadcrumb.controls.append(
                ft.TextButton(
                    text=name,
                    on_click=lambda _, idx=i: self.navigate_to_path_index(idx),
                )
            )
        self.page.update()

    def navigate_to_path_index(self, index: int):
        """Navigate to specific point in path"""
        if index < len(self.current_path):
            self.current_folder_id = self.folder_stack[index]
            self.folder_stack = self.folder_stack[:index]
            self.current_path = self.current_path[: index + 1]
            self.update_breadcrumb()
            self.load_current_folder()

    # Preview functionality (similar to search UI)
    def view_document(self, file_id):
        """View document preview"""
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

            def close_dialog(e):
                self.page.close(dialog)
                self.page.update()

            def download_file(e):
                allowed = ["pdf"] if ext == ".pdf" else ["png"]
                self.save_file_picker.save_file(
                    file_name=title, allowed_extensions=allowed
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
                        "Download", icon=ft.icons.DOWNLOAD, on_click=download_file
                    ),
                    ft.TextButton("Close", on_click=close_dialog),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            self.page.overlay_service.hide_all()
            self.page.open(dialog)

        except Exception as e:
            self.page.overlay_service.hide_all()
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Error viewing file: {str(e)}"),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.open(snack_bar)
        finally:
            self.page.update()

    # File handling methods (similar to search UI)
    def _create_temp_file(self, suffix: str) -> str:
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp.close()
        return temp.name

    def _process_pdf(self, file) -> tuple[str, str]:
        pdf_path = self._create_temp_file(".pdf")
        file.GetContentFile(pdf_path)

        import pypdfium2 as pdfium

        pdf_doc = pdfium.PdfDocument(pdf_path)
        page0 = pdf_doc.get_page(0)
        bitmap = page0.render(scale=2)
        pil_image = bitmap.to_pil()
        page0.close()
        pdf_doc.close()

        png_path = self._create_temp_file(".png")
        pil_image.save(png_path, format="PNG")
        return png_path, pdf_path

    def _process_image(self, file, ext: str) -> tuple[str, str]:
        image_path = self._create_temp_file(ext)
        file.GetContentFile(image_path)
        return image_path, image_path

    def save_file_result(self, e: ft.FilePickerResultEvent):
        source_path = getattr(self, "download_source", self.current_image_path)
        if not e.path or not source_path:
            return

        try:
            save_path = e.path
            if not any(save_path.lower().endswith(ext) for ext in [".pdf", ".png"]):
                allowed_ext = ".pdf" if source_path.endswith(".pdf") else ".png"
                save_path += allowed_ext
            shutil.copy2(source_path, save_path)

            snack_bar = ft.SnackBar(
                content=ft.Text("File saved successfully!"),
                bgcolor=ft.Colors.GREEN_700,
            )
            self.page.open(snack_bar)
        except Exception as e:
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Error saving file: {str(e)}"),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.open(snack_bar)
        finally:
            self.page.update()

    def __del__(self):
        """Cleanup temporary files"""
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except:
                pass
