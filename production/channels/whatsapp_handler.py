
import os
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.request_validator import RequestValidator
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhatsAppHandler:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")

        if not self.account_sid or not self.auth_token or not self.twilio_whatsapp_number:
            raise ValueError("Twilio credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER) not found in .env file")

        self.client = Client(self.account_sid, self.auth_token)
        self.validator = RequestValidator(self.auth_token)

    def validate_webhook(self, request_body, twilio_signature, twilio_url):
        """Validates the incoming Twilio webhook signature."""
        try:
            return self.validator.validate(twilio_url, request_body, twilio_signature)
        except Exception as e:
            logger.error(f"Error validating Twilio webhook: {e}")
            return False

    def process_webhook(self, request_form):
        """Processes an incoming Twilio WhatsApp webhook request."""
        try:
            message_sid = request_form.get('SmsSid')
            from_number = request_form.get('From')
            to_number = request_form.get('To')
            message_body = request_form.get('Body')

            logger.info(f"Received WhatsApp message SID: {message_sid} from {from_number} to {to_number}")

            return {
                "message_sid": message_sid,
                "from_number": from_number,
                "to_number": to_number,
                "message_body": message_body
            }
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {e}")
            raise

    def send_message(self, to_number: str, message: str):
        """Sends a WhatsApp message using Twilio."""
        try:
            # Twilio has a message size limit. Split long messages.
            parts = self.format_response(message)
            sids = []
            for part in parts:
                message_response = self.client.messages.create(
                    from_=f"whatsapp:{self.twilio_whatsapp_number}",
                    body=part,
                    to=f"whatsapp:{to_number}"
                )
                sids.append(message_response.sid)
                logger.info(f"Sent WhatsApp message part SID: {message_response.sid} to {to_number}")
            return {"status": "sent", "sids": sids}
        except Exception as e:
            logger.error(f"Error sending WhatsApp message to {to_number}: {e}")
            raise

    def format_response(self, message: str, max_length: int = 1600):
        """Splits a long message into multiple parts suitable for WhatsApp (Twilio limit ~1600 chars)."""
        if len(message) <= max_length:
            return [message]

        parts = []
        current_part = ""
        sentences = message.split('. ') # Attempt to split by sentence for better readability

        for sentence in sentences:
            if len(current_part) + len(sentence) + 2 <= max_length: # +2 for ". "
                current_part += sentence + ". "
            else:
                parts.append(current_part.strip())
                current_part = sentence + ". "
        if current_part:
            parts.append(current_part.strip())
        return parts

