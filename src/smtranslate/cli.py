import logging
import os
import sys
from typing import Any

import yaml

import click
from smtranslate import parser

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def cli() -> None:
    pass


@cli.command("check")
@click.option("--config-folder", default="config", help="Configuration folder path.")
@click.option(
    "--translation-folder", required=True, help="Sourcemod translations folder path"
)
@click.version_option()
def check(config_folder: str, translation_folder: str) -> None:
    config_folder_path = os.path.abspath(config_folder)
    config_file_path = os.path.abspath(f"{config_folder_path}/config.yml")

    config: dict[str, Any] = {}
    try:
        with open(config_file_path, "r") as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        logger.error("File not found.")
    except yaml.YAMLError as exc:
        logger.error(sys._getframe().f_code.co_name + " " + str(exc))
        sys.exit(1)

    logging.basicConfig(
        level=logging.getLevelName(config["logging"]["level"]),
        format=config["logging"]["format"],
        datefmt=config["logging"]["datefmt"],
    )

    language_cfg_path = os.path.abspath(f"{config_folder}/languages.cfg")
    translation_folder_path = os.path.abspath(translation_folder)

    parser.run(
        language_cfg_path=language_cfg_path,
        translation_folder_path=translation_folder_path,
    )
