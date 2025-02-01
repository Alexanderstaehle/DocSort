import os
import csv
import pandas as pd
from transformers import pipeline

class DocumentClassifier:
    def __init__(self, preferred_language='de'):
        self.classifier = pipeline("zero-shot-classification", 
                                 model="MoritzLaurer/bge-m3-zeroshot-v2.0",
                                 device=-1)
        
        # Initialize T5 model for both translation and language detection
        self.t5_model = pipeline(
            "text2text-generation",
            model="t5-small",
            tokenizer="t5-small",
            device=-1
        )
        
        self.preferred_language = preferred_language
        self.default_categories = ["Other"]
        self.category_mapping = self.load_category_mapping()
        self.supported_languages = self.get_supported_languages()
        self.categories = self.get_categories_in_language('en')  # Always use English for classification
        self.debug = True  # Add debug flag

    def load_category_mapping(self):
        """Load category mappings from CSV file into a pandas DataFrame"""
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            file_path = os.path.join(base_path, 'storage', 'data', 'category_mapping.csv')
            return pd.read_csv(file_path)
        except Exception as e:
            print(f"Error loading category mapping: {str(e)}")
            return pd.DataFrame({'en': self.default_categories})

    def get_supported_languages(self):
        """Get list of supported languages from CSV columns"""
        return list(self.category_mapping.columns)

    def get_categories_in_language(self, lang):
        """Get categories in specified language"""
        if lang in self.supported_languages:
            return self.category_mapping[lang].tolist()
        return self.default_categories

    def detect_language(self, text):
        """Detect the language of the text using T5"""
        try:
            # Truncate text for language detection
            sample_text = text[:100]  # Use first 100 chars for detection
            result = self.t5_model(
                "detect language: " + sample_text,
                max_length=10,
                num_beams=1
            )
            
            # T5 typically returns language name, map to language code
            lang_mapping = {
                "english": "en",
                "german": "de",
                "french": "fr",
                "spanish": "es",
                "italian": "it",
                "dutch": "nl",
                # Add more mappings as needed
            }
            
            detected = result[0]['generated_text'].lower().strip()
            return lang_mapping.get(detected, "en")  # Default to English if unknown
        except Exception as e:
            print(f"Language detection error: {str(e)}")
            return "en"  # Default to English on error

    def translate_to_english(self, text, source_lang):
        """Translate text to English using T5"""
        try:
            if source_lang == 'en':
                return text
                
            # Truncate text if too long
            max_length = 512
            if len(text) > max_length:
                text = text[:max_length]
            
            # T5 translation prompt
            task_prefix = f"translate {source_lang} to english: "
            
            result = self.t5_model(
                task_prefix + text,
                max_length=512,
                num_beams=4,
                do_sample=False
            )
            
            return result[0]['generated_text'] if result else text
                
        except Exception as e:
            print(f"Translation error: {str(e)}")
            return text

    def map_category(self, category, target_lang='en'):
        """Map category from English to target language"""
        try:
            # Find the row where English category matches
            row_idx = self.category_mapping[self.category_mapping['en'] == category].index[0]
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
        """
        Classify text and return categories in preferred language
        """
        if not text.strip():
            return {"labels": [], "scores": [], "language": None, "error": "Empty text"}

        try:
            # Use T5 for language detection
            detected_lang = self.detect_language(text)
            if self.debug:
                print(f"Detected language: {detected_lang}")
            
            # Translate to English for classification
            processed_text = self.translate_to_english(text, detected_lang)
            if self.debug:
                print(f"Translated text: {processed_text[:200]}...")  # Show first 200 chars

            # Use English categories for classification
            english_categories = self.get_categories_in_language('en')
            
            result = self.classifier(
                processed_text,
                english_categories,
                multi_label=multi_label,
                hypothesis_template="This text is about {}"
            )

            if self.debug:
                print("Raw classification results:")
                for label, score in zip(result['labels'], result['scores']):
                    print(f"  {label}: {score:.3f}")

            # Lower threshold and take top 5 results
            filtered_results = [
                (self.map_category(label, self.preferred_language), score) 
                for label, score in zip(result['labels'], result['scores'])
                if score > 0.05  # Lower threshold from 0.1 to 0.05
            ][:5]  # Increase from 3 to 5 results

            if not filtered_results:
                # If no results above threshold, take top result anyway
                if result['labels'] and result['scores']:
                    top_label = result['labels'][0]
                    top_score = result['scores'][0]
                    filtered_results = [(self.map_category(top_label, self.preferred_language), top_score)]
                    if self.debug:
                        print(f"Using fallback top result: {top_label} ({top_score:.3f})")

            return {
                "labels": [r[0] for r in filtered_results],
                "scores": [r[1] for r in filtered_results],
                "language": detected_lang,
                "error": None if filtered_results else "No categories matched"
            }

        except Exception as e:
            error_msg = str(e)
            print(f"Classification error: {error_msg}")
            return {"labels": [], "scores": [], "language": None, "error": error_msg}
