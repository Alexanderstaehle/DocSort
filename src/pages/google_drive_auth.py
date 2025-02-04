import flet as ft
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import os.path
from classification.zero_shot import DocumentClassifier
import pandas as pd


class GoogleDriveAuth:
    def __init__(self, page: ft.Page):
        self.page = page
        self.gauth = None
        self.drive = None
        self.view = None
        self.content = self.create_content()
        # Initialize snackbar
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(""),
            bgcolor=ft.Colors.RED_700,  # Default to error color for auth messages
        )

    def create_content(self):
        """Create the authentication UI content"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Google Drive Authentication",
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Connect to Google Drive to enable document storage",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        content=ft.ElevatedButton(
                            "Connect to Google Drive", on_click=self.authenticate
                        ),
                        margin=ft.margin.only(top=20),
                        alignment=ft.alignment.center,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )

    def setup_ui(self):
        """Create the view container"""
        return ft.View(
            "/auth",
            [self.content],
        )

    def check_auth(self):
        """Check if already authenticated"""
        try:
            self.gauth = GoogleAuth()
            # Try to load saved client configuration
            self.gauth.LoadCredentialsFile("mycreds.txt")

            if self.gauth.credentials is None:
                return False
            elif self.gauth.access_token_expired:
                # Refresh them if expired
                self.gauth.Refresh()
                self.gauth.SaveCredentialsFile("mycreds.txt")
            else:
                # Initialize the saved creds
                self.gauth.Authorize()

            # Create drive instance
            self.drive = GoogleDrive(self.gauth)
            return True
        except Exception as e:
            print(f"Auth check error: {e}")
            return False

    def authenticate(self, e):
        """Handle authentication flow"""
        try:
            self.gauth = GoogleAuth()
            # This will automatically handle the auth flow including opening browser
            self.gauth.LocalWebserverAuth()
            self.gauth.SaveCredentialsFile("mycreds.txt")
            self.drive = GoogleDrive(self.gauth)
            # Set the drive service on the page before routing
            self.page.drive_service = self.drive

            # Check if setup is needed after explicit login
            if not self.check_docsort_folder():
                self.page.go("/setup")
            else:
                # Try to recreate user categories from existing folders
                if self.recreate_user_categories():
                    self.page.setup_ui.show_reset_dialog()
                    self.page.in_reset_dialog = True
                else:
                    # If recreation fails, force setup
                    self.page.go("/setup")

        except Exception as e:
            print(f"Authentication error: {e}")
            self.page.snack_bar.bgcolor = ft.Colors.RED_700
            self.page.snack_bar.content.value = (
                "Authentication failed. Please try again."
            )
            self.page.open(self.page.snack_bar)
            self.page.update()

    def get_drive_service(self):
        """Get Google Drive instance"""
        return self.drive

    def get_user_email(self):
        """Get authenticated user's email"""
        try:
            if self.drive:
                about = self.drive.GetAbout()
                return about["user"]["emailAddress"]
            return None
        except Exception as e:
            print(f"Error getting user email: {e}")
            return None

    def logout(self):
        """Handle logout and credential cleanup"""
        try:
            if os.path.exists("mycreds.txt"):
                os.remove("mycreds.txt")
            self.gauth = None
            self.drive = None
            return True
        except Exception as e:
            print(f"Logout error: {e}")
            return False

    def check_docsort_folder(self):
        """Check if DocSort folder exists"""
        try:
            if not self.drive:
                return False

            file_list = self.drive.ListFile(
                {
                    "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            return len(file_list) > 0
        except Exception as e:
            print(f"Error checking DocSort folder: {e}")
            return False

    def delete_docsort_folder(self):
        """Delete existing DocSort folder"""
        try:
            file_list = self.drive.ListFile(
                {
                    "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            for file in file_list:
                file.Trash()  # Or file.Delete() for permanent deletion
            return True
        except Exception as e:
            print(f"Error deleting DocSort folder: {e}")
            return False

    def create_folder_structure(self, categories):
        """Create DocSort folder and category subfolders"""
        try:
            # Create main DocSort folder
            docsort = self.drive.CreateFile(
                {"title": "DocSort", "mimeType": "application/vnd.google-apps.folder"}
            )
            docsort.Upload()

            # Create category subfolders
            for category in categories:
                subfolder = self.drive.CreateFile(
                    {
                        "title": category,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [{"id": docsort["id"]}],
                    }
                )
                subfolder.Upload()

            return True
        except Exception as e:
            print(f"Error creating folder structure: {e}")
            return False

    def recreate_user_categories(self):
        """Recreate user_categories.csv from existing DocSort folders"""
        try:
            if not self.drive:
                return False

            # Get DocSort folder
            file_list = self.drive.ListFile(
                {
                    "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            if not file_list:
                return False

            docsort_id = file_list[0]["id"]

            # Get all subfolders (categories)
            categories = self.drive.ListFile(
                {
                    "q": f"'{docsort_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            # Get category names
            category_names = [cat["title"] for cat in categories]

            # Create classifier instance for translations
            classifier = DocumentClassifier()

            # Create DataFrame with translations
            df = pd.DataFrame(columns=["en", "de"])  # Add more languages as needed

            # Add each category with translations
            for category in category_names:
                new_row = {}
                # Detect language of category name
                detected_lang = classifier.detect_language(category)

                # Translate to each supported language
                for lang in df.columns:
                    if lang == detected_lang:
                        new_row[lang] = category
                    else:
                        translated = classifier.translate_category(
                            category, detected_lang, lang
                        )
                        new_row[lang] = translated

                df.loc[len(df)] = new_row

            # Save to user_categories.csv
            df.to_csv("storage/data/user_categories.csv", index=False)
            return True

        except Exception as e:
            print(f"Error recreating user categories: {e}")
            return False
