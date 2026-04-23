
import os
import base64
import email
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import asyncio
import logging
import json

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")
GMAIL_WATCH_TOPIC = os.getenv("GMAIL_WATCH_TOPIC", "projects/your-gcp-project-id/topics/gmail-notifications")
GMAIL_WATCH_LABEL = os.getenv("GMAIL_WATCH_LABEL", "INBOX")

class GmailHandler:
    def __init__(self):
        self.creds = None
        self.service = None
        asyncio.run(self._authenticate())

    async def _authenticate(self):
        if os.path.exists(GMAIL_TOKEN_PATH):
            self.creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, SCOPES)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    GMAIL_CREDENTIALS_PATH, SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            with open(GMAIL_TOKEN_PATH, "w") as token:
                token.write(self.creds.to_json())

        self.service = build("gmail", "v1", credentials=self.creds)
        logger.info("Gmail service authenticated successfully.")

    async def setup_push_notifications(self):
        """Sets up Gmail push notifications for new emails."""
        try:
            request_body = {
                'labelIds': [GMAIL_WATCH_LABEL],
                'topicName': GMAIL_WATCH_TOPIC
            }
            watch_response = self.service.users().watch(userId='me', body=request_body).execute()
            logger.info(f"Gmail push notifications set up: {watch_response}")
            return watch_response
        except HttpError as error:
            logger.error(f"An error occurred while setting up Gmail push notifications: {error}")
            raise

    async def process_notification(self, data: dict):
        """Processes a Pub/Sub notification to identify new emails."""
        try:
            # The data received from Pub/Sub is base64 encoded JSON
            message_data = base64.b64decode(data['message']['data']).decode('utf-8')
            message_json = json.loads(message_data)
            email_address = message_json['emailAddress']
            history_id = message_json['historyId']

            logger.info(f"Received Gmail notification for {email_address}, historyId: {history_id}")

            # You can then use history_id to fetch new messages if needed
            # For simplicity, we'll assume we get the full message ID directly or iterate INBOX
            return {"emailAddress": email_address, "historyId": history_id}

        except Exception as e:
            logger.error(f"Error processing Gmail notification: {e}")
            raise

    async def get_message(self, message_id: str):
        """Retrieves and parses a full email message by ID."""
        try:
            msg = self.service.users().messages().get(userId='me', id=message_id, format='full').execute()
            msg_payload = msg['payload']
            headers = {header['name']: header['value'] for header in msg_payload['headers']}

            sender = self._extract_email(headers.get('From', ''))
            recipient = self._extract_email(headers.get('To', ''))
            subject = headers.get('Subject', '')
            body = self._extract_body(msg_payload)

            return {
                "id": message_id,
                "sender": sender,
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "headers": headers
            }
        except HttpError as error:
            logger.error(f"An error occurred while getting message {message_id}: {error}")
            raise

    async def send_reply(self, to_email: str, subject: str, message_body: str, in_reply_to_id: str = None, references: str = None):
        """Sends an email reply."""
        try:
            message = email.message.EmailMessage()
            message['To'] = to_email
            message['From'] = os.getenv("GMAIL_SENDER_EMAIL") # Ensure this is set in .env
            message['Subject'] = subject
            message.set_content(message_body)

            if in_reply_to_id:
                message['In-Reply-To'] = in_reply_to_id
                if references:
                    message['References'] = references + f" {in_reply_to_id}"
                else:
                    message['References'] = in_reply_to_id

            # Encoded message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': encoded_message}

            send_message = (
                self.service.users()
                .messages()
                .send(userId="me", body=create_message)
                .execute()
            )
            logger.info(f"Message sent to {to_email}: {send_message['id']}")
            return send_message
        except HttpError as error:
            logger.error(f"An error occurred while sending email: {error}")
            raise

    def _extract_body(self, payload):
        """Extracts the plain text body from an email payload."""
        parts = payload.get('parts')
        if parts:
            for part in parts:
                mime_type = part.get('mimeType')
                if mime_type == 'text/plain':
                    data = part['body']['data']
                    return base64.urlsafe_b64decode(data).decode('utf-8')
                elif mime_type == 'multipart/alternative':
                    return self._extract_body(part) # Recurse for multipart alternatives
        elif payload.get('body') and payload['body'].get('data'):
            data = payload['body']['data']
            return base64.urlsafe_b64decode(data).decode('utf-8')
        return ""

    def _extract_email(self, full_email_string):
        """Extracts the email address from a full 'Name <email@example.com>' string."""
        import re
        match = re.search(r'<(.+?)>', full_email_string)
        if match:
            return match.group(1)
        return full_email_string # Return as is if no angle brackets


