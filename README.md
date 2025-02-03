# DocSort
## Installation

1. Create and activate the conda environment:
```bash
conda env create -f environment.yaml
conda activate docsort
```

2. Start the application:
```bash
cd frontend
flet run
```
DocSort is a Flet-based application that streamlines document digitalization and organization. Key features:

- Automatic document scanning with corner detection
- OCR (Optical Character Recognition) for text extraction
- Smart categorization into structured folders
- Google Drive integration
- Natural language search capabilities through RAG (Retrieval-Augmented Generation)
- Customizable document categories
- Intelligent document classification

Perfect for managing personal or business documents while maintaining searchable digital records.

## Roadmap

### ✅ Completed Features
- Corner detection implementation
- Image quality enhancement filters
- OCR text extraction
- Automated file categorization
- Company detection

### 🚧 In Development
1. **Document Scanning**
    - Camera integration
    - Multi-page document support

2. **Smart Organization**
    - Suggest new category if "Other" selected
    - Fix category translation
    - Intelligent folder structure
    - Google Drive integration

### 📅 Future Enhancements
- Vector-based search functionality
- Custom category management


### Known Issues
- File upload on web returns None for file path (seems to be an issue with Flet)
- Snackbar not showing up