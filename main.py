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
    # {"power": 7500, "amp": 11, "psm": 2},
    # 3 phase
    {"power": 6900, "amp": 10, "psm": 2},
    {"power": 6200, "amp": 9, "psm": 2},
    {"power": 5500, "amp": 8, "psm": 2},
    {"power": 4800, "amp": 7, "psm": 2},
    {"power": 4100, "amp": 6, "psm": 2},
    # 1 phase
    {"power": 3700, "amp": 16, "psm": 1},
    {"power": 3200, "amp": 14, "psm": 1},
    {"power": 2800, "amp": 12, "psm": 1},
    {"power": 2300, "amp": 10, "psm": 1},
    {"power": 1800, "amp": 8, "psm": 1},
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
        frc, energy, frm, pgt = (
            charger_data.get("frc"),
            charger_data.get("nrg")[11],
            charger_data.get("frm"),
            charger_data.get("pgt"),
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
        # ignore the battery power, most of the time there is enough difference between used and available power
        # but use the pgt value which is intended to control a buffer that should be set to allow battery charge.
        available_power = pv_data.solar_power - effective_household - pgt

        # allow discharging of battery when it is almost full (only until 15 pm)
        if pv_data.state_of_charge > 90 and datetime.now().hour < 15:
            logger.info(
                f"Temporarily allowing discharge of battery due to SoC = {pv_data.state_of_charge}"
            )
            # limit the artificial increase to 7500, because the VX3 cannot deliver more than that
            available_power = min(7500, available_power + 1500)
        if frm == 0 and energy > 0 and pv_data.state_of_charge > 50:
            # in frm=0 mode, prevent continuously enabling/disabling charger. once it's charging, keep it charging until battery is below 50%.
            logger.info(
                f"Keep charging until battery SoC is below 50% (SoC = {pv_data.state_of_charge})"
            )
            available_power = max(available_power, 1500)
        if available_power <= 0:
            logger.info("Disabling charger as there is no solar power available")
            charger.disable(charger_data)
        else:
            logger.info(
                f"Available solar power to use: {to_kilo_watt(available_power)}"
            )
            if frm != 2:
                logger.info(f"Available power limited to 1-phase only")
            target_settings = next(
                (
                    {k: v for k, v in p.items() if k in {"amp", "psm"}}
                    for p in possible_charger_settings
                    if p["power"] <= available_power and (frm == 2 or p["psm"] == 1)
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
