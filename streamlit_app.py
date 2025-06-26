"""
Autodesk Construction Cloud (ACC) Issues Fetcher Tool - Streamlit Version
This tool fetches issues from Autodesk BIM 360/ACC Docs using the APS toolkit.
Features:
- Hub and project selection
- Issue type filtering
- Export to CSV/Excel
- Web-based interface using Streamlit

Requirements:
- aps-toolkit
- streamlit
- pandas
- requests

Author: AI Assistant
Date: 2025-06-26
"""

import streamlit as st
import os
import sys
from datetime import datetime
import json
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import time
import threading
import io

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # Manual .env loading if python-dotenv is not available
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

try:
    import requests
    import pandas as pd
    from aps_toolkit import Auth, BIM360
except ImportError as e:
    st.error(
        "Missing required packages. Please install: pip install aps-toolkit pandas requests streamlit"
    )
    st.error(f"Error: {e}")
    st.stop()


class OAuth3LeggedHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback"""

    def do_GET(self):
        """Handle the OAuth callback"""
        if self.path.startswith("/callback"):
            # Parse the callback URL
            from urllib.parse import urlparse, parse_qs

            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            if "code" in query_params:
                # Success - we got the authorization code
                auth_code = query_params["code"][0]
                self.server.auth_code = auth_code

                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                success_html = """
                <html>
                <head><title>Authorization Successful</title></head>
                <body>
                    <h1>✅ Authorization Successful!</h1>
                    <p>You can close this window and return to the application.</p>
                    <script>window.close();</script>
                </body>
                </html>
                """
                self.wfile.write(success_html.encode())

            elif "error" in query_params:
                # Error from OAuth provider
                error = query_params["error"][0]
                error_description = query_params.get(
                    "error_description", ["Unknown error"]
                )[0]

                self.server.auth_error = f"{error}: {error_description}"

                # Send error response
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                error_html = f"""
                <html>
                <head><title>Authorization Failed</title></head>
                <body>
                    <h1>❌ Authorization Failed</h1>
                    <p>Error: {error}</p>
                    <p>Description: {error_description}</p>
                    <p>Please check your APS app configuration.</p>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
        else:
            # Unknown path
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Override to reduce noise"""
        pass


class Manual3LeggedAuth:
    """Manual implementation of 3-legged OAuth for APS"""

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

        # Determine callback URL based on environment
        if self._is_streamlit_cloud():
            # For Streamlit Cloud deployment
            self.callback_url = "https://issues-fetcher.streamlit.app/callback"
            self.use_local_server = False
        else:
            # For local development
            self.callback_url = "http://localhost:8080/callback"
            self.use_local_server = True

        self.base_url = "https://developer.api.autodesk.com"

        # Scopes required for Issues API
        self.scopes = ["data:read", "data:write", "account:read", "code:all"]

    def _is_streamlit_cloud(self):
        """Detect if running on Streamlit Cloud"""
        # Check various environment indicators for Streamlit Cloud
        return (
            os.getenv("STREAMLIT_SERVER_PORT") is not None
            or os.getenv("STREAMLIT_SHARING_MODE") is not None
            or "streamlit.app" in os.getenv("HOSTNAME", "")
            or "streamlit" in os.getenv("USER", "").lower()
        )

    def get_authorization_url(self):
        """Generate the authorization URL"""
        auth_url = "https://developer.api.autodesk.com/authentication/v2/authorize"

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.callback_url,
            "scope": " ".join(self.scopes),
            "state": "streamlit_auth_state",
        }

        query_string = urllib.parse.urlencode(params)
        full_url = f"{auth_url}?{query_string}"

        return full_url

    def start_callback_server(self):
        """Start the HTTP server to handle OAuth callback"""
        server = HTTPServer(("localhost", 8080), OAuth3LeggedHandler)
        server.auth_code = None
        server.auth_error = None
        server.timeout = 1  # Non-blocking

        return server

    def exchange_code_for_token(self, auth_code):
        """Exchange authorization code for access token"""
        token_url = f"{self.base_url}/authentication/v2/token"

        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.callback_url,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(token_url, data=data, headers=headers, timeout=30)

        if response.status_code == 200:
            token_data = response.json()
            return token_data
        else:
            return None

    def authenticate(self):
        """Complete 3-legged authentication flow"""
        if self.use_local_server:
            return self._authenticate_with_local_server()
        else:
            return self._authenticate_with_manual_entry()

    def _authenticate_with_local_server(self):
        """Authenticate using local callback server (for development)"""
        # Start callback server
        server = self.start_callback_server()

        # Generate authorization URL
        auth_url = self.get_authorization_url()
        webbrowser.open(auth_url)

        # Wait for callback
        start_time = time.time()
        timeout = 300  # 5 minutes

        while time.time() - start_time < timeout:
            server.handle_request()

            if hasattr(server, "auth_code") and server.auth_code:
                auth_code = server.auth_code
                server.server_close()

                # Exchange code for token
                token_data = self.exchange_code_for_token(auth_code)
                return token_data

            elif hasattr(server, "auth_error") and server.auth_error:
                server.server_close()
                return None

            time.sleep(0.1)

        server.server_close()
        return None

    def _authenticate_with_manual_entry(self):
        """Authenticate using manual code entry (for cloud deployment)"""
        # Generate authorization URL
        auth_url = self.get_authorization_url()

        # Store the auth URL in session state for the UI to use
        st.session_state.auth_url = auth_url
        st.session_state.waiting_for_auth_code = True

        return None  # Will be handled by the UI


# Create a simple Token class to mimic aps-toolkit Token
class SimpleToken:
    """Simple token class to hold access token"""

    def __init__(self, token_data):
        self.access_token = token_data.get("access_token", "")
        self.token_type = token_data.get("token_type", "Bearer")
        self.expires_in = token_data.get("expires_in", 3600)


class IssuesAPI:
    """
    Extended Issues API functionality for Autodesk Construction Cloud (ACC)
    """

    def __init__(self, token):
        self.token = token
        self.base_url = "https://developer.api.autodesk.com"

    def get_project_container_id(self, hub_id, project_id):
        """
        Get the correct container ID for Issues API from project details
        """
        try:
            url = f"{self.base_url}/project/v1/hubs/{hub_id}/projects/{project_id}"
            headers = {
                "Authorization": f"Bearer {self.token.access_token}",
                "Content-Type": "application/vnd.api+json",
            }

            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                project_data = response.json().get("data", {})

                # Look for container information in project attributes
                attributes = project_data.get("attributes", {})
                extension = attributes.get("extension", {})
                ext_data = extension.get("data", {})

                # For ACC projects, try different container ID patterns
                if attributes.get("scopes"):
                    scopes = attributes["scopes"]
                    for scope in scopes:
                        if scope.startswith("b360project."):
                            # Extract the container ID from the scope
                            container_id = scope.replace("b360project.", "")
                            return container_id

                # Fallback: use project ID without the 'b.' prefix
                if project_id.startswith("b."):
                    container_id = project_id[2:]  # Remove 'b.' prefix
                    return container_id

                return None
            else:
                return None

        except Exception as e:
            return None

    def get_issues(
        self, project_id, container_id=None, issue_type=None, status=None, limit=200
    ):
        """
        Fetch issues from ACC using the correct Construction Issues API endpoint
        """
        if not container_id:
            return []

        # Ensure limit doesn't exceed API maximum
        if limit > 200:
            limit = 200

        url = f"{self.base_url}/construction/issues/v1/projects/{container_id}/issues"

        headers = {
            "Authorization": f"Bearer {self.token.access_token}",
            "Content-Type": "application/vnd.api+json",
        }

        params = {"limit": limit}

        if issue_type:
            params["filter[issueTypeId]"] = issue_type
        if status:
            params["filter[status]"] = status

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                # The API returns 'results' not 'data'
                issues = response_data.get("results", [])

                # If no results, also try 'data' for backward compatibility
                if not issues:
                    issues = response_data.get("data", [])

                return issues
            else:
                return []
        except Exception as e:
            return []

    def get_issue_types(self, container_id):
        """
        Fetch available issue types for a project using the correct Construction Issues API endpoint
        """
        if not container_id:
            return []

        url = f"{self.base_url}/construction/issues/v1/projects/{container_id}/issue-types"

        headers = {
            "Authorization": f"Bearer {self.token.access_token}",
            "Content-Type": "application/vnd.api+json",
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                # The API returns 'results' not 'data'
                issue_types = response_data.get("results", [])

                # If no results, also try 'data' for backward compatibility
                if not issue_types:
                    issue_types = response_data.get("data", [])

                return issue_types
            else:
                return []
        except Exception as e:
            return []


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "auth" not in st.session_state:
        st.session_state.auth = None
    if "bim360" not in st.session_state:
        st.session_state.bim360 = None
    if "issues_api" not in st.session_state:
        st.session_state.issues_api = None
    if "has_issues_access" not in st.session_state:
        st.session_state.has_issues_access = False
    if "hubs" not in st.session_state:
        st.session_state.hubs = {}
    if "projects" not in st.session_state:
        st.session_state.projects = {}
    if "issue_types" not in st.session_state:
        st.session_state.issue_types = {}
    if "current_issues" not in st.session_state:
        st.session_state.current_issues = []
    if "current_container_id" not in st.session_state:
        st.session_state.current_container_id = None
    if "client_id" not in st.session_state:
        st.session_state.client_id = ""
    if "client_secret" not in st.session_state:
        st.session_state.client_secret = ""
    if "auth_url" not in st.session_state:
        st.session_state.auth_url = None
    if "waiting_for_auth_code" not in st.session_state:
        st.session_state.waiting_for_auth_code = False


def authenticate():
    """Authenticate with Autodesk APS using both 2-legged and 3-legged auth"""
    with st.spinner("Authenticating..."):
        try:
            # Get credentials from session state (user input) or environment
            client_id = st.session_state.client_id or os.getenv("APS_CLIENT_ID")
            client_secret = st.session_state.client_secret or os.getenv(
                "APS_CLIENT_SECRET"
            )

            if not client_id or not client_secret:
                st.error("Please provide both APS Client ID and Client Secret")
                return False

            # First, get 2-legged token for Data Management API (hubs/projects)
            try:
                st.session_state.auth = Auth()
                token_2leg = st.session_state.auth.auth2leg()
                st.session_state.bim360 = BIM360(token_2leg)
                st.success("✅ 2-legged authentication successful (Data Management)")

            except Exception as e2leg:
                st.error(f"❌ 2-legged authentication failed: {str(e2leg)}")
                return False

            # Then, attempt 3-legged authentication for Issues API
            try:
                st.info("🔐 Starting 3-legged authentication for Issues API...")

                # Use manual 3-legged authentication
                auth_3leg = Manual3LeggedAuth(client_id, client_secret)

                if auth_3leg.use_local_server:
                    st.info("📖 A browser window will open for authorization...")
                    token_data_3leg = auth_3leg.authenticate()
                else:
                    # For cloud deployment, we need manual code entry
                    token_data_3leg = auth_3leg.authenticate()
                    if token_data_3leg is None and st.session_state.get(
                        "waiting_for_auth_code"
                    ):
                        # Authentication process started, will be completed in UI
                        return "waiting_for_code"

                if token_data_3leg:
                    st.success("✅ 3-legged authentication successful (Issues API)")
                    # Create token object
                    token_3leg = SimpleToken(token_data_3leg)
                    # Initialize Issues API with 3-legged token
                    st.session_state.issues_api = IssuesAPI(token_3leg)
                    st.session_state.has_issues_access = True
                else:
                    raise Exception("3-legged authentication failed")

            except Exception as e3leg:
                st.warning(f"⚠️ 3-legged authentication failed: {str(e3leg)}")
                st.info(
                    "📋 Issues API will not be available, but hub/project browsing will work"
                )
                # Create a dummy Issues API that will fail gracefully
                st.session_state.issues_api = IssuesAPI(token_2leg)
                st.session_state.has_issues_access = False

            st.session_state.authenticated = True
            return True

        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            return False


def load_hubs():
    """Load available hubs"""
    try:
        hubs_data = st.session_state.bim360.get_hubs()

        st.session_state.hubs.clear()

        # More robust handling of different return formats
        hubs_list = []

        if isinstance(hubs_data, str):
            st.error(f"API returned string instead of data: {hubs_data}")
            return
        elif isinstance(hubs_data, list):
            hubs_list = hubs_data
        elif isinstance(hubs_data, dict):
            if "data" in hubs_data:
                hubs_list = hubs_data["data"]
            elif "error" in hubs_data:
                error_msg = hubs_data.get("error", "Unknown error")
                st.error(f"API error: {error_msg}")
                return
            else:
                if "id" in hubs_data and "attributes" in hubs_data:
                    hubs_list = [hubs_data]
                else:
                    st.error("Unexpected data format from hubs API")
                    return

        # Process hubs list
        for i, hub in enumerate(hubs_list):
            try:
                if not isinstance(hub, dict):
                    continue

                hub_id = hub.get("id", "")
                if not hub_id:
                    continue

                hub_attrs = hub.get("attributes", {})
                if not isinstance(hub_attrs, dict):
                    hub_name = f"Hub {hub_id}"
                else:
                    hub_name = hub_attrs.get("name", f"Hub {hub_id}")

                st.session_state.hubs[hub_name] = hub_id

            except Exception as hub_error:
                continue

    except Exception as e:
        st.error(f"Error loading hubs: {str(e)}")


def load_projects(hub_id):
    """Load projects for selected hub"""
    try:
        projects_data = st.session_state.bim360.get_projects(hub_id)

        st.session_state.projects.clear()

        # More robust handling of different return formats
        projects_list = []

        if isinstance(projects_data, str):
            st.error(f"API returned string instead of data: {projects_data}")
            return
        elif isinstance(projects_data, list):
            projects_list = projects_data
        elif isinstance(projects_data, dict):
            if "data" in projects_data:
                projects_list = projects_data["data"]
            elif "error" in projects_data:
                error_msg = projects_data.get("error", "Unknown error")
                st.error(f"API error: {error_msg}")
                return
            else:
                if "id" in projects_data and "attributes" in projects_data:
                    projects_list = [projects_data]
                else:
                    st.error("Unexpected data format from projects API")
                    return

        # Process projects list
        for i, project in enumerate(projects_list):
            try:
                if not isinstance(project, dict):
                    continue

                project_id = project.get("id", "")
                if not project_id:
                    continue

                project_attrs = project.get("attributes", {})
                if not isinstance(project_attrs, dict):
                    project_name = f"Project {project_id}"
                else:
                    project_name = project_attrs.get("name", f"Project {project_id}")

                st.session_state.projects[project_name] = project_id

            except Exception as project_error:
                continue

    except Exception as e:
        st.error(f"Error loading projects: {str(e)}")


def load_issue_types(hub_id, project_id):
    """Load issue types for selected project"""
    try:
        # Get the correct container ID for Issues API
        container_id = st.session_state.issues_api.get_project_container_id(
            hub_id, project_id
        )

        if not container_id:
            st.warning(
                "Could not find container ID for project - Issues API may not be available"
            )
            return

        # Store the container ID for later use
        st.session_state.current_container_id = container_id

        issue_types_data = st.session_state.issues_api.get_issue_types(container_id)

        st.session_state.issue_types.clear()

        # More robust handling of issue types data
        if isinstance(issue_types_data, list):
            for i, issue_type in enumerate(issue_types_data):
                try:
                    if not isinstance(issue_type, dict):
                        continue

                    type_id = issue_type.get("id", "")
                    if not type_id:
                        continue

                    # Handle both JSON:API format (with attributes) and direct format
                    if "attributes" in issue_type:
                        # JSON:API format
                        type_attrs = issue_type.get("attributes", {})
                        if not isinstance(type_attrs, dict):
                            type_name = f"Type {type_id}"
                        else:
                            type_name = type_attrs.get("title", f"Type {type_id}")
                    else:
                        # Direct format (used by current API)
                        type_name = issue_type.get("title", f"Type {type_id}")
                        # Only include active issue types
                        if not issue_type.get("isActive", True):
                            continue

                    st.session_state.issue_types[type_name] = type_id

                except Exception as type_error:
                    continue

    except Exception as e:
        st.warning(f"Failed to load issue types: {str(e)}")


def fetch_issues(project_id, container_id, issue_type_id=None, status=None):
    """Fetch issues from the selected project"""
    try:
        if not container_id:
            st.error(
                "Cannot fetch issues: No valid container ID found for this project"
            )
            return []

        # Fetch issues (API limit is 200 max per request)
        issues = st.session_state.issues_api.get_issues(
            project_id=project_id,
            container_id=container_id,
            issue_type=issue_type_id,
            status=status,
            limit=200,
        )

        return issues

    except Exception as e:
        st.error(f"Failed to fetch issues: {str(e)}")
        return []


def issues_to_dataframe(issues):
    """Convert issues to pandas DataFrame"""
    data = []

    for issue in issues:
        # Handle both JSON:API format (with attributes) and direct format
        if "attributes" in issue:
            # JSON:API format
            attributes = issue.get("attributes", {})
            row = {
                "ID": issue.get("id", ""),
                "Title": attributes.get("title", ""),
                "Description": attributes.get("description", ""),
                "Issue Type": attributes.get("issueType", {}).get("title", ""),
                "Status": attributes.get("status", ""),
                "Priority": attributes.get("priority", ""),
                "Created At": attributes.get("createdAt", ""),
                "Updated At": attributes.get("updatedAt", ""),
                "Assigned To": (
                    attributes.get("assignedTo", {}).get("name", "")
                    if attributes.get("assignedTo")
                    else ""
                ),
                "Created By": (
                    attributes.get("createdBy", {}).get("name", "")
                    if attributes.get("createdBy")
                    else ""
                ),
                "Location": attributes.get("locationDescription", ""),
                "Due Date": attributes.get("dueDate", ""),
            }
        else:
            # Direct format
            row = {
                "ID": issue.get("id", ""),
                "Title": issue.get("title", ""),
                "Description": issue.get("description", ""),
                "Issue Type": (
                    issue.get("issueType", {}).get("title", "")
                    if isinstance(issue.get("issueType"), dict)
                    else str(issue.get("issueType", ""))
                ),
                "Status": issue.get("status", ""),
                "Priority": issue.get("priority", ""),
                "Created At": issue.get("createdAt", ""),
                "Updated At": issue.get("updatedAt", ""),
                "Assigned To": (
                    issue.get("assignedTo", {}).get("name", "")
                    if isinstance(issue.get("assignedTo"), dict)
                    else str(issue.get("assignedTo", ""))
                ),
                "Created By": (
                    issue.get("createdBy", {}).get("name", "")
                    if isinstance(issue.get("createdBy"), dict)
                    else str(issue.get("createdBy", ""))
                ),
                "Location": issue.get("locationDescription", ""),
                "Due Date": issue.get("dueDate", ""),
            }

        data.append(row)

    return pd.DataFrame(data)


def validate_credentials(client_id, client_secret):
    """Validate APS credentials format"""
    errors = []

    if not client_id:
        errors.append("Client ID is required")
    elif len(client_id) < 10:
        errors.append("Client ID appears to be too short")

    if not client_secret:
        errors.append("Client Secret is required")
    elif len(client_secret) < 20:
        errors.append("Client Secret appears to be too short")

    return errors


def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="ACC/BIM 360 Issues Fetcher",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🏗️ ACC/BIM 360 Issues Fetcher")
    st.markdown("---")

    # Initialize session state
    initialize_session_state()

    # Sidebar for authentication and navigation
    with st.sidebar:
        st.header("Authentication")

        if not st.session_state.authenticated:
            st.warning("⚠️ Not authenticated")

            # Credential input fields
            st.subheader("APS Credentials")

            # Load credentials from environment as defaults
            default_client_id = os.getenv("APS_CLIENT_ID", "")
            default_client_secret = os.getenv("APS_CLIENT_SECRET", "")

            # Initialize session state with defaults if empty
            if not st.session_state.client_id and default_client_id:
                st.session_state.client_id = default_client_id
            if not st.session_state.client_secret and default_client_secret:
                st.session_state.client_secret = default_client_secret

            client_id = st.text_input(
                "APS Client ID:",
                value=st.session_state.client_id,
                type="default",
                help="Enter your APS Application Client ID",
            )

            client_secret = st.text_input(
                "APS Client Secret:",
                value=st.session_state.client_secret,
                type="password",
                help="Enter your APS Application Client Secret",
            )

            # Update session state
            st.session_state.client_id = client_id
            st.session_state.client_secret = client_secret

            # Validate credentials
            validation_errors = validate_credentials(client_id, client_secret)

            # Show validation
            if not validation_errors and client_id and client_secret:
                st.success("✅ Credentials provided")
            elif validation_errors:
                for error in validation_errors:
                    st.warning(f"⚠️ {error}")
            else:
                st.info("💡 Enter your APS credentials above")

            # Authentication button
            auth_disabled = bool(validation_errors) or not (client_id and client_secret)

            # Handle cloud deployment manual authentication
            if st.session_state.get("waiting_for_auth_code") and st.session_state.get(
                "auth_url"
            ):
                st.info(
                    "🔗 **Step 1:** Click the link below to authorize the application:"
                )
                st.markdown(
                    f"[🔐 **Authorize Application**]({st.session_state.auth_url})"
                )

                st.info(
                    "📋 **Step 2:** After authorization, you'll be redirected to a page with an authorization code. Copy and paste it below:"
                )

                auth_code = st.text_input(
                    "Authorization Code:",
                    help="Paste the authorization code from the redirect page",
                    key="manual_auth_code",
                )

                col_auth1, col_auth2 = st.columns(2)
                with col_auth1:
                    if st.button("✅ Complete Authentication", disabled=not auth_code):
                        if auth_code:
                            try:
                                # Get credentials
                                client_id = st.session_state.client_id or os.getenv(
                                    "APS_CLIENT_ID"
                                )
                                client_secret = (
                                    st.session_state.client_secret
                                    or os.getenv("APS_CLIENT_SECRET")
                                )

                                # Create auth object and exchange code for token
                                auth_3leg = Manual3LeggedAuth(client_id, client_secret)
                                token_data_3leg = auth_3leg.exchange_code_for_token(
                                    auth_code
                                )

                                if token_data_3leg:
                                    st.success(
                                        "✅ 3-legged authentication successful (Issues API)"
                                    )
                                    # Create token object
                                    token_3leg = SimpleToken(token_data_3leg)
                                    # Initialize Issues API with 3-legged token
                                    st.session_state.issues_api = IssuesAPI(token_3leg)
                                    st.session_state.has_issues_access = True
                                    st.session_state.authenticated = True
                                    st.session_state.waiting_for_auth_code = False
                                    st.session_state.auth_url = None
                                    load_hubs()
                                    st.rerun()
                                else:
                                    st.error(
                                        "❌ Failed to exchange authorization code for token"
                                    )
                            except Exception as e:
                                st.error(f"❌ Authentication failed: {str(e)}")

                with col_auth2:
                    if st.button("❌ Cancel"):
                        st.session_state.waiting_for_auth_code = False
                        st.session_state.auth_url = None
                        st.rerun()
            else:
                if st.button("🔐 Authenticate", type="primary", disabled=auth_disabled):
                    result = authenticate()
                    if result == "waiting_for_code":
                        st.rerun()  # Refresh to show manual code entry
                    elif result:
                        load_hubs()
                        st.rerun()
        else:
            if st.session_state.has_issues_access:
                st.success("✅ Authenticated (Full Access)")
            else:
                st.warning("⚠️ Authenticated (Limited - No Issues API)")

            # Show current credentials (masked)
            st.subheader("Current Credentials")
            if st.session_state.client_id:
                masked_id = (
                    st.session_state.client_id[:8] + "..."
                    if len(st.session_state.client_id) > 8
                    else st.session_state.client_id
                )
                st.text(f"Client ID: {masked_id}")
            if st.session_state.client_secret:
                st.text(f"Client Secret: {'*' * 8}")

            if st.button("🔄 Re-authenticate"):
                # Reset authentication state
                st.session_state.authenticated = False
                st.session_state.has_issues_access = False
                st.rerun()

        st.markdown("---")

    # Main content area
    if not st.session_state.authenticated:
        st.info(
            "Please enter your APS credentials in the sidebar and authenticate to access your ACC/BIM 360 data."
        )

        # Display setup instructions
        st.markdown("### Setup Instructions")
        st.markdown(
            """
        1. **Create APS Application** at [APS Developer Portal](https://aps.autodesk.com/myapps):
           - App type: Web App
           - **Callback URLs** (add both):
             - For local development: `http://localhost:8080/callback`
             - For Streamlit Cloud: `https://issues-fetcher.streamlit.app/callback`
           - Enable APIs: Data Management, Construction Cloud Issues
           - Scopes: `data:read`, `data:write`, `account:read`, `code:all`

        2. **Enter credentials**:
           - Use the sidebar to enter your APS Client ID and Client Secret
           - Alternatively, you can set environment variables `APS_CLIENT_ID` and `APS_CLIENT_SECRET`
           - The app will automatically load credentials from environment if available

        3. **Add the custom integration to your hub admin portal**:
           - https://admin.b360.autodesk.com/admin/
           
        4. **Authentication Flow**:
           - **Local Development**: Browser will open automatically for OAuth
           - **Streamlit Cloud**: You'll get a link to click and then paste the authorization code
           
        5. **Troubleshooting**:
           - Make sure your callback URLs include both local and cloud URLs
           - Ensure the required APIs are enabled in your APS app
           - Check that your user has access to the ACC/BIM 360 projects
        """
        )

        return

    # Hub and Project Selection
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Hub Selection")
        if st.session_state.hubs:
            selected_hub = st.selectbox(
                "Select Hub:",
                options=list(st.session_state.hubs.keys()),
                key="hub_selectbox",
            )

            if selected_hub:
                hub_id = st.session_state.hubs[selected_hub]

                # Load projects when hub changes
                if (
                    "last_selected_hub" not in st.session_state
                    or st.session_state.last_selected_hub != hub_id
                ):
                    st.session_state.last_selected_hub = hub_id
                    with st.spinner("Loading projects..."):
                        load_projects(hub_id)
        else:
            st.info("No hubs available or not loaded yet.")

    with col2:
        st.subheader("Project Selection")
        if st.session_state.projects:
            selected_project = st.selectbox(
                "Select Project:",
                options=list(st.session_state.projects.keys()),
                key="project_selectbox",
            )

            if selected_project:
                project_id = st.session_state.projects[selected_project]

                # Load issue types when project changes
                if (
                    "last_selected_project" not in st.session_state
                    or st.session_state.last_selected_project != project_id
                ):
                    st.session_state.last_selected_project = project_id
                    if st.session_state.has_issues_access:
                        with st.spinner("Loading issue types..."):
                            load_issue_types(hub_id, project_id)
        else:
            st.info("No projects available. Please select a hub first.")

    # Filters Section
    if st.session_state.projects and selected_project:
        st.markdown("---")
        st.subheader("Filters")

        col3, col4 = st.columns(2)

        with col3:
            # Issue Type Filter
            issue_type_options = [""] + list(st.session_state.issue_types.keys())
            selected_issue_type = st.selectbox(
                "Issue Type:", options=issue_type_options, key="issue_type_selectbox"
            )

        with col4:
            # Status Filter
            status_options = ["", "open", "closed", "in_progress", "resolved"]
            selected_status = st.selectbox(
                "Status:", options=status_options, key="status_selectbox"
            )

        # Fetch Issues Button
        st.markdown("---")

        if not st.session_state.has_issues_access:
            st.warning(
                "⚠️ Issues API access required for fetching issues. Please re-authenticate with user consent."
            )
            if st.button("🔄 Re-authenticate for Issues API", type="primary"):
                st.session_state.authenticated = False
                st.rerun()
        else:
            if st.button("📥 Fetch Issues", type="primary"):
                with st.spinner("Fetching issues..."):
                    project_id = st.session_state.projects[selected_project]
                    container_id = st.session_state.current_container_id

                    issue_type_id = None
                    if (
                        selected_issue_type
                        and selected_issue_type in st.session_state.issue_types
                    ):
                        issue_type_id = st.session_state.issue_types[
                            selected_issue_type
                        ]

                    status = selected_status if selected_status else None

                    issues = fetch_issues(
                        project_id, container_id, issue_type_id, status
                    )
                    st.session_state.current_issues = issues

        # Display Issues
        if st.session_state.current_issues:
            st.markdown("---")
            st.subheader(f"Issues ({len(st.session_state.current_issues)} found)")

            # Convert to DataFrame for display
            df = issues_to_dataframe(st.session_state.current_issues)

            # Display issues table
            st.dataframe(df, use_container_width=True)

            # Export options
            st.markdown("---")
            st.subheader("Export Options")

            col5, col6 = st.columns(2)

            with col5:
                # CSV Export
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()

                st.download_button(
                    label="📄 Download as CSV",
                    data=csv_data,
                    file_name=f"issues_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )

            with col6:
                # Excel Export
                excel_buffer = io.BytesIO()
                df.to_excel(excel_buffer, index=False, engine="openpyxl")
                excel_data = excel_buffer.getvalue()

                st.download_button(
                    label="📊 Download as Excel",
                    data=excel_data,
                    file_name=f"issues_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

        elif (
            st.session_state.has_issues_access
            and "last_selected_project" in st.session_state
        ):
            st.info(
                "No issues found. Click 'Fetch Issues' to search for issues in this project."
            )


if __name__ == "__main__":
    main()
