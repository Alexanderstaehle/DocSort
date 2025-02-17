# DocSort
![Demo](DocSortDemo.gif)

DocSort is a Flet-based application that streamlines document digitalization and organization. Key features:

- Automatic document scanning with corner detection
- OCR (Optical Character Recognition) for text extraction
- Smart categorization into structured folders
- Google Drive integration
- Natural language search capabilities through RAG (Retrieval-Augmented Generation)
- Customizable document categories
- All ML models are running offline so no data is published (except over Google Drive API)

Perfect for managing personal or business documents while maintaining searchable digital records.

Currently supported languages: English, German
## Installation

1. Create and activate the conda environment:
```bash
conda env create -f environment.yaml
conda activate docsort
```

2. Setup Offline Models:
 ```bash
python3 scripts/setup_models
```

3. Setup Google Drive API Project:
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
- Save to Drive in smart folder structure
- Setup page
- Offline Inference no extra API's (except Google Drive access)
- Vector-based search functionality
- Allow manual upload and sync search service
- Folder explorer

### 🚧 In Development
1. **Document Scanning**
    - Camera integration
    - Multi-page document support

2. **Smart Organization**
    - Suggest new category if "Other" selected

3. **Multi-platform support**
    - Build application on Android and iOS


### Known Issues
- File upload on web returns None for file path (seems to be an issue with Flet)