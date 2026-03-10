# Salesforce Agent — Slack Bot (ADK + MCP, Cloud Run)

A Slack Bot that lets you interact with Salesforce data using natural language. Built with [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) and [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), powered by [Vertex AI Gemini](https://cloud.google.com/vertex-ai), and deployed on [Cloud Run](https://cloud.google.com/run).

Based on [slack-bot-adk-python-cloudrun](https://github.com/danishi/slack-bot-adk-python-cloudrun).

## Features

- `@mention` the bot in a Slack channel to perform Salesforce operations
- CRUD operations on standard objects: Account, Contact, Opportunity, Lead, Case
- SOQL query-based data search and retrieval
- Maintains conversation context within Slack threads
- Multimodal input support: text, images, PDFs, video, and audio
- Access control to restrict bot usage to specific Slack members
- Rich text output with Slack-compatible Markdown

## Architecture

```
Slack → FastAPI (/slack/events) → ADK Root Agent
                                    ├── McpToolset (stdio) → Salesforce MCP Server
                                    │       ├── salesforce_query (SOQL execution)
                                    │       ├── salesforce_describe (object metadata)
                                    │       ├── salesforce_create_record (create)
                                    │       ├── salesforce_update_record (update)
                                    │       └── salesforce_delete_record (delete)
                                    ├── get_current_datetime (datetime utility)
                                    ├── web_search_agent (Google Search)
                                    ├── url_fetch_agent (URL content retrieval)
                                    └── salesforce_agent (Salesforce sub-agent)
```

## Project Structure

```
app/
  main.py                    # FastAPI app, Slack Bolt handlers, root agent, access control
  __init__.py                # root_agent export (entry point for `adk web`)
  agents/
    salesforce_agent.py      # Salesforce CRUD sub-agent
    web_search_agent.py      # Web search and URL fetch agents
  tools/
    get_current_datetime.py  # Datetime utility tool
mcp_servers/
  salesforce_server.py       # FastMCP server wrapping Salesforce REST API
scripts/
  deploy.sh                  # Cloud Run deployment script
Dockerfile                   # Container definition
requirements.txt             # Python dependencies
```

## Prerequisites

- Python 3.13
- [Google Cloud SDK](https://cloud.google.com/sdk) (`gcloud` authenticated)
- A Slack workspace where you can install apps
- Salesforce Connected App (client_credentials grant)

## Local Development

1. Install dependencies
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure environment variables
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set the following:
   - `SLACK_BOT_TOKEN` / `SLACK_SIGNING_SECRET` — Slack Bot credentials
   - `SF_CLIENT_ID` / `SF_CLIENT_SECRET` — Salesforce Connected App credentials
   - `SF_LOGIN_URL` — Your Salesforce instance URL (default: `https://login.salesforce.com`)
   - `ALLOWED_SLACK_USERS` — Comma-separated Slack user IDs to allow (empty = allow all)

3. Start the server
   ```bash
   uvicorn app.main:fastapi_app --host 0.0.0.0 --port 8080 --reload
   ```

4. Use a tunneling tool like `ngrok` to expose `http://localhost:8080/slack/events` to Slack during development.

### ADK Web Development UI

You can test and debug agents using the ADK Web UI.

```bash
gcloud auth application-default login
adk web
```

Open `http://127.0.0.1:8000` in your browser to interact with the agents.

## Slack App Setup

1. Create a new Slack app at <https://api.slack.com/apps>.
2. Under **OAuth & Permissions**, add these Bot Token Scopes:
   - `app_mentions:read`
   - `chat:write`
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
   - `files:read`
   - `reactions:write`
   - `users:read`
3. Install the app to your workspace and obtain the `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`.
4. Enable **Event Subscriptions** and set the Request URL to `https://<your-cloud-run-url>/slack/events`.
5. Subscribe to the following bot events:
   - `app_mention` — Respond to @mentions in channels
   - `message.im` — Respond to direct messages
6. Invite the bot to the channels where you want to use it.

## Getting Slack User IDs

To configure `ALLOWED_SLACK_USERS`, you need Slack user IDs:

### Option 1: From the Slack App

1. Open the target user's profile (click their name)
2. Click the **⋮** (more actions) menu
3. Select **"Copy member ID"**

### Option 2: Via Slack API

```bash
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  "https://slack.com/api/users.list" | jq '.members[] | {id, name, real_name: .profile.real_name}'
```

User IDs start with `U` followed by alphanumeric characters (e.g., `U01AB2CD3EF`). Separate multiple IDs with commas:

```
ALLOWED_SLACK_USERS=U01AB2CD3EF,U04XY5ZW6GH
```

## Salesforce Connected App Setup

1. In Salesforce, go to **Setup** → **App Manager** → **New Connected App**
2. Enable **OAuth Settings** and configure:
   - Callback URL: `https://login.salesforce.com/services/oauth2/callback`
   - OAuth Scopes: `Manage user data via APIs (api)`, `Perform requests at any time (refresh_token, offline_access)`
3. Enable **Client Credentials Flow** and assign a run-as user
4. Set `SF_CLIENT_ID` (Consumer Key) and `SF_CLIENT_SECRET` (Consumer Secret) in your `.env` file

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | Yes | Slack Bot User OAuth token |
| `SLACK_SIGNING_SECRET` | Yes | Slack app signing secret |
| `SF_CLIENT_ID` | Yes | Salesforce Connected App consumer key |
| `SF_CLIENT_SECRET` | Yes | Salesforce Connected App consumer secret |
| `SF_LOGIN_URL` | No | Salesforce login URL (default: `https://login.salesforce.com`) |
| `SF_API_VERSION` | No | Salesforce API version (default: `v66.0`) |
| `MODEL_NAME` | No | Gemini model name (default: `gemini-3.1-flash-lite-preview`) |
| `ALLOWED_SLACK_WORKSPACE` | No | Slack Team ID to restrict requests to |
| `ALLOWED_SLACK_USERS` | No | Comma-separated Slack user IDs allowed to use the bot |
| `GOOGLE_GENAI_USE_VERTEXAI` | No | Set to `TRUE` to use Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | No | Google Cloud project ID |
| `APP_NAME` | No | ADK application name (default: `salesforce-agent`) |
| `REACTION_PROCESSING` | No | Slack emoji for processing indicator (default: `eyes`) |
| `REACTION_COMPLETED` | No | Slack emoji for completion indicator (default: `white_check_mark`) |

## Deploy to Cloud Run

Ensure the required environment variables are set in `.env` before deploying.

### First-Time Setup (one-time only)

```bash
gcloud services enable cloudbuild.googleapis.com
```

### Deploy

```bash
./scripts/deploy.sh
```

The script will:
1. Build the container image using Cloud Build
2. Deploy to Cloud Run with all environment variables
3. Display the service URL

After deployment, set the Cloud Run service URL (`https://<service-url>/slack/events`) as the Event Subscriptions Request URL in your Slack app configuration.
