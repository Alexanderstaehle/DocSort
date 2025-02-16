from ocr.ocr import OCRHandler
from classification.zero_shot import DocumentClassifier
from classification.company_detection import CompanyDetector
from services.search_service import SearchService
import cv2
import time
import json


class ClassificationService:
    def __init__(self):
        self._initialize_services()
        self.folder_language = self._load_folder_language()

    def _initialize_services(self):
        """Initialize required services"""
        self.ocr_handler = OCRHandler()
        self.doc_classifier = DocumentClassifier()
        self.company_detector = CompanyDetector()
        self.search_service = SearchService()

    def _load_folder_language(self):
        """Load folder language from config"""
        try:
            with open("storage/data/config.json", "r") as f:
                config = json.load(f)
                return config.get("folder_language", "de")
        except:
            return "de"  # Default to German if config not found

    def update_language(self, new_language: str):
        """Update preferred language and reinitialize services"""
        self.preferred_language = new_language
        self.doc_classifier = DocumentClassifier(self.preferred_language)

    def process_document(self, image_path: str) -> dict:
        """Process document with OCR and classification"""
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError("Could not load image")

            # Perform OCR
            ocr_result = self.ocr_handler.process_image(image)
            if not ocr_result["success"]:
                raise ValueError(ocr_result.get("error", "OCR failed"))

            # Detect companies
            detected_companies = self.company_detector.detect_companies(
                ocr_result["full_text"]
            )
            existing_companies = self.company_detector.get_permanent_companies()

            # Get document classification
            doc_type = self.doc_classifier.classify_text(ocr_result["full_text"])

            # Map the category to folder language
            if doc_type["labels"]:
                doc_type["labels"] = [
                    self.doc_classifier.map_category(label, self.folder_language)
                    for label in doc_type["labels"]
                ]

            return {
                "success": True,
                "ocr_result": ocr_result,
                "detected_companies": detected_companies,
                "existing_companies": existing_companies,
                "classification": doc_type,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_document(self, drive_service, document_data: dict) -> tuple[bool, str]:
        """Save document to Drive and update search index"""
        try:
            category = document_data["category"]
            company = document_data["company"]
            filename = document_data["filename"]
            image_path = document_data["image_path"]
            ocr_text = document_data["ocr_text"]

            # Create folder path
            folder_path = f"{category}/{company}" if company else category
            folder_id = self._ensure_folder_path(drive_service, folder_path)

            # Upload file
            file = drive_service.CreateFile(
                {"title": filename, "parents": [{"id": folder_id}]}
            )
            file.SetContentFile(image_path)
            file.Upload()

            # Add to search index
            search_data = self.search_service.prepare_document_data(
                text=ocr_text,
                category=category,
                company=company,
                file_id=file["id"],
                filename=filename,
            )
            search_data["upload_timestamp"] = time.time()

            # Update search index
            documents = self.search_service.load_search_data(drive_service)
            documents.append(search_data)
            self.search_service.save_search_data(drive_service, documents)

            return True, "Document saved successfully"

        except Exception as e:
            return False, f"Error saving document: {str(e)}"

    def _ensure_folder_path(self, drive, folder_path: str) -> str:
        """Create folder hierarchy and return final folder ID"""
        # Get or create DocSort folder
        docsort_list = drive.ListFile(
            {
                "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            }
        ).GetList()

        if not docsort_list:
            docsort = drive.CreateFile(
                {
                    "title": "DocSort",
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [{"id": "root"}],
                }
            )
            docsort.Upload()
            parent_id = docsort["id"]
        else:
            parent_id = docsort_list[0]["id"]

        # Create remaining folder structure
        for folder_name in folder_path.split("/"):
            file_list = drive.ListFile(
                {
                    "q": f"title='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                }
            ).GetList()

            if not file_list:
                folder = drive.CreateFile(
                    {
                        "title": folder_name,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [{"id": parent_id}],
                    }
                )
                folder.Upload()
                parent_id = folder["id"]
            else:
                parent_id = file_list[0]["id"]

        return parent_id

    def add_company(self, company_name: str) -> bool:
        """Add a new company to the list"""
        return self.company_detector.add_company(company_name)

    def get_companies(self) -> list:
        """Get list of all companies"""
        return self.company_detector.get_companies()

    def get_categories(self, language: str) -> list:
        """Get categories in specified language"""
        return self.doc_classifier.get_categories_in_language(language)

    def add_category(self, category: str) -> bool:
        """Add a new category with translations"""
        return self.doc_classifier.add_new_category(category)
