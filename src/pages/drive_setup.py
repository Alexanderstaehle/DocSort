import flet as ft
import pandas as pd
import time
from classification.zero_shot import DocumentClassifier
from services.drive_sync_service import DriveSyncService
import os
import json


class DriveSetupUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.manual_entries = []
        self.sync_service = DriveSyncService()
        self.folder_language = "de"  # Default folder language
        self.setup_ui()

    def setup_ui(self):
        # Add language selector at the top
        self.language_dropdown = ft.Dropdown(
            label="Select folder language",
            width=300,
            value=self.folder_language,
            options=[
                ft.dropdown.Option("de", "Deutsch"),
                ft.dropdown.Option("en", "English"),
            ],
            on_change=self.on_language_change,
        )

        # Load initial categories with preferred language
        categories = self._load_initial_categories(self.page.preferred_language)

        # Create checkboxes for default categories
        self.category_checks = [
            ft.Checkbox(label=cat, value=False) for cat in categories
        ]

        # Container for manual entries
        self.manual_entries_column = ft.Column([], spacing=10)

        # Create scrollable container for checkboxes
        checkbox_container = ft.Container(
            content=ft.Column(
                self.category_checks,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
            ),
            height=300,  # Set a fixed height
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=10,
            padding=10,
        )

        # Setup content
        self.content = ft.Column(
            [
                # Header row with title and continue button
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "DocSort Drive Setup",
                                    size=32,
                                    weight=ft.FontWeight.BOLD,
                                    text_align=ft.TextAlign.LEFT,
                                ),
                            ],
                            expand=True,
                        ),
                        ft.FilledButton(
                            "Continue",
                            on_click=self.create_folders,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(
                    "Select the language for your folder structure:",
                    size=16,
                ),
                self.language_dropdown,
                ft.Divider(),
                ft.Text(
                    "Select categories to create in Google Drive:",
                    size=16,
                ),
                checkbox_container,  # Use the scrollable container
                ft.Divider(),
                ft.Text("Add custom categories:", size=16),
                self.manual_entries_column,
                ft.IconButton(
                    icon=ft.Icons.ADD_CIRCLE,
                    tooltip="Add custom category",
                    on_click=self.add_manual_entry,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        )

        # Create reset dialog
        self.reset_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Existing Setup Found"),
            content=ft.Text(
                "A DocSort folder already exists. Would you like to reset it or continue with the existing setup?"
            ),
            actions=[
                ft.TextButton("Continue", on_click=self.continue_existing),
                ft.TextButton("Reset", on_click=self.reset_drive),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # Create reset confirmation dialog
        self.reset_confirmation_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm Reset"),
            content=ft.Text(
                "WARNING: This will delete all files and folders in your DocSort folder. This action cannot be undone. Are you sure you want to continue?"
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.cancel_reset),
                ft.TextButton(
                    "Delete Everything",
                    on_click=self.confirm_reset,
                    style=ft.ButtonStyle(
                        color=ft.Colors.ERROR,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # Main view
        self.view = ft.Container(
            content=ft.Column(
                [
                    ft.Column(
                        controls=[self.content],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    )
                ],
                expand=True,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )

    def _load_initial_categories(self, language="en"):
        """Load categories from CSV file for the specified language"""
        try:
            df = pd.read_csv("storage/data/category_mapping.csv")  # Fix the path
            return df[language].unique().tolist()  # Use the specified language column
        except Exception as e:
            print(f"Error loading categories: {e}")
            return []

    def update_categories(self, language):
        """Update category list when language changes"""
        categories = self._load_initial_categories(language)
        self.category_checks = [
            ft.Checkbox(label=cat, value=False) for cat in categories
        ]
        # Update the checkbox container with new options
        checkbox_container = self.content.controls[2].content
        checkbox_container.controls = self.category_checks
        self.page.update()

    def on_language_change(self, e):
        """Handle language change in setup"""
        self.folder_language = e.data
        # Update category list to show names in selected language
        categories = self._load_initial_categories(self.folder_language)

        # Create new checkbox list with categories in selected language
        self.category_checks = [
            ft.Checkbox(label=cat, value=False) for cat in categories
        ]

        # Update the checkbox container
        checkbox_container = next(
            control
            for control in self.content.controls
            if isinstance(control, ft.Container)
            and isinstance(control.content, ft.Column)
            and all(isinstance(c, ft.Checkbox) for c in control.content.controls)
        )
        checkbox_container.content.controls = self.category_checks
        self.page.update()

    def add_manual_entry(self, e):
        """Add a new manual entry row"""

        def create_remove_handler(row_to_remove):
            return lambda e: self.remove_manual_entry(e, row_to_remove)

        entry_row = ft.Row(
            controls=[
                ft.TextField(
                    hint_text="Enter category name",
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.REMOVE_CIRCLE,
                    tooltip="Remove category",
                    on_click=None,  # Will be set after row creation
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        # Store reference to text field
        entry_row.entry_field = entry_row.controls[0]

        # Set the on_click handler now that entry_row exists
        entry_row.controls[1].on_click = create_remove_handler(entry_row)

        self.manual_entries.append(entry_row)
        self.manual_entries_column.controls.append(entry_row)
        self.page.update()

    def remove_manual_entry(self, e, row):
        """Remove a manual entry row"""
        if row in self.manual_entries:
            self.manual_entries.remove(row)
        if row in self.manual_entries_column.controls:
            self.manual_entries_column.controls.remove(row)
        self.page.update()

    def show_reset_dialog(self):
        """Show reset confirmation dialog"""
        self.page.open(self.reset_dialog)
        self.page.update()

    def continue_existing(self, e):
        """Continue with existing setup and sync files"""
        self.page.close(self.reset_dialog)
        self.page.in_reset_dialog = False

        # Show sync overlay with language detection message
        self.page.sync_overlay.visible = True
        progress_bar = self.page.sync_overlay.controls[1].content.controls[0]
        status_text = self.page.sync_overlay.controls[1].content.controls[2]
        progress_bar.value = None  # Show indeterminate progress
        status_text.value = "Detecting folder structure..."
        self.page.update()

        try:
            # Detect folder language from existing structure
            detected_lang = self._detect_folder_language()
            if detected_lang:
                # Save detected language to config
                self.save_folder_language(detected_lang)

            # Continue with sync
            if self.sync_files():
                self.page.go("/")
        finally:
            self.page.sync_overlay.visible = False
            self.page.update()

    def _detect_folder_language(self) -> str:
        """Detect folder language from existing structure"""
        try:
            # Get DocSort root folder
            docsort_list = self.page.drive_service.ListFile(
                {
                    "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            if not docsort_list:
                return None

            # Get all folders in DocSort
            folders = self.page.drive_service.ListFile(
                {
                    "q": f"'{docsort_list[0]['id']}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            folder_names = [folder["title"] for folder in folders]

            # Load category mappings
            df = pd.read_csv("storage/data/category_mapping.csv")

            # Check which language has the most matches
            lang_matches = {}
            for lang in df.columns:
                categories = df[lang].str.lower().tolist()
                matches = sum(1 for name in folder_names if name.lower() in categories)
                lang_matches[lang] = matches

            # Return language with most matches
            if lang_matches:
                detected = max(lang_matches.items(), key=lambda x: x[1])[0]
                print(f"Detected folder language: {detected}")
                return detected

            return "de"  # Default to German if no matches

        except Exception as e:
            print(f"Error detecting folder language: {e}")
            return "de"

    def reset_drive(self, e):
        """Show confirmation dialog before resetting"""
        self.page.close(self.reset_dialog)
        self.page.open(self.reset_confirmation_dialog)
        self.page.update()

    def cancel_reset(self, e):
        """Cancel reset action"""
        self.page.close(self.reset_confirmation_dialog)
        self.page.update()

    def confirm_reset(self, e):
        """Actually perform the reset after confirmation"""
        self.page.close(self.reset_confirmation_dialog)
        self.page.in_reset_dialog = False

        # Show reset overlay
        self.page.overlay_service.show_loading("Resetting Drive structure...")

        try:
            # Delay slightly to ensure overlay is shown
            time.sleep(0.1)

            # Use auth_handler to delete folder
            if self.page.auth_handler.delete_docsort_folder():
                # Delete company names file
                if os.path.exists("storage/data/company_names.csv"):
                    os.remove("storage/data/company_names.csv")

                self.page.overlay_service.hide_all()
                self.page.go("/setup")
            else:
                print("Failed to delete DocSort folder")
                # Show error message
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Failed to delete DocSort folder"),
                    bgcolor=ft.Colors.RED_700,
                )
                self.page.open(self.page.snack_bar)
                self.page.overlay_service.hide_all()
                self.page.update()
        except Exception as e:
            print(f"Error resetting drive: {e}")
            # Show error message
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error resetting Drive: {str(e)}"),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.open(self.page.snack_bar)
            self.page.overlay_service.hide_all()
            self.page.update()

    def save_user_categories(self, categories):
        """Save selected categories with translations to user_categories.csv"""
        try:
            # Get existing category mappings
            df = pd.read_csv("storage/data/category_mapping.csv")

            # Create empty DataFrame with same columns
            user_categories = pd.DataFrame(columns=df.columns)

            for category in categories:
                # Check if category exists in predefined mappings
                existing_row = df[df[self.page.preferred_language] == category]

                if not existing_row.empty:
                    # Add existing category mapping
                    user_categories = pd.concat([user_categories, existing_row])
                else:
                    # Handle manual entry
                    new_row = {}
                    source_lang = self.page.preferred_language
                    classifier = DocumentClassifier(preferred_language=source_lang)

                    # Translate to each supported language
                    for target_lang in df.columns:
                        if target_lang == source_lang:
                            new_row[target_lang] = category
                        else:
                            translated = classifier.translate_category(
                                category, source_lang, target_lang
                            )
                            new_row[target_lang] = translated

                    # Add new row to user categories
                    user_categories = pd.concat(
                        [user_categories, pd.DataFrame([new_row])], ignore_index=True
                    )

            # Save to user_categories.csv
            user_categories.to_csv("storage/data/user_categories.csv", index=False)
            return True
        except Exception as e:
            print(f"Error saving user categories: {e}")
            return False

    def create_folders(self, e):
        """Create selected folders in Drive"""
        self.page.overlay_service.show_loading("Setting up folders...")

        try:
            # Store the selected folder language
            self.save_folder_language(self.folder_language)

            # Get selected categories
            selected_cats = [
                check.label for check in self.category_checks if check.value
            ]

            # Get manual entries
            manual_cats = [
                entry.entry_field.value
                for entry in self.manual_entries
                if entry.entry_field.value
            ]

            # Combine all categories
            all_categories = selected_cats + manual_cats

            # Save user categories first
            if not self.save_user_categories(all_categories):
                raise Exception("Failed to save user categories")

            # Use drive_service instead of drive_handler
            auth_handler = self.page.auth_handler
            if auth_handler and all_categories:
                auth_handler.create_folder_structure(all_categories)
                # Navigate to main page
                self.page.go("/")
        except Exception as e:
            print(f"Error creating folders: {e}")
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error creating folders: {str(e)}"),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.open(self.page.snack_bar)
        finally:
            self.page.overlay_service.hide_all()
            self.page.update()

    def save_folder_language(self, language):
        """Save folder language to configuration"""
        config_path = "storage/data/config.json"
        config = {"folder_language": language}
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f)

    def sync_files(self):
        """Sync files with Drive"""

        def update_progress(current, total, message):
            progress_bar = self.page.sync_overlay.controls[1].content.controls[0]
            status_text = self.page.sync_overlay.controls[1].content.controls[2]
            if total > 0:
                progress_bar.value = current / total
            status_text.value = f"{message}\n({current}/{total} files)"
            self.page.update()

        # Show sync overlay
        self.page.sync_overlay.visible = True
        progress_bar = self.page.sync_overlay.controls[1].content.controls[0]
        status_text = self.page.sync_overlay.controls[1].content.controls[2]
        progress_bar.value = 0
        status_text.value = ""
        self.page.update()

        try:
            success, message = self.sync_service.sync_drive_files(
                self.page.drive_service, update_progress
            )
            self.page.sync_overlay.visible = False
            snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.GREEN_700 if success else ft.Colors.RED_700,
            )
            self.page.open(snack_bar)
            return success
        except Exception as e:
            self.page.sync_overlay.visible = False
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Error syncing: {str(e)}"),
                bgcolor=ft.Colors.RED_700,
            )
            self.page.open(snack_bar)
            return False
        finally:
            self.page.update()
