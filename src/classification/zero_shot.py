import os
import csv
import pandas as pd
from transformers import pipeline, T5Tokenizer, T5ForConditionalGeneration
import torch
from concurrent.futures import ThreadPoolExecutor
import threading
from langdetect import detect


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
            self.t5_tokenizer = None
            self.t5_model = None
            self.preferred_language = preferred_language
            self.default_categories = ["Other"]
            self.category_mapping = self.load_category_mapping()
            self.supported_languages = self.get_supported_languages()
            self.categories = self.get_categories_in_language(
                "en"
            )  # Always use English for classification
            self.debug = True

            # Start loading models in background
            with ThreadPoolExecutor() as executor:
                executor.submit(self._load_models)

    def _load_models(self):
        """Load NLP models from local storage"""
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            models_path = os.path.join(base_path, "storage", "data", "models")

            # Ensure models directory exists
            os.makedirs(models_path, exist_ok=True)

            # Load classifier
            self.classifier = pipeline(
                "zero-shot-classification",
                model="MoritzLaurer/ModernBERT-base-zeroshot-v2.0",
                device=-1,
            )

            # Load T5 model and tokenizer directly
            self.t5_tokenizer = T5Tokenizer.from_pretrained(
                "google-t5/t5-small", local_files_only=True, cache_dir=models_path
            )
            self.t5_model = T5ForConditionalGeneration.from_pretrained(
                "google-t5/t5-small",
                return_dict=True,
                local_files_only=True,
                cache_dir=models_path,
            )

            # Move to CPU
            self.t5_model = self.t5_model.to("cpu")

            print("NLP models loaded successfully")

        except Exception as e:
            print(f"Error loading NLP models: {str(e)}")

    def _ensure_models_loaded(self):
        """Wait for models to be loaded"""
        while (
            self.classifier is None
            or self.t5_model is None
            or self.t5_tokenizer is None
        ):
            print("Waiting for NLP models to load...")
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

    def _split_into_chunks(self, text, max_tokens):
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
            tokens = self.t5_tokenizer(test_chunk, return_tensors="pt")

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
        """Translate text to English using T5, processing in chunks if needed"""
        self._ensure_models_loaded()
        try:
            if source_lang == "en":
                return text

            # Calculate maximum text length per chunk (accounting for prompt)
            prompt_template = f"translate {source_lang} to English: "
            prompt_tokens = self.t5_tokenizer(
                prompt_template, return_tensors="pt"
            ).input_ids.shape[1]
            max_text_tokens = (
                512 - prompt_tokens - 10
            )  # Leave 10 tokens as safety margin

            # Split text into chunks
            chunks = self._split_into_chunks(text, max_text_tokens)
            translated_chunks = []

            if self.debug:
                print(f"Split text into {len(chunks)} chunks")

            # Translate each chunk
            for i, chunk in enumerate(chunks):
                prompt = f"translate {source_lang} to English: {chunk}"

                if self.debug:
                    print(f"\nTranslating chunk {i+1}/{len(chunks)}:")

                input_ids = self.t5_tokenizer(
                    prompt, return_tensors="pt", truncation=True, max_length=512
                ).input_ids

                outputs = self.t5_model.generate(
                    input_ids, max_length=512, num_beams=4, do_sample=False
                )

                translated = self.t5_tokenizer.decode(
                    outputs[0], skip_special_tokens=True
                )
                translated_chunks.append(translated)

            # Combine translated chunks
            final_translation = " ".join(translated_chunks)

            if self.debug:
                print(f"\nFinal combined translation: {final_translation}...")
                print(f"Total length: {len(final_translation)}")

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
        """Translate a category name between languages"""
        self._ensure_models_loaded()
        try:
            if source_lang == target_lang:
                return text

            # Prepare translation prompt
            prompt = f"translate {source_lang} to {target_lang}: {text}"

            # Tokenize and generate
            input_ids = self.t5_tokenizer(prompt, return_tensors="pt").input_ids
            outputs = self.t5_model.generate(
                input_ids, max_length=50, num_beams=4, do_sample=False
            )

            # Decode
            translated = self.t5_tokenizer.decode(outputs[0], skip_special_tokens=True)
            return translated if translated else text

        except Exception as e:
            print(f"Translation error: {str(e)}")
            return text

    def add_new_category(self, category):
        """Add a new category to the category mapping with translations"""
        try:
            # Check if category already exists in any language
            for lang_column in self.category_mapping.columns:
                if category in self.category_mapping[lang_column].values:
                    print(f"Category '{category}' already exists")
                    return True

            # Initialize new row with the category in all columns
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

            # Add the new row to the mapping and save
            self.category_mapping.loc[len(self.category_mapping)] = new_row
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            file_path = os.path.join(
                base_path, "storage", "data", "category_mapping.csv"
            )
            self.category_mapping.to_csv(file_path, index=False)
            return True
        except Exception as e:
            print(f"Error adding new category: {str(e)}")
            return False
