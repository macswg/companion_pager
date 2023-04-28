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


def dictDeepCopy(dictToCopyFrom: dict, dictToCopyTo: dict, numOfCopies: int, startIndex: int):
    for i, (key, value) in enumerate(dictToCopyTo.items()):
        if i == numOfCopies + startIndex:
            break
        if i >= startIndex:
            dictToCopyTo[key] = copy.deepcopy(dictToCopyFrom)


def buttonTitleUpdate(pageDict: dict, numOfIterations: int, startIndex: int, buttonTitle: int or str = 1):
    for i, (key, value) in enumerate(pageDict.items()):
        if i == numOfIterations + startIndex:
            break
        if i >= startIndex:
            buttonTitle = str(buttonTitle)
            pageDict[key]['text'] = buttonTitle
            try:
                buttonTitle = int(buttonTitle)
                buttonTitle += 1
                buttonTitle = str(buttonTitle)
            except ValueError:
                logger.info('Unable to increment the button title becuase it is not an int.')


def buttonActionUpdate(pageDict: dict, numOfIterations: int, startIndex: int, scriptIdStart: int, scriptCue: int):
    '''
    Updates the actions of multiple buttons and iterates up the RegisterID to match the appropriate
    button number.

    :pageDict: The dict of the page to update buttons on.
    :numOfIterations: The number of buttons to update.
    :startIndex: The index of the button to start on. This allows updating only a few buttons on the page.
    :scriptIdStart: The script ID to start with.
    :scriptCue: The scriptCue to put in each preset. 1=Program 0=Preview
    '''
    for i, (key, value) in enumerate(pageDict.items()):
        if i == numOfIterations + int(startIndex):
            break
        if i >= int(startIndex):
            for i in pageDict[key]:
                i['options']['sidx'] = str(scriptIdStart)
                i['options']['cidx'] = str(scriptCue)
            strtIdx = int(scriptIdStart)
            strtIdx += 1
            scriptIdStart = str(strtIdx)


def updatePageTitle(fullDict: dict, pageNum: str, pageTitle: str):
    '''
    Updates the page title of the designated button page.

    :fullDict: The base-level dict of the config (the full config dict)
    :pageNum: The page to update. Needs to be a string e.g. '1'.
    :pageTitle: The string of the new page title.
    '''
    fullDict['page'][pageNum]['name'] = pageTitle


logger.info(' ***** Start of program ***** ')

read_config_file = 'example config files for ref/SpyderStartPage.companionconfig'
write_config_file = 'python_updated.companionconfig'
# dict variables


with open(read_config_file, "r") as f:
    readFile = f.readlines()
# convert list to string for JSON import
strForJson = readFile[0]
# import JSON to python dicts
fullConfigDict = json.loads(strForJson)


# dict of page 1 configs
p1Buttons = fullConfigDict['config']['1']

# individual button style
configOrigPgm = fullConfigDict['config']['1']['1']
configOrigPst = fullConfigDict['config']['1']['9']

#
#
# variables to update to make the script easier to change
updatePageTitle(fullConfigDict, '1', 'Core Presets (2)')

sBtnR1 = 0  # button start index on row 1; norm=0
sBtnR2 = 8  # button start index on row 2; norm=8
sBtnR3 = 16  # button start index on row 3; norm=16
sBtnR4 = 24  # button start index on row 4; norm=24

nBtsR1 = 8  # number of copies to make on row 1; norm=8
nBtsR2 = 8  # number of copies to make on row 2; norm=8
nBtsR3 = 4  # number of copies to make on row 3; norm=4
nBtsR4 = 4  # number of copies to make on row 4; norm=4

sIndxR1 = 0  # script ID start number on row 1; norm=0
sIndxR2 = 0  # script ID start number on row 2; norm=0
sIndxR3 = 8  # script ID start number on row 3; norm=8
sIndxR4 = 8  # script ID start number on row 4; norm=8

bTtlsR1 = 1  # button title (if using numbers) to start with on row 1; norm=1
bTtlsR2 = 1  # button title (if using numbers) to start with on row 2: norm=1
bTtlsR3 = 9  # button title (if using numbers) to start with on row 3; norm=R1+9
bTtlsR4 = 9  # button title (if using numbers) to start with on row 4; norm=R1+9
#
#

# deep copy action dicts from first in example file to to other buttons
dictDeepCopy(configOrigPgm, p1Buttons, nBtsR1, sBtnR1)
dictDeepCopy(configOrigPst, p1Buttons, nBtsR2, sBtnR2)
dictDeepCopy(configOrigPgm, p1Buttons, nBtsR3, sBtnR3)
dictDeepCopy(configOrigPst, p1Buttons, nBtsR4, sBtnR4)

# update button titles
buttonTitleUpdate(p1Buttons, nBtsR1, sBtnR1, bTtlsR1)
buttonTitleUpdate(p1Buttons, nBtsR2, sBtnR2, bTtlsR2)
buttonTitleUpdate(p1Buttons, nBtsR3, sBtnR3, bTtlsR3)
buttonTitleUpdate(p1Buttons, nBtsR4, sBtnR4, bTtlsR4)

#
# actions
#
# dict of page 1 actions
p1Actions = fullConfigDict['actions']['1']

# individual button actions
actionOrigPgm = p1Actions['1']
actionOrigPst = p1Actions['9']

# deep copy action dicts from first in example file to to other buttons
dictDeepCopy(actionOrigPgm, p1Actions, nBtsR1, sBtnR1)
dictDeepCopy(actionOrigPst, p1Actions, nBtsR2, sBtnR2)
dictDeepCopy(actionOrigPgm, p1Actions, nBtsR3, sBtnR3)
dictDeepCopy(actionOrigPst, p1Actions, nBtsR4, sBtnR4)

# update button actions
buttonActionUpdate(p1Actions, nBtsR1, sBtnR1, sIndxR1, 1)  # Script Cue at 1 for PGM
buttonActionUpdate(p1Actions, nBtsR2, sBtnR2, sIndxR2, 0)  # Script Cue at 0 for PVW
buttonActionUpdate(p1Actions, nBtsR3, sBtnR3, sIndxR3, 1)  # Script Cue at 1 for PGM
buttonActionUpdate(p1Actions, nBtsR4, sBtnR4, sIndxR4, 0)  # Script Cue at 0 for PVW

#
# create JSON from dict
newJSON = json.dumps(fullConfigDict)

# writes to new file
with open(write_config_file, 'w') as newF:
    newF.write(newJSON)


logging.debug('***** LAST LINE *****')
