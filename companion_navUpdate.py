#! python3
# companion_navUpdate.py

# Python script to update nav buttons on all pages of the companion config

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
format = f'{APP_NAME}: %(message)s'
formatter = logging.Formatter(format)
# pTrlHandler.setFormatter(formatter)

# creates handler for local logging and sets handler format
localHandler = logging.FileHandler(filename='logs/pagerLog.txt')
# formatLocal = '%(asctime)s - %(levelname)s - %(message)s'
# formatterLocal = logging.Formatter(formatLocal)
localHandler.setFormatter(formatter)

# logger.addHandler(pTrlHandler)
logger.addHandler(localHandler)

# disables logging when uncommented
# logging.disable(logging.CRITICAL)
# logging.debug(' Start of program')


def makeNavButtons(fullDict: dict):
    pageConfigDict = fullDict['config']
    for i, (key, value) in enumerate(pageConfigDict.items()):
        # logger.debug(f'FullDict = {fullDict[key]}')
        pageConfigDict[key]['24']['style'] = 'pageup'
        pageConfigDict[key]['31']['style'] = 'pagenum'
        pageConfigDict[key]['32']['style'] = 'pagedown'


logger.info(' ***** Start of program ***** ')

read_config_file = 'example config files for ref/SpyderStartPage.companionconfig'
write_config_file = 'python_nav_updated.companionconfig'

with open(read_config_file, "r") as f:
    readFile = f.readlines()
# convert list to string for JSON import
strForJson = readFile[0]
# import JSON to python dicts
fullConfigDict = json.loads(strForJson)

#
# Update nav buttons on all pages
makeNavButtons(fullConfigDict)

#
# create JSON from dict
newJSON = json.dumps(fullConfigDict)

# writes to new file
with open(write_config_file, 'w') as newF:
    newF.write(newJSON)


logging.debug('***** LAST LINE *****\n')
