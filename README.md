# Emoji Moderator

A Slack bot deployed on AWS Lambda that monitors emoji additions in a Slack workspace and gives moderators the ability to review and remove newly uploaded emojis.

---

## Overview

When a user uploads a new emoji to the workspace, the bot:
1. Detects the `emoji_changed` (add) event via Slack's Event API.
2. Looks up the uploader's identity using the Slack Audit Logs API.
3. Posts a notification to a designated moderation channel with a **Remove** button.

A moderator can click **Remove** to open a modal, optionally enter a justification, and submit. The bot then:
- Deletes the emoji from the workspace via `admin_emoji_remove`.
- Updates the moderation channel message with a removal record.
- DMs the original uploader to notify them, including the justification if one was provided.

---

## Architecture

```
Slack Workspace
    │  emoji_changed event (add/remove)
    ▼
AWS Lambda (slack_bolt SlackRequestHandler)
    ├── main.py          — Event handlers, app logic
    ├── aws_secrets.py   — Secrets retrieval from AWS Secrets Manager
    └── ui_templates.py  — Slack Block Kit UI templates
```

The app uses `slack_bolt` with `process_before_response=True` and lazy listeners to satisfy Slack's 3-second acknowledgment requirement within AWS Lambda.

---

## File Reference

### `aws_secrets.py`

Retrieves Slack credentials from **AWS Secrets Manager** in the `us-west-1` region. Secret names are read from environment variables.

| Function | Returns | Env var for secret name |
|---|---|---|
| `get_bot_token()` | Slack bot token (`xoxb-...`) | `bot_token_secret_name` |
| `get_signing_secret()` | Slack signing secret | `signing_secret_name` |
| `get_user_token()` | Slack user token (`xoxp-...`) | `user_token_secret_name` |

All three functions raise a `botocore.exceptions.ClientError` on failure.

---

### `main.py`

Main application module. Initializes the `slack_bolt` app and registers all event/action/view handlers.

#### Helpers

| Function | Description |
|---|---|
| `get_todays_date()` | Returns the current datetime string formatted as `YYYY-MM-DD HH:MM:SS AM/PM PDT` in Pacific Time. |
| `get_actor_id(event_timestamp)` | Queries the Slack Audit Logs API (`/audit/v1/logs`) for the most recent `emoji_added` events and returns the Slack user ID matching the given Unix timestamp. Requires a user token with `auditlogs:read` scope. |
| `respond_to_slack_within_3_seconds(ack)` | Shared acknowledgment function used across all handlers to immediately satisfy Slack's 3-second response window. |

#### Event & Action Handlers

| Handler | Trigger | Behavior |
|---|---|---|
| `handle_emoji_changed_events` | `emoji_changed` / `add` | Resolves the uploader via `get_actor_id`, then posts a Block Kit message to `MOD_CHANNEL` with a Remove button. |
| `handle_remove_button` | `remove_emoji` action | Opens the `revoke_message_modal` modal in Slack, passing emoji name, uploader ID, and message metadata as `private_metadata`. |
| `handle_emoji_removal` | `emoji_changed` / `remove` | Acknowledges the event and takes no further action (prevents unhandled event warnings). |
| `handle_view_submission_events` | `revoke_message_modal` view submission | Removes the emoji, updates the mod channel message with a removal record & justification, and DMs the uploader. |

#### AWS Lambda Entrypoint

```python
def handler(event, context):
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)
```

---

### `ui_templates.py`

Builds Slack Block Kit payloads for the bot's UI elements.

#### `update_blocks_message(emoji, user_id, ts) → str`

Returns a JSON string for the moderation channel message containing:
- A section block: `:<emoji>: was uploaded by <@user_id> on <date>`.
- An actions block with a red **Remove** button (`action_id: remove_emoji`, value set to the emoji name).

`ts` (Unix timestamp) is converted to a Pacific Time string via `convert_epoch_timestamp`.

#### `revoke_message_modal(private_metadata: dict) → str`

Returns a JSON string for the emoji removal modal (`callback_id: revoke_message_modal`). The modal contains an optional multiline text input for a moderator justification. `private_metadata` (emoji name, uploader ID, message ts, current message text) is JSON-serialized into the modal's `private_metadata` field.

#### `convert_epoch_timestamp(timestamp) → str`

Converts a Unix timestamp to a `YYYY-MM-DD HH:MM:SS AM/PM PDT` string in Pacific Time.

---

## Required Slack Scopes

| Token | Scope | Purpose |
|---|---|---|
| Bot (`xoxb`) | `chat:write` | Post and update messages in the mod channel |
| Bot (`xoxb`) | `emoji:read` | Receive `emoji_changed` events |
| User (`xoxp`) | `auditlogs:read` | Look up who uploaded an emoji |
| User (`xoxp`) | `admin.teams:write` | Remove emojis via `admin_emoji_remove` |

---

## Environment Variables

| Variable | Description |
|---|---|
| `bot_token_secret_name` | AWS Secrets Manager secret name for the Slack bot token |
| `signing_secret_name` | AWS Secrets Manager secret name for the Slack signing secret |
| `user_token_secret_name` | AWS Secrets Manager secret name for the Slack user token |
| `MOD_CHANNEL` | Slack channel ID where moderation notifications are posted |

---

## Setup

### Prerequisites
- Python 3.11+
- AWS account with Secrets Manager secrets configured for Slack credentials
- Slack app installed to an Enterprise Grid workspace with the scopes listed above

### Install dependencies

```bash
pip install -r requirements.txt
```

### Local development

Create a `.env` file:

```env
bot_token_secret_name=<secret-name>
signing_secret_name=<secret-name>
user_token_secret_name=<secret-name>
MOD_CHANNEL=<channel-id>
```

### Deployment

Infrastructure is defined in `terraform/lambda_infra.tf`. Package the Python source and deploy to AWS Lambda, setting the handler to `main.handler`.
