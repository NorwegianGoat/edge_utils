import shutil
import requests
import tarfile
import os
import logging
import sys
import csv
import argparse


class Node:
    # 1478 is the default libp2p port
    def __init__(self, ip: str, id: str, key: str, port: str, bootnode: bool):
        self.ip = ip
        self.id = id
        self.key = key
        self.port = port
        self.bootnode = bootnode

    def is_bootnode(self):
        return self.bootnode

    def get_key(self):
        return self.key

    def get_multiaddr(self):
        return '/ip4/' + self.ip + "/tcp/" + self.port + "/p2p/" + self.id


__URL = "https://github.com/0xPolygon/polygon-edge/releases/download/v0.1.0/polygon-sdk_0.1.0_linux_amd64.tar.gz"
__PATH = "edge"
__SDK_NAME = "polygon-sdk"
__LOG_LEVEL = logging.INFO


def sdk_init():
    # General cleanup if a previous chain exists
    if os.path.exists(__PATH):
        shutil.rmtree(__PATH)
    # Sdk download and extraction
    logging.info("Downloading the SDK.")
    response = requests.get(__URL, stream=True)
    if response.status_code == 200:
        os.makedirs(name="edge", exist_ok=True)
        download_path = os.path.join(__PATH, "edge.tar.gz")
        with open(download_path, "wb") as f:
            f.write(response.content)
        tar = tarfile.open(download_path)
        logging.info("Extracting the SDK.")
        tar.extract(__SDK_NAME, __PATH)
        os.remove(download_path)
        os.chdir(__PATH)
        # SDK init
        logging.info("Generating secrets.")
        command = "./"+__SDK_NAME + " secrets init --data-dir data-dir > node.info"
        os.system(command)
    else:
        exit("Unable to download the SDK. Try again later or check the URL.")


def generate_genesis(node_list_path: str, premine_list_path: str):
    # Read other validators data
    if os.path.exists(node_list_path):
        with open(node_list_path, 'r') as file:
            data = csv.reader(file, delimiter=',')
            next(data)
            nodes = [Node(row[0], row[1], row[2], row[3], row[4] == "True")
                     for row in data]
    else:
        exit("node_list file not found. Path may be wrong.")
    n_bootnodes = 0
    n_validators = 0
    bootnodes = ""
    validators = ""
    # genesis.json command creation
    for node in nodes:
        if node.is_bootnode():
            bootnodes += "--bootnode=" + node.get_multiaddr() + " "
            n_bootnodes += 1
        validators += "--ibft-validator=" + node.get_key() + " "
        n_validators += 1
    logging.info("Found " + str(n_bootnodes) +
                 " bootnodes out of " + str(n_validators) + ".")
    command = "./" + __SDK_NAME + " genesis --consensus ibft " + validators + bootnodes
    # Adding pre-mined balances based on premine file
    if premine_list_path:
        if os.path.exists(premine_list_path):
            logging.info("Found premine file.")
            premine = ""
            with open(premine_list_path, 'r') as file:
                data = csv.reader(file, delimiter=',')
                next(data)
                for row in data:
                    premine += "--premine " + row[0]+":"+row[1]+" "
                command += premine
        else:
            exit("Premine file not found. Path may be wrong.")
    os.chdir(__PATH)
    os.system(command)


def start_validator():
    os.chdir(__PATH)
    command = "./" + __SDK_NAME + \
        " server --data-dir data-dir --chain genesis.json --libp2p 0.0.0.0:1478 --seal"
    os.system(command)


if __name__ == "__main__":
    logging.basicConfig(level=__LOG_LEVEL)
    # CLI command parsing
    parser = argparse.ArgumentParser(
        description="Utility for edge-sdk configuration.")
    subparser = parser.add_subparsers(dest="command")
    # Init command
    init = subparser.add_parser(
        "init", help="Download the SDK and initializes node secrets.")
    # Config validator command
    generate = subparser.add_parser(
        "generate_genesis", help="Generates the genesis.json using a node_list and an optional premine_list.")
    generate.add_argument('--node_list', type=str,
                          default="./nodelist.csv", required=False)
    generate.add_argument('--premine_list', type=str,
                          default="./preminelist.csv", required=False)
    # Start validator command
    start = subparser.add_parser(
        "start_validator", help="Starts a previously configured validator.")
    # Parses the input
    args = parser.parse_args()
    # Executes the method
    if args.command == "init":
        sdk_init()
    elif args.command == "generate_genesis":
        generate_genesis(args.node_list, args.premine_list)
    elif args.command == "start_validator":
        start_validator()
    else:
        exit("No command given.")
