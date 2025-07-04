# ACC/BIM 360 Issues Fetcher

A tool to fetch issues from Autodesk Construction Cloud (ACC) and BIM 360 projects using the APS API.

## Features

- Secure OAuth 2.0 authentication with Autodesk APS
- Browse hubs and projects
- Filter issues by type and status
- Export to CSV or Excel
- Two interface options:
  - **Tkinter GUI** (`script.py`) - Desktop application
  - **Streamlit Web App** (`streamlit_app.py`) - Web-based interface

## Prerequisites

- Python 3.7+
- Autodesk APS Application with proper configuration
- ACC/BIM 360 access

## Dev Setup

1. **Create APS Application** at [APS Developer Portal](https://aps.autodesk.com/myapps):
   - App type: Web App
   - Callback URL: `http://localhost:8080/callback`
   - Enable APIs: Data Management, Construction Cloud Issues
   - Scopes: `data:read`, `account:read`

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure credentials**:
   - Copy `config_template.env` to `.env`
   - Add your APS Client ID and Client Secret

4. **Add the custom integration to your hub admin portal**
   - https://admin.b360.autodesk.com/admin/

## Usage for the common people

### Option 1: Desktop Application (Tkinter)
1. Run the application: `python script.py` OR Run the `run.bat` file
2. Click "Authenticate" (browser will open)
3. Select hub and project from dropdowns
4. Apply filters if needed
5. Click "Fetch Issues"
6. Export results using CSV or Excel buttons

### Option 2: Web Application (Streamlit)
1. Run the application: `streamlit run streamlit_app.py` OR Run the `run_streamlit.bat` file
2. Open your browser to `http://localhost:8501`
3. Click "Authenticate" in the sidebar (browser will open)
4. Select hub and project from dropdowns
5. Apply filters if needed
6. Click "Fetch Issues"
7. Download results using CSV or Excel buttons





