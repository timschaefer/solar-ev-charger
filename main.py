import json
from typings import Config
from logger import setup_logger

def load_config() -> Config:
    with open("config.json", "r") as file:
        data = json.load(file)

    config = Config(**data)
    return config


def main():
    config = load_config()
    logger = setup_logger()

    if config.enabled:
        logger.info("Starting checks...")
    else:
        logger.info("Script disabled, exiting")


if __name__ == "__main__":
    main()