import json
import os
from logging import Logger
from typing import Optional
from custom.config import Config, ViessmannConfig, IoTConfig, IAMConfig, ChargerConfig
from custom.iot import PhotovoltaicData
from logger import setup_logger
from viessmann import Viessmann
from datetime import datetime
from charger import Charger

os.chdir(os.path.dirname(os.path.abspath(__file__)))
config_path = "config.json"

possible_charger_settings = [
    # {"power": 11000, "amp": 16, "psm": 2},
    # {"power": 9700, "amp": 14, "psm": 2},
    # {"power": 8300, "amp": 12, "psm": 2},
    {"power": 6900, "amp": 10, "psm": 2},
    {"power": 4100, "amp": 6, "psm": 2},
    {"power": 3700, "amp": 16, "psm": 1},
    {"power": 3200, "amp": 14, "psm": 1},
    {"power": 2800, "amp": 12, "psm": 1},
    {"power": 2300, "amp": 10, "psm": 1},
    {"power": 1400, "amp": 6, "psm": 1},
]


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

    charger_config = ChargerConfig(**data["charger"])

    config = Config(
        enabled=data.get("enabled", False),
        viessmann=viessmann_config,
        charger=charger_config,
    )
    return config


def get_photovoltaic_data(viessmann: Viessmann, logger: Logger) -> PhotovoltaicData:
    pv_data = viessmann.get_photovoltaic_data()
    battery_label = (
        "Batterieentladung" if pv_data.battery_power > 0 else "Batterieaufladung"
    )
    grid_label = "Netzbezug" if pv_data.grid_exchange > 0 else "Einspeisung"
    logger.info(
        f"Photovoltaic data: "
        f"Solarleistung: {to_kilo_watt(pv_data.solar_power)}, "
        f"{battery_label}: {to_kilo_watt(pv_data.battery_power)}, "
        f"{grid_label}: {to_kilo_watt(pv_data.grid_exchange)}, "
        f"Haushalt: {to_kilo_watt(pv_data.household)}"
    )
    return pv_data


def to_kilo_watt(value: float):
    if value < 1000:
        return f"{value:.2f} W"
    else:
        return f"{(value / 1000):.2f} kW"


def main():
    config = load_config()
    logger = setup_logger()

    logger.info(
        "================================== Starting up =================================="
    )

    if config is None or not config.enabled:
        logger.info("Script disabled by configuration, exiting.")
        return 0

    viessmann = Viessmann(config.viessmann, logger)
    charger = Charger(config.charger, logger)

    try:
        # check if wallbox is ready to charge and there is a need to adjust settings based on pv data
        charger_data = charger.check_for_readiness()
        if not charger_data:
            return 0
        frc, energy, frm = (
            charger_data.get("frc"),
            charger_data.get("nrg")[11],
            charger_data.get("frm"),
        )

        logger.info(
            f"Charger is currently {'not charging' if energy == 0 else f'charging with {to_kilo_watt(energy)}'}"
        )

        try:
            pv_data = get_photovoltaic_data(viessmann, logger)
        except:
            logger.error("Could not fetch pv data, disabling Wallbox for safety")
            charger.disable(charger_data)
            return 0

        # we have solar power and can enable/adjust wallbox
        effective_household = pv_data.household - energy
        if energy > 0:
            logger.info(
                f"Calculated: Haushalt: {to_kilo_watt(effective_household)}, Wallbox: {to_kilo_watt(energy)}"
            )
        # calculate available power.
        # depending on "frm" (Leistungspräferenz) we need to prioritize either pv battery or charger.
        # frm = 2 means pv battery should be prioritized over charger.
        # this will allow the pv battery to fill more quickly and is intended for summer.
        battery = min(pv_data.battery_power, 0) if frm == 2 else 0
        available_power = pv_data.solar_power - effective_household + battery

        # special logic to apply when frm = 0: until 15 pm, allow discharging of battery when it is almost full.
        # this represents a more "aggressive" behavior which is intended for winter.
        if frm == 0 and pv_data.state_of_charge > 90 and datetime.now().hour < 15:
            logger.info(
                f"Temporarily allowing discharge of battery due to SoC = {pv_data.state_of_charge}"
            )
            available_power += 1800
        if available_power <= 0:
            logger.info("Disabling charger as there is no solar power available")
            charger.disable(charger_data)
        else:
            logger.info(
                f"Available solar power to use: {to_kilo_watt(available_power)}"
            )
            target_settings = next(
                (
                    {k: v for k, v in p.items() if k in {"amp", "psm"}}
                    for p in possible_charger_settings
                    if p["power"] <= available_power
                ),
                None,
            )

            if target_settings:
                logger.info(f"Setting: {target_settings}")
                charger.set_value(charger_data, frc=0, **target_settings)
            else:
                logger.info("Not enough solar power, disabling charger")
                charger.disable(charger_data)

    except Exception as e:
        logger.error(f"Unknown error occurred: {e}")


if __name__ == "__main__":
    main()
