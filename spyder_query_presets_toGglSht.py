#! python3
# spyder_query_scratch.py

# import binascii
import socket
import logging

PAPERTRAIL_HOST = "logs5.papertrailapp.com"
PAPERTRAIL_PORT = 54000
APP_NAME = "spyder_query_presets.py"

# creates logger and sets logger level
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# creates handler for online logging and sets handler format
# pTrlHandler = SysLogHandler(address=(PAPERTRAIL_HOST, PAPERTRAIL_PORT))
format = f'{APP_NAME}: %(message)s'
formatter = logging.Formatter(format)
# pTrlHandler.setFormatter(formatter)

# creates handler for local logging and sets handler format
localHandler = logging.FileHandler(filename='logs/py_packet_senders_Log.txt')
# formatLocal = '%(asctime)s - %(levelname)s - %(message)s'
# formatterLocal = logging.Formatter(formatLocal)
localHandler.setFormatter(formatter)

# logger.addHandler(pTrlHandler)
logger.addHandler(localHandler)

# disables logging when uncommented
# logging.disable(logging.CRITICAL)
# logging.debug(' Start of program')


def spyder_message(message):
    SPYDER_HEADER = 'spyder\00\00\00\00'
    message_joiner = SPYDER_HEADER + message
    return message_joiner.encode('utf-8')


def resp_code_parse(resp_code):
    response = ''
    if resp_code == '0':
        response = '0 = Success - The command was successfully processed.'
    elif resp_code == '1':
        response = '1 = Empty - The data requested is not available.'
    elif resp_code == '2':
        response = '2 = Header - An invalid command was specified'
    elif resp_code == '3':
        response = '3 = Argument count - The command is missing the required minimum number of arguments.'
    elif resp_code == '4':
        response = '4 = Argument value - One or more arguments of the command were invalid.'
    elif resp_code == '5':
        response = '5 = Execution - An error occured while processing the command. Check alert viewer.'
    elif resp_code == '6':
        response = '6 = Checksum - Reserved'
    # elif resp_code == '4':
        # response == '5 = Execution - An error occured while processing the command. Check alert viewer.'
    # elif resp_code == '6':
    #     response == '6 = Checksum - Reserved'
    return (response)


def replace_space(strings: list[str]) -> list[str]:
    """
    Replaces '%20' with ' ' in a list of strings.

    :param strings: A list of strings to process.
    :return: A list of strings with '%20' replaced with ' '.
    """
    new_strings = []
    for s in strings:
        new_s = s.replace('%20', ' ')
        new_strings.append(new_s)
    return new_strings


logger.debug('***** Start of program ***** ')

#
#
# variables to update to easily change request
cmd = 'RRL'  # Spyder command to send
regTp = 4  # register type; command key/script=4
pgNm = 0  # page number; zero-based index
sInx = 0  # start index to begin returning
mxC = 50  # max number of registers to return
chr = 30  # number of characters to truncate names to
#
#

message_to_send = f'{cmd} {regTp} {pgNm} {sInx} {mxC} {chr}'
message = spyder_message(message_to_send)

# sends UDP packet
UDP_IP = '192.168.1.148'
UDP_PORT = 11116
BUFFER_SIZE = 1024
MESSAGE = message

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


#s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#s.connect((UDP_IP, UDP_PORT))

s.sendto(MESSAGE, (UDP_IP, UDP_PORT))

data = s.recv(BUFFER_SIZE)
# s.close()

received_message = data.decode('utf-8')

# logger.debug(f'message = {message}')
# logger.debug(f'received data: {received_message}')

resCode = received_message[0:1]
messageBody = received_message[2:-1].split(' ')
returnCount = messageBody[0]
msgRcvd = messageBody[1:-1]

# replace %20 with spaces
parsedMessage = replace_space(msgRcvd)


logger.debug(f'response code: {resp_code_parse(resCode)}')
logger.debug(f'Return count: {returnCount}')
logger.debug(f'message receeived: {parsedMessage}')

logging.debug('***** LAST LINE *****\n')
