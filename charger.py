from custom.config import ChargerConfig
import logging
import requests


class Charger:
    def __init__(self, config: ChargerConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def check_for_readiness(self):
        status = self.get_status()
        fup, car, frc = status.get("fup"), status.get("car"), status.get("frc")
        if not fup:
            self.logger.info(
                "Surplus disabled in Go-e Charger, exiting",
            )
            return False
        if car == 1:
            self.logger.info("Vehicle not connected to charger, exiting")
            return False

        if car == 4 and frc == 0:
            self.logger.info("Vehicle completely charged, exiting")
            return False

        return status

    def get_status(self):
        self.logger.info("Fetching status from charger...")
        url = f"{self.config.base_url}/status"
        params = {"filter": "amp,psm,car,frc,nrg,fup,frm,pgt"}

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            result = response.json()
            self.logger.info(result)
            return result
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Failed to fetch status from Go-e Charger API: {e}")
            raise e

    def disable(self, status: dict):
        return self.set_value(status, frc=1)

    def set_value(self, status: dict, **kwargs: dict):
        url = f"{self.config.base_url}/set"
        params = {k: v for k, v in kwargs.items() if str(status.get(k)) != str(v)}

        if not params:
            # avoid unnecessary api calls
            return

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()

            return response.json()
        except requests.exceptions.HTTPError as e:
            self.logger.error(
                f"Failed to set parameters {kwargs} in Go-e Charger API: {e}"
            )
            raise e
