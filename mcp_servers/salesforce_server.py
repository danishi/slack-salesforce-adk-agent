"""Salesforce MCP Server — exposes Salesforce REST API operations as MCP tools."""

import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

SF_CLIENT_ID = os.environ.get("SF_CLIENT_ID", "")
SF_CLIENT_SECRET = os.environ.get("SF_CLIENT_SECRET", "")
SF_LOGIN_URL = os.environ.get("SF_LOGIN_URL", "https://login.salesforce.com")
SF_API_VERSION = os.environ.get("SF_API_VERSION", "v66.0")

mcp = FastMCP("salesforce")

# Cached auth token
_auth_cache: dict[str, str] = {}


async def _get_auth() -> tuple[str, str]:
    """Authenticate via client_credentials and return (access_token, instance_url)."""
    if "access_token" in _auth_cache and "instance_url" in _auth_cache:
        return _auth_cache["access_token"], _auth_cache["instance_url"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{SF_LOGIN_URL}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": SF_CLIENT_ID,
                "client_secret": SF_CLIENT_SECRET,
            },
        )
        if resp.status_code != 200:
            detail = resp.text
            raise RuntimeError(
                f"Salesforce auth failed ({resp.status_code}): {detail}"
            )
        data = resp.json()

    token = data["access_token"]
    instance_url = data["instance_url"]
    _auth_cache["access_token"] = token
    _auth_cache["instance_url"] = instance_url
    return token, instance_url


async def _sf_request(method: str, path: str, **kwargs) -> dict:
    """Make an authenticated request to Salesforce REST API."""
    token, instance_url = await _get_auth()
    url = f"{instance_url}/services/data/{SF_API_VERSION}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, url, headers=headers, **kwargs)
        # Handle token expiration
        if resp.status_code == 401:
            _auth_cache.clear()
            token, instance_url = await _get_auth()
            url = f"{instance_url}/services/data/{SF_API_VERSION}{path}"
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 204:
            return {"success": True}
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def salesforce_query(soql: str) -> str:
    """Execute a SOQL query against Salesforce and return the results as JSON.

    Args:
        soql: The SOQL query string to execute. Example: "SELECT Id, Name FROM Account LIMIT 10"
    """
    import json
    import urllib.parse

    encoded = urllib.parse.quote(soql)
    result = await _sf_request("GET", f"/query?q={encoded}")
    records = result.get("records", [])
    # Remove attributes metadata for cleaner output
    for r in records:
        r.pop("attributes", None)
    return json.dumps(
        {"totalSize": result.get("totalSize", 0), "records": records},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def salesforce_describe(sobject: str) -> str:
    """Get metadata (fields, picklist values, relationships) for a Salesforce object.

    Args:
        sobject: The Salesforce object API name. Example: "Account", "Opportunity", "Contact"
    """
    import json

    result = await _sf_request("GET", f"/sobjects/{sobject}/describe")
    fields = []
    for f in result.get("fields", []):
        field_info = {
            "name": f["name"],
            "label": f["label"],
            "type": f["type"],
            "required": not f.get("nillable", True) and not f.get("defaultedOnCreate", False),
        }
        if f.get("picklistValues"):
            field_info["picklistValues"] = [
                pv["value"] for pv in f["picklistValues"] if pv.get("active")
            ]
        if f.get("referenceTo"):
            field_info["referenceTo"] = f["referenceTo"]
        fields.append(field_info)
    return json.dumps({"objectName": sobject, "fields": fields}, ensure_ascii=False, indent=2)


@mcp.tool()
async def salesforce_create_record(sobject: str, field_values: dict) -> str:
    """Create a new record in Salesforce.

    Args:
        sobject: The Salesforce object API name. Example: "Account", "Contact", "Opportunity"
        field_values: Dictionary of field API names to values. Example: {"Name": "Test Account", "Industry": "Technology"}
    """
    import json

    result = await _sf_request("POST", f"/sobjects/{sobject}", json=field_values)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def salesforce_update_record(sobject: str, record_id: str, field_values: dict) -> str:
    """Update an existing Salesforce record.

    Args:
        sobject: The Salesforce object API name. Example: "Account", "Opportunity"
        record_id: The 15 or 18-character Salesforce record ID.
        field_values: Dictionary of field API names to new values. Example: {"StageName": "Closed Won"}
    """
    import json

    result = await _sf_request("PATCH", f"/sobjects/{sobject}/{record_id}", json=field_values)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def salesforce_delete_record(sobject: str, record_id: str) -> str:
    """Delete a Salesforce record by its ID.

    Args:
        sobject: The Salesforce object API name. Example: "Account"
        record_id: The 15 or 18-character Salesforce record ID to delete.
    """
    import json

    result = await _sf_request("DELETE", f"/sobjects/{sobject}/{record_id}")
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
