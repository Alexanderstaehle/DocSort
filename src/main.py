import flet as ft
import asyncio
from pages.doc_scanner import DocumentScannerUI
from pages.classification import ClassificationUI
from ocr.ocr import OCRHandler
from classification.zero_shot import DocumentClassifier
from pages.google_drive_auth import GoogleDriveAuth
from pages.upload_success import UploadSuccessUI
from pages.drive_setup import DriveSetupUI
from pages.search import SearchUI


def create_app_bar(page: ft.Page, auth_handler: GoogleDriveAuth):
    """Create header bar with Google Drive status and navigation rail"""
    status_color = ft.Colors.GREEN if page.drive_service else ft.Colors.RED
    email = auth_handler.get_user_email() if page.drive_service else "Not connected"

    # Create navigation rail
    def handle_nav_change(e):
        if e.control.selected_index == 0:
            page.go("/")
        elif e.control.selected_index == 1:
            page.go("/search")
        page.update()

    nav_rail = ft.NavigationRail(
        selected_index=0 if page.route not in ["/search"] else 1,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.DOCUMENT_SCANNER_OUTLINED,
                selected_icon=ft.Icons.DOCUMENT_SCANNER,
                label="Scanner",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SEARCH_OUTLINED,
                selected_icon=ft.Icons.SEARCH,
                label="Search",
            ),
        ],
        on_change=handle_nav_change,
    )

    language_dropdown = ft.Container(
        content=ft.Dropdown(
            width=60,
            options=[
                ft.dropdown.Option("de"),
                ft.dropdown.Option("en"),
            ],
            value="de",  # Default to German
            on_change=lambda e: handle_language_change(e, page),
        ),
        margin=ft.margin.only(right=20),
    )

    status_icon = ft.Container(
        content=ft.Icon(ft.Icons.CIRCLE, color=status_color, size=12),
        tooltip=f"Google Drive Status: {email}",
        margin=ft.margin.only(right=20),
    )

    logout_button = ft.Container(
        content=ft.IconButton(
            icon=ft.Icons.LOGOUT,
            tooltip="Logout from Google Drive",
            visible=bool(page.drive_service),
            on_click=lambda _: handle_logout(page, auth_handler),
        ),
        margin=ft.margin.only(right=10),
    )

    # Create header bar using Container
    header = ft.Container(
        content=ft.Row(
            [
                ft.Text("DocSort", size=24, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [language_dropdown, status_icon, logout_button],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=10,
        bgcolor=ft.Colors.SURFACE,
    )

    # Create a container for the main content that will be updated
    content_container = ft.Container(expand=True)
    page.content_container = content_container  # Store reference for updates

    return ft.Row(
        [
            nav_rail,
            ft.VerticalDivider(width=1),
            ft.Column(
                [
                    header,
                    ft.Container(height=1, bgcolor=ft.Colors.OUTLINE_VARIANT),
                    content_container,
                ],
                expand=True,
            ),
        ],
        expand=True,
    )


def handle_logout(page: ft.Page, auth_handler: GoogleDriveAuth):
    """Handle logout action"""
    if auth_handler.logout():
        page.drive_service = None
        page.views.clear()
        page.go("/auth")
        page.update()


def handle_language_change(e, page):
    page.preferred_language = e.data
    # Update UI if drive setup is active
    if hasattr(page, "setup_ui") and page.setup_ui:
        page.setup_ui.update_categories(e.data)
    # Update UI if classification is active
    if hasattr(page, "classification_ui") and page.classification_ui:
        page.classification_ui.doc_classifier.set_preferred_language(e.data)
    page.update()


async def main(page: ft.Page):
    # Configure page
    page.title = "Document Scanner"
    page.padding = 20
    page.window_width = 1000
    page.window_height = 800
    page.auto_scroll = True

    # Set initial preferred language BEFORE creating any UI components
    page.preferred_language = "de"  # Move this line up

    # Start loading models in background
    async def load_models():
        # Initialize singleton instances
        OCRHandler()
        DocumentClassifier()

    # Start model loading in background
    asyncio.create_task(load_models())

    # Initialize refs before creating pages
    page.refs = {
        "folder_path": ft.Ref[ft.Text](),
        "filename": ft.Ref[ft.Text](),
        "image": ft.Ref[ft.Image](),
    }

    # Create pages after refs are initialized
    auth_handler = GoogleDriveAuth(page)
    setup_ui = DriveSetupUI(page)
    # Store references on page for cross-component access
    page.auth_handler = auth_handler
    page.setup_ui = setup_ui
    scanner_ui = DocumentScannerUI(page)
    classification_ui = ClassificationUI(page)
    success_ui = UploadSuccessUI(page)
    search_ui = SearchUI(page)

    # Check authentication and store drive service
    if auth_handler.check_auth():
        page.drive_service = auth_handler.get_drive_service()
        # Always go to main page on startup if already authenticated
        page.go("/")
    else:
        page.drive_service = None
        page.go("/auth")

    def route_change(e):
        # Remove any auth view before adding a new one
        page.views.clear()

        scanner_ui.editor_view.visible = False
        scanner_ui.result_view.visible = False
        classification_ui.view.visible = False

        # Create app bar for all views
        app_bar = create_app_bar(page, auth_handler)

        # Check if authentication is needed
        if not page.drive_service and page.route != "/auth":
            page.go("/auth")
            return

        # Update the content based on the route
        if page.route == "/auth":
            page.content_container.content = auth_handler.content
        elif page.route == "/setup":
            page.content_container.content = setup_ui.view
        elif page.route == "/":
            scanner_ui.editor_view.visible = True
            scanner_ui.result_view.visible = bool(
                page.client_storage.get("processed_image_path")
            )
            page.content_container.content = ft.Column(
                [scanner_ui.editor_view, scanner_ui.result_view],
                expand=True,
            )
        elif page.route == "/classify":
            classification_ui.view.visible = True
            page.content_container.content = classification_ui.view
        elif page.route == "/success":
            # Get success details from storage
            folder_path = page.client_storage.get("success_folder_path")
            filename = page.client_storage.get("success_filename")
            # Reset scanner UI to clear the image
            scanner_ui.reset_ui()
            # Show success page with details
            success_ui.show_success(folder_path, filename)
            page.content_container.content = success_ui.view
        elif page.route == "/search":
            page.content_container.content = search_ui.view

        page.views.append(
            ft.View(
                page.route,
                [app_bar],
            )
        )

        # Chain the route change events
        if hasattr(classification_ui, "handle_route_change"):
            classification_ui.handle_route_change(e)
        page.update()

    def view_pop(e):
        page.views.pop()
        if len(page.views) > 0:
            page.go(page.views[-1].route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go(page.route)


if __name__ == "__main__":
    ft.app(target=main, view=None)
