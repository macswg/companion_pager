#! python3
# companion_pager.py

# Python script to update companion buttons

import copy
import json
import logging

# from logging.handlers import SysLogHandler


PAPERTRAIL_HOST = "logs5.papertrailapp.com"
PAPERTRAIL_PORT = 54000
APP_NAME = "companion_pager.py"

# creates logger and sets logger level
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# creates handler for online logging and sets handler format
# pTrlHandler = SysLogHandler(address=(PAPERTRAIL_HOST, PAPERTRAIL_PORT))
format = f"{APP_NAME}: %(message)s"
formatter = logging.Formatter(format)
# pTrlHandler.setFormatter(formatter)

# creates handler for local logging and sets handler format
localHandler = logging.FileHandler(filename="logs/pagerLog.txt")
# formatLocal = '%(asctime)s - %(levelname)s - %(message)s'
# formatterLocal = logging.Formatter(formatLocal)
localHandler.setFormatter(formatter)

# logger.addHandler(pTrlHandler)
logger.addHandler(localHandler)

# disables logging when uncommented
# logging.disable(logging.CRITICAL)
# logging.debug(' Start of program')


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
    button_title: int or str = 1,
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
    Updates the actions of multiple buttons and iterates up the RegisterID to match the appropriate
    button number.

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
            for i in page_dict[key]:
                i["options"]["sidx"] = str(script_id_start)
                i["options"]["cidx"] = str(script_cue)
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
    full_dict["page"][page_num]["name"] = page_title


logger.info(" ***** Start of program ***** ")


READ_CONFIG_FILE = (
    "example config files for ref/ready_for_python_update.companionconfig"
)

WRITE_CONFIG_FILE = "outputs/python_updated.companionconfig"
# dict variables


def main() -> None:
    """The main function"""
    with open(READ_CONFIG_FILE, "r", encoding="utf-8") as f:
        read_file = f.readlines()
    # convert list to string for JSON import
    str_for_json = read_file[0]
    # import JSON to python dicts
    full_config_dict = json.loads(str_for_json)

    # dict of page 1 configs
    p1_buttons = full_config_dict["config"]["1"]

    # individual button style
    config_orig_pgm = full_config_dict["config"]["1"]["1"]
    config_orig_pst = full_config_dict["config"]["1"]["9"]

    #
    #
    # variables to update to make the script easier to change
    update_page_title(full_config_dict, "1", "Core Presets (2)")

    s_btn_r1 = 0  # button start index on row 1; norm=0
    s_btn_r2 = 8  # button start index on row 2; norm=8
    s_btn_r3 = 16  # button start index on row 3; norm=16
    s_btn_r4 = 24  # button start index on row 4; norm=24

    n_bts_r1 = 8  # number of copies to make on row 1; norm=8
    n_bts_r2 = 8  # number of copies to make on row 2; norm=8
    n_bts_r3 = 4  # number of copies to make on row 3; norm=4
    n_bts_r4 = 4  # number of copies to make on row 4; norm=4

    s_indx_r1 = 0  # script ID start number on row 1; norm=0
    s_indx_r2 = 0  # script ID start number on row 2; norm=0
    s_indx_r3 = 8  # script ID start number on row 3; norm=8
    s_indx_r4 = 8  # script ID start number on row 4; norm=8

    b_ttls_r1 = 1  # button title (if using numbers) to start with on row 1; norm=1
    b_ttls_r2 = 1  # button title (if using numbers) to start with on row 2: norm=1
    b_ttls_r3 = 9  # button title (if using numbers) to start with on row 3; norm=R1+9
    b_ttls_r4 = 9  # button title (if using numbers) to start with on row 4; norm=R1+9
    #
    #

    # deep copy action dicts from first in example file to to other buttons
    dict_deep_copy(config_orig_pgm, p1_buttons, n_bts_r1, s_btn_r1)
    dict_deep_copy(config_orig_pst, p1_buttons, n_bts_r2, s_btn_r2)
    dict_deep_copy(config_orig_pgm, p1_buttons, n_bts_r3, s_btn_r3)
    dict_deep_copy(config_orig_pst, p1_buttons, n_bts_r4, s_btn_r4)

    # update button titles
    button_title_update(p1_buttons, n_bts_r1, s_btn_r1, b_ttls_r1)
    button_title_update(p1_buttons, n_bts_r2, s_btn_r2, b_ttls_r2)
    button_title_update(p1_buttons, n_bts_r3, s_btn_r3, b_ttls_r3)
    button_title_update(p1_buttons, n_bts_r4, s_btn_r4, b_ttls_r4)

    #
    # actions
    #
    # dict of page 1 actions
    p1_actions = full_config_dict["actions"]["1"]

    # individual button actions
    action_orig_pgm = p1_actions["1"]
    action_orig_pst = p1_actions["9"]

    # deep copy action dicts from first in example file to to other buttons
    dict_deep_copy(action_orig_pgm, p1_actions, n_bts_r1, s_btn_r1)
    dict_deep_copy(action_orig_pst, p1_actions, n_bts_r2, s_btn_r2)
    dict_deep_copy(action_orig_pgm, p1_actions, n_bts_r3, s_btn_r3)
    dict_deep_copy(action_orig_pst, p1_actions, n_bts_r4, s_btn_r4)

    # update button actions
    button_action_update(
        p1_actions, n_bts_r1, s_btn_r1, s_indx_r1, 1
    )  # Script Cue at 1 for PGM
    button_action_update(
        p1_actions, n_bts_r2, s_btn_r2, s_indx_r2, 0
    )  # Script Cue at 0 for PVW
    button_action_update(
        p1_actions, n_bts_r3, s_btn_r3, s_indx_r3, 1
    )  # Script Cue at 1 for PGM
    button_action_update(
        p1_actions, n_bts_r4, s_btn_r4, s_indx_r4, 0
    )  # Script Cue at 0 for PVW

    #
    # create JSON from dict
    new_json = json.dumps(full_config_dict)

    # writes to new file
    with open(WRITE_CONFIG_FILE, "w", encoding="utf-8") as new_f:
        new_f.write(new_json)


if __name__ == "__main__":
    main()

logging.debug("***** LAST LINE *****\n")
