import shutil
import requests
import tarfile
import os
import logging
import time
import csv
import argparse
import validators


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
__NULL_ADDRESS = "0x0000000000000000000000000000000000000000"


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
    logging.info(
        "Now you need to give the genesis file to the other nodes, so that they can use it to start the chain.")


def start_validator(ip: str):
    os.chdir(__PATH)
    command = "./" + __SDK_NAME + \
        " server --data-dir data-dir --chain genesis.json --libp2p 0.0.0.0:1478 "
    if ip:
        command += "--nat " + ip + " "
    else:
        command += "--seal"
    os.system(command)


def backup_data(backup_destination: str):
    dest = os.path.join(backup_destination, "backup_"+str(time.time()))
    os.makedirs(dest)
    shutil.copy(os.path.join(__PATH, "genesis.json"),
                os.path.join(dest, "genesis.json"))
    shutil.copytree(os.path.join(__PATH, "data-dir"),
                    os.path.join(dest, "data-dir"))


def restore_backup(backup_path: str):
    if os.path.exists(backup_path):
        shutil.rmtree(os.path.join(__PATH, "data-dir"))
        os.remove(os.path.join(__PATH, "genesis.json"))
        shutil.copy(os.path.join(backup_path, "genesis.json"),
                    os.path.join(__PATH, "genesis.json"))
        shutil.copytree(os.path.join(backup_path, "data-dir"),
                        os.path.join(__PATH, "data-dir"))
    else:
        exit("Path does not exists. Please check the given path.")


def benchmark_chain(jsonrpc: str, sender: str, receiver: str, tps: int, count: int):
    os.chdir(__PATH)
    if validators.url(jsonrpc):
        command = "./" + __SDK_NAME + " loadbot --jsonrpc " + jsonrpc + \
            " --sender " + sender + " --receiver " + receiver + " --count " + \
            str(count) + " --value 0x100 --tps " + str(tps)
        os.system(command)
    else:
        exit("Endpoint url is not valid.")


if __name__ == "__main__":
    logging.basicConfig(level=__LOG_LEVEL)
    # CLI command parser
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
    start.add_argument('--ip', help="Your IP address.",
                       type=str, required=False)
    # Backup blockchain data command
    backup = subparser.add_parser(
        "backup", help="Backups blockchain data and genesis.json file.")
    backup.add_argument(
        "--backup_dest", help="The path in which the backup has to be saved.",
        default=__PATH, type=str, required=False)
    # Restore data command
    restore = subparser.add_parser(
        "restore", help="Restores a blockchain backup.")
    restore.add_argument(
        "--backup_path", help="Fullpath to the backup folder.", type=str,
        required=True)
    # Benchmark: uses the loadbot to test the chain
    benchmark = subparser.add_parser(
        "loadbot", help="Stress test for the blockchain.")
    benchmark.add_argument(
        "--jsonrpc", help="The jsonrpc endpoint.", type=str, required=True)
    benchmark.add_argument(
        "--sender", help="The sender address. Public and private key must be an environment variable on your system.",
        type=str, required=True)
    benchmark.add_argument(
        "--receiver", help="The receiver address. Default is null address.",
        type=str, required=False, default=__NULL_ADDRESS)
    benchmark.add_argument(
        "--tps", help="The number of transaction per second to perform.",
        type=int, required=False, default=100)
    benchmark.add_argument(
        "--count", help="The total number of transaction to perform.", type=int,
        required=False, default=2000)
    # Parses the input
    args = parser.parse_args()
    # Executes the method
    if args.command == "init":
        sdk_init()
    elif args.command == "generate_genesis":
        generate_genesis(args.node_list, args.premine_list)
    elif args.command == "start_validator":
        start_validator(args.ip)
    elif args.command == "backup":
        backup_data(args.backup_dest)
    elif args.command == "restore":
        restore_backup(args.backup_path)
    elif args.command == "loadbot":
        benchmark_chain(args.jsonrpc, args.sender,
                        args.receiver, args.tps, args.count)
    else:
        exit("Command not recognized.")
