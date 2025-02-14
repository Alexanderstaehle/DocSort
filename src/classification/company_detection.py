import os
from pathlib import Path
import pandas as pd
from transformers import pipeline


class CompanyDetector:
    def __init__(self):
        self.base_path = Path(__file__).parent.parent.parent
        self.models_path = self.base_path / "storage" / "data" / "models"
        self.companies_path = self.base_path / "storage" / "data" / "company_names.csv"

        # Initialize NER pipeline with local model
        self.ner = self._initialize_ner()
        self.companies = self._load_companies()
        self.temp_companies = []

    def _initialize_ner(self):
        """Initialize the NER pipeline with local model"""
        return pipeline(
            "ner",
            model="dslim/bert-base-NER",
            device=-1,
            model_kwargs={"cache_dir": self.models_path, "local_files_only": True},
        )

    def _load_companies(self) -> set:
        """Load companies from CSV file"""
        try:
            if self.companies_path.exists():
                return set(pd.read_csv(self.companies_path, header=None)[0])
            return set()
        except Exception as e:
            print(f"Error loading companies: {str(e)}")
            return set()

    def _save_companies(self) -> bool:
        """Save companies to CSV file"""
        try:
            companies_list = sorted(self.companies)
            pd.Series(companies_list).to_csv(
                self.companies_path, index=False, header=False
            )
            return True
        except Exception as e:
            print(f"Error saving companies: {str(e)}")
            return False

    def _process_company_name(self, tokens) -> str:
        """Process a sequence of tokens into a company name"""
        return " ".join(tokens).replace(" ##", "")

    def detect_companies(self, text: str) -> list:
        """Detect company names in text using NER"""
        predictions = self.ner(text)
        companies = []
        current_company = []

        for pred in predictions:
            if pred["entity"] in ["B-ORG", "I-ORG"]:
                current_company.append(pred["word"])
            elif current_company:
                company_name = self._process_company_name(current_company)
                if "#" not in company_name:
                    companies.append(company_name)
                current_company = []

        # Process last company if exists
        if current_company:
            company_name = self._process_company_name(current_company)
            if "#" not in company_name:
                companies.append(company_name)

        return companies

    def add_company(self, company_name: str) -> bool:
        """Add a new company if it doesn't exist"""
        if not company_name or company_name.lower() in {
            c.lower() for c in self.companies
        }:
            return False

        self.companies.add(company_name)
        return self._save_companies()

    def get_companies(self) -> list:
        """Get all companies (permanent and temporary)"""
        return sorted(set(list(self.companies) + self.temp_companies))

    def clear_temp_companies(self):
        """Clear temporary companies"""
        self.temp_companies = []

    def get_permanent_companies(self) -> list:
        """Get only permanent companies"""
        return sorted(self.companies)
