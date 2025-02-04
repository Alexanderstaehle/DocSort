# DocSort
DocSort is a Flet-based application that streamlines document digitalization and organization. Key features:

- Automatic document scanning with corner detection
- OCR (Optical Character Recognition) for text extraction
- Smart categorization into structured folders
- Google Drive integration
- Natural language search capabilities through RAG (Retrieval-Augmented Generation)
- Customizable document categories
- Intelligent document classification
- All ML models are running offline so no data is published (except over Google Drive API)

Perfect for managing personal or business documents while maintaining searchable digital records.
## Installation

1. Create and activate the conda environment:
```bash
conda env create -f environment.yaml
conda activate docsort
```

2. Setup Google Drive API Project:
    - Visit the [Google Cloud Console](https://console.cloud.google.com/)
    - Create a new project or select an existing one
    - Enable the Google Drive API for your project
    - Navigate to Credentials
    - Create an OAuth 2.0 Client ID (select Desktop application)
    - Download the JSON file
    - Rename it to `client_secrets.json`
    - Place the file in your project root directory
    > **Important**: Google sets the project into testing phase initially. This means that users that should be able to use the App using the Google Drive API have to be manually added as test users.

3. Start the application:
```bash
flet run
```


## Roadmap

### ✅ Completed Features
- Corner detection on document images
- Image quality enhancement filters
- OCR text extraction
- Automated file categorization
- Company detection

### 🚧 In Development
1. **Document Scanning**
    - Camera integration
    - Multi-page document support

2. **Smart Organization**
    - Run models offline
    - Suggest new category if "Other" selected
    - Fix category translation
    - Intelligent folder structure
    - Google Drive integration

### 📅 Future Enhancements
- Vector-based search functionality
- Custom category management


### Known Issues
- File upload on web returns None for file path (seems to be an issue with Flet)
- Classification has long inference time and low acc
- Translation often fails since language is not properly detected (upgrade to large?)

- Output language selection in AppBar
- cleanup console outputs