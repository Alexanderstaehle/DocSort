from utils.warning_filters import setup_warning_filters

setup_warning_filters()

import flet as ft
from pages.doc_scanner import DocumentScannerUI
from pages.classification import ClassificationUI
from pages.google_drive_auth import GoogleDriveAuth
from pages.upload_success import UploadSuccessUI
from pages.drive_setup import DriveSetupUI
from pages.search import SearchUI
from services.drive_sync_service import DriveSyncService
from services.overlay_service import OverlayService


def create_app_structure(page: ft.Page, auth_handler: GoogleDriveAuth):
    """Create the main app structure with Pagelet (called once during initialization)"""

    def update_drive_status():
        """Update drive status in AppBar"""
        status_color = ft.Colors.GREEN if page.drive_service else ft.Colors.RED
        email = auth_handler.get_user_email() if page.drive_service else "Not connected"

        # Update status icon
        actions[1].content.color = status_color
        actions[1].tooltip = f"Google Drive Status: {email}"

        # Update sync and logout button visibility
        actions[2].content.visible = bool(page.drive_service)  # sync button
        actions[3].content.visible = bool(page.drive_service)  # logout button

        # Update navigation bar visibility
        page.main_pagelet.navigation_bar.visible = bool(page.drive_service)

        page.update()

    # Store update function on page for access from other components
    page.update_drive_status = update_drive_status

    def handle_nav_change(e):
        if e.control.selected_index == 0:
            page.go("/")
        elif e.control.selected_index == 1:
            page.go("/search")
        page.update()

    # Create sync overlay
    page.sync_overlay = ft.Stack(
        controls=[
            ft.Container(
                bgcolor=ft.Colors.BLACK,
                opacity=0.7,
                expand=True,
            ),
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressBar(width=300),
                        ft.Text("Syncing files...", color=ft.Colors.WHITE),
                        ft.Text("", color=ft.Colors.WHITE, size=12),  # Status text
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

    def handle_sync(e):
        if not page.drive_service:
            return

        # Reset overlay content
        page.sync_overlay.visible = True
        progress_bar = page.sync_overlay.controls[1].content.controls[0]
        status_text = page.sync_overlay.controls[1].content.controls[2]
        progress_bar.value = 0  # Reset progress bar
        status_text.value = ""  # Reset status text
        page.update()

        def update_progress(current, total, message):
            if total > 0:  # Avoid division by zero
                progress_bar.value = current / total
            status_text.value = f"{message}\n({current}/{total} files)"
            page.update()

        sync_service = DriveSyncService()
        success, message = sync_service.sync_drive_files(
            page.drive_service, update_progress
        )

        page.sync_overlay.visible = False
        snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.GREEN_700 if success else ft.Colors.RED_700,
        )
        page.open(snack_bar)
        page.update()

    # Create app bar actions
    actions = [
        ft.Container(
            content=ft.Dropdown(
                width=60,
                options=[
                    ft.dropdown.Option("de"),
                    ft.dropdown.Option("en"),
                ],
                value="de",
                on_change=lambda e: handle_language_change(e, page),
            ),
            margin=ft.margin.only(right=20),
        ),
        ft.Container(
            content=ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.RED, size=12),
            tooltip="Google Drive Status: Not connected",
            margin=ft.margin.only(right=20),
        ),
        ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.SYNC,
                tooltip="Sync with Google Drive",
                visible=False,
                on_click=handle_sync,
            ),
            margin=ft.margin.only(right=10),
        ),
        ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.LOGOUT,
                tooltip="Logout from Google Drive",
                visible=False,
                on_click=lambda _: handle_logout(page, auth_handler),
            ),
            margin=ft.margin.only(right=10),
        ),
    ]

    # Create content container
    content_container = ft.Container(expand=True)
    page.content_container = content_container

    # Create navigation bar with initial visible=False
    navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.DOCUMENT_SCANNER_OUTLINED,
                selected_icon=ft.Icons.DOCUMENT_SCANNER,
                label="Scanner",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SEARCH_OUTLINED,
                selected_icon=ft.Icons.SEARCH,
                label="Search",
            ),
        ],
        on_change=handle_nav_change,
        selected_index=0,
        visible=False,  # Initially hidden
    )

    # Create permanent Pagelet structure
    page.main_pagelet = ft.Pagelet(
        expand=True,
        appbar=ft.AppBar(
            title=ft.Text("DocSort", size=24, weight=ft.FontWeight.BOLD),
            actions=actions,
            bgcolor=ft.Colors.SURFACE,
        ),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=1, bgcolor=ft.Colors.OUTLINE_VARIANT),
                    ft.Container(
                        content=content_container,
                        expand=True,
                        padding=20,
                    ),
                ],
                expand=True,
                spacing=0,
            ),
            expand=True,
        ),
        navigation_bar=navigation_bar,
    )

    return page.main_pagelet


def handle_logout(page: ft.Page, auth_handler: GoogleDriveAuth):
    """Handle logout action"""
    if auth_handler.logout():
        page.drive_service = None
        page.views.clear()
        page.update_drive_status()
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
    page.window_width = 1000
    page.window_height = 800
    page.auto_scroll = True
    page.theme = ft.Theme(
        page_transitions=ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.OPEN_UPWARDS,
            ios=ft.PageTransitionTheme.CUPERTINO,
            macos=ft.PageTransitionTheme.FADE_UPWARDS,
            linux=ft.PageTransitionTheme.ZOOM,
            windows=ft.PageTransitionTheme.NONE,
        )
    )

    # Set initial preferred language before creating any UI components
    page.preferred_language = "de"

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

    # Initialize overlay service
    page.overlay_service = OverlayService(page)

    # Check authentication and store drive service
    if auth_handler.check_auth():
        page.drive_service = auth_handler.get_drive_service()
        # Always go to main page on startup if already authenticated
        page.go("/")
    else:
        page.drive_service = None
        page.go("/auth")

    # Create main app structure once
    main_pagelet = create_app_structure(page, auth_handler)

    # Initial update of drive status
    page.update_drive_status()

    def route_change(e):
        page.views.clear()
        scanner_ui.editor_view.visible = False
        scanner_ui.result_view.visible = False
        classification_ui.view.visible = False

        # Update navigation bar visibility along with selected index
        if page.drive_service:
            page.main_pagelet.navigation_bar.visible = True
            page.main_pagelet.navigation_bar.selected_index = (
                1 if page.route == "/search" else 0
            )
        else:
            page.main_pagelet.navigation_bar.visible = False

        # Check if authentication is needed
        if not page.drive_service and page.route != "/auth":
            page.go("/auth")
            return

        # Update only the content based on the route
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
            folder_path = page.client_storage.get("success_folder_path")
            filename = page.client_storage.get("success_filename")
            scanner_ui.reset_ui()
            success_ui.show_success(folder_path, filename)
            page.content_container.content = success_ui.view
        elif page.route == "/search":
            page.content_container.content = search_ui.view

        # Update view with existing Pagelet and overlays
        page.views.append(
            ft.View(
                page.route,
                [
                    ft.Stack(
                        [
                            ft.Container(  # Wrap everything in a container
                                content=ft.Stack(
                                    [
                                        page.main_pagelet,
                                        page.sync_overlay,
                                    ],
                                ),
                                expand=True,
                            ),
                            page.overlay_stack,  # Place overlay_stack last for highest z-index
                        ],
                        expand=True,
                    ),
                ],
            )
        )

        if hasattr(classification_ui, "handle_route_change"):
            classification_ui.handle_route_change(e)
        # Update drive status when route changes
        page.update_drive_status()
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
