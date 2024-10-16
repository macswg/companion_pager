#! python3i
"""Module updates the companion config so that it has Sean's standard
Navigation buttons."""
# companion_navUpdate.py

# Python script to update nav buttons on all pages of the companion config
# I do not believe this needs to be run if starting a new config

import json
import logging

PAPERTRAIL_HOST = "logs5.papertrailapp.com"
PAPERTRAIL_PORT = 54000
APP_NAME = "companion_navUpdate.py"

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


def make_nav_buttons(full_dict: dict):
    """Function makes Sean's standard navigation buttons"""
    page_config_dict = full_dict["config"]
    for i, (key, value) in enumerate(page_config_dict.items()):
        # logger.debug(f'FullDict = {fullDict[key]}')
        page_config_dict[key]["24"]["style"] = "pageup"
        page_config_dict[key]["31"]["style"] = "pagenum"
        page_config_dict[key]["32"]["style"] = "pagedown"


logger.info(" ***** Start of program ***** ")

READ_CONFIG_FILE = "example config files for ref/SpyderStartPage.companionconfig"
WRITE_CONFIG_FILE = "python_nav_updated.companionconfig"

with open(READ_CONFIG_FILE, "r", encoding="utf-8") as f:
    readFile = f.readlines()
# convert list to string for JSON import
strForJson = readFile[0]
# import JSON to python dicts
fullConfigDict = json.loads(strForJson)

#
# Update nav buttons on all pages
make_nav_buttons(fullConfigDict)

#
# create JSON from dict
newJSON = json.dumps(fullConfigDict)

# writes to new file
with open(WRITE_CONFIG_FILE, "w", encoding="utf-8") as newF:
    newF.write(newJSON)


logging.debug("***** LAST LINE *****\n")
