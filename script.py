"""
Autodesk Construction Cloud (ACC) Issues Fetcher Tool
This tool fetches issues from Autodesk BIM 360/ACC Docs using the APS toolkit.
Features:
- Hub and project selection
- Issue type filtering
- Export to CSV/Excel
- Basic GUI interface

Requirements:
- aps-toolkit
- tkinter (usually included with Python)
- pandas
- requests

Author: AI Assistant
Date: 2025-06-26
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import sys
from datetime import datetime
import json
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

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
    print(
        "Missing required packages. Please install: pip install aps-toolkit pandas requests"
    )
    print(f"Error: {e}")
    sys.exit(1)


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
        self.callback_url = "http://localhost:8080/callback"
        self.base_url = "https://developer.api.autodesk.com"

        # Scopes required for Issues API
        self.scopes = ["data:read", "data:write", "account:read", "code:all"]

    def get_authorization_url(self):
        """Generate the authorization URL"""
        auth_url = "https://developer.api.autodesk.com/authentication/v2/authorize"

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.callback_url,
            "scope": " ".join(self.scopes),
            "state": "gui_auth_state",
        }

        query_string = urllib.parse.urlencode(params)
        full_url = f"{auth_url}?{query_string}"

        print(f"🔗 Authorization URL: {full_url}")
        return full_url

    def start_callback_server(self):
        """Start the HTTP server to handle OAuth callback"""
        server = HTTPServer(("localhost", 8080), OAuth3LeggedHandler)
        server.auth_code = None
        server.auth_error = None
        server.timeout = 1  # Non-blocking

        print(f"🌐 Starting callback server on {self.callback_url}")
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

        print(f"🔄 Exchanging code for token...")
        response = requests.post(token_url, data=data, headers=headers, timeout=30)

        if response.status_code == 200:
            token_data = response.json()
            print(f"✅ Token exchange successful!")
            return token_data
        else:
            print(f"❌ Token exchange failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    def authenticate(self):
        """Complete 3-legged authentication flow"""
        print("🔐 Starting 3-legged authentication...")

        # Start callback server
        server = self.start_callback_server()

        # Generate and open authorization URL
        auth_url = self.get_authorization_url()
        print(f"📖 Opening browser for authorization...")
        webbrowser.open(auth_url)

        # Wait for callback
        print(f"⏳ Waiting for authorization callback...")
        start_time = time.time()
        timeout = 300  # 5 minutes

        while time.time() - start_time < timeout:
            server.handle_request()

            if hasattr(server, "auth_code") and server.auth_code:
                print(f"✅ Received authorization code!")
                auth_code = server.auth_code
                server.server_close()

                # Exchange code for token
                token_data = self.exchange_code_for_token(auth_code)
                return token_data

            elif hasattr(server, "auth_error") and server.auth_error:
                print(f"❌ Authorization error: {server.auth_error}")
                server.server_close()
                return None

            time.sleep(0.1)

        print(f"⏰ Authorization timed out after {timeout} seconds")
        server.server_close()
        return None


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

        Args:
            hub_id (str): Hub ID
            project_id (str): Project ID

        Returns:
            str or None: Container ID if found, None otherwise
        """
        try:
            # Try to get project details to find container information
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
                            print(f"Found container ID from scope: {container_id}")
                            return container_id

                # Fallback: use project ID without the 'b.' prefix
                if project_id.startswith("b."):
                    container_id = project_id[2:]  # Remove 'b.' prefix
                    print(
                        f"Using project ID as container ID (without prefix): {container_id}"
                    )
                    return container_id

                print(f"No suitable container ID found in project data")
                return None
            else:
                print(
                    f"Failed to get project details: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            print(f"Exception getting container ID: {str(e)}")
            return None

    def get_issues(
        self, project_id, container_id=None, issue_type=None, status=None, limit=200
    ):
        """
        Fetch issues from ACC using the correct Construction Issues API endpoint

        Args:
            project_id (str): Project ID (used as projectId in the API)
            container_id (str): Container ID (same as project_id for ACC Issues API)
            issue_type (str): Issue type filter (optional)
            status (str): Issue status filter (optional)
            limit (int): Maximum number of issues to fetch (max 200 per request)

        Returns:
            list: List of issues
        """
        if not container_id:
            print(f"No container ID provided for issues fetch")
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
            print(f"Fetching issues from: {url}")
            print(f"Parameters: {params}")
            print(f"Headers: Authorization: Bearer {self.token.access_token[:20]}...")

            response = requests.get(url, headers=headers, params=params, timeout=30)

            print(f"Issues response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")

            if response.status_code == 200:
                response_data = response.json()
                print(f"Raw response data structure: {type(response_data)}")
                print(
                    f"Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}"
                )

                # The API returns 'results' not 'data'
                issues = response_data.get("results", [])

                # If no results, also try 'data' for backward compatibility
                if not issues:
                    issues = response_data.get("data", [])

                print(f"✅ Successfully fetched {len(issues)} issues")

                # Log first few issues for debugging
                for i, issue in enumerate(issues[:3]):
                    # Check the structure - it might be different for issues
                    if "attributes" in issue:
                        # Standard JSON:API format
                        attrs = issue.get("attributes", {})
                        title = attrs.get("title", "No title")
                        issue_id = issue.get("id", "No ID")
                    else:
                        # Direct format (like issue types)
                        title = issue.get("title", "No title")
                        issue_id = issue.get("id", "No ID")

                    print(f"  Issue {i+1}: {title} (ID: {issue_id})")

                if len(issues) > 3:
                    print(f"  ... and {len(issues) - 3} more issues")

                return issues
            elif response.status_code == 404:
                print(
                    f"Issues API not available for this project (404). This project may not have Issues enabled."
                )
                print(f"Response body: {response.text}")
                return []
            elif response.status_code == 401:
                print(
                    f"Authentication error (401). The Construction Issues API requires 3-legged authentication (user consent)."
                )
                print(f"Response body: {response.text}")
                return []
            elif response.status_code == 403:
                print(
                    f"Access denied (403). You may not have permission to access Issues for this project."
                )
                print(f"Response body: {response.text}")
                return []
            else:
                print(
                    f"Error fetching issues: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            print(f"Exception occurred while fetching issues: {str(e)}")
            import traceback

            traceback.print_exc()
            return []

    def get_issue_types(self, container_id):
        """
        Fetch available issue types for a project using the correct Construction Issues API endpoint

        Args:
            container_id (str): Container ID (same as project_id for ACC Issues API)

        Returns:
            list: List of issue types
        """
        if not container_id:
            print(f"No container ID provided for issue types fetch")
            return []

        url = f"{self.base_url}/construction/issues/v1/projects/{container_id}/issue-types"

        headers = {
            "Authorization": f"Bearer {self.token.access_token}",
            "Content-Type": "application/vnd.api+json",
        }

        try:
            print(f"Fetching issue types from: {url}")
            print(f"Headers: Authorization: Bearer {self.token.access_token[:20]}...")

            response = requests.get(url, headers=headers, timeout=30)

            print(f"Issue types response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")

            if response.status_code == 200:
                response_data = response.json()
                print(f"Raw response data: {response_data}")

                # The API returns 'results' not 'data'
                issue_types = response_data.get("results", [])

                # If no results, also try 'data' for backward compatibility
                if not issue_types:
                    issue_types = response_data.get("data", [])

                print(f"✅ Successfully fetched {len(issue_types)} issue types")

                # Log each issue type for debugging
                for i, issue_type in enumerate(issue_types):
                    # The structure is different - no 'attributes', data is directly in the object
                    title = issue_type.get("title", "No title")
                    type_id = issue_type.get("id", "No ID")
                    is_active = issue_type.get("isActive", True)
                    print(
                        f"  Issue Type {i+1}: {title} (ID: {type_id}, Active: {is_active})"
                    )

                return issue_types
            elif response.status_code == 404:
                print(
                    f"Issues API not available for this project (404). This project may not have Issues enabled."
                )
                print(f"Response body: {response.text}")
                return []
            elif response.status_code == 401:
                print(
                    f"Authentication error (401). The Construction Issues API requires 3-legged authentication (user consent)."
                )
                print(f"Response body: {response.text}")
                return []
            elif response.status_code == 403:
                print(
                    f"Access denied (403). You may not have permission to access Issues for this project."
                )
                print(f"Response body: {response.text}")
                return []
            else:
                print(
                    f"Error fetching issue types: {response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            print(f"Exception occurred while fetching issue types: {str(e)}")
            import traceback

            traceback.print_exc()
            return []


class IssuesFetcherApp:
    """
    Main GUI application for fetching ACC/BIM 360 issues
    """

    def __init__(self, root):
        self.root = root
        self.root.title("ACC/BIM 360 Issues Fetcher")
        self.root.geometry("800x600")

        # Initialize API components
        self.auth = None
        self.bim360 = None
        self.issues_api = None

        # Data storage
        self.hubs = {}
        self.projects = {}
        self.issue_types = {}
        self.current_issues = []
        self.current_container_id = None
        self.has_issues_access = False

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Authentication section
        auth_frame = ttk.LabelFrame(main_frame, text="Authentication", padding="5")
        auth_frame.grid(
            row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10)
        )
        auth_frame.columnconfigure(1, weight=1)

        ttk.Label(auth_frame, text="Status:").grid(row=0, column=0, sticky=tk.W)
        self.auth_status = ttk.Label(
            auth_frame, text="Not authenticated", foreground="red"
        )
        self.auth_status.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))

        self.auth_btn = ttk.Button(
            auth_frame, text="Authenticate", command=self.authenticate
        )
        self.auth_btn.grid(row=0, column=2, padx=(10, 0))

        # Hub selection
        ttk.Label(main_frame, text="Hub:").grid(
            row=1, column=0, sticky=tk.W, pady=(5, 0)
        )
        self.hub_var = tk.StringVar()
        self.hub_combo = ttk.Combobox(
            main_frame, textvariable=self.hub_var, state="readonly"
        )
        self.hub_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(5, 0))
        self.hub_combo.bind("<<ComboboxSelected>>", self.on_hub_selected)

        # Project selection
        ttk.Label(main_frame, text="Project:").grid(
            row=2, column=0, sticky=tk.W, pady=(5, 0)
        )
        self.project_var = tk.StringVar()
        self.project_combo = ttk.Combobox(
            main_frame, textvariable=self.project_var, state="readonly"
        )
        self.project_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(5, 0))
        self.project_combo.bind("<<ComboboxSelected>>", self.on_project_selected)

        # Filters section
        filters_frame = ttk.LabelFrame(main_frame, text="Filters", padding="5")
        filters_frame.grid(
            row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0)
        )
        filters_frame.columnconfigure(1, weight=1)

        # Issue type filter
        ttk.Label(filters_frame, text="Issue Type:").grid(row=0, column=0, sticky=tk.W)
        self.issue_type_var = tk.StringVar()
        self.issue_type_combo = ttk.Combobox(
            filters_frame, textvariable=self.issue_type_var, state="readonly"
        )
        self.issue_type_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))

        # Status filter
        ttk.Label(filters_frame, text="Status:").grid(
            row=1, column=0, sticky=tk.W, pady=(5, 0)
        )
        self.status_var = tk.StringVar()
        self.status_combo = ttk.Combobox(
            filters_frame,
            textvariable=self.status_var,
            values=["", "open", "closed", "in_progress", "resolved"],
        )
        self.status_combo.grid(
            row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0)
        )

        # Fetch button
        self.fetch_btn = ttk.Button(
            main_frame, text="Fetch Issues", command=self.fetch_issues, state="disabled"
        )
        self.fetch_btn.grid(row=4, column=0, columnspan=2, pady=(10, 0))

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode="indeterminate")
        self.progress.grid(
            row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0)
        )

        # Results section
        results_frame = ttk.LabelFrame(main_frame, text="Issues", padding="5")
        results_frame.grid(
            row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0)
        )
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)

        # Treeview for issues
        columns = (
            "ID",
            "Title",
            "Type",
            "Status",
            "Priority",
            "Created",
            "Assigned To",
        )
        self.tree = ttk.Treeview(
            results_frame, columns=columns, show="headings", height=10
        )

        # Define headings
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(
            results_frame, orient="vertical", command=self.tree.yview
        )
        h_scrollbar = ttk.Scrollbar(
            results_frame, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set
        )

        # Grid layout for treeview and scrollbars
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Export buttons
        export_frame = ttk.Frame(main_frame)
        export_frame.grid(row=7, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(export_frame, text="Export to CSV", command=self.export_csv).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(
            export_frame, text="Export to Excel", command=self.export_excel
        ).pack(side=tk.LEFT)

        # Status bar
        self.status_bar = ttk.Label(
            main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_bar.grid(
            row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0)
        )

    def authenticate(self):
        """Authenticate with Autodesk APS using both 2-legged and 3-legged auth"""

        def auth_thread():
            try:
                self.root.after(0, lambda: self.update_status("Authenticating..."))
                self.root.after(0, lambda: self.progress.start())

                # Get credentials
                client_id = os.getenv("APS_CLIENT_ID")
                client_secret = os.getenv("APS_CLIENT_SECRET")

                if not client_id or not client_secret:
                    raise Exception(
                        "Missing APS_CLIENT_ID or APS_CLIENT_SECRET in environment"
                    )

                # First, get 2-legged token for Data Management API (hubs/projects)
                try:
                    self.auth = Auth()
                    token_2leg = self.auth.auth2leg()
                    print(
                        "✅ 2-legged token obtained successfully (for Data Management)"
                    )

                    # Initialize BIM360 with 2-legged token for basic data access
                    self.bim360 = BIM360(token_2leg)

                except Exception as e2leg:
                    print(f"❌ 2-legged auth failed: {str(e2leg)}")
                    raise Exception(f"2-legged authentication failed: {str(e2leg)}")

                # Then, attempt 3-legged authentication for Issues API
                try:
                    print("🔐 Attempting 3-legged authentication for Issues API...")
                    print("📖 This will open a browser window for user consent...")

                    # Use manual 3-legged authentication
                    auth_3leg = Manual3LeggedAuth(client_id, client_secret)
                    token_data_3leg = auth_3leg.authenticate()

                    if token_data_3leg:
                        print(
                            "✅ 3-legged token obtained successfully (for Issues API)"
                        )

                        # Create token object
                        token_3leg = SimpleToken(token_data_3leg)

                        # Initialize Issues API with 3-legged token
                        self.issues_api = IssuesAPI(token_3leg)
                        self.has_issues_access = True
                    else:
                        raise Exception("3-legged authentication failed")

                except Exception as e3leg:
                    print(f"⚠️  3-legged auth failed: {str(e3leg)}")
                    print(
                        "📋 Issues API will not be available, but hub/project browsing will work"
                    )

                    # Create a dummy Issues API that will return appropriate messages
                    self.issues_api = IssuesAPI(token_2leg)  # Will fail gracefully
                    self.has_issues_access = False

                # Update UI status in main thread
                if self.has_issues_access:
                    self.root.after(
                        0,
                        lambda: self.auth_status.config(
                            text="Authenticated (Full Access)", foreground="green"
                        ),
                    )
                    status_msg = "Authentication successful - Full access to hubs, projects, and issues"
                else:
                    self.root.after(
                        0,
                        lambda: self.auth_status.config(
                            text="Authenticated (Limited)", foreground="orange"
                        ),
                    )
                    status_msg = "Authentication successful - Hub/project access only (Issues requires user consent)"

                self.root.after(0, lambda: self.auth_btn.config(text="Re-authenticate"))

                # Load hubs using 2-legged token
                self.root.after(0, lambda: self.load_hubs())
                self.root.after(0, lambda: self.update_status(status_msg))

            except Exception as e:
                error_msg = str(e)

                # Provide specific guidance based on error type
                if "AUTH-001" in error_msg:
                    detailed_msg = (
                        "Authentication Error (AUTH-001):\n\n"
                        "Your APS application doesn't have access to the required APIs.\n\n"
                        "To fix this:\n"
                        "1. Go to https://aps.autodesk.com/myapps\n"
                        "2. Select your application\n"
                        "3. Enable these APIs:\n"
                        "   • Data Management API\n"
                        "   • Construction Cloud Issues API\n"
                        "4. Add these scopes:\n"
                        "   • data:read\n"
                        "   • data:write\n"
                        "   • account:read\n"
                        "   • code:all\n"
                        "5. Set callback URL to: http://localhost:8080/callback\n"
                        "6. Save and try again\n\n"
                        f"Technical details: {error_msg}"
                    )
                elif "client_id" in error_msg.lower():
                    detailed_msg = (
                        "Invalid Client ID/Secret:\n\n"
                        "Please check your credentials in the .env file:\n"
                        "• APS_CLIENT_ID\n"
                        "• APS_CLIENT_SECRET\n\n"
                        f"Error: {error_msg}"
                    )
                else:
                    detailed_msg = f"Authentication failed: {error_msg}"

                # Use print instead of messagebox to avoid KeyboardInterrupt
                print("=" * 60)
                print("AUTHENTICATION ERROR")
                print("=" * 60)
                print(detailed_msg)
                print("=" * 60)

                self.root.after(
                    0,
                    lambda: self.auth_status.config(
                        text="Authentication failed", foreground="red"
                    ),
                )
                self.root.after(
                    0,
                    lambda: self.update_status(
                        "Authentication failed - check console for details"
                    ),
                )
            finally:
                self.root.after(0, lambda: self.progress.stop())

        # Start authentication in separate thread to avoid blocking UI
        thread = threading.Thread(target=auth_thread, daemon=True)
        thread.start()

    def load_hubs(self):
        """Load available hubs"""
        try:
            self.update_status("Loading hubs...")
            hubs_data = self.bim360.get_hubs()

            print(f"Debug - Hubs data type: {type(hubs_data)}")
            print(f"Debug - Hubs data: {str(hubs_data)[:500]}...")

            self.hubs.clear()
            hub_names = []

            # More robust handling of different return formats
            hubs_list = []

            if isinstance(hubs_data, str):
                # Sometimes the API returns error messages as strings
                print(f"Error: API returned string instead of data: {hubs_data}")
                raise Exception(f"API error: {hubs_data}")
            elif isinstance(hubs_data, list):
                # Direct list of hubs
                hubs_list = hubs_data
            elif isinstance(hubs_data, dict):
                if "data" in hubs_data:
                    # Wrapped in data object
                    hubs_list = hubs_data["data"]
                elif "error" in hubs_data:
                    # Error response
                    error_msg = hubs_data.get("error", "Unknown error")
                    raise Exception(f"API error: {error_msg}")
                else:
                    # Try to use the dict directly if it looks like a single hub
                    if "id" in hubs_data and "attributes" in hubs_data:
                        hubs_list = [hubs_data]
                    else:
                        print(f"Warning: Unexpected hubs data format: {hubs_data}")
                        raise Exception("Unexpected data format from hubs API")
            else:
                print(f"Warning: Unexpected hubs data type: {type(hubs_data)}")
                raise Exception(
                    f"Unexpected data type from hubs API: {type(hubs_data)}"
                )

            # Process hubs list
            for i, hub in enumerate(hubs_list):
                try:
                    if not isinstance(hub, dict):
                        print(f"Warning: Hub {i} is not a dict: {type(hub)} - {hub}")
                        continue

                    hub_id = hub.get("id", "")
                    if not hub_id:
                        print(f"Warning: Hub {i} has no ID: {hub}")
                        continue

                    hub_attrs = hub.get("attributes", {})
                    if not isinstance(hub_attrs, dict):
                        print(
                            f"Warning: Hub {i} attributes are not a dict: {type(hub_attrs)} - {hub_attrs}"
                        )
                        hub_name = f"Hub {hub_id}"
                    else:
                        hub_name = hub_attrs.get("name", f"Hub {hub_id}")

                    self.hubs[hub_name] = hub_id
                    hub_names.append(hub_name)
                    print(f"Successfully loaded hub: {hub_name} (ID: {hub_id})")

                except Exception as hub_error:
                    print(f"Error processing hub {i}: {str(hub_error)}")
                    print(f"Hub data: {hub}")
                    continue

            self.hub_combo["values"] = hub_names
            if hub_names:
                self.hub_combo.current(0)
                self.on_hub_selected(None)

            self.update_status(f"Loaded {len(hub_names)} hubs")

        except Exception as e:
            print(f"Error loading hubs: {str(e)}")
            print(f"Full error details: {repr(e)}")
            import traceback

            traceback.print_exc()
            self.update_status("Failed to load hubs - check console for details")

    def on_hub_selected(self, event):
        """Handle hub selection"""
        if not self.hub_var.get():
            return

        try:
            self.update_status("Loading projects...")
            hub_id = self.hubs[self.hub_var.get()]
            projects_data = self.bim360.get_projects(hub_id)

            print(f"Debug - Projects data type: {type(projects_data)}")
            print(f"Debug - Projects data: {str(projects_data)[:500]}...")

            self.projects.clear()
            project_names = []

            # More robust handling of different return formats
            projects_list = []

            if isinstance(projects_data, str):
                # Sometimes the API returns error messages as strings
                print(f"Error: API returned string instead of data: {projects_data}")
                raise Exception(f"API error: {projects_data}")
            elif isinstance(projects_data, list):
                # Direct list of projects
                projects_list = projects_data
            elif isinstance(projects_data, dict):
                if "data" in projects_data:
                    # Wrapped in data object
                    projects_list = projects_data["data"]
                elif "error" in projects_data:
                    # Error response
                    error_msg = projects_data.get("error", "Unknown error")
                    raise Exception(f"API error: {error_msg}")
                else:
                    # Try to use the dict directly if it looks like a single project
                    if "id" in projects_data and "attributes" in projects_data:
                        projects_list = [projects_data]
                    else:
                        print(
                            f"Warning: Unexpected projects data format: {projects_data}"
                        )
                        raise Exception("Unexpected data format from projects API")
            else:
                print(f"Warning: Unexpected projects data type: {type(projects_data)}")
                raise Exception(
                    f"Unexpected data type from projects API: {type(projects_data)}"
                )

            # Process projects list
            for i, project in enumerate(projects_list):
                try:
                    if not isinstance(project, dict):
                        print(
                            f"Warning: Project {i} is not a dict: {type(project)} - {project}"
                        )
                        continue

                    project_id = project.get("id", "")
                    if not project_id:
                        print(f"Warning: Project {i} has no ID: {project}")
                        continue

                    project_attrs = project.get("attributes", {})
                    if not isinstance(project_attrs, dict):
                        print(
                            f"Warning: Project {i} attributes are not a dict: {type(project_attrs)} - {project_attrs}"
                        )
                        project_name = f"Project {project_id}"
                    else:
                        project_name = project_attrs.get(
                            "name", f"Project {project_id}"
                        )

                    self.projects[project_name] = project_id
                    project_names.append(project_name)
                    print(
                        f"Successfully loaded project: {project_name} (ID: {project_id})"
                    )

                except Exception as project_error:
                    print(f"Error processing project {i}: {str(project_error)}")
                    print(f"Project data: {project}")
                    continue

            self.project_combo["values"] = project_names
            if project_names:
                self.project_combo.current(0)
                self.on_project_selected(None)

            self.update_status(f"Loaded {len(project_names)} projects")

        except Exception as e:
            print(f"Error loading projects: {str(e)}")
            print(f"Full error details: {repr(e)}")
            import traceback

            traceback.print_exc()
            self.update_status("Failed to load projects - check console for details")

    def on_project_selected(self, event):
        """Handle project selection"""
        if not self.project_var.get():
            return

        try:
            project_id = self.projects[self.project_var.get()]
            hub_id = self.hubs[self.hub_var.get()]

            # Check if we have issues access
            if not self.has_issues_access:
                print(f"⚠️  Issues API access not available (requires 3-legged auth)")
                self.fetch_btn.config(state="normal")
                self.update_status(
                    "Project selected (Issues API requires user consent - click Fetch to see demo)"
                )
                return

            self.update_status("Loading issue types...")

            # Get the correct container ID for Issues API
            print(f"Looking for container ID for project: {project_id}")
            container_id = self.issues_api.get_project_container_id(hub_id, project_id)

            if not container_id:
                print(f"Could not find container ID for project {project_id}")
                # Still enable fetch button but with warning
                self.fetch_btn.config(state="normal")
                self.update_status("Project selected (Issues API may not be available)")
                return

            print(f"Using container ID: {container_id}")

            # Store the container ID for later use
            self.current_container_id = container_id

            issue_types_data = self.issues_api.get_issue_types(container_id)

            print(f"Debug - Issue types data type: {type(issue_types_data)}")
            print(f"Debug - Issue types data: {str(issue_types_data)[:500]}...")

            self.issue_types.clear()
            issue_type_names = [""]  # Empty option for no filter

            # More robust handling of issue types data
            if isinstance(issue_types_data, list):
                for i, issue_type in enumerate(issue_types_data):
                    try:
                        if not isinstance(issue_type, dict):
                            print(
                                f"Warning: Issue type {i} is not a dict: {type(issue_type)} - {issue_type}"
                            )
                            continue

                        type_id = issue_type.get("id", "")
                        if not type_id:
                            print(f"Warning: Issue type {i} has no ID: {issue_type}")
                            continue

                        # Handle both JSON:API format (with attributes) and direct format
                        if "attributes" in issue_type:
                            # JSON:API format
                            type_attrs = issue_type.get("attributes", {})
                            if not isinstance(type_attrs, dict):
                                print(
                                    f"Warning: Issue type {i} attributes are not a dict: {type(type_attrs)} - {type_attrs}"
                                )
                                type_name = f"Type {type_id}"
                            else:
                                type_name = type_attrs.get("title", f"Type {type_id}")
                        else:
                            # Direct format (used by current API)
                            type_name = issue_type.get("title", f"Type {type_id}")
                            # Only include active issue types
                            if not issue_type.get("isActive", True):
                                print(f"Skipping inactive issue type: {type_name}")
                                continue

                        self.issue_types[type_name] = type_id
                        issue_type_names.append(type_name)
                        print(
                            f"Successfully loaded issue type: {type_name} (ID: {type_id})"
                        )

                    except Exception as type_error:
                        print(f"Error processing issue type {i}: {str(type_error)}")
                        print(f"Issue type data: {issue_type}")
                        continue
            else:
                print(
                    f"Issue types data is not a list: {type(issue_types_data)} - {issue_types_data}"
                )

            self.issue_type_combo["values"] = issue_type_names
            self.issue_type_combo.current(0)

            # Enable fetch button
            self.fetch_btn.config(state="normal")

            if len(issue_type_names) > 1:
                self.update_status(f"Loaded {len(issue_type_names)-1} issue types")
            else:
                self.update_status("Project selected (no issue types available)")

        except Exception as e:
            print(f"Warning: Failed to load issue types: {str(e)}")
            print(f"Full error details: {repr(e)}")
            import traceback

            traceback.print_exc()
            # Still enable fetch button even if issue types fail
            self.fetch_btn.config(state="normal")
            self.update_status("Project selected (issue types unavailable)")

    def fetch_issues(self):
        """Fetch issues from the selected project"""
        if not self.project_var.get():
            messagebox.showwarning("Warning", "Please select a project first")
            return

        # Check if we have Issues API access
        if not self.has_issues_access:
            messagebox.showinfo(
                "Issues API Access Required",
                "To access the Issues API, you need to:\n\n"
                "1. Re-authenticate and provide user consent when prompted\n"
                "2. The browser will open for authorization\n"
                "3. Grant permission to access your ACC/BIM 360 data\n\n"
                "Click 'Re-authenticate' to try 3-legged authentication.",
            )
            return

        def fetch_thread():
            try:
                self.progress.start()
                self.update_status("Fetching issues...")

                project_id = self.projects[self.project_var.get()]

                # Use the stored container ID if available
                container_id = getattr(self, "current_container_id", None)

                if not container_id:
                    # Try to get container ID again
                    hub_id = self.hubs[self.hub_var.get()]
                    container_id = self.issues_api.get_project_container_id(
                        hub_id, project_id
                    )

                if not container_id:
                    error_msg = "Cannot fetch issues: No valid container ID found for this project. This project may not have Issues API enabled."
                    print(error_msg)
                    self.root.after(
                        0, lambda: messagebox.showwarning("Warning", error_msg)
                    )
                    self.root.after(
                        0,
                        lambda: self.update_status(
                            "Issues not available for this project"
                        ),
                    )
                    return

                # Get filter values
                issue_type_id = None
                if (
                    self.issue_type_var.get()
                    and self.issue_type_var.get() in self.issue_types
                ):
                    issue_type_id = self.issue_types[self.issue_type_var.get()]

                status = self.status_var.get() if self.status_var.get() else None

                print(f"Fetching issues with:")
                print(f"  Project ID: {project_id}")
                print(f"  Container ID: {container_id}")
                print(f"  Issue Type ID: {issue_type_id}")
                print(f"  Status: {status}")

                # Fetch issues (API limit is 200 max per request)
                issues = self.issues_api.get_issues(
                    project_id=project_id,
                    container_id=container_id,
                    issue_type=issue_type_id,
                    status=status,
                    limit=200,
                )

                # Update UI in main thread
                self.root.after(0, lambda: self.display_issues(issues))

            except Exception as e:
                error_msg = f"Failed to fetch issues: {str(e)}"
                print(f"Exception in fetch_issues: {error_msg}")
                import traceback

                traceback.print_exc()

                self.root.after(
                    0,
                    lambda: messagebox.showerror("Error", error_msg),
                )
                self.root.after(0, lambda: self.update_status("Failed to fetch issues"))
            finally:
                self.root.after(0, lambda: self.progress.stop())

        # Start fetch in separate thread
        thread = threading.Thread(target=fetch_thread, daemon=True)
        thread.start()

    def display_issues(self, issues):
        """Display issues in the treeview"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.current_issues = issues

        if not issues:
            # Add a message when no issues are found
            self.tree.insert(
                "",
                "end",
                values=(
                    "",
                    "No issues found",
                    "This project may not have Issues API enabled",
                    "",
                    "",
                    "",
                    "",
                ),
            )
            self.update_status(
                "No issues found - Issues API may not be available for this project"
            )
            return

        # Add issues to treeview
        for issue in issues:
            # Handle both JSON:API format (with attributes) and direct format
            if "attributes" in issue:
                # JSON:API format
                attributes = issue.get("attributes", {})
                issue_id = issue.get("id", "")
                title = attributes.get("title", "")
                issue_type = attributes.get("issueType", {}).get("title", "")
                status = attributes.get("status", "")
                priority = attributes.get("priority", "")
                created = attributes.get("createdAt", "")
                assigned_to = (
                    attributes.get("assignedTo", {}).get("name", "")
                    if attributes.get("assignedTo")
                    else ""
                )
            else:
                # Direct format (if the issues API uses the same structure as issue types)
                issue_id = issue.get("id", "")
                title = issue.get("title", "")
                issue_type = (
                    issue.get("issueType", {}).get("title", "")
                    if isinstance(issue.get("issueType"), dict)
                    else str(issue.get("issueType", ""))
                )
                status = issue.get("status", "")
                priority = issue.get("priority", "")
                created = issue.get("createdAt", "")
                assigned_to = (
                    issue.get("assignedTo", {}).get("name", "")
                    if isinstance(issue.get("assignedTo"), dict)
                    else str(issue.get("assignedTo", ""))
                )

            # Format created date
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = created_dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass  # Keep original format if parsing fails

            self.tree.insert(
                "",
                "end",
                values=(
                    issue_id,
                    title,
                    issue_type,
                    status,
                    priority,
                    created,
                    assigned_to,
                ),
            )

        self.update_status(f"Fetched {len(issues)} issues")

    def export_csv(self):
        """Export issues to CSV"""
        if not self.current_issues:
            messagebox.showwarning("Warning", "No issues to export")
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )

            if filename:
                df = self.issues_to_dataframe()
                df.to_csv(filename, index=False)
                messagebox.showinfo("Success", f"Issues exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")

    def export_excel(self):
        """Export issues to Excel"""
        if not self.current_issues:
            messagebox.showwarning("Warning", "No issues to export")
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            )

            if filename:
                df = self.issues_to_dataframe()
                df.to_excel(filename, index=False)
                messagebox.showinfo("Success", f"Issues exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export Excel: {str(e)}")

    def issues_to_dataframe(self):
        """Convert issues to pandas DataFrame"""
        data = []

        for issue in self.current_issues:
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

    def update_status(self, message):
        """Update status bar"""
        self.status_bar.config(text=message)
        self.root.update_idletasks()


def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = IssuesFetcherApp(root)

    # Center the window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()
