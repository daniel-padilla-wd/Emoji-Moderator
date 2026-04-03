import os
import json
import requests
import datetime
from zoneinfo import ZoneInfo
import re
import aws_secrets
import ui_templates


from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_sdk.errors import SlackApiError


import logging
logging.basicConfig(level=logging.DEBUG)

from dotenv import load_dotenv
load_dotenv()

SLACK_SIGNING_SECRET = aws_secrets.get_signing_secret()
SLACK_BOT_TOKEN = aws_secrets.get_bot_token()
SLACK_USER_TOKEN = aws_secrets.get_user_token()
MOD_CHANNEL = os.getenv("MOD_CHANNEL")

# https://api.slack.com/authentication/verifying-requests-from-slack
# Initializes your app with your bot token and signing secret
app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
    process_before_response=True
)

# Helper functions
def get_todays_date() -> str:
    """Returns today's date in the format %Y-%m-%d %I:%M:%S %p %Z."""
    # Get the current datetime object
    now = datetime.datetime.now()
    # Convert to Pacific Time (Los Angeles)
    pacific_timezone = ZoneInfo("America/Los_Angeles") 
    now_aware = now.astimezone(pacific_timezone)
    formatted_datetime = now_aware.strftime("%Y-%m-%d %I:%M:%S %p %Z")
    return formatted_datetime

# Core Functionality
def get_actor_id(event_timestamp:str) -> str:
    '''
    Authorization
    - The token must be a Slack user token (beginning with xoxp) associated with an Enterprise Grid organization owner
    - Grid organization administrator tokens are not currently supported
    - the token must be granted the auditlogs:read
    '''
    # https://api.slack.com/admins/audit-logs
    # https://api.slack.com/admins/audit-logs-call

    headers = {"Authorization": f"Bearer {SLACK_USER_TOKEN}"}
    params = {
        "action": "emoji_added",
        "limit": 20  # fetch the most recent events
    }
    response = requests.get("https://api.slack.com/audit/v1/logs", headers=headers, params=params)
    for event in response.json().get("entries"):
        if event.get("date_create") == event_timestamp:
            return event.get("actor").get("user").get("id")

def respond_to_slack_within_3_seconds(ack):
    ack()

def handle_emoji_changed_events(ack, body, event, client):
    ack()
    emoji=event["name"]
    ts=body["event_time"]
    actor_id = get_actor_id(event_timestamp=ts)

    client.chat_postMessage(
        channel=MOD_CHANNEL,
        text=f":{emoji}: was uploaded by <@{actor_id}>",
        blocks=ui_templates.update_blocks_message(emoji, actor_id, ts)
    )
app.event({'type': 'emoji_changed', 'subtype': 'add'})(ack=respond_to_slack_within_3_seconds, lazy=[handle_emoji_changed_events])

def handle_remove_button(ack, body, client):
    ack()
    trigger_id=body["trigger_id"]
    private_metadata={
        "emoji":body["actions"][0]["value"],
        "user_id":re.findall(r"<@([^>]+)>", body["message"]["text"])[0],
        "message_ts":body["message"]["ts"],
        "current_message":body["message"]["blocks"][0]["text"]["text"]
    }
    client.views_open(
        view=ui_templates.revoke_message_modal(private_metadata),
        trigger_id=trigger_id
    )
app.action("remove_emoji")(ack=respond_to_slack_within_3_seconds, lazy=[handle_remove_button])

def handle_emoji_removal(ack):
    ack()
    pass # Do nothing, this is just to acknowledge the event
app.event({'type': 'emoji_changed', 'subtype': 'remove'})(ack=respond_to_slack_within_3_seconds, lazy=[handle_emoji_removal])

def handle_view_submission_events(ack, body, client, view, logger):
    ack()
    today = get_todays_date()
    private_metadata=json.loads(view["private_metadata"])
    justification=view["state"]["values"]["input_block"]["submit_button"]["value"]
    text=f"Your emoji, :{private_metadata["emoji"]}:, was removed on {today}"
    last_message = private_metadata["current_message"]
    client.admin_emoji_remove(
        token=SLACK_USER_TOKEN,
        name=private_metadata["emoji"]
    )
    client.chat_update(
        channel=MOD_CHANNEL,
        ts=private_metadata["message_ts"],
        text=f"{last_message}\n:x: `:{private_metadata['emoji']}:` was removed by <@{body['user']['id']}> on {today}\nJustification: {justification}",
    )
    if justification == None:
        client.chat_postMessage(
            channel=private_metadata["user_id"],
            text=text
        )
    else:
        client.chat_postMessage(
            channel=private_metadata["user_id"],
            text=f"{text}\nJustification: {justification}"
        )
    logger.info(body)
app.view("revoke_message_modal")(ack=respond_to_slack_within_3_seconds, lazy=[handle_view_submission_events])

# AWS Lambda entrypoint
def handler(event, context):
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)