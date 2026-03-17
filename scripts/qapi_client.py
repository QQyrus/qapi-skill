#!/usr/bin/env python3
"""
QAPI CLI client for creating and saving API tests.

Usage:
  python scripts/qapi_client.py new-suite-id
  python scripts/qapi_client.py get-teams
  python scripts/qapi_client.py get-workspaces --team-id <UUID>
  python scripts/qapi_client.py create-placeholder --team-id <UUID> --workspace-id <UUID> --name <str> [--suite-id <UUID>]
  python scripts/qapi_client.py save-test --team-id <UUID> --workspace-id <UUID> --test-json <JSON-string> [--suite-id <UUID>]

Required environment variables:
  QAPI_API_TOKEN       - Personal API token (X-API-Key header)
  QAPI_GATEWAY_TOKEN   - Static gateway bearer token (Authorization header)
  QAPI_USER_EMAIL      - User email address (Login header)
  QAPI_APP_URL         - App URL (default: qapi.qyrus.com)

Fixed headers added automatically:
  scope                - AI_SDK
"""

import argparse
import json
import os
import sys
import uuid
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print(json.dumps({"error": "Missing dependency: pip install requests"}), file=sys.stderr)
    sys.exit(1)


# --- Environment resolution ---

APP_URL_MAP = {
    "qapi.qyrus.com": {
        "gateway": "api-pc-gateway.qyrus.com",
        "prefix": "/api-marketplace/",
        "team_path": "/usermgmt/v2/api/team-list",
    },
    "stg-api.qyrus.com": {
        "gateway": "stg-gateway.qyrus.com:8243",
        "prefix": "/api-marketplace-qapi/",
        "team_path": "/user-mgmt-qapi/v1/api/team-list",
    },
}


def get_env_config():
    """Read and validate env vars, return config dict."""
    api_token = os.environ.get("QAPI_API_TOKEN")
    gateway_token = os.environ.get("QAPI_GATEWAY_TOKEN")
    user_email = os.environ.get("QAPI_USER_EMAIL")
    app_url = os.environ.get("QAPI_APP_URL", "qapi.qyrus.com").rstrip("/")

    missing = []
    if not api_token:
        missing.append("QAPI_API_TOKEN")
    if not gateway_token:
        missing.append("QAPI_GATEWAY_TOKEN")
    if not user_email:
        missing.append("QAPI_USER_EMAIL")

    if missing:
        print(
            json.dumps({"error": f"Missing required environment variables: {', '.join(missing)}"}),
            file=sys.stderr,
        )
        sys.exit(1)

    app_url_key = normalize_app_url(app_url)
    route_cfg = APP_URL_MAP.get(app_url_key)
    if route_cfg is None:
        supported = ", ".join(sorted(APP_URL_MAP))
        print(
            json.dumps(
                {
                    "error": (
                        f"Unsupported QAPI_APP_URL '{app_url_key}'. "
                        f"Supported values: {supported}"
                    )
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    gateway_base = f"https://{route_cfg['gateway']}"

    return {
        "api_token": api_token,
        "gateway_token": gateway_token,
        "user_email": user_email,
        "app_url": app_url_key,
        "gateway_base": gateway_base,
        "prefix": route_cfg["prefix"],
        "team_path": route_cfg["team_path"],
    }


def normalize_app_url(app_url):
    """Normalize QAPI_APP_URL to a hostname without scheme or path."""
    parsed = urlparse(app_url if "://" in app_url else f"https://{app_url}")
    host = parsed.netloc or parsed.path
    return host.rstrip("/").lower()


def build_headers(cfg, team_id=None):
    """Build common request headers."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['gateway_token']}",
        "X-API-Key": cfg["api_token"],
        "Login": cfg["user_email"],
        "scope": "AI_SDK",
    }
    if team_id:
        headers["Team-Id"] = team_id
    return headers


def generate_suite_id():
    """Generate a suite UUID that can be reused across create/save calls."""
    return str(uuid.uuid4())


def build_scripts_url(cfg, workspace_id, suite_id):
    """Build the shared scripts endpoint for create/save flows."""
    return (
        f"{cfg['gateway_base']}{cfg['prefix']}v1/api/scripts"
        f"?suiteId={suite_id}&projectId={workspace_id}&isChaining=false"
    )


def handle_response(resp, context=""):
    """Check HTTP status, print error and exit on failure."""
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        msg = {"error": str(e), "status_code": resp.status_code}
        try:
            msg["detail"] = resp.json()
        except Exception:
            msg["detail"] = resp.text
        print(json.dumps(msg), file=sys.stderr)
        sys.exit(1)


# --- Subcommand implementations ---

def cmd_get_teams(cfg):
    """GET team list and print JSON array."""
    url = f"{cfg['gateway_base']}{cfg['team_path']}"
    headers = build_headers(cfg)
    resp = requests.get(url, headers=headers, timeout=30)
    handle_response(resp, "get-teams")
    data = resp.json()
    # Normalize: the API returns either a list directly or {content: [...]}
    if isinstance(data, list):
        teams = data
    elif isinstance(data, dict) and "content" in data:
        teams = data["content"]
    else:
        teams = [data]
    print(json.dumps(teams))


def cmd_get_workspaces(cfg, team_id):
    """POST project-details and print JSON array of workspaces."""
    url = f"{cfg['gateway_base']}{cfg['prefix']}v1/api/project-details"
    headers = build_headers(cfg, team_id)
    payload = {
        "userEmail": cfg["user_email"],
        "page": 0,
        "size": 100,
        "type": None,
        "projectName": None,
        "collaborators": None,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    handle_response(resp, "get-workspaces")
    data = resp.json()
    if isinstance(data, list):
        workspaces = data
    elif isinstance(data, dict) and "content" in data:
        workspaces = data["content"]
    else:
        workspaces = [data]
    print(json.dumps(workspaces))


def cmd_new_suite_id():
    """Print a reusable suite UUID."""
    print(json.dumps({"suiteId": generate_suite_id()}))


def cmd_create_placeholder(cfg, team_id, workspace_id, name, suite_id=None):
    """Create a placeholder test and return server-assigned id + sequenceId."""
    suite_id = suite_id or generate_suite_id()
    url = build_scripts_url(cfg, workspace_id, suite_id)
    headers = build_headers(cfg, team_id)
    payload = [
        {
            "name": name,
            "method": "GET",
            "protocol": "https",
            "host": "",
            "port": "",
            "contextPath": "",
            "url": "",
            "schemaValidations": [],
            "urlEncodeEnabled": True,
            "timeout": 300,
            "requestBody": None,
            "headers": [],
            "params": [],
            "formData": [],
            "assertBodies": None,
            "assertHeaders": [],
            "assertJsonPaths": [],
            "assertXpaths": [],
            "authorizations": [],
            "certUuid": None,
            "variableName": None,
            "isBodyParameterized": False,
            "isChaining": False,
            "chainingConfigration": None,
            "isParameterized": False,
            "sequenceId": None,
            "databaseAssertions": [],
            "databaseInfo": None,
            "parameterizedType": None,
            "assertOnResponseBody": False,
            "apiType": "REST",
            "isDatabaseAssertion": False,
            "databaseStatement": "",
            "scriptType": "PLAYGROUND",
            "dataHandlers": [],
            "isActive": True,
        }
    ]
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    handle_response(resp, "create-placeholder")
    result = resp.json()
    # API returns a list; extract first item
    if isinstance(result, list) and len(result) > 0:
        item = result[0]
    else:
        item = result
    print(
        json.dumps(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "sequenceId": item.get("sequenceId"),
                "suiteId": suite_id,
            }
        )
    )


def cmd_save_test(cfg, team_id, workspace_id, test_json_str, suite_id=None):
    """Save a full test object (must have server-assigned id). Prints server response."""
    try:
        test_obj = json.loads(test_json_str)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON in --test-json: {e}"}), file=sys.stderr)
        sys.exit(1)

    # test_obj may be a dict (single test) or a list; normalize to list
    if isinstance(test_obj, dict):
        test_list = [test_obj]
    elif isinstance(test_obj, list):
        test_list = test_obj
    else:
        print(
            json.dumps({"error": "--test-json must decode to a JSON object or array"}),
            file=sys.stderr,
        )
        sys.exit(1)

    suite_id = suite_id or generate_suite_id()
    url = build_scripts_url(cfg, workspace_id, suite_id)
    headers = build_headers(cfg, team_id)
    resp = requests.post(url, headers=headers, json=test_list, timeout=30)
    handle_response(resp, "save-test")
    print(json.dumps(resp.json()))


# --- Main / argparse ---

def main():
    parser = argparse.ArgumentParser(
        description="QAPI CLI client — reads QAPI_* env vars, prints JSON to stdout."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # new-suite-id
    subparsers.add_parser("new-suite-id", help="Generate a suite UUID to reuse across create/save")

    # get-teams
    subparsers.add_parser("get-teams", help="List teams for the authenticated user")

    # get-workspaces
    ws_parser = subparsers.add_parser("get-workspaces", help="List workspaces for a team")
    ws_parser.add_argument("--team-id", required=True, help="Team UUID")

    # create-placeholder
    cp_parser = subparsers.add_parser(
        "create-placeholder", help="Create a blank test placeholder and return server ID"
    )
    cp_parser.add_argument("--team-id", required=True, help="Team UUID")
    cp_parser.add_argument("--workspace-id", required=True, help="Workspace/project UUID")
    cp_parser.add_argument("--name", required=True, help="Test name")
    cp_parser.add_argument(
        "--suite-id",
        help="Suite UUID to reuse across placeholder and save requests",
    )

    # save-test
    st_parser = subparsers.add_parser("save-test", help="Save a full test object to QAPI")
    st_parser.add_argument("--team-id", required=True, help="Team UUID")
    st_parser.add_argument("--workspace-id", required=True, help="Workspace/project UUID")
    st_parser.add_argument(
        "--test-json",
        required=True,
        help="Full test object as a JSON string (single object or array)",
    )
    st_parser.add_argument(
        "--suite-id",
        help="Suite UUID to reuse across placeholder and save requests",
    )

    args = parser.parse_args()
    if args.command == "new-suite-id":
        cmd_new_suite_id()
        return

    cfg = get_env_config()

    if args.command == "get-teams":
        cmd_get_teams(cfg)
    elif args.command == "get-workspaces":
        cmd_get_workspaces(cfg, args.team_id)
    elif args.command == "create-placeholder":
        cmd_create_placeholder(
            cfg,
            args.team_id,
            args.workspace_id,
            args.name,
            suite_id=args.suite_id,
        )
    elif args.command == "save-test":
        cmd_save_test(
            cfg,
            args.team_id,
            args.workspace_id,
            args.test_json,
            suite_id=args.suite_id,
        )


if __name__ == "__main__":
    main()
