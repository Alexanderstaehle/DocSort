import flet as ft
from pages.doc_scanner import DocumentScannerUI
from pages.classification import ClassificationUI

def main(page: ft.Page):
    # Configure page
    page.title = "Document Scanner"
    page.padding = 20
    page.window_width = 1000
    page.window_height = 800
    page.auto_scroll = True

    # Create pages
    scanner_ui = DocumentScannerUI(page)
    classification_ui = ClassificationUI(page)
    
    def route_change(e):
        scanner_ui.editor_view.visible = False
        scanner_ui.result_view.visible = False
        classification_ui.view.visible = False
        
        if page.route == "/":
            scanner_ui.editor_view.visible = True
            scanner_ui.result_view.visible = True
            page.views.append(
                ft.View(
                    "/",
                    [scanner_ui.editor_view, scanner_ui.result_view],
                )
            )
        elif page.route == "/classify":
            classification_ui.view.visible = True
            page.views.append(
                ft.View(
                    "/classify",
                    [classification_ui.view],
                )
            )
        
        # Chain the route change events
        if hasattr(classification_ui, 'handle_route_change'):
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
    ft.app(target=main)
