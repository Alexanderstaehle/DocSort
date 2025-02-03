import os
import pandas as pd
from transformers import pipeline

class CompanyDetector:
    def __init__(self):
        self.ner = pipeline("ner", model="dslim/bert-base-NER", device=-1)
        self.companies = self.load_companies()

    def load_companies(self):
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            file_path = os.path.join(base_path, 'storage', 'data', 'company_names.csv')
            df = pd.read_csv(file_path)
            return df['company'].tolist()
        except Exception as e:
            print(f"Error loading companies: {str(e)}")
            return []

    def detect_companies(self, text):
        # Get NER predictions
        predictions = self.ner(text)
        
        # Extract company names (entities labeled as 'ORG')
        companies = []
        current_company = []
        
        for pred in predictions:
            if pred['entity'] in ['B-ORG', 'I-ORG']:
                current_company.append(pred['word'])
            elif current_company:
                companies.append(' '.join(current_company).replace(' ##', ''))
                current_company = []
                
        if current_company:
            companies.append(' '.join(current_company).replace(' ##', ''))
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(companies))

    def add_company(self, company_name):
        """Add a company to the list if it doesn't exist"""
        try:
            # Case-insensitive check for existing company
            if any(company.lower() == company_name.lower() for company in self.companies):
                print(f"Company '{company_name}' already exists")
                return True
                
            self.companies.append(company_name)
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            file_path = os.path.join(base_path, 'storage', 'data', 'company_names.csv')
            pd.DataFrame({'company': self.companies}).to_csv(file_path, index=False)
            return True
        except Exception as e:
            print(f"Error adding company: {str(e)}")
            return False

    def get_companies(self):
        return self.companies
