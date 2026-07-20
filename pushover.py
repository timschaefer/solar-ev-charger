from custom.config import PushoverConfig
import logging
import requests


class Pushover:
    def __init__(self, config: PushoverConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def send_notification(self, message: str):
        url = f"{self.config.base_url}/messages.json"
        response = requests.post(
            url,
            data={
                "token": self.config.api_token,
                "user": self.config.user_key,
                "title": "Solar EV Charger",
                "message": message,
                "priority": 0,
            },
            timeout=10,
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Failed to send data to pushover: {e}")
            raise e

        self.logger.info("pushover message sent")
