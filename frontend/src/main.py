import flet as ft
from pages.doc_scanner import DocumentScannerUI


def main(page: ft.Page):
    # Configure page
    page.title = "Document Scanner"
    page.padding = 20
    page.window_width = 1000
    page.window_height = 800
    page.auto_scroll = True

    # Initialize UI
    scanner_ui = DocumentScannerUI(page)
    page.add(scanner_ui.editor_view, scanner_ui.result_view)


if __name__ == "__main__":
    ft.app(target=main)
