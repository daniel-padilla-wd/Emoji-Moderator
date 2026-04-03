import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError
load_dotenv()

bot_token_secret_name = os.getenv("bot_token_secret_name")
signing_secret_name = os.getenv("signing_secret_name")
user_token_secret_name = os.getenv("user_token_secret_name")
region_name = "us-west-1"
# Create a Secrets Manager client
session = boto3.session.Session()
client = session.client(
    service_name='secretsmanager',
    region_name=region_name
)

def get_bot_token():
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=bot_token_secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e
    secret = get_secret_value_response['SecretString']
    return secret

def get_signing_secret():
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=signing_secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response['SecretString']
    return secret

def get_user_token():
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=user_token_secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response['SecretString']
    return secret
