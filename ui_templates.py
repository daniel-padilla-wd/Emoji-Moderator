import datetime
from zoneinfo import ZoneInfo
import json

# Helper Functions
def convert_epoch_timestamp(timestamp: float) -> str:
    """Converts a Unix timestamp to a human-readable 12-hour datetime string in Pacific Time (Los Angeles).
    Args:
        timestamp: The Unix timestamp (integer or float)
    Returns:
        A string representing the date and time in Pacific Time (12-hour format).
    """
    pacific_time = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo("America/Los_Angeles"))
    return pacific_time.strftime("%Y-%m-%d %I:%M:%S %p %Z")

# Core Functionality
BLOCKS_MESSAGE = [
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "text"
        }
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "action_id": "remove_emoji",
                "text": {
                    "type": "plain_text",
                    "emoji": True,
                    "text": "Remove"
                },
                "style": "danger",
                "value": "click_me_123"
            }
        ]
    }
]


def update_blocks_message(emoji: str, user_id:str, ts:str) -> str:
    date=convert_epoch_timestamp(float(ts))
    text=f":{emoji}: was uploaded by <@{user_id}> on {date}"
    BLOCKS_MESSAGE[0]["text"]["text"]=text
    BLOCKS_MESSAGE[1]["elements"][0]["value"]=emoji
    return json.dumps(BLOCKS_MESSAGE)

REVOKE_MESSAGE_MODAL = {
	"type": "modal",
	"submit": {
		"type": "plain_text",
		"text": "Submit",
		"emoji": True
	},
	"close": {
		"type": "plain_text",
		"text": "Cancel",
		"emoji": True
	},
	"private_metadata":"",
	"title": {
		"type": "plain_text",
		"text": "Remove Emoji",
		"emoji": True
	},
	"callback_id": "revoke_message_modal",
	"blocks": [
		{
			"type": "input",
			"block_id": "input_block",
			"label": {
				"type": "plain_text",
				"text": "Anything else you want to tell the user?",
				"emoji": True
			},
			"element": {
				"type": "plain_text_input",
				"action_id": "submit_button",
				"multiline": True
			},
			"optional": True
		}
	]
}

def revoke_message_modal(private_metadata: dict):
    REVOKE_MESSAGE_MODAL["private_metadata"] = json.dumps(private_metadata)
    return json.dumps(REVOKE_MESSAGE_MODAL)