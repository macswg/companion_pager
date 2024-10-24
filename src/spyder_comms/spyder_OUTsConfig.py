#!/usr/bin/env python3
# spyder_query_scratch.py

# Python script to read Spyder presets from an X80 and add the preset IDs and names to Google Sheet

# import binascii
import socket

# import pygsheets
import logging
from logging.handlers import SysLogHandler
import os
from typing import Any, List

PAPERTRAIL_HOST = "logs5.papertrailapp.com"
PAPERTRAIL_PORT = 54000
APP_NAME = "spyder_query_presets.py"
UDP_IP = "10.211.55.3"
UDP_PORT = 11116
BUFFER_SIZE = 1024


def setup_logging():
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)

    pTrlHandler = SysLogHandler(address=(PAPERTRAIL_HOST, PAPERTRAIL_PORT))
    pTrlHandler.setFormatter(logging.Formatter(f"{APP_NAME}: %(message)s"))

    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
    )
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "py_packet_senders_Log.txt")
    localHandler = logging.FileHandler(filename=log_file)
    localHandler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )

    logger.addHandler(pTrlHandler)
    logger.addHandler(localHandler)

    return logger


logger = setup_logging()


def spyder_message(message):
    SPYDER_HEADER = "spyder\00\00\00\00"
    return (SPYDER_HEADER + message).encode("utf-8")


def resp_code_parse(resp_code):
    responses = {
        "0": "Success - The command was successfully processed.",
        "1": "Empty - The data requested is not available.",
        "2": "Header - An invalid command was specified",
        "3": "Argument count - The command is missing the required minimum number of arguments.",
        "4": "Argument value - One or more arguments of the command were invalid.",
        "5": "Execution - An error occurred while processing the command. Check alert viewer.",
        "6": "Checksum - Reserved",
    }
    return f"{resp_code} = {responses.get(resp_code, 'Unknown response code')}"


def replace_space(strings):
    return [s.replace("%20", " ") for s in strings]


def create_spyder_command(cmd, *args):
    return spyder_message(f"{cmd} {' '.join(map(str, args))}")


def send_spyder_message(msg: str, *args: Any) -> List[str]:
    """
    Send a Spyder command message and receive the response.

    This function creates a Spyder command, sends it via UDP, and processes the response.

    Args:
        msg (str): The Spyder command to send.
        *args: Variable length argument list for additional command parameters.

    Returns:
        List[str]: A list of parsed message elements from the Spyder response.

    Side effects:
        - Logs debug information about the sent message and response code.
        - Sends a UDP message to the globally defined UDP_IP and UDP_PORT.
        - Receives data from the UDP socket.

    Note:
        This function relies on global variables UDP_IP, UDP_PORT, and BUFFER_SIZE.
        It also uses external functions create_spyder_command, replace_space, and
        resp_code_parse.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        message: bytes = create_spyder_command(msg, *args)
        logger.debug(f"message is = {message}")
        s.sendto(message, (UDP_IP, UDP_PORT))
        data: bytes = s.recv(BUFFER_SIZE)
        received_message: str = data.decode("utf-8")
        res_code: str = received_message[0:1]
        msg_rcvd: List[str] = received_message[2:].split(" ")
        parsed_message: List[str] = replace_space(msg_rcvd)
        logger.debug(f"response code = {resp_code_parse(res_code)}")
        print(f"message = {message}")
        return res_code, parsed_message
        # return res_code


def calc_16x9_size(width):
    height = width * 9 / 16
    return int(height)


def main():
    logger.info("***** Start of program ***** ")
    res_code, parsed_message = send_spyder_message(
        "OSP",
        0,
        # "Name", "PYname25",
        "Mode",
        "Normal",
        "HActive",
        3840,
        "VActive",
        2160,
        "RefreshRate",
        "FR_59_94",
        "IsInterlaced",
        "False",
        "Colorspace",
        2,
        "Chroma",
        1,
        "ColorRange",
        "Limited",
        "Connector",
        "SDI",
        "SDIMode",
        0,
    )
    print(f"Response code: {res_code}, parsed message: {parsed_message}")
    print(resp_code_parse(res_code))

    # Output Get Properties
    # res_code, parsed_message = send_spyder_message("OGP", 0)
    # print(f"Response code: {res_code}, parsed message: {parsed_message}")
    # print(resp_code_parse(res_code))

    logger.info("***** End of program *****")


if __name__ == "__main__":
    main()
