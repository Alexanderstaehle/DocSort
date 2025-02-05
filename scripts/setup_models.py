import os
import sys
import shutil
from pathlib import Path
import torch
import argostranslate.package
from transformers import AutoTokenizer, AutoModel
from doctr.models import db_resnet50, crnn_vgg16_bn

def setup_directory():
    """Create and return the models directory path"""
    base_path = Path(__file__).parent.parent
    models_path = base_path / "storage" / "data" / "models"
    models_path.mkdir(parents=True, exist_ok=True)
    return models_path

def setup_doctr_models(models_path):
    """Download and save DocTR models"""
    print("Setting up DocTR models...")
    doctr_path = models_path / "ocr"
    doctr_path.mkdir(exist_ok=True)

    # Download and save detection model
    print("Downloading DB_ResNet50...")
    det_model = db_resnet50(pretrained=True)
    torch.save(det_model.state_dict(), doctr_path / "db_resnet50.pt")
    
    # Download and save recognition model
    print("Downloading CRNN_VGG16_BN...")
    reco_model = crnn_vgg16_bn(pretrained=True)
    torch.save(reco_model.state_dict(), doctr_path / "crnn_vgg16_bn.pt")
    
    # Save model configs if needed
    det_config = {
        "type": "db_resnet50",
        "pretrained": True
    }
    reco_config = {
        "type": "crnn_vgg16_bn",
        "pretrained": True
    }
    
    torch.save(det_config, doctr_path / "db_resnet50_config.pt")
    torch.save(reco_config, doctr_path / "crnn_vgg16_bn_config.pt")
    
    print("DocTR models downloaded successfully")

def setup_transformers_models(models_path):
    """Download Hugging Face transformer models"""
    print("Setting up Transformer models...")
    
    # ModernBERT for zero-shot classification
    print("Downloading ModernBERT...")
    model_name = "MoritzLaurer/ModernBERT-base-zeroshot-v2.0"
    AutoTokenizer.from_pretrained(model_name, cache_dir=models_path)
    AutoModel.from_pretrained(model_name, cache_dir=models_path)
    
    # BERT-NER for company detection
    print("Downloading BERT-NER...")
    model_name = "dslim/bert-base-NER"
    AutoTokenizer.from_pretrained(model_name, cache_dir=models_path)
    AutoModel.from_pretrained(model_name, cache_dir=models_path)

def setup_argos_models(models_path):
    """Download and install Argos Translate language packages"""
    print("Setting up Argos Translate models...")
    argos_path = models_path / "argos"
    argos_path.mkdir(exist_ok=True)
    
    # Set Argos package path
    argostranslate.package.INSTALLED_PACKAGES_PATH = str(argos_path)
    
    # Update package index
    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()
    
    # Define language pairs to install
    lang_pairs = [
        ('de', 'en'), ('en', 'de'),
        ('nl', 'en'), ('en', 'nl')
    ]
    
    # Install required packages
    for from_code, to_code in lang_pairs:
        print(f"Installing {from_code}->{to_code} translation...")
        package = next(
            (pkg for pkg in available_packages 
             if pkg.from_code == from_code and pkg.to_code == to_code),
            None
        )
        if package:
            argostranslate.package.install_from_path(package.download())
        else:
            print(f"Warning: Could not find package for {from_code}->{to_code}")

def main():
    try:
        models_path = setup_directory()
        print(f"Setting up models in: {models_path}")
        
        setup_doctr_models(models_path)
        setup_transformers_models(models_path)
        setup_argos_models(models_path)
        
        print("\nAll models have been successfully downloaded and set up!")
        
    except Exception as e:
        print(f"Error during setup: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
