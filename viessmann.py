import hashlib
import logging
from typing import Optional

import requests

from requests.auth import HTTPBasicAuth
import base64
import os
from urllib.parse import urlparse, parse_qs
from custom.config import ViessmannConfig, IAMConfig, IoTConfig
from custom.iot import IoTFeatureResponse, PhotovoltaicData


class Viessmann:
    def __init__(self, config: ViessmannConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.code_verifier = self.generate_code_verifier()
        self.code_challenge = self.generate_code_challenge(self.code_verifier)

    def generate_code_verifier(self) -> str:
        return base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8").rstrip("=")

    def generate_code_challenge(self, verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def get_authorization_code(self, iam: IAMConfig) -> str:
        params = {
            "client_id": iam.client_id,
            "scope": "IoT User offline_access",
            "response_type": "code",
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "redirect_uri": iam.redirect_uri,
        }
        auth_url = f"{iam.base_url}/authorize"
        response = requests.get(
            auth_url,
            params=params,
            auth=HTTPBasicAuth(iam.username, iam.password),
            allow_redirects=False,
        )
        response.raise_for_status()
        if response.status_code == 302:
            location = response.headers.get("Location")
            parsed = urlparse(location)
            query_params = parse_qs(parsed.query)
            authorization_code = query_params.get("code", [None])[0]

            return authorization_code
        return ""

    def get_access_token(self, iam: IAMConfig) -> str:
        params = {
            "client_id": iam.client_id,
            "redirect_uri": iam.redirect_uri,
            "response_type": "id_token token",
            "nonce": "anything_goes",
        }
        auth_url = f"{iam.base_url}/authorize"
        response = requests.get(
            auth_url,
            params=params,
            auth=HTTPBasicAuth(iam.username, iam.password),
            allow_redirects=False,
        )
        response.raise_for_status()
        if response.status_code == 302:
            location = response.headers.get("Location")
            parsed = urlparse(location)
            fragment = parse_qs(parsed.fragment)
            return fragment.get("access_token", [None])[0]
        return ""

    def get_access_token_pkce(self, iam: IAMConfig) -> str:
        auth_code = self.get_authorization_code(iam)
        data = {
            "client_id": iam.client_id,
            "redirect_uri": iam.redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": self.code_verifier,
            "code": auth_code,
        }
        response = requests.post(f"{iam.base_url}/token", data=data)
        response.raise_for_status()
        return response.json().get("access_token")

    def get_token(self) -> str:
        iam = self.config.iam

        try:
            if iam.use_pkce_flow:
                token = self.get_access_token_pkce(iam)
            else:
                token = self.get_access_token(iam)
            self.logger.info("Successfully obtained access token")
            return token
        except Exception as e:
            self.logger.error(f"Failed to retrieve access token: {e}")
            raise e

    def get_device_features(
        self, token: str, config: IoTConfig
    ) -> Optional[IoTFeatureResponse]:
        url = f"{config.base_url}/features/installations/{config.installation_id}/gateways/{config.gateway_id}/devices/0/features"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {
            "filter": [
                "photovoltaic.production.current",
                "ess.power",
                "pcc.transfer.power.exchange",
                "ess.stateOfCharge",
            ]
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        try:
            return IoTFeatureResponse.model_validate(response.json())
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Failed to fetch pv data from IoT API: {e}")
            raise e
        except Exception as e:
            self.logger.error(f"Failed to parse: {e}")
            raise e

    def get_feature_value(self, features: IoTFeatureResponse, feature_name: str):
        return next(
            (
                d.properties.value.value
                for d in features.data
                if d.feature == feature_name
            ),
            None,
        )

    def get_photovoltaic_data(self) -> PhotovoltaicData:
        token = self.get_token()
        iot = self.config.iot

        features = self.get_device_features(token, iot)
        solar_power = (
            self.get_feature_value(features, "photovoltaic.production.current")
        ) * 1000
        battery_power = self.get_feature_value(features, "ess.power")
        grid_exchange = self.get_feature_value(features, "pcc.transfer.power.exchange")
        state_of_charge = self.get_feature_value(features, "ess.stateOfCharge")
        household = solar_power + battery_power + grid_exchange

        return PhotovoltaicData(
            _solar_power=solar_power,
            _battery_power=battery_power,
            _grid_exchange=grid_exchange,
            _state_of_charge=state_of_charge,
            _household=household,
        )
