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


# TODO: update function to add button index (which will match the title not the companion button index)
def buttonActionUpdate(pageDict: dict, numOfIterations: int, startIndex: int, scriptCue: int):
    '''
    Updates the actions of multiple buttons and iterates up the RegisterID to match the appropriate
    button number.

    :pageDict: The dict of the page to update buttons on.
    :numOfIterations: The number of buttons to update. 
    :startIndex: The index of the button to start on. This allows updating only a few buttons on the page.
    :scriptCue: The scriptCue to put in each preset. 1=Program 0=Preview
    '''
    for i, (key, value) in enumerate(pageDict.items()):
        if i == numOfIterations + int(startIndex):
            break
        if i >= int(startIndex):
            for i in pageDict[key]:
                i['options']['sidx'] = startIndex
                i['options']['cidx'] = str(scriptCue)
            sID = int(startIndex)
            sID += 1
            startIndex = str(sID)



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

# make deep copy of dict of button '1' to subsequent buttons
dictDeepCopy(configOrigPgm, p1Buttons, 7, 1)
dictDeepCopy(configOrigPst, p1Buttons, 7, 9)
dictDeepCopy(configOrigPgm, p1Buttons, 4, 16)
dictDeepCopy(configOrigPst, p1Buttons, 4, 24)

# update button titles
buttonTitleUpdate(p1Buttons, 8, 0, 1)
buttonTitleUpdate(p1Buttons, 8, 8, 1)
buttonTitleUpdate(p1Buttons, 4, 16, 9)
buttonTitleUpdate(p1Buttons, 4, 24, 9)


#
# actions
#

# dict of page 1 actions
p1Actions = fullConfigDict['actions']['1']

# individual button actions
actionOrigPgm = p1Actions['1']
actionOrigPst = p1Actions['9']

# deep copy action dicts from first button to other buttons
dictDeepCopy(actionOrigPgm, p1Actions, 7, 1)
dictDeepCopy(actionOrigPst, p1Actions, 7, 9)
dictDeepCopy(actionOrigPgm, p1Actions, 4, 16)
dictDeepCopy(actionOrigPst, p1Actions, 4, 24)

# update button actions
buttonActionUpdate(p1Actions, 7, 0, 1) # Script Cue at 1 for PGM
buttonActionUpdate(p1Actions, 7, 0, 0) # Script Cue at 0 for PVW
buttonActionUpdate(p1Actions, 4, 16, 1) # Script Cue at 1 for PGM
buttonActionUpdate(p1Actions, 4, 24, 0) # Script Cue at 0 for PVW


# jsonActions = json.dumps(p1Actions, indent=4)
# logger.debug(f'p1Actions = {jsonActions}')


# buttonId = '1'
# for i, (key, value) in enumerate(p1Buttons.items()):
#     if i == 7:
#         break
#     p1Buttons[key]['text'] = buttonTitle
#     buttonTitle = int(buttonTitle)
#     buttonTitle += 1
#     buttonTitle = str(buttonTitle)

# for key, subdict in p1Buttons.items():
#     intId = int(buttonId)
#     intId += 1
#     newId = str(intId)
#     for i in range(5):
#         p1Buttons[key]['text'] = newId

# p1Buttons['2']['text'] = '2'
# p1Buttons['3']['text'] = '3'

# # all instances
# instDict = fullConfigDict['instances']
# # print(type(ogDict))
# jsonData6 = json.dumps(instDict, indent=2)
# logging.debug(jsonData6)

# # actions
# actDict = fullConfigDict['actions']['1']['1']
# actListLabel, actListInst = actDict[0]['label'], actDict[0]['instance']
# jsonData7 = json.dumps(actListLabel, indent=2)
# jsonData8 = json.dumps(actListInst, indent=2)
# logging.debug(jsonData7)

# open new file and write updated JSON
# with open(write_config_file) as newF:
#     readNewFile = newF.readlines()
# newStrForJson = readNewFile[0]
# newConfigDict = json.loads(newStrForJson)
# newConfigDict['config']['1']['1'] = ogDict


# print(writeFile)
# updatedStrForJson = writeFile[0]
# newDict = json.loads(updatedStrForJson)
# newDict['config']['1']['1'] = ogDict

# updateStyle = newDict['config']['1']['1']
# updateStyle = ogDict

# print(type(updatedStrForJson[0]))

# print(type(newDict))


newJSON = json.dumps(fullConfigDict)

# writes to new file
with open(write_config_file, 'w') as newF:
    newF.write(newJSON)


logging.debug('***** LAST LINE *****')
