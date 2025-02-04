import flet as ft


class UploadSuccessUI:
    def __init__(self, page: ft.Page):
        self.page = page
        # Ensure refs exist
        if not hasattr(self.page, "refs"):
            self.page.refs = {
                "folder_path": ft.Ref[ft.Text](),
                "filename": ft.Ref[ft.Text](),
                "image": ft.Ref[ft.Image](),
            }
        self.setup_ui()

    def setup_ui(self):
        self.folder_path_text = ft.Text("", size=16, color=ft.Colors.BLUE)
        self.filename_text = ft.Text("", size=16, color=ft.Colors.BLUE)

        # Create the main container
        content = ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(
                                name=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                                color=ft.Colors.GREEN,
                                size=64,
                            ),
                            ft.Text(
                                "Upload Successful!",
                                size=32,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREEN,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    margin=ft.margin.only(top=20, bottom=20),
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Saved to folder:", size=16),
                            self.folder_path_text,
                            ft.Text("Filename:", size=16),
                            self.filename_text,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    margin=ft.margin.only(bottom=20),
                ),
                ft.Container(
                    content=ft.FilledButton(
                        "Upload Another Document",
                        on_click=self.handle_new_upload,
                        width=250,
                    ),
                    alignment=ft.alignment.center,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Store the view as a property
        self.view = content

    def show_success(self, folder_path, filename):
        self.folder_path_text.value = folder_path
        self.filename_text.value = filename
        self.page.update()

    def handle_new_upload(self, e):
        # Clear the stored image path
        self.page.client_storage.remove("processed_image_path")
        # Go back to main page
        self.page.go("/")
