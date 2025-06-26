# ACC/BIM 360 Issues Fetcher Tool

✅ **STATUS: WORKING** - 3-legged authentication and Issues API access are now functional!

This tool fetches issues from Autodesk Construction Cloud (ACC) and BIM 360 projects using the Autodesk Platform Services (APS) API.

## 🎉 What's Working

- ✅ 2-legged authentication for Data Management API (hubs/projects)
- ✅ 3-legged authentication for Construction Issues API
- ✅ Manual 3-legged OAuth implementation (bypasses aps-toolkit issues)
- ✅ Issues API endpoint access with proper authentication
- ✅ GUI application with full functionality
- ✅ Export to CSV/Excel formats

## 🚀 Quick Start

1. **Configure your APS app** (see Configuration section below)
2. **Set up environment**: Create `.env` file with your credentials
3. **Run the GUI**: `python script.py`
4. **Authenticate**: Click "Authenticate" button (browser will open for consent)
5. **Select hub/project**: Choose from the dropdowns
6. **Fetch issues**: Click "Fetch Issues" to retrieve and display issues

## 📁 Files

- `script.py` - Main GUI application with working 3-legged auth
- `test_3leg_isolated.py` - Standalone 3-legged authentication test
- `test_issues_quick.py` - Quick test with real project data
- `check_app_config.py` - App configuration diagnostic tool
- `requirements.txt` - Python dependencies
- `.env` - Your APS credentials (create from config_template.env)

## Features

- **Authentication**: Secure OAuth 2.0 authentication with Autodesk APS
- **Hub/Project Selection**: Browse and select from available hubs and projects
- **Issue Filtering**: Filter issues by type and status
- **Export Options**: Export results to CSV or Excel format
- **User-Friendly GUI**: Tkinter-based interface for easy interaction

## ⚠️ Important: Issues API Authentication

**The Construction Issues API requires 3-legged authentication (user consent flow).**

When you try to fetch issues, you may see this message:
```
Authentication error (401). The Construction Issues API requires 3-legged authentication (user consent).
```

This is **normal** and indicates:

- ✅ **Authentication is working correctly** (for Data Management API)
- ✅ **API endpoints are correct**
- ✅ **Container ID detection is working**
- ⚠️ **Issues API requires different authentication type**

### What Works vs What Requires Enhancement:
- ✅ **Hub browsing**: Always works (2-legged auth)
- ✅ **Project browsing**: Always works (2-legged auth)  
- ⚠️ **Issues fetching**: Requires 3-legged auth implementation

### Authentication Types:
- **2-legged auth** (current): Service-to-service, no user consent
- **3-legged auth** (needed for Issues): Includes user consent flow via browser

To access Issues data, the application would need to be enhanced to support 3-legged authentication with user consent flow.

See `AUTHENTICATION_ANALYSIS.md` for detailed technical information.

## Prerequisites

1. **Python 3.7+** installed on your system
2. **Autodesk APS Application**: You need to create and properly configure an app at [APS Developer Portal](https://aps.autodesk.com/myapps)
3. **ACC/BIM 360 Access**: Your APS app needs appropriate permissions for Issues API

### Setting Up Your APS Application

**Important**: The most common cause of authentication errors is improper APS app configuration.

1. **Create APS Application**:
   - Go to [APS Developer Portal](https://aps.autodesk.com/myapps)
   - Click "Create App"
   - Choose "Web App" type
   - Set callback URL to `http://localhost:8080/callback` (even if not used)

2. **Enable Required APIs**:
   - ✅ **Data Management API** (required for hubs/projects)
   - ✅ **Model Derivative API** (for 3D model access)
   - ✅ **Construction Cloud Issues API** (required for issues)
   - ✅ **Webhooks API** (optional, for real-time updates)

3. **Configure Scopes**:
   - ✅ `data:read` - Read project data
   - ✅ `data:write` - Write project data (if updating issues)
   - ✅ `account:read` - Read account information
   - ✅ `code:all` - For comprehensive access

4. **Save and Note Credentials**:
   - Copy your **Client ID** and **Client Secret**
   - These will go in your `.env` file

## Installation

1. **Clone or download** this repository
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure APS credentials**:
   - Copy `config_template.env` to `.env`
   - Fill in your APS application credentials:
     ```
     APS_CLIENT_ID=your_client_id_here
     APS_CLIENT_SECRET=your_client_secret_here
     ```

## Usage

1. **Run the application**:
   ```bash
   python script.py
   ```

2. **If you encounter authentication errors**, run diagnostics first:
   ```bash
   python diagnose.py
   ```

3. **Authenticate**: Click "Authenticate" to connect to Autodesk APS

4. **Select Hub and Project**: Choose from the dropdown menus

5. **Apply Filters** (optional):
   - Select issue type
   - Choose status (open, closed, etc.)

6. **Fetch Issues**: Click "Fetch Issues" to retrieve data

7. **Export Results**: Use "Export to CSV" or "Export to Excel" buttons

## API Endpoints Used

The tool uses the following Autodesk APS endpoints:

- **Hubs**: `/project/v1/hubs`
- **Projects**: `/project/v1/hubs/{hub_id}/projects`
- **Issues**: `/construction/issues/v1/projects/{projectId}/issues`
- **Issue Types**: `/construction/issues/v1/projects/{projectId}/issue-types`

## Permissions Required

Your APS application needs the following scopes:
- `data:read` - To access project data
- `account:read` - To read account information

For Issues API access, you may need additional permissions depending on your specific setup.

## Troubleshooting

### Authentication Issues (AUTH-001)

**Error**: `The client_id specified does not have access to the api product`

**Solution**:
1. **Check API Access**:
   - Go to [APS Developer Portal](https://aps.autodesk.com/myapps)
   - Select your application
   - Verify these APIs are enabled:
     - Data Management API ✅
     - Construction Cloud Issues API ✅
     - Model Derivative API ✅

2. **Verify Scopes**:
   - Ensure your app has these scopes:
     - `data:read` ✅
     - `data:write` ✅ (if updating data)
     - `account:read` ✅
     - `code:all` ✅

3. **Check Credentials**:
   - Verify your APS_CLIENT_ID and APS_CLIENT_SECRET are correct
   - Ensure no extra spaces or characters in your `.env` file
   - Make sure you're using the production credentials, not sandbox

4. **App Type Configuration**:
   - Your app should be configured as a "Web App"
   - Set callback URL to `http://localhost:8080/callback`

## Quick Fix for AUTH-001 Error

If you're getting the `AUTH-001` error, here's a quick checklist:

1. **Create proper .env file**:
   ```bash
   cp config_template.env .env
   # Edit .env with your actual credentials
   ```

2. **Verify APS app setup**:
   - Go to [APS Developer Portal](https://aps.autodesk.com/myapps)
   - Enable **Data Management API** and **Construction Cloud Issues API**
   - Add scopes: `data:read`, `data:write`, `account:read`, `code:all`

3. **Test your setup**:
   ```bash
   python diagnose.py
   ```

4. **If still having issues**:
   - Check if you have access to any ACC/BIM 360 projects
   - Try with a different APS application
   - Contact your ACC/BIM 360 administrator for API access

The most common cause is that your APS application doesn't have the required APIs enabled. The diagnostics script will help identify the specific issue.

### Common Issues and Solutions

**"No hubs found"**:
- Your account might not have access to any ACC/BIM 360 hubs
- Verify you have admin/member access to at least one ACC/BIM 360 account
- Try with a different account that has proper access

**"Issues API not accessible"**:
- Issues API might require 3-legged authentication (user consent)
- Some organizations restrict API access
- Contact your ACC/BIM 360 administrator

**"Import errors"**:
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- For tkinter issues on Linux: `sudo apt-get install python3-tk`

### Testing Your Setup

1. **Test Basic Authentication**:
   ```bash
   python simple_example.py
   ```

2. **Check APS App Status**:
   - Log into [APS Developer Portal](https://aps.autodesk.com/myapps)
   - Verify your app status is "Active"
   - Check the "Usage" tab for any error logs

3. **Verify Credentials**:
   - Make sure your `.env` file exists and has correct format:
     ```
     APS_CLIENT_ID=your_actual_client_id
     APS_CLIENT_SECRET=your_actual_client_secret
     ```

## Code Structure

- `IssuesAPI`: Handles ACC/BIM 360 Issues API calls
- `IssuesFetcherApp`: Main GUI application class
- `main()`: Application entry point

## Extending the Tool

You can extend this tool by:

1. **Adding more filters**: Modify the `get_issues()` method to support additional filters
2. **Custom export formats**: Add new export methods in the `IssuesFetcherApp` class
3. **Issue details view**: Add a detailed view for individual issues
4. **Bulk operations**: Add functionality to update multiple issues

## Known Limitations

1. **Container ID**: The tool currently uses project_id as container_id, which may not work for all projects
2. **Authentication**: Currently uses 2-legged auth; some operations may require 3-legged auth
3. **Rate Limiting**: No built-in rate limiting for API calls
4. **Error Handling**: Basic error handling; could be enhanced for production use

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve this tool.

## License

This tool is provided as-is for educational and development purposes. Please ensure compliance with Autodesk's terms of service when using their APIs.

## Support

For issues related to:
- **APS Authentication**: Check [APS Documentation](https://aps.autodesk.com/en/docs/)
- **Issues API**: Refer to [ACC API Documentation](https://aps.autodesk.com/en/docs/acc/v1/overview/)
- **This Tool**: Create an issue in this repository
