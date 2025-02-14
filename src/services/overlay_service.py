import flet as ft


class OverlayService:
    def __init__(self, page: ft.Page):
        self.page = page
        self._setup_overlays()

    def _setup_overlays(self):
        """Setup global overlays"""
        # Loading overlay
        self.loading_overlay = ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(),
                    ft.Text("Loading...", color=ft.Colors.WHITE),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.7, ft.Colors.BLACK),
            width=float("inf"),  # Make container span full width
            height=float("inf"),  # Make container span full height
            visible=False,
        )

        # Save overlay
        self.save_overlay = ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(),
                    ft.Text("Saving...", color=ft.Colors.WHITE),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.7, ft.Colors.BLACK),
            width=float("inf"),  # Make container span full width
            height=float("inf"),  # Make container span full height
            visible=False,
        )

        # Create overlay stack that will be positioned on top of everything
        self.page.overlay_stack = ft.Stack(
            controls=[self.loading_overlay, self.save_overlay],
            width=float("inf"),
            height=float("inf"),
        )

    def show_loading(self, message: str = "Loading..."):
        """Show loading overlay with custom message"""
        self.loading_overlay.content.controls[1].value = message
        self.loading_overlay.visible = True
        self.page.update()

    def show_saving(self, message: str = "Saving..."):
        """Show saving overlay with custom message"""
        self.save_overlay.content.controls[1].value = message
        self.save_overlay.visible = True
        self.page.update()

    def hide_all(self):
        """Hide all overlays"""
        self.loading_overlay.visible = False
        self.save_overlay.visible = False
        self.page.update()
