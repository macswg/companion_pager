#! python3
# companion_pager.py

# Python script to update companion buttons

import copy
import json
from typing import Any, Dict, Union
import logging
import os
import re

PAPERTRAIL_HOST = "logs5.papertrailapp.com"
PAPERTRAIL_PORT = 54000
APP_NAME = "companion_pager.py"

# creates logger and sets logger level
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# creates handler for online logging and sets handler format
format = f"{APP_NAME}: %(message)s"
formatter = logging.Formatter(format)

# creates handler for local logging and sets handler format
localHandler = logging.FileHandler(filename="logs/pagerLog.txt")
localHandler.setFormatter(formatter)

# logger.addHandler(pTrlHandler)
logger.addHandler(localHandler)

# disables logging when uncommented
# logging.disable(logging.CRITICAL)


def dict_deep_copy(
    dict_to_copy_from: dict, dict_to_copy_to: dict, num_of_copies: int, start_index: int
):
    """Makes a deep copy of the dict. Each page is a dict and each button is a dict.
    A deep copy of the dicts are necessary so that they can be completly independent."""
    for i, (key, value) in enumerate(dict_to_copy_to.items()):
        if i == num_of_copies + start_index:
            break
        if i >= start_index:
            dict_to_copy_to[key] = copy.deepcopy(dict_to_copy_from)


def button_title_update(
    page_dict: dict,
    num_of_iterations: int,
    start_index: int,
    button_title: Union[int, str] = 1,
):
    """Updates the button titles"""
    for i, (key, value) in enumerate(page_dict.items()):
        if i == num_of_iterations + start_index:
            break
        if i >= start_index:
            button_title = str(button_title)
            page_dict[key]["text"] = button_title
            try:
                button_title = int(button_title)
                button_title += 1
                button_title = str(button_title)
            except ValueError:
                logger.info(
                    "Unable to increment the button title becuase it is not an int."
                )


def button_action_update(
    page_dict: dict,
    num_of_iterations: int,
    start_index: int,
    script_id_start: int,
    script_cue: int,
):
    """
    Updates the actions of multiple buttons and iterates up the RegisterID to
    match the appropriatebutton number.

    :pageDict: The dict of the page to update buttons on.
    :numOfIterations: The number of buttons to update.
    :startIndex: The index of the button to start on.
    This allows updating only a few buttons on the page.
    :scriptIdStart: The script ID to start with.
    :scriptCue: The scriptCue to put in each preset. 1=Program 0=Preview
    """
    for i, (key, value) in enumerate(page_dict.items()):
        if i == num_of_iterations + int(start_index):
            break
        if i >= int(start_index):
            if isinstance(value, dict) and "options" in value:
                value["options"]["sidx"] = str(script_id_start)
                value["options"]["cidx"] = str(script_cue)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "options" in item:
                        item["options"]["sidx"] = str(script_id_start)
                        item["options"]["cidx"] = str(script_cue)
            else:
                logger.warning(f"Unexpected structure for key {key}: {value}")
            strt_idx = int(script_id_start)
            strt_idx += 1
            script_id_start = str(strt_idx)


def update_page_title(full_dict: dict, page_num: str, page_title: str) -> None:
    """
    Updates the page title of the designated button page.

    :fullDict: The base-level dict of the config (the full config dict)
    :pageNum: The page to update. Needs to be a string e.g. '1'.
    :pageTitle: The string of the new page title.
    """
    if "pages" in full_dict:
        full_dict["pages"][page_num]["name"] = page_title
    else:
        logger.warning(
            f"'pages' key not found in the config. Unable to update page title"
            f" for page {page_num}"
        )


logger.info(" ***** Start of program ***** ")


# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the config file
READ_CONFIG_FILE = os.path.join(
    current_dir,
    "..",
    "example config files for ref",
    "reset_template_ready_for_python.companionconfig",
)

WRITE_CONFIG_FILE = os.path.join(
    current_dir, "..", "outputs", "python_updated.companionconfig"
)


def load_json_as_dict(file_path: str) -> Dict[str, Any]:
    """
    Load a JSON file and return its contents as a dict.

    Args:
        file_path (str): The file path to the JSON file

    Returns:
        Dict[str, Any]: The contents of the JSON file as a dict

    Raises:
        FileNotFoundError: If the specified file is not found
        json.JSONDecodeError: If the file contains invalid JSON
    """
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        logger.error(f"Current working directory: {os.getcwd()}")
        logger.error(f"Directory contents: {os.listdir(os.path.dirname(file_path))}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in file: {file_path}")
        raise


def increment_button_text(text, increment_by=1):
    """Increment the number in the button text by the specified amount."""

    def increment(match):
        return str(int(match.group(0)) + increment_by)

    return re.sub(r"\d+", increment, text)


def copy_and_increment_buttons(controls, row, start_col, end_col):
    for i in range(start_col, end_col + 1):
        controls[str(row)][str(i)] = copy.deepcopy(controls[str(row)]["0"])

        # Update the button text
        if (
            "style" in controls[str(row)][str(i)]
            and "text" in controls[str(row)][str(i)]["style"]
        ):
            old_text = controls[str(row)][str(i)]["style"]["text"]
            new_text = increment_button_text(old_text, i)
            controls[str(row)][str(i)]["style"]["text"] = new_text
            logger.info(
                f"Updated button {row}/{i} text from '{old_text}' to '{new_text}'"
            )

        # Update the action if it exists
        if (
            "steps" in controls[str(row)][str(i)]
            and "0" in controls[str(row)][str(i)]["steps"]
        ):
            steps = controls[str(row)][str(i)]["steps"]["0"]
            if "action_sets" in steps and "down" in steps["action_sets"]:
                for action in steps["action_sets"]["down"]:
                    if "options" in action and "sidx" in action["options"]:
                        action["options"]["sidx"] = str(
                            int(action["options"]["sidx"]) + i
                        )


def main() -> None:
    """The main function"""
    data = load_json_as_dict(READ_CONFIG_FILE)
    logger.debug(f'dict test "version" = {data["version"]}')

    if (
        "pages" not in data
        or "1" not in data["pages"]
        or "controls" not in data["pages"]["1"]
    ):
        logger.error("Expected structure not found in the config file")
        return

    controls = data["pages"]["1"]["controls"]

    # Check if buttons 0/0 and 1/0 exist
    for row in ["0", "1"]:
        if row not in controls or "0" not in controls[row]:
            logger.error(f"Button {row}/0 not found in the configuration")
            return

    # Copy buttons
    copy_and_increment_buttons(controls, 0, 1, 7)  # Row 0, columns 1-7
    copy_and_increment_buttons(controls, 1, 1, 7)  # Row 1, columns 1-7

    # Update page title
    update_page_title(data, "1", "Core Presets")

    # Create JSON from dict
    new_json = json.dumps(data, indent=2)

    # Ensure the output directory exists
    output_dir = os.path.dirname(WRITE_CONFIG_FILE)
    os.makedirs(output_dir, exist_ok=True)

    # Write to new file
    try:
        with open(WRITE_CONFIG_FILE, "w", encoding="utf-8") as new_f:
            new_f.write(new_json)
        logger.info(f"Successfully wrote updated config to {WRITE_CONFIG_FILE}")
    except IOError as e:
        logger.error(f"Error writing to file {WRITE_CONFIG_FILE}: {e}")


if __name__ == "__main__":
    main()

logger.debug("***** LAST LINE *****\n")
