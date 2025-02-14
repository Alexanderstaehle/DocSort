import os
import csv
import pandas as pd
from transformers import pipeline
from concurrent.futures import ThreadPoolExecutor
import threading
from langdetect import detect
import argostranslate.package
import argostranslate.translate
import shutil


class DocumentClassifier:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, preferred_language="de"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DocumentClassifier, cls).__new__(cls)
        return cls._instance

    def __init__(self, preferred_language="de"):
        if not self._initialized:
            self._initialized = True
            self.classifier = None
            self.preferred_language = preferred_language
            self.default_categories = ["Other"]
            self.category_mapping = self.load_category_mapping()
            self.supported_languages = self.get_supported_languages()
            self.categories = self.get_categories_in_language("en")
            self.debug = True
            self.lang_to_model = {"de": "de-en", "nl": "nl-en", "en": None}

            # Start loading models in background
            with ThreadPoolExecutor() as executor:
                executor.submit(self._load_models)

    def _load_models(self):
        """Load NLP models"""
        try:
            # Set up local model directories
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            models_path = os.path.join(base_path, "storage", "data", "models")
            argos_path = os.path.join(models_path, "argos")

            # Ensure model directories exist
            os.makedirs(argos_path, exist_ok=True)

            # Load classifier with local model path
            self.classifier = pipeline(
                "zero-shot-classification",
                model="MoritzLaurer/ModernBERT-base-zeroshot-v2.0",
                device=-1,
                model_kwargs={"cache_dir": models_path, "local_files_only": True},
            )

            # Point argostranslate to our local package directory
            argostranslate.package.INSTALLED_PACKAGES_PATH = argos_path

            # Check if we have packages installed by trying to get installed languages
            installed_languages = argostranslate.translate.get_installed_languages()

            if not installed_languages:
                print("No local packages found, downloading...")
                # Download and install Argos Translate packages
                argostranslate.package.update_package_index()
                available_packages = argostranslate.package.get_available_packages()

                # Install required language pairs
                for source_lang, lang_pair in self.lang_to_model.items():
                    if lang_pair:
                        try:
                            # Find packages for both directions
                            to_en_package = next(
                                (
                                    pkg
                                    for pkg in available_packages
                                    if pkg.from_code == source_lang
                                    and pkg.to_code == "en"
                                ),
                                None,
                            )
                            en_to_package = next(
                                (
                                    pkg
                                    for pkg in available_packages
                                    if pkg.from_code == "en"
                                    and pkg.to_code == source_lang
                                ),
                                None,
                            )

                            # Download and install packages
                            if to_en_package:
                                package_path = to_en_package.download()
                                argostranslate.package.install_from_path(package_path)
                            if en_to_package:
                                package_path = en_to_package.download()
                                argostranslate.package.install_from_path(package_path)
                        except Exception as e:
                            print(
                                f"Error installing language pair for {source_lang}: {str(e)}"
                            )
            else:
                print("Using existing local packages")

            print("Classification models loaded successfully")

        except Exception as e:
            print(f"Error loading models: {str(e)}")

    def _ensure_models_loaded(self):
        """Wait for models to be loaded"""
        while self.classifier is None:
            print("Waiting for models to load...")
            import time

            time.sleep(0.5)

    def load_category_mapping(self):
        """Load category mappings from CSV file into a pandas DataFrame"""
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            user_file = os.path.join(
                base_path, "storage", "data", "user_categories.csv"
            )
            default_file = os.path.join(
                base_path, "storage", "data", "category_mapping.csv"
            )

            # Try to load user categories first
            if os.path.exists(user_file):
                return pd.read_csv(user_file)

            # Fall back to default categories
            return pd.read_csv(default_file)

        except Exception as e:
            print(f"Error loading category mapping: {str(e)}")
            return pd.DataFrame({"en": self.default_categories})

    def get_supported_languages(self):
        """Get list of supported languages from CSV columns"""
        return list(self.category_mapping.columns)

    def get_categories_in_language(self, lang):
        """Get categories in specified language"""
        if lang in self.supported_languages:
            return self.category_mapping[lang].tolist()
        return self.default_categories

    def detect_language(self, text):
        """Detect the language of the text using langdetect"""
        try:
            # Truncate text for language detection if needed
            sample_text = text[:1000]  # Use first 1000 chars for detection

            lang_mapping = ["en", "de", "fr", "es", "it", "nl"]
            detected = detect(sample_text)

            print("Detected language:", detected)
            return detected if detected in lang_mapping else "de"
        except Exception as e:
            print(f"Language detection error: {str(e)}")
            return "de"  # Default to German on error

    def _split_into_chunks(self, text, max_tokens, tokenizer):
        """Split text into chunks that fit within token limit"""
        chunks = []
        current_chunk = ""

        # Split text into sentences (rough approximation)
        sentences = text.replace("\n", ". ").split(". ")

        for sentence in sentences:
            # Skip empty sentences
            if not sentence.strip():
                continue

            # Try adding sentence to current chunk
            test_chunk = current_chunk + ". " + sentence if current_chunk else sentence
            tokens = tokenizer(test_chunk, return_tensors="pt")

            # If adding sentence would exceed limit, save current chunk and start new one
            if tokens.input_ids.shape[1] > max_tokens and current_chunk:
                chunks.append(current_chunk)
                current_chunk = sentence
            # Otherwise add sentence to current chunk
            else:
                current_chunk = test_chunk

        # Add final chunk if it exists
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def translate_to_english(self, text, source_lang):
        """Translate text to English using Argos Translate"""
        try:
            if source_lang == "en":
                return text

            if source_lang not in self.lang_to_model:
                print(f"No translation model available for {source_lang}")
                return text

            # Get installed languages
            installed_languages = argostranslate.translate.get_installed_languages()

            # Find the right language objects
            from_lang = next(
                (lang for lang in installed_languages if lang.code == source_lang), None
            )
            to_lang = next(
                (lang for lang in installed_languages if lang.code == "en"), None
            )

            if not from_lang or not to_lang:
                print(f"Translation not available for {source_lang} to en")
                return text

            # Get translation
            translation = from_lang.get_translation(to_lang)
            if not translation:
                print(f"Could not create translation for {source_lang} to en")
                return text

            if self.debug:
                print(f"Translating from {source_lang} to English")

            # Split text into smaller chunks to avoid memory issues
            chunk_size = 5000  # characters
            chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
            translated_chunks = []

            for i, chunk in enumerate(chunks):
                if chunk.strip():  # Only translate non-empty chunks
                    translated = translation.translate(chunk)
                    translated_chunks.append(translated)
                    if self.debug:
                        print(f"Translated chunk {i+1}/{len(chunks)}")

            final_translation = " ".join(translated_chunks)

            if self.debug:
                print(f"Final translation length: {len(final_translation)}")
                print(f"Final translation sample: {final_translation}...")

            return final_translation if final_translation else text

        except Exception as e:
            print(f"Translation error: {str(e)}")
            return text

    def map_category(self, category, target_lang="en"):
        """Map category from English to target language"""
        try:
            # Find the row where English category matches
            row_idx = self.category_mapping[
                self.category_mapping["en"] == category
            ].index[0]
            # Get the category in target language
            return self.category_mapping.at[row_idx, target_lang]
        except:
            return category

    def set_preferred_language(self, lang):
        """Set the preferred output language"""
        if lang in self.supported_languages:
            self.preferred_language = lang
            return True
        return False

    def classify_text(self, text, multi_label=True):
        """Classify text and return categories in preferred language"""
        self._ensure_models_loaded()
        if not text.strip():
            return {"labels": [], "scores": [], "language": None, "error": "Empty text"}

        try:
            # Force reload of category mapping to ensure we're using user categories
            self.category_mapping = self.load_category_mapping()

            # Use T5 for language detection
            detected_lang = self.detect_language(text)
            if self.debug:
                print(f"Detected language: {detected_lang}")

            # Translate to English for classification
            processed_text = self.translate_to_english(text, detected_lang)

            # Use English categories from user categories for classification
            english_categories = self.get_categories_in_language("en")
            if self.debug:
                print(f"Using categories for classification: {english_categories}")

            result = self.classifier(
                processed_text,
                english_categories,
                multi_label=multi_label,
                hypothesis_template="This text is about {}",
            )

            if self.debug:
                print("Raw classification results:")
                for label, score in zip(result["labels"], result["scores"]):
                    print(f"  {label}: {score:.3f}")

            # Lower threshold and take top 5 results
            filtered_results = [
                (self.map_category(label, self.preferred_language), score)
                for label, score in zip(result["labels"], result["scores"])
                if score > 0.05  # Lower threshold from 0.1 to 0.05
            ][
                :5
            ]  # Increase from 3 to 5 results

            if not filtered_results:
                # If no results above threshold, take top result anyway
                if result["labels"] and result["scores"]:
                    top_label = result["labels"][0]
                    top_score = result["scores"][0]
                    filtered_results = [
                        (
                            self.map_category(top_label, self.preferred_language),
                            top_score,
                        )
                    ]
                    if self.debug:
                        print(
                            f"Using fallback top result: {top_label} ({top_score:.3f})"
                        )

            return {
                "labels": [r[0] for r in filtered_results],
                "scores": [r[1] for r in filtered_results],
                "language": detected_lang,
                "error": None if filtered_results else "No categories matched",
            }

        except Exception as e:
            error_msg = str(e)
            print(f"Classification error: {error_msg}")
            return {"labels": [], "scores": [], "language": None, "error": error_msg}

    def translate_category(self, text, source_lang, target_lang):
        """Translate a category name between languages using Argos Translate"""
        try:
            if source_lang == target_lang:
                return text

            # Get installed languages
            installed_languages = argostranslate.translate.get_installed_languages()

            # First translate to English if not already in English
            if source_lang != "en":
                from_lang = next(
                    (lang for lang in installed_languages if lang.code == source_lang),
                    None,
                )
                to_lang = next(
                    (lang for lang in installed_languages if lang.code == "en"), None
                )

                if from_lang and to_lang:
                    translation = from_lang.get_translation(to_lang)
                    if translation:
                        text = translation.translate(text)

            # Then translate from English to target language if needed
            if target_lang != "en":
                from_lang = next(
                    (lang for lang in installed_languages if lang.code == "en"), None
                )
                to_lang = next(
                    (lang for lang in installed_languages if lang.code == target_lang),
                    None,
                )

                if from_lang and to_lang:
                    translation = from_lang.get_translation(to_lang)
                    if translation:
                        text = translation.translate(text)

            return text

        except Exception as e:
            print(f"Translation error: {str(e)}")
            return text

    def add_new_category(self, category):
        """Add a new category to the user categories with translations"""
        try:
            # Check if category already exists in any language
            for lang_column in self.category_mapping.columns:
                if category in self.category_mapping[lang_column].values:
                    print(f"Category '{category}' already exists")
                    return True

            # Create new row with translations
            new_row = {}
            source_lang = self.preferred_language

            # Translate category to each supported language
            for target_lang in self.category_mapping.columns:
                if target_lang == source_lang:
                    new_row[target_lang] = category
                else:
                    translated = self.translate_category(
                        category, source_lang, target_lang
                    )
                    new_row[target_lang] = translated
                    if self.debug:
                        print(f"Translated '{category}' to {target_lang}: {translated}")

            self.category_mapping.loc[len(self.category_mapping)] = new_row

            # Save only to user_categories.csv
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            user_file = os.path.join(
                base_path, "storage", "data", "user_categories.csv"
            )

            # If user_categories.csv doesn't exist yet, create it from current mapping
            if not os.path.exists(user_file):
                self.category_mapping.to_csv(user_file, index=False)
            else:
                # Load existing user categories
                user_categories = pd.read_csv(user_file)
                # Add new row
                user_categories.loc[len(user_categories)] = new_row
                # Save back to file
                user_categories.to_csv(user_file, index=False)

            return True

        except Exception as e:
            print(f"Error adding new category: {str(e)}")
            return False
