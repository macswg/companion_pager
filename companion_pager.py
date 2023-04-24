#! python3
# companion_pager.py

# Python script to update companion buttons

import json
import copy
import logging
from logging.handlers import SysLogHandler


PAPERTRAIL_HOST = "logs5.papertrailapp.com"
PAPERTRAIL_PORT = 54000
APP_NAME = "companion_pager.py"

# creates logger and sets logger level
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# creates handler for online logging and sets handler format
handler = SysLogHandler(address=(PAPERTRAIL_HOST, PAPERTRAIL_PORT))
format = f'{APP_NAME}: %(message)s'
formatter = logging.Formatter(format)
handler.setFormatter(formatter)

# creates handler for local logging and sets handler format
# handlerLocal = logging.FileHandler(filename='pagerLog.txt')
# formatLocal = '%(asctime)s - %(levelname)s - %(message)s'
# formatterLocal = logging.Formatter(formatLocal)
# handlerLocal.setFormatter(formatterLocal)

logger.addHandler(handler)

# logging.basicConfig(
    # filename='pagerLog.txt',
    # level=logging.DEBUG,
    # format=' %(asctime)s - %(levelname)s - %(message)s',
# )

# disables logging when uncommented
# logging.disable(logging.CRITICAL)
# logging.debug(' Start of program')

logger.info(' ***** Start of program ***** ')

# read_config_file = 'example config files for ref/newPage_1button2023.companionconfig'
# temp read file for viewing:
read_config_file = 'example config files for ref/Coachella_NUC-Spy-Green_full-config_20230412-1705.companionconfig'
write_config_file = 'python_updated.companionconfig'
# dict variables


with open(read_config_file, "r") as f:
    readFile = f.readlines()
# convert list to string for JSON import
strForJson = readFile[0]
# import JSON to python dicts
fullConfigDict = json.loads(strForJson)


# individual button style dict
# ['config']['page']['button']
configOrig = fullConfigDict['config']['1']['1']

# button actions list
# ['actions']['page']['button']
actionsOrig = fullConfigDict['actions']['1']['1']
# print(f' ActionsOrig Type = {type(actionsOrig)}')
# actionsList = actionsOrig
# actionsListDict = actionsList[0]




#
# update config with new items here
fullConfigDict['config']['1']['2'] = copy.deepcopy(configOrig)



newJSON = json.dumps(fullConfigDict)


# writes to new file
with open(write_config_file, 'w') as newF:
    newF.write(newJSON)


logger.debug('***** LAST LINE *****')
