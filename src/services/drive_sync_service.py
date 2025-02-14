import os
from pathlib import Path
import tempfile
import json
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from services.search_service import SearchService
import pandas as pd
from classification.zero_shot import DocumentClassifier
from docling.datamodel.pipeline_options import PdfPipelineOptions


class DriveSyncService:
    def __init__(self):
        self.search_service = SearchService()

        # Set up docling with local models
        base_path = Path(__file__).parent.parent.parent
        artifacts_path = base_path / "storage" / "data" / "models" / "docling"
        pipeline_options = PdfPipelineOptions(artifacts_path=str(artifacts_path))

        self.doc_converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            },
        )
        self.doc_classifier = DocumentClassifier()

    def list_drive_files(
        self, drive_service, folder_id="root", files_dict=None, current_path=None
    ):
        """Recursively list all files in DocSort folder"""
        if files_dict is None:
            files_dict = {}
            print("Starting file listing from root")

        try:
            # Force refresh of file list with maxResults parameter and orderBy
            file_list = drive_service.ListFile(
                {
                    "q": f"'{folder_id}' in parents and trashed=false",
                    "orderBy": "modifiedDate desc",  # Order by most recently modified
                    "supportsAllDrives": True,  # Support all drive types
                    "includeItemsFromAllDrives": True,
                }
            ).GetList()

            # Add small delay to ensure API response is complete
            import time

            time.sleep(0.5)

            print(f"Scanning folder: {current_path or 'root'}")
            print(f"Found {len(file_list)} items in {current_path or 'root'}")

            for file_item in file_list:
                if file_item["title"] == "search_data.json":
                    continue

                # Build the path
                item_path = file_item["title"]
                if current_path:
                    item_path = f"{current_path}/{item_path}"

                print(f"Processing: {item_path}")

                if file_item["mimeType"] == "application/vnd.google-apps.folder":
                    # Recursively process subfolders with retry logic
                    retry_count = 3
                    while retry_count > 0:
                        try:
                            print(f"Found folder: {item_path}")
                            self.list_drive_files(
                                drive_service, file_item["id"], files_dict, item_path
                            )
                            break
                        except Exception as e:
                            print(
                                f"Error processing folder {item_path}, retries left: {retry_count-1}"
                            )
                            retry_count -= 1
                            time.sleep(1)  # Wait before retry
                            if retry_count == 0:
                                raise e
                else:
                    # Only process files that are in the correct structure
                    path_parts = item_path.split("/")
                    if (
                        len(path_parts) >= 3
                    ):  # DocSort/Category/file or DocSort/Category/Company/file
                        print(f"Adding file to process: {item_path}")

                        # Fix company detection logic
                        is_in_company_folder = len(path_parts) > 3
                        category = path_parts[
                            1
                        ]  # Category is always the first subfolder

                        if is_in_company_folder:
                            # If file is in a company subfolder
                            company = path_parts[2]
                            filename = path_parts[-1]
                        else:
                            # If file is directly in category folder
                            company = ""
                            filename = path_parts[-1]

                        files_dict[file_item["id"]] = {
                            "title": filename,
                            "modifiedDate": file_item["modifiedDate"],
                            "mimeType": file_item["mimeType"],
                            "path": item_path,
                            "category": category,
                            "company": company,
                        }
                    else:
                        print(f"Skipping file with invalid path structure: {item_path}")

        except Exception as e:
            print(f"Error listing files in {current_path}: {str(e)}")
            raise  # Re-raise to trigger retry logic

        return files_dict

    def sync_categories_and_companies(self, drive_service):
        """Sync categories and companies from Drive folder structure"""
        try:
            # Get DocSort folder
            docsort_list = drive_service.ListFile(
                {
                    "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            if not docsort_list:
                return

            # Get all categories (direct subfolders of DocSort)
            categories = drive_service.ListFile(
                {
                    "q": f"'{docsort_list[0]['id']}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            # Load existing categories and companies
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            user_categories_path = os.path.join(
                base_path, "storage", "data", "user_categories.csv"
            )
            companies_path = os.path.join(
                base_path, "storage", "data", "company_names.csv"
            )

            # Load or create category DataFrame
            if os.path.exists(user_categories_path):
                categories_df = pd.read_csv(user_categories_path)
            else:
                categories_df = pd.DataFrame(columns=["en", "de"])

            # Load existing companies
            companies = set()
            if os.path.exists(companies_path):
                with open(companies_path, "r", encoding="utf-8") as f:
                    companies = set(line.strip() for line in f.readlines())

            # Process categories and their subfolders
            new_categories = set()
            new_companies = set()

            for category in categories:
                cat_name = category["title"]
                if (
                    cat_name not in categories_df["de"].values
                    and cat_name not in categories_df["en"].values
                ):
                    new_categories.add(cat_name)

                # Check for company folders
                company_folders = drive_service.ListFile(
                    {
                        "q": f"'{category['id']}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                    }
                ).GetList()

                for company in company_folders:
                    if company["title"] not in companies:
                        new_companies.add(company["title"])

            # Add new categories with translations
            if new_categories:
                print(f"Adding new categories: {new_categories}")
                for category in new_categories:
                    self.doc_classifier.add_new_category(category)

            # Add new companies (append mode)
            if new_companies:
                print(f"Adding new companies: {new_companies}")
                companies.update(new_companies)
                # Write all companies back to file
                with open(companies_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(sorted(companies)))

            return True

        except Exception as e:
            print(f"Error syncing categories and companies: {str(e)}")
            return False

    def sync_drive_files(self, drive_service, progress_callback=None):
        """Sync files from Drive with search index"""
        try:
            # First sync categories and companies
            self.sync_categories_and_companies(drive_service)

            # Get DocSort folder
            docsort_list = drive_service.ListFile(
                {
                    "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            if not docsort_list:
                return False, "DocSort folder not found"

            print("Found DocSort folder, starting file scan...")

            # Get all files in DocSort starting with DocSort as the root path
            all_files = self.list_drive_files(
                drive_service, docsort_list[0]["id"], None, "DocSort"
            )

            if not all_files:
                print("No files found in DocSort folder structure")
                return True, "No files found in DocSort folder"

            # Filter out files that aren't in a category subfolder
            valid_files = {
                file_id: file_info
                for file_id, file_info in all_files.items()
                if "category"
                in file_info  # Only process files that are in a proper category folder
            }

            if not valid_files:
                return (
                    False,
                    "No properly structured files found. Files must be in category subfolders.",
                )

            # Load existing search data
            search_data = self.search_service.load_search_data(drive_service)
            existing_files = {doc["file_id"]: doc for doc in search_data}

            # Debug print for investigation
            print(f"Total valid files in Drive: {len(valid_files)}")
            print(f"Total files in search index: {len(existing_files)}")

            # Track files that need processing and existing files
            files_to_process = []
            metadata_updates = []  # New list for files that only need metadata updates
            new_search_data = []

            for file_id, file_info in valid_files.items():
                existing_file = existing_files.get(file_id)

                if existing_file:
                    # Check what kind of update is needed
                    metadata_changed = (
                        existing_file.get("category") != file_info["category"]
                        or existing_file.get("company") != file_info["company"]
                    )
                    content_changed = (
                        existing_file.get("modifiedDate") != file_info["modifiedDate"]
                    )

                    if content_changed and "upload_timestamp" not in existing_file:
                        # Only reprocess if content changed and file wasn't just uploaded
                        print(f"Content changes detected for: {file_info['title']}")
                        files_to_process.append((file_id, file_info))
                    elif metadata_changed:
                        # Only metadata update needed
                        print(f"Metadata changes detected for: {file_info['title']}")
                        print(
                            f"Old category/company: {existing_file.get('category')}/{existing_file.get('company')}"
                        )
                        print(
                            f"New category/company: {file_info['category']}/{file_info['company']}"
                        )

                        # Create updated metadata while preserving existing embeddings
                        updated_doc = existing_file.copy()
                        updated_doc.update(
                            {
                                "category": file_info["category"],
                                "company": file_info["company"],
                                "path": file_info["path"],
                                "modifiedDate": file_info["modifiedDate"],
                            }
                        )
                        metadata_updates.append(updated_doc)
                    else:
                        # No changes, keep existing data
                        new_search_data.append(existing_file)
                else:
                    # New file, needs full processing
                    print(f"New file found: {file_info['title']}")
                    files_to_process.append((file_id, file_info))

            total_files = len(files_to_process)
            print(f"Files to process: {total_files}")
            print(f"Metadata updates: {len(metadata_updates)}")

            # Add metadata updates to new_search_data
            new_search_data.extend(metadata_updates)

            # Process files that need full processing
            if total_files > 0:
                if progress_callback:
                    progress_callback(0, total_files, "Starting sync...")

                # Process each file
                for idx, (file_id, file_info) in enumerate(files_to_process, 1):
                    if progress_callback:
                        progress_callback(
                            idx, total_files, f"Processing {file_info['title']}..."
                        )

                    temp_file = None
                    try:
                        # Create temp file with context manager
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=Path(file_info["title"]).suffix
                        ) as temp:
                            temp_file = temp.name  # Store the name for later cleanup
                            file = drive_service.CreateFile({"id": file_id})
                            file.GetContentFile(temp.name)

                        # Process file after the context manager has closed it
                        path_parts = file_info["path"].split("/")
                        category = path_parts[1] if len(path_parts) > 1 else "Unsorted"
                        company = path_parts[2] if len(path_parts) > 2 else ""

                        print(
                            f"Processing {file_info['title']} in {category}/{company}"
                        )

                        # Convert document to text
                        conv_results = self.doc_converter.convert_all([Path(temp_file)])
                        text = ""
                        for res in conv_results:
                            text += res.document.export_to_markdown()

                        # Create document data
                        doc_data = self.search_service.prepare_document_data(
                            text=text,
                            category=file_info["category"],
                            company=file_info["company"],
                            file_id=file_id,
                            filename=file_info["title"],
                        )
                        doc_data["modifiedDate"] = file_info["modifiedDate"]
                        new_search_data.append(doc_data)

                    except Exception as e:
                        print(f"Error processing file {file_info['title']}: {str(e)}")
                        continue
                    finally:
                        # Clean up temp file in finally block
                        if temp_file and os.path.exists(temp_file):
                            try:
                                os.unlink(temp_file)
                            except Exception as e:
                                print(f"Error cleaning up temp file: {str(e)}")

                # Save updated search data
                self.search_service.save_search_data(drive_service, new_search_data)
                return (
                    True,
                    f"Synced {total_files} files, updated metadata for {len(metadata_updates)} files",
                )
            else:
                if metadata_updates:
                    # Save if we have metadata updates even without full processing
                    self.search_service.save_search_data(drive_service, new_search_data)
                    return True, f"Updated metadata for {len(metadata_updates)} files"
                return True, "No files needed syncing"

        except Exception as e:
            print(f"Sync error: {str(e)}")
            return False, f"Sync error: {str(e)}"
