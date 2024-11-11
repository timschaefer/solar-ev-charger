import json
import os
from logging import Logger
from typing import Optional, Any, Union
from custom.config import Config, ViessmannConfig, IoTConfig, IAMConfig
from custom.iot import PhotovoltaicData
from logger import setup_logger
from viessmann import Viessmann

os.chdir(os.path.dirname(os.path.abspath(__file__)))
config_path = "config.json"


def load_config() -> Optional[Config]:
    if not os.path.exists(config_path):
        print(
            "config.json does not exist. Please copy config.template.json and adjust it accordingly."
        )
        return None
    with open(config_path, "r") as file:
        data = json.load(file)

    iam = IAMConfig(**data["viessmann"]["iam"])
    iot = IoTConfig(**data["viessmann"]["iot"])
    viessmann_config = ViessmannConfig(iam=iam, iot=iot)

    config = Config(enabled=data.get("enabled", False), viessmann=viessmann_config)
    return config


def get_photovoltaic_data(
    viessmann: Viessmann, logger: Logger
) -> Optional[PhotovoltaicData]:
    pv_data = viessmann.get_photovoltaic_data()
    battery_label = (
        "Batterieentladung" if pv_data.battery_power > 0 else "Batterieaufladung"
    )
    grid_label = "Netzbezug" if pv_data.grid_exchange > 0 else "Einspeisung"
    logger.info(
        f"Photovoltaic data: "
        f"Solarleistung: {pv_data.solar_power:.2f} W, "
        f"{battery_label}: {pv_data.battery_power:.2f} W, "
        f"{grid_label}: {pv_data.grid_exchange:.2f} W, "
        f"Haushalt: {pv_data.household:.2f} W"
    )
    if pv_data.solar_power == 0:
        logger.info(f"No solar power available, exiting.")
        return None
    return pv_data


def main():
    config = load_config()
    logger = setup_logger()

    if config is None or not config.enabled:
        logger.info("Script disabled by configuration, exiting.")
        return 0

    logger.info("Starting up...")

    viessmann = Viessmann(config.viessmann, logger)

    try:
        # fetch wallbox data, then pv data (only if wallbox is able to charge)
        pv_data = get_photovoltaic_data(viessmann, logger)

        # effective_household = household - wallbox
        # available for wallbox: solar_power - effective_household + min(battery_power, 0)
    except Exception as e:
        logger.error(f"Unknown error occurred: {e}")


if __name__ == "__main__":
    main()
