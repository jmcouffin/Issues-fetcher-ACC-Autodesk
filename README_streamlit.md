# ACC/BIM 360 Issues Fetcher - Streamlit Web App

A web-based version of the ACC Issues Fetcher tool built with Streamlit. This application allows you to fetch, filter, and export issues from Autodesk Construction Cloud (ACC) and BIM 360 projects through a user-friendly web interface.

## Features

- 🔐 **OAuth3 Authentication**: Secure 3-legged authentication for full API access
- 🏢 **Hub & Project Selection**: Browse and select from available hubs and projects
- 🔍 **Advanced Filtering**: Filter issues by type and status
- 📊 **Data Visualization**: View issues in an interactive table with metrics
- 📥 **Export Options**: Download issues data as CSV or Excel files
- 🌐 **Web Deployment**: Works both locally and on cloud platforms like Streamlit Cloud

## Setup Instructions

### 1. APS Application Setup

1. Go to [Autodesk Platform Services](https://aps.autodesk.com/myapps)
2. Create a new application or use an existing one
3. Enable these APIs:
   - **Data Management API**
   - **Construction Cloud Issues API**
4. Configure the following scopes:
   - `data:read`
   - `data:write`
   - `account:read`
   - `code:all`

### 2. Callback URL Configuration

**For Local Development:**
```
http://localhost:8501
```

**For Streamlit Cloud Deployment:**
```
https://your-app-name.streamlit.app
```

### 3. Environment Variables

Create a `.env` file in the project root:

```env
APS_CLIENT_ID=your_client_id_here
APS_CLIENT_SECRET=your_client_secret_here
```

### 4. Installation

```bash
# Clone or download the project
cd Issues-fetcher-ACC-Autodesk

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

### Local Development

```bash
streamlit run streamlit_app.py
```

The app will be available at `http://localhost:8501`

### Streamlit Cloud Deployment

1. Push your code to a GitHub repository
2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Connect your GitHub repository
4. Add your environment variables in the app settings:
   - `APS_CLIENT_ID`
   - `APS_CLIENT_SECRET`
5. Deploy the app

## Usage

### 1. Authentication

1. Click the **"Authenticate"** button in the sidebar
2. Complete 2-legged authentication (automatic)
3. Click the authorization link for 3-legged authentication
4. Grant permissions in the browser
5. You'll be redirected back to the app

### 2. Project Selection

1. Select a **Hub** from the dropdown
2. Click **"Refresh Projects"** to load projects
3. Select a **Project** from the dropdown
4. Click **"Load Issue Types"** (if Issues API is available)

### 3. Fetching Issues

1. Choose filters (Issue Type, Status)
2. Click **"Fetch Issues"**
3. View results in the interactive table
4. Download data as CSV or Excel

## Key Differences from Desktop App

### State Management
- Uses Streamlit's session state for data persistence
- Maintains authentication state across page reloads
- Stores API responses to minimize API calls

### OAuth3 Implementation
- Adapted for web deployment with proper callback URL handling
- Automatic detection of local vs. deployed environment
- Secure state parameter for OAuth security

### User Interface
- Modern web interface with responsive design
- Interactive data tables and filtering
- Real-time metrics and progress indicators
- Streamlined workflow with guided steps

### Export Functionality
- In-browser download links for CSV/Excel files
- Automatic filename generation with timestamps
- No file dialog - direct download to browser's download folder

## Authentication Flow

### 2-Legged Authentication (Automatic)
- Used for Data Management API (hubs, projects)
- Automatic token retrieval and refresh
- No user interaction required

### 3-Legged Authentication (User Consent)
- Required for Issues API access
- Opens browser window for user authorization
- Secure callback handling with state verification
- Token storage in session state

## Troubleshooting

### Authentication Issues

**Problem**: "Missing APS_CLIENT_ID or APS_CLIENT_SECRET"
**Solution**: Ensure your `.env` file is properly configured and the environment variables are set

**Problem**: "AUTH-001" Error
**Solution**: 
- Verify your APS app has the required APIs enabled
- Check that all required scopes are configured
- Ensure callback URL matches your deployment

### Issues API Access

**Problem**: "Issues API access not available"
**Solution**: 
- Complete the 3-legged authentication process
- Ensure the project has Issues API enabled
- Verify your APS app has Construction Cloud Issues API enabled

### Deployment Issues

**Problem**: OAuth callback not working on deployed app
**Solution**: 
- Update the callback URL in your APS app settings
- Use the correct deployed app URL
- Ensure HTTPS is used for production deployments

## Security Considerations

- Environment variables are used for sensitive credentials
- OAuth state parameter prevents CSRF attacks
- Token storage is session-based and temporary
- No credentials are stored permanently

## Limitations

- Maximum 200 issues per fetch (API limitation)
- Session state is lost on browser refresh (reauthentication required)
- Issues API requires user consent for each session
- Some projects may not have Issues API enabled

## File Structure

```
├── script.py              # Original desktop application (unchanged)
├── streamlit_app.py       # Streamlit web application
├── requirements.txt       # Updated dependencies
├── .env                   # Environment variables (create this)
├── config_template.env    # Template for environment variables
└── README.md             # This file
```

## Support

For issues related to:
- **APS APIs**: Check [APS Documentation](https://aps.autodesk.com/developer/documentation)
- **Streamlit**: Check [Streamlit Documentation](https://docs.streamlit.io/)
- **Issues API**: Ensure your ACC/BIM 360 project has Issues enabled

## License

This project maintains the same license as the original desktop application.
