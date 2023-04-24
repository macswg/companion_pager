#! python3
# dictTester.py

# Python script to test interacting with dicts

import copy
import json
import logging
from logging.handlers import SysLogHandler

PAPERTRAIL_HOST = "logs5.papertrailapp.com"
PAPERTRAIL_PORT = 54000
APP_NAME = "dictTester.py"

# creates logger and sets logger level
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# creates handler for online logging and sets handler format
handler = SysLogHandler(address=(PAPERTRAIL_HOST, PAPERTRAIL_PORT))
format = f'{APP_NAME}: %(message)s'
formatter = logging.Formatter(format)
handler.setFormatter(formatter)

logger.addHandler(handler)

logger.info(' **************************** ')
logger.info(' ***** START OF PROGRAM ***** ')

# create an empty dict
mainDict = {}

# define keys for the main dict
keys = ['1', '2', '3', '4', '5']

for key in keys:
    # Create a sub-dictionary for each key
    subDict = {}
#     # add 5 nested keys to the sub-dictionary
#     for i in range(1, 6):
#         subDict[f'subKey{i}'] = f'subValue{i}'
#     # add the sub-dictionary as a value to the main dictionary
    mainDict[key] = subDict

subDict = {}
# add 5 nested keys to the sub-dictionary
for i in range(1, 6):   
    subDict[f'subKey{i}'] = f'subValue{i}'

mainDict['1'] = subDict

# convert the dict to JSON string to print pretty
jsonDict = json.dumps(mainDict, indent=4)

# print the dict to the log
logger.info(f'Dict 1 = {jsonDict}')

# OG item to copy
DictToCopy = mainDict['1'] 

# updating the dict
# copy the dict from item 1 to other items
for key, value in mainDict.items():
    mainDict[key] = copy.deepcopy(DictToCopy)

# update subkey2 in each dict
x = '1'
for key, value in mainDict.items():
    mainDict[key]['subKey2'] = x
    x = int(x)
    x += 1
    x = str(x)

# convert the dict to JSON string to print pretty
jsonDict2 = json.dumps(mainDict, indent=4)
# print the dict to the log
logger.info(f'Dict 1 updated = {jsonDict2}')

logger.info(' ***** END OF PROGRAM ***** ')
