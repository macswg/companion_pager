#!/usr/bin/env python3
# spyder_query_presets_toGglSht.py

import socket
import os
import logging
from logging.handlers import SysLogHandler
import pygsheets
import pandas as pd

PAPERTRAIL_HOST = "logs5.papertrailapp.com"
PAPERTRAIL_PORT = 54000
APP_NAME = "spyder_query_presets.py"
UDP_IP = "10.211.55.3"
UDP_PORT = 11116
BUFFER_SIZE = 1024

# Create an empty DataFrame
df = pd.DataFrame(columns=["Page", "RegisterID", "Name"])


def setup_logging():
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)

    # Papertrail handler
    pTrlHandler = SysLogHandler(address=(PAPERTRAIL_HOST, PAPERTRAIL_PORT))
    pTrlHandler.setFormatter(logging.Formatter(f"{APP_NAME}: %(message)s"))

    # Local file handler
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
    return f"spyder\00\00\00\00{message}".encode("utf-8")


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


def g_sht_open(client, gSheet, wrksheet):
    return client.open(gSheet).worksheet_by_title(wrksheet)


def send_spyder_message(cmd, regTp, pgNm, sInx, mxC, chr):
    message = spyder_message(f"{cmd} {regTp} {pgNm} {sInx} {mxC} {chr}")
    logger.debug(f"message sent = {message}")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(message, (UDP_IP, UDP_PORT))
        data = s.recv(BUFFER_SIZE)

    return data.decode("utf-8")


def parse_received_message(received_message):
    resCode, *messageBody = received_message.split(" ")
    returnCount = ["Return Count", messageBody[0]]
    msgRcvd = messageBody[1:]

    logger.debug(f"returnCount = {returnCount}")
    logger.debug(f"message received = {received_message}")

    return resCode, returnCount, msgRcvd


def create_preset_list(parsedMessage):
    gList = [
        [int(parsedMessage[i]), parsedMessage[i + 1]]
        for i in range(0, len(parsedMessage) - 1, 2)
    ]
    existing_indexes = set(x[0] for x in gList)

    min_index, max_index = min(existing_indexes), max(existing_indexes)
    gList.extend(
        [i, "---"] for i in range(min_index, max_index + 1) if i not in existing_indexes
    )
    gList.sort()

    return gList


def update_google_sheet(df):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.join(
        current_dir,
        "..",
        "..",
        "secret",
        "credentials_python-int-2023-2e89fbfc8ab6.json",
    )

    client = pygsheets.authorize(service_file=credentials_path)
    wks = g_sht_open(client, "SpyderPresets_iHeartFiesta2024", "SpyderPresets")

    wks.clear()

    # Handle NaN values and infer objects
    pd.set_option("future.no_silent_downcasting", True)
    df = df.fillna(pd.NA).infer_objects(copy=False)

    wks.set_dataframe(df, start="A1", copy_head=True)


def query_spyder_presets(df, cmd="RRL", regTp=4, sInx=0, mxC=50, chr=30, pgNm=0):
    message = spyder_message(f"{cmd} {regTp} {pgNm} {sInx} {mxC} {chr}")
    logger.debug(f"message sent = {message}")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(message, (UDP_IP, UDP_PORT))
        data = s.recv(BUFFER_SIZE)

    received_message = data.decode("utf-8")
    resCode, *messageBody = received_message.split(" ")
    returnCount = ["Return Count", messageBody[0]]
    msgRcvd = messageBody[1:]

    logger.debug(f"returnCount = {returnCount}")
    logger.debug(f"message received = {received_message}")

    parsedMessage = replace_space(msgRcvd)
    gList = [
        [int(parsedMessage[i]), parsedMessage[i + 1]]
        for i in range(0, len(parsedMessage) - 1, 2)
    ]
    existing_indexes = set(x[0] for x in gList)

    try:
        min_index, max_index = min(existing_indexes), max(existing_indexes)
        gList.extend(
            [i, "---"]
            for i in range(min_index, max_index + 1)
            if i not in existing_indexes
        )
        gList.sort()

        new_df = pd.DataFrame(gList, columns=["RegisterID", "Name"])
        new_df["Page"] = pgNm  # Add the Page column with pgNm value
        df = (
            pd.concat([df, new_df])
            .drop_duplicates(subset=["Page", "RegisterID"], keep="last")
            .sort_values(["Page", "RegisterID"])
            .reset_index(drop=True)
        )

    except ValueError:
        error_message = f"\nValue Error - The page may not exist\nSpyder response {resp_code_parse(resCode)}\n"
        print(error_message)
        raise ValueError(error_message)
    except NameError:
        print(f"Name Error - Spyder response {resp_code_parse(resCode)}")

    logger.info(f"response code: {resp_code_parse(resCode)}")
    logger.info(f"Return count: {returnCount}")
    logger.info(f"Page Number: {pgNm}")

    return df


def query_spyder_presets_all_pages(df):
    pgNm = 0
    while True:
        try:
            df = query_spyder_presets(df, pgNm=pgNm)
            pgNm += 1
        except ValueError:
            break
    return df


def main():
    logger.info("***** Start of program ***** ")
    global df

    # Query all Spyder presets
    df = query_spyder_presets_all_pages(df)

    update_google_sheet(df)
    logger.info("***** LAST LINE *****\n")


if __name__ == "__main__":
    main()
