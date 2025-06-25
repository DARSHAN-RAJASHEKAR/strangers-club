import os
import json
import requests
import logging
from typing import List

logger = logging.getLogger(__name__)

class WhatsAppService:
    """Service for sending WhatsApp messages through Gupshup.io API."""
    
    def __init__(self):
        # Get credentials from environment variables with hardcoded defaults
        # Use the exact same values as your working test code
        self.api_key = os.getenv("GUPSHUP_API_KEY", "csvhgf8ahngm0dgts79lmytapqxblp7c")
        self.source_number = os.getenv("GUPSHUP_SOURCE_NUMBER", "918217207520")
        self.app_name = os.getenv("GUPSHUP_APP_NAME", "strangersmeet")
        self.template_id = os.getenv("GUPSHUP_TEMPLATE_ID", "f8a32b3a-5f70-4524-a94c-4068a0a39212")
        self.api_url = "https://api.gupshup.io/wa/api/v1/template/msg"
        
        # Log initialization
        logger.info(f"WhatsApp service initialized with default API key")
    
    async def send_otp(self, phone_number: str, otp_code: str) -> bool:
        """
        Send OTP code via WhatsApp.
        
        Args:
            phone_number: 10-digit phone number (without country code)
            otp_code: 6-digit OTP code
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not phone_number or not otp_code:
            logger.error("Invalid phone number or OTP code")
            return False
            
        # Ensure phone number has country code (91 for India)
        destination = f"91{phone_number}" if not phone_number.startswith("91") else phone_number
        
        # Log sending attempt
        logger.info(f"Sending OTP to {destination}")
        
        try:
            # Construct the payload exactly like the working test code
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
            
            # Construct the headers exactly like the working test code
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "apikey": self.api_key
            }
            
            # Send the request
            response = requests.post(self.api_url, headers=headers, data=payload)
            
            # Check response
            if response.status_code == 200 or response.status_code == 202:
                logger.info(f"OTP sent successfully. Status: {response.status_code}, Response: {response.text}")
                return True
            else:
                logger.error(f"Failed to send OTP. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.exception(f"Error sending OTP: {str(e)}")
            return False

# Singleton instance
whatsapp_service = WhatsAppService()