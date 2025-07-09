import os
import json
import requests
from requests import Response
import datetime
from zoneinfo import ZoneInfo
import re


from slack_bolt import App
from slack_sdk.errors import SlackApiError
from slack_bolt.adapter.socket_mode import SocketModeHandler

import logging
logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv()

SLACK_APP_TOKEN= os.getenv("APP_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SIGNING_SECRET")
SLACK_BOT_TOKEN = os.getenv("BOT_TOKEN")
SLACK_USER_TOKEN = os.getenv("USER_TOKEN")

# https://api.slack.com/authentication/verifying-requests-from-slack
# Initializes your app with your bot token and signing secret
app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET
)

def convert_epoch_timestamp(timestamp: float) -> str:
    """Converts a Unix timestamp to a human-readable 12-hour datetime string in Pacific Time (Los Angeles).
    Args:
        timestamp: The Unix timestamp (integer or float)
    Returns:
        A string representing the date and time in Pacific Time (12-hour format).
    """
    pacific_time = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo("America/Los_Angeles"))
    return pacific_time.strftime("%Y-%m-%d %I:%M:%S %p %Z")

def view_block():
    with open('modal.json', 'r') as file:
        blocks = json.load(file)
    return json.dumps(blocks)

def blocks_message(emoji: str, user_id:str, ts:str) -> str:
    date=convert_epoch_timestamp(float(ts))
    text=f":{emoji}: was uploaded by <@{user_id}> on {date}"
    with open('blocks.json', 'r') as file:
        blocks = json.load(file)
        blocks["blocks"][0]["text"]["text"]=text
        blocks["blocks"][1]["elements"][0]["value"]=emoji
    return json.dumps(blocks["blocks"])

def update_source_msg(response_url:str, text:str) -> Response:
    payload = {
        "replace_original": "true",
        "text": f"{text}"
    }
    response = requests.post(response_url, data=json.dumps(payload))
    return response

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
    
# Event payload: (message: {"envelope_id":"6f2e1bfa-360f-4399-8b6d-1f88c02e0253","payload":{"token":"fKwAhlpTIXDnundHLb5GfFYM","team_id":"T08NXSDNGCB","enterprise_id":"E08NY9QJLSW","api_app_id":"A094F1W8E2W","event":{"type":"emoji_changed","subtype":"add","name":"profile","value":"https:\/\/emoji.slack-edge.com\/T08NY9QJLSW\/profile\/383da0ea71393398.jpg","event_ts":"1751677629.004200"},"type":"event_callback","event_id":"Ev0948DDP61Z","event_time":1751677629,"authorizations":[{"enterprise_id":"E08NY9QJLSW","team_id":null,"user_id":"U0942DUS631","is_bot":true,"is_enterprise_install":true}],"is_ext_shared_channel":false},"type":"events_api","accepts_response_payload":false,"retry_attempt":2,"retry_reason":"timeout"})
# Unhandled request ({'type': 'event_callback', 'event': {'type': 'emoji_changed', 'subtype': 'add'}})
# [Suggestion] You can handle this type of event with the following listener function:
@app.event({'type': 'emoji_changed', 'subtype': 'add'})
def handle_emoji_changed_events(ack, body, event, client):
    ack()
    emoji=event["name"]
    ts=body["event_time"]
    actor_id = get_actor_id(event_timestamp=ts)

    client.chat_postMessage(
        channel="C0923REDJ0Z",
        text=f":{emoji}: was uploaded by <@{actor_id}>",
        blocks=blocks_message(emoji, actor_id, ts)
    )

# Unhandled request ({'type': 'block_actions', 'action_id': 'remove_emoji'})
# [Suggestion] You can handle this type of event with the following listener function:
@app.action("remove_emoji")
def handle_remove_button(ack, body, client):
    ack()
    trigger_id=body["trigger_id"]
    client.views_open(
        view=view_block(),
        trigger_id=trigger_id
    )
    """
    ts=float(body["actions"][0]["action_ts"])
    date=convert_epoch_timestamp(ts)
    emoji=body["actions"][0]["value"]
    actor_id=body["user"]["id"]
    prev_message=body["message"]["text"]
    user_id=re.findall(r"<@([^>]+)>", prev_message)[0]
    new_message=f":x: `:{emoji}:` was removed by <@{actor_id}> on {date}"
    client.admin_emoji_remove(
        token=SLACK_USER_TOKEN,
        name=emoji
    )
    # https://api.slack.com/interactivity/handling#updating_message_response
    update_source_msg(body["response_url"], f"{prev_message}\n{new_message}")

    client.chat_postMessage(
        channel=user_id,
        text=new_message
    )
"""
# Unhandled request ({'type': 'event_callback', 'event': {'type': 'emoji_changed', 'subtype': 'remove'}})
# [Suggestion] You can handle this type of event with the following listener function:
@app.event({'type': 'emoji_changed', 'subtype': 'remove'})
def handle_emoji_removal(ack):
    ack()
    pass # Do nothing

# Unhandled request ({'type': 'view_submission', 'view': {'type': 'modal', 'callback_id': ''}})
# [Suggestion] You can handle this type of event with the following listener function:
@app.view({'type': 'view_submission', 'view': {'type': 'modal', 'callback_id': 'memes'}})
def handle_view_submission_events(ack, body, logger):
    ack()
    logger.info(body)

if __name__ == "__main__":      
    SocketModeHandler(app, SLACK_APP_TOKEN).start()