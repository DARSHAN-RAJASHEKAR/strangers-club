import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.api_key = os.environ["GUPSHUP_API_KEY"]
        self.source_number = os.environ["GUPSHUP_SOURCE_NUMBER"]
        self.app_name = os.environ["GUPSHUP_APP_NAME"]
        self.template_id = os.environ["GUPSHUP_TEMPLATE_ID"]
        self.api_url = "https://api.gupshup.io/wa/api/v1/template/msg"

    async def send_otp(self, phone_number: str, otp_code: str) -> bool:
        if not phone_number or not otp_code:
            return False

        destination = f"91{phone_number}" if not phone_number.startswith("91") else phone_number

        try:
            payload = {
                "channel": "whatsapp",
                "source": self.source_number,
                "destination": destination,
                "src.name": self.app_name,
                "template": json.dumps({
                    "id": self.template_id,
                    "params": [otp_code]
                })
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "apikey": self.api_key
            }
            response = requests.post(self.api_url, headers=headers, data=payload, timeout=10)
            if response.status_code in (200, 202):
                return True
            else:
                logger.error(f"Failed to send OTP. Status: {response.status_code}")
                return False
        except Exception:
            logger.exception("Error sending OTP")
            return False

# Singleton instance
whatsapp_service = WhatsAppService()
