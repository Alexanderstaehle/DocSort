import os
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import threading
from concurrent.futures import ThreadPoolExecutor


class SearchService:
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    model = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SearchService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.model = None
            # Load model in background
            with ThreadPoolExecutor() as executor:
                executor.submit(self._load_model)

    def _load_model(self):
        """Load the sentence transformer model from local storage"""
        try:
            base_path = Path(__file__).parent.parent.parent
            models_path = base_path / "storage" / "data" / "models"
            sentence_model = "all-MiniLM-L6-v2"
            model_path = models_path / sentence_model

            if model_path.exists():
                print("Loading local sentence transformer model...")
                self.model = SentenceTransformer(str(model_path))
                print("Successfully loaded local model")
            else:
                print("Local model not found, downloading...")
                self.model = SentenceTransformer(
                    sentence_model, cache_folder=str(models_path)
                )
                print("Model downloaded and saved successfully")

        except Exception as e:
            print(f"Error in model loading: {str(e)}")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def _ensure_model_loaded(self):
        """Wait for model to be loaded"""
        while self.model is None:
            print("Waiting for sentence transformer to load...")
            import time

            time.sleep(0.5)

    def embed_text(self, text: str) -> np.ndarray:
        """Create embedding for text"""
        self._ensure_model_loaded()
        return self.model.encode(text)

    def search(self, query: str, documents: list, top_k: int = 5) -> list:
        """Search documents using cosine similarity"""
        query_embedding = self.embed_text(query)

        # Convert stored embeddings back to numpy arrays
        results = []
        for doc in documents:
            embedding = np.array(json.loads(doc["embedding"]))
            similarity = np.dot(query_embedding, embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
            )
            results.append((similarity, doc))

        # Sort by similarity and return top_k results
        results.sort(reverse=True, key=lambda x: x[0])
        return [(doc, score) for score, doc in results[:top_k]]

    def get_search_file_id(self, drive_service):
        """Get or create the search data file in Google Drive"""
        # Look for existing search data file
        file_list = drive_service.ListFile(
            {"q": "title='search_data.json' and 'root' in parents and trashed=false"}
        ).GetList()

        # Get DocSort folder
        docsort_list = drive_service.ListFile(
            {
                "q": "title='DocSort' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            }
        ).GetList()

        if not docsort_list:
            return None

        docsort_id = docsort_list[0]["id"]

        # Look for file in DocSort folder
        file_list = drive_service.ListFile(
            {
                "q": f"title='search_data.json' and '{docsort_id}' in parents and trashed=false"
            }
        ).GetList()

        if file_list:
            return file_list[0]

        # Create new file if it doesn't exist
        file = drive_service.CreateFile(
            {"title": "search_data.json", "parents": [{"id": docsort_id}]}
        )
        file.SetContentString(json.dumps([]))
        file.Upload()
        return file

    def load_search_data(self, drive_service):
        """Load search data from Google Drive"""
        file = self.get_search_file_id(drive_service)
        if not file:
            return []

        content = file.GetContentString()
        return json.loads(content) if content else []

    def save_search_data(self, drive_service, documents):
        """Save search data to Google Drive"""
        file = self.get_search_file_id(drive_service)
        if file:
            file.SetContentString(json.dumps(documents))
            file.Upload()

    def prepare_document_data(
        self, text: str, category: str, company: str, file_id: str, filename: str
    ) -> dict:
        """Prepare document data for storage using Drive file ID instead of local path"""
        self._ensure_model_loaded()

        try:
            # Get embeddings for each component separately
            filename_embedding = self.embed_text(filename)
            company_embedding = (
                self.embed_text(company)
                if company
                else np.zeros_like(filename_embedding)
            )
            category_embedding = self.embed_text(category)
            text_embedding = self.embed_text(text)

            # Apply weights to each component
            # Filename: 5.0, Company: 3.0, Category: 1.0, Text: 1.0
            weighted_embedding = (
                5.0 * filename_embedding
                + 3.0 * company_embedding
                + 1.0 * category_embedding
                + 1.0 * text_embedding
            ) / 10.0  # Normalize by sum of weights

            return {
                "text": text,
                "category": category,
                "company": company,
                "file_id": file_id,
                "filename": filename,
                "embedding": json.dumps(weighted_embedding.tolist()),
            }
        except Exception as e:
            print(f"Error preparing document data: {str(e)}")
            fallback_embedding = [0.0] * 384
            return {
                "text": text,
                "category": category,
                "company": company,
                "file_id": file_id,
                "filename": filename,
                "embedding": json.dumps(fallback_embedding),
            }
