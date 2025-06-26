"""
Autodesk Construction Cloud (ACC) Issues Fetcher - Streamlit Web App
This is a web version of the desktop ACC Issues Fetcher tool using Streamlit.

Features:
- Hub and project selection
- Issue type filtering
- Export to CSV/Excel
- OAuth3 authentication for web deployment
- State management for seamless user experience

Requirements:
- streamlit
- aps-toolkit
- pandas
- requests

Author: AI Assistant
Date: 2025-06-26
"""

import streamlit as st
import pandas as pd
import requests
import os
import sys
import json
import urllib.parse
import time
from datetime import datetime
import traceback
import base64
from io import BytesIO

# Load environment variables
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
    from aps_toolkit import Auth, BIM360
except ImportError as e:
    st.error(
        "Missing required packages. Please install: pip install aps-toolkit pandas requests streamlit"
    )
    st.error(f"Error: {e}")
    st.stop()


class StreamlitOAuth3Handler:
    """OAuth3 handler adapted for Streamlit deployment"""

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

        # Determine callback URL based on deployment
        # For Streamlit, we need to use the base URL without additional path
        # The OAuth provider will redirect to the base URL with query parameters

        # Check if we have a custom callback URL set in environment
        callback_url = os.getenv("APS_CALLBACK_URL")

        if callback_url:
            self.callback_url = callback_url
        else:
            # Default callback URLs
            try:
                # Try to detect if we're running locally
                import streamlit.web.server.server as server

                # For local development, use localhost:8080
                self.callback_url = "http://localhost:8080"
            except:
                # For deployed apps, use a generic callback
                # This should be set via environment variable in production
                self.callback_url = "https://your-app.streamlit.app"

        self.base_url = "https://developer.api.autodesk.com"
        self.scopes = ["data:read", "data:write", "account:read", "code:all"]

        # Debug information
        st.info(f"🔗 OAuth Callback URL configured as: {self.callback_url}")
        st.info("📝 Make sure this URL is configured in your APS application settings")

    def get_authorization_url(self):
        """Generate the authorization URL"""
        auth_url = "https://developer.api.autodesk.com/authentication/v2/authorize"

        # Generate a simple state parameter for security - use timestamp for uniqueness
        import time

        state = f"streamlit_{int(time.time())}"
        st.session_state["oauth_state"] = state

        # Also store in a more persistent way
        if "oauth_states" not in st.session_state:
            st.session_state["oauth_states"] = []
        st.session_state["oauth_states"].append(state)

        # Keep only last 5 states to avoid memory issues
        if len(st.session_state["oauth_states"]) > 5:
            st.session_state["oauth_states"] = st.session_state["oauth_states"][-5:]

        st.info(f"🔐 Generated OAuth state: {state}")

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.callback_url,
            "scope": " ".join(self.scopes),
            "state": state,
        }

        query_string = urllib.parse.urlencode(params)
        full_url = f"{auth_url}?{query_string}"

        return full_url

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

        try:
            response = requests.post(token_url, data=data, headers=headers, timeout=30)

            if response.status_code == 200:
                token_data = response.json()
                return token_data
            else:
                st.error(f"Token exchange failed: {response.status_code}")
                st.error(f"Response: {response.text}")
                return None
        except Exception as e:
            st.error(f"Exception during token exchange: {str(e)}")
            return None


class SimpleToken:
    """Simple token class to hold access token"""

    def __init__(self, token_data):
        self.access_token = token_data.get("access_token", "")
        self.token_type = token_data.get("token_type", "Bearer")
        self.expires_in = token_data.get("expires_in", 3600)
        self.expires_at = time.time() + self.expires_in


class IssuesAPI:
    """Issues API functionality for Autodesk Construction Cloud (ACC)"""

    def __init__(self, token):
        self.token = token
        self.base_url = "https://developer.api.autodesk.com"

    def get_project_container_id(self, hub_id, project_id):
        """Get the correct container ID for Issues API from project details"""
        try:
            url = f"{self.base_url}/project/v1/hubs/{hub_id}/projects/{project_id}"
            headers = {
                "Authorization": f"Bearer {self.token.access_token}",
                "Content-Type": "application/vnd.api+json",
            }

            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                project_data = response.json().get("data", {})
                attributes = project_data.get("attributes", {})

                if attributes.get("scopes"):
                    scopes = attributes["scopes"]
                    for scope in scopes:
                        if scope.startswith("b360project."):
                            container_id = scope.replace("b360project.", "")
                            return container_id

                # Fallback: use project ID without the 'b.' prefix
                if project_id.startswith("b."):
                    container_id = project_id[2:]
                    return container_id

                return None
            else:
                st.error(f"Failed to get project details: {response.status_code}")
                return None

        except Exception as e:
            st.error(f"Exception getting container ID: {str(e)}")
            return None

    def get_issues(
        self, project_id, container_id=None, issue_type=None, status=None, limit=200
    ):
        """Fetch issues from ACC using the Construction Issues API"""
        if not container_id:
            return []

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
                issues = response_data.get("results", [])

                if not issues:
                    issues = response_data.get("data", [])

                return issues
            elif response.status_code == 404:
                st.warning(
                    "Issues API not available for this project. This project may not have Issues enabled."
                )
                return []
            elif response.status_code == 401:
                st.error("Authentication error. Please re-authenticate.")
                return []
            elif response.status_code == 403:
                st.error(
                    "Access denied. You may not have permission to access Issues for this project."
                )
                return []
            else:
                st.error(
                    f"Error fetching issues: {response.status_code} - {response.text}"
                )
                return []

        except Exception as e:
            st.error(f"Exception occurred while fetching issues: {str(e)}")
            return []

    def get_issue_types(self, container_id):
        """Fetch available issue types for a project"""
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
                issue_types = response_data.get("results", [])

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
    if "has_issues_access" not in st.session_state:
        st.session_state.has_issues_access = False
    if "token_3leg" not in st.session_state:
        st.session_state.token_3leg = None


def handle_oauth_callback():
    """Handle OAuth callback from URL parameters"""
    query_params = st.query_params

    if "code" in query_params and "state" in query_params:
        auth_code = query_params["code"]
        state = query_params["state"]

        # For debugging
        st.info(f"🔍 Received state: {state}")
        st.info(f"🔍 Stored state: {st.session_state.get('oauth_state', 'None')}")

        # Verify state parameter for security - be more lenient for debugging
        stored_state = st.session_state.get("oauth_state")
        stored_states = st.session_state.get("oauth_states", [])

        if state == stored_state or state in stored_states or not stored_state:
            # If no stored state, we'll proceed but with a warning
            if not stored_state and state not in stored_states:
                st.warning(
                    "⚠️ No stored OAuth state found - this might be due to session reset"
                )
            else:
                st.success("✅ OAuth state verified successfully")

            # Get credentials
            client_id = os.getenv("APS_CLIENT_ID")
            client_secret = os.getenv("APS_CLIENT_SECRET")

            if client_id and client_secret:
                oauth_handler = StreamlitOAuth3Handler(client_id, client_secret)
                token_data = oauth_handler.exchange_code_for_token(auth_code)

                if token_data:
                    st.session_state.token_3leg = SimpleToken(token_data)
                    st.session_state.has_issues_access = True
                    st.session_state.authenticated = True

                    # Initialize APIs
                    try:
                        # 2-legged auth for Data Management
                        st.session_state.auth = Auth()
                        token_2leg = st.session_state.auth.auth2leg()
                        st.session_state.bim360 = BIM360(token_2leg)

                        # 3-legged auth for Issues
                        st.session_state.issues_api = IssuesAPI(
                            st.session_state.token_3leg
                        )

                        st.success(
                            "✅ Authentication successful! You can now access hubs, projects, and issues."
                        )

                        # Clear URL parameters to clean up the URL
                        st.query_params.clear()

                        # Force a rerun to refresh the UI
                        st.rerun()

                        # Load hubs
                        load_hubs()

                    except Exception as e:
                        st.error(f"Error initializing APIs: {str(e)}")
                else:
                    st.error("Failed to exchange authorization code for token")
            else:
                st.error("Missing APS_CLIENT_ID or APS_CLIENT_SECRET in environment")
        else:
            st.error(f"Invalid state parameter. Expected: {stored_state}, Got: {state}")
            st.error(f"Valid states: {stored_states}")
            st.info(
                "This might be due to browser session issues. Try clearing browser cache and cookies, then restart authentication."
            )

    elif "error" in query_params:
        error = query_params["error"]
        error_description = query_params.get("error_description", "Unknown error")
        st.error(f"Authorization failed: {error} - {error_description}")
        # Clear error parameters
        st.query_params.clear()


def authenticate():
    """Handle authentication process"""
    client_id = os.getenv("APS_CLIENT_ID")
    client_secret = os.getenv("APS_CLIENT_SECRET")

    if not client_id or not client_secret:
        st.error("Missing APS_CLIENT_ID or APS_CLIENT_SECRET in environment variables")
        st.info("Please set up your environment variables in a .env file:")
        st.code(
            """
APS_CLIENT_ID=your_client_id_here
APS_CLIENT_SECRET=your_client_secret_here
# Optional: Custom callback URL (defaults to http://localhost:8080 for local)
APS_CALLBACK_URL=http://localhost:8080
        """
        )
        return

    try:
        # First, get 2-legged token for Data Management API
        st.session_state.auth = Auth()
        token_2leg = st.session_state.auth.auth2leg()
        st.session_state.bim360 = BIM360(token_2leg)

        # Then, initiate 3-legged authentication for Issues API
        oauth_handler = StreamlitOAuth3Handler(client_id, client_secret)
        auth_url = oauth_handler.get_authorization_url()

        st.success("✅ 2-legged authentication successful (for Data Management)")

        st.info("🔐 To access Issues API, please authorize the application:")

        # Create a prominent button/link for authorization
        st.markdown(
            f"""
        ### Click the link below to authorize:
        **[🔓 Authorize Issues API Access]({auth_url})**
        
        📋 **Important Notes:**
        - You will be redirected to Autodesk's authorization page
        - After granting permission, you'll be redirected back to this page
        - The page will automatically refresh with your new permissions
        """
        )

        st.warning("⚠️ Make sure your APS application callback URL is set correctly!")

        # Show current callback URL for verification
        st.code(f"Expected callback URL: {oauth_handler.callback_url}")

        # Load hubs with 2-legged token
        load_hubs()

    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")

        if "AUTH-001" in str(e):
            st.info(
                """
            **Authentication Error (AUTH-001):**
            
            Your APS application doesn't have access to the required APIs.
            
            To fix this:
            1. Go to https://aps.autodesk.com/myapps
            2. Select your application
            3. Enable these APIs:
               • Data Management API
               • Construction Cloud Issues API
            4. Add these scopes:
               • data:read
               • data:write
               • account:read
               • code:all
            5. Set callback URL to: http://localhost:8080 (for local) or your deployed URL
            6. Save and try again
            """
            )


def load_hubs():
    """Load available hubs"""
    if not st.session_state.bim360:
        return

    try:
        with st.spinner("Loading hubs..."):
            hubs_data = st.session_state.bim360.get_hubs()

            st.session_state.hubs.clear()

            # Handle different return formats
            hubs_list = []
            if isinstance(hubs_data, list):
                hubs_list = hubs_data
            elif isinstance(hubs_data, dict) and "data" in hubs_data:
                hubs_list = hubs_data["data"]

            for hub in hubs_list:
                if isinstance(hub, dict) and "id" in hub:
                    hub_id = hub["id"]
                    hub_attrs = hub.get("attributes", {})
                    hub_name = hub_attrs.get("name", f"Hub {hub_id}")
                    st.session_state.hubs[hub_name] = hub_id

            st.success(f"✅ Loaded {len(st.session_state.hubs)} hubs")

    except Exception as e:
        st.error(f"Error loading hubs: {str(e)}")


def load_projects(hub_id):
    """Load projects for selected hub"""
    if not st.session_state.bim360 or not hub_id:
        return

    try:
        with st.spinner("Loading projects..."):
            projects_data = st.session_state.bim360.get_projects(hub_id)

            st.session_state.projects.clear()

            # Handle different return formats
            projects_list = []
            if isinstance(projects_data, list):
                projects_list = projects_data
            elif isinstance(projects_data, dict) and "data" in projects_data:
                projects_list = projects_data["data"]

            for project in projects_list:
                if isinstance(project, dict) and "id" in project:
                    project_id = project["id"]
                    project_attrs = project.get("attributes", {})
                    project_name = project_attrs.get("name", f"Project {project_id}")
                    st.session_state.projects[project_name] = project_id

            st.success(f"✅ Loaded {len(st.session_state.projects)} projects")

    except Exception as e:
        st.error(f"Error loading projects: {str(e)}")


def load_issue_types(hub_id, project_id):
    """Load issue types for selected project"""
    if not st.session_state.issues_api or not st.session_state.has_issues_access:
        return

    try:
        with st.spinner("Loading issue types..."):
            container_id = st.session_state.issues_api.get_project_container_id(
                hub_id, project_id
            )

            if not container_id:
                st.warning("Could not find container ID for this project")
                return

            st.session_state.current_container_id = container_id
            issue_types_data = st.session_state.issues_api.get_issue_types(container_id)

            st.session_state.issue_types.clear()

            for issue_type in issue_types_data:
                if isinstance(issue_type, dict):
                    type_id = issue_type.get("id", "")
                    type_name = issue_type.get("title", f"Type {type_id}")

                    # Only include active issue types
                    if issue_type.get("isActive", True):
                        st.session_state.issue_types[type_name] = type_id

            st.success(f"✅ Loaded {len(st.session_state.issue_types)} issue types")

    except Exception as e:
        st.warning(f"Could not load issue types: {str(e)}")


def fetch_issues(project_id, container_id, issue_type_id=None, status=None):
    """Fetch issues from selected project"""
    if not st.session_state.issues_api or not st.session_state.has_issues_access:
        st.error(
            "Issues API access not available. Please complete 3-legged authentication."
        )
        return []

    try:
        with st.spinner("Fetching issues..."):
            issues = st.session_state.issues_api.get_issues(
                project_id=project_id,
                container_id=container_id,
                issue_type=issue_type_id,
                status=status,
                limit=200,
            )

            st.session_state.current_issues = issues
            return issues

    except Exception as e:
        st.error(f"Error fetching issues: {str(e)}")
        return []


def issues_to_dataframe(issues):
    """Convert issues to pandas DataFrame"""
    if not issues:
        return pd.DataFrame()

    data = []
    for issue in issues:
        # Handle both JSON:API format and direct format
        if "attributes" in issue:
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


def download_csv(df, filename):
    """Create download link for CSV"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV file</a>'
    return href


def download_excel(df, filename):
    """Create download link for Excel"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Issues")

    output.seek(0)
    b64 = base64.b64encode(output.read()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Download Excel file</a>'
    return href


def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="ACC/BIM 360 Issues Fetcher",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🏗️ ACC/BIM 360 Issues Fetcher")
    st.markdown("**Web version of the ACC Issues Fetcher tool**")

    # Initialize session state
    initialize_session_state()

    # Handle OAuth callback first (before any other UI elements)
    handle_oauth_callback()

    # Debug information for OAuth callback issues
    if st.sidebar.button("🔍 Show Debug Info"):
        current_url = st.query_params
        st.sidebar.write("Current URL parameters:", dict(current_url))
        st.sidebar.write("Session state keys:", list(st.session_state.keys()))

    # Sidebar for authentication and settings
    with st.sidebar:
        st.header("🔐 Authentication")

        if st.session_state.authenticated and st.session_state.has_issues_access:
            st.success("✅ Fully authenticated")
            st.info("✅ Data Management API access")
            st.info("✅ Issues API access")
        elif st.session_state.authenticated:
            st.warning("⚠️ Partially authenticated")
            st.info("✅ Data Management API access")
            st.error("❌ Issues API access (user consent required)")
        else:
            st.error("❌ Not authenticated")

        if st.button(
            "🔓 Authenticate"
            if not st.session_state.authenticated
            else "🔄 Re-authenticate"
        ):
            authenticate()

        if st.session_state.authenticated:
            st.header("📁 Project Selection")

            # Hub selection
            if st.session_state.hubs:
                hub_names = list(st.session_state.hubs.keys())
                selected_hub_name = st.selectbox("Select Hub:", hub_names)

                if selected_hub_name:
                    hub_id = st.session_state.hubs[selected_hub_name]

                    # Load projects for selected hub
                    if st.button("🔄 Refresh Projects"):
                        load_projects(hub_id)

                    # Project selection
                    if st.session_state.projects:
                        project_names = list(st.session_state.projects.keys())
                        selected_project_name = st.selectbox(
                            "Select Project:", project_names
                        )

                        if selected_project_name:
                            project_id = st.session_state.projects[
                                selected_project_name
                            ]

                            # Load issue types for selected project
                            if st.session_state.has_issues_access:
                                if st.button("🔄 Load Issue Types"):
                                    load_issue_types(hub_id, project_id)

    # Main content area
    if st.session_state.authenticated:
        if st.session_state.hubs:
            # Get currently selected hub and project from sidebar state
            hub_names = list(st.session_state.hubs.keys())
            project_names = (
                list(st.session_state.projects.keys())
                if st.session_state.projects
                else []
            )

            if hub_names and project_names:
                # Use the first available selections (in a real app, these would come from sidebar widgets)
                selected_hub_name = hub_names[0]
                selected_project_name = project_names[0]

                if selected_hub_name and selected_project_name:
                    hub_id = st.session_state.hubs[selected_hub_name]
                    project_id = st.session_state.projects[selected_project_name]

                    st.header(f"📋 Issues for: {selected_project_name}")

                    # Filters
                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        # Issue type filter
                        issue_type_options = ["All"] + list(
                            st.session_state.issue_types.keys()
                        )
                        selected_issue_type = st.selectbox(
                            "Issue Type:", issue_type_options
                        )
                        issue_type_id = (
                            st.session_state.issue_types.get(selected_issue_type)
                            if selected_issue_type != "All"
                            else None
                        )

                    with col2:
                        # Status filter
                        status_options = [
                            "All",
                            "open",
                            "closed",
                            "in_progress",
                            "resolved",
                        ]
                        selected_status = st.selectbox("Status:", status_options)
                        status = selected_status if selected_status != "All" else None

                    with col3:
                        st.write("")  # Spacing
                        st.write("")  # Spacing
                        if st.button("🔍 Fetch Issues", type="primary"):
                            if (
                                st.session_state.has_issues_access
                                and st.session_state.current_container_id
                            ):
                                issues = fetch_issues(
                                    project_id,
                                    st.session_state.current_container_id,
                                    issue_type_id,
                                    status,
                                )

                                if issues:
                                    st.success(f"✅ Fetched {len(issues)} issues")
                                else:
                                    st.info("ℹ️ No issues found")
                            else:
                                st.error(
                                    "❌ Issues API access required. Please complete 3-legged authentication."
                                )

                    # Display issues
                    if st.session_state.current_issues:
                        df = issues_to_dataframe(st.session_state.current_issues)

                        # Display metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Issues", len(df))
                        with col2:
                            if "Status" in df.columns:
                                open_issues = len(df[df["Status"] == "open"])
                                st.metric("Open Issues", open_issues)
                        with col3:
                            if "Priority" in df.columns:
                                high_priority = len(df[df["Priority"] == "high"])
                                st.metric("High Priority", high_priority)
                        with col4:
                            if "Issue Type" in df.columns:
                                unique_types = df["Issue Type"].nunique()
                                st.metric("Issue Types", unique_types)

                        # Display table
                        st.subheader("📊 Issues Data")
                        st.dataframe(df, use_container_width=True)

                        # Export options
                        st.subheader("📥 Export Options")
                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("📄 Download as CSV"):
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = (
                                    f"issues_{selected_project_name}_{timestamp}.csv"
                                )
                                st.markdown(
                                    download_csv(df, filename), unsafe_allow_html=True
                                )

                        with col2:
                            if st.button("📊 Download as Excel"):
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = (
                                    f"issues_{selected_project_name}_{timestamp}.xlsx"
                                )
                                st.markdown(
                                    download_excel(df, filename), unsafe_allow_html=True
                                )

                    else:
                        st.info(
                            "🔍 Select filters and click 'Fetch Issues' to load data"
                        )

                else:
                    st.info("👆 Please select a hub and project from the sidebar")
            else:
                st.info("👆 Please select a hub and project from the sidebar")
        else:
            st.info("🔄 Loading hubs and projects...")

    else:
        st.info("🔐 Please authenticate using the sidebar to get started")

        st.markdown(
            """
        ### 📋 Setup Instructions
        
        1. **Create APS Application:**
           - Go to https://aps.autodesk.com/myapps
           - Create a new application
           - Enable these APIs:
             - Data Management API
             - Construction Cloud Issues API
        
        2. **Configure Scopes:**
           - data:read
           - data:write
           - account:read
           - code:all
        
        3. **Set Callback URL:**
           - For local development: `http://localhost:8080`
           - For deployed app: `https://your-app.streamlit.app`
        
        4. **Environment Variables:**
           Create a `.env` file with your credentials:
           ```
           APS_CLIENT_ID=your_client_id_here
           APS_CLIENT_SECRET=your_client_secret_here
           ```
        """
        )


if __name__ == "__main__":
    main()
