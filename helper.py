import shutil
import requests
import tarfile
import os
import logging
import time
import csv
import argparse
import validators
import subprocess


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


__LOG_LEVEL = logging.DEBUG
__URL = "https://github.com/0xPolygon/polygon-edge/releases/download/v0.1.0/polygon-sdk_0.1.0_linux_amd64.tar.gz"
__PATH = "edge"
__SDK_NAME = "polygon-sdk"
__DATA_DIR_NAME = "data-dir"
__NULL_ADDRESS = "0x0000000000000000000000000000000000000000"
__LOCALHOST = "127.0.0.1"
__GENESIS_PATH = os.path.join(__PATH, "genesis.json")
__DATA_DIR_PATH = os.path.join(__PATH, __DATA_DIR_NAME)


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
        command = "./"+__SDK_NAME + " secrets init --data-dir " + \
            __DATA_DIR_NAME + " > node.info"
        logging.debug(command)
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
    command = "./" + __SDK_NAME + " genesis --consensus ibft " + \
        validators + bootnodes + "--block-gas-limit 9000000"
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
    logging.debug(command)
    os.system(command)
    logging.info(
        "Now you need to give the genesis file to the other nodes, so that they can use it to start the chain.")


def start_validator(ip: str, jsonrpc: int, grpc: int):
    os.chdir(__PATH)
    command = "nohup ./" + __SDK_NAME + \
        " server --data-dir " + __DATA_DIR_NAME + " --chain genesis.json --libp2p 0.0.0.0:1478 --grpc " + \
        ip+":"+str(grpc) + " --jsonrpc " + ip+":" + str(jsonrpc) + " "
    if ip != __LOCALHOST:
        command += "--nat " + ip + " "
    command += "--seal &"
    logging.debug(command)
    os.system(command)


def _is_node_running():
    command = "pgrep " + __SDK_NAME
    logging.debug(command)
    try:
        pid = str(int(subprocess.check_output(command, shell=True)))
    except subprocess.CalledProcessError:
        pid = False
    finally:
        return pid


def halt_node():
    pid = _is_node_running()
    if pid:
        logging.debug("Node pid: " + pid)
        os.system("kill -15 " + pid)
    else:
        exit("Node seems to be inactive.")


def _bc_data_exists() -> bool:
    if (os.path.exists(__DATA_DIR_PATH) and os.path.exists(__GENESIS_PATH)):
        return True
    return False


def backup_data(backup_destination: str, backup_prefix: str):
    if _bc_data_exists():
        dest = os.path.join(backup_destination,
                            backup_prefix+"_" + str(time.time()))
        os.makedirs(dest)
        shutil.copy(__GENESIS_PATH,
                    os.path.join(dest, "genesis.json"))
        shutil.copytree(__DATA_DIR_PATH,
                        os.path.join(dest, __DATA_DIR_NAME))
    else:
        exit("Blockchain data not consistent. Unable to backup.")


def restore_backup(backup_path: str):
    if _bc_data_exists():
        reset_chain(is_hard_reset=True, make_backup=True)
    if os.path.exists(backup_path):
        shutil.copy(os.path.join(backup_path, "genesis.json"),
                    __GENESIS_PATH)
        shutil.copytree(os.path.join(backup_path, __DATA_DIR_NAME),
                        __DATA_DIR_PATH)
    else:
        exit("Backup not found. Please check the given path.")


def benchmark_chain(jsonrpc: str, sender: str, receiver: str, tps: int, count: int):
    os.chdir(__PATH)
    if validators.url(jsonrpc):
        command = "./" + __SDK_NAME + " loadbot --jsonrpc " + jsonrpc + \
            " --sender " + sender + " --receiver " + receiver + " --count " +\
            str(count) + " --value 0x100 --tps " + str(tps)
        logging.debug(command)
        os.system(command)
    else:
        exit("Endpoint url is not valid.")


def reset_chain(is_hard_reset: bool, make_backup: bool):
    if make_backup:
        backup_data(__PATH, "reset")
    if _bc_data_exists():
        if(is_hard_reset):
            os.remove(__GENESIS_PATH)
        shutil.rmtree(__DATA_DIR_PATH)
    else:
        exit("Blockchain data not found. Nothing to delete.")


def node_status():
    pid = _is_node_running()
    if pid:
        command = "tail " + os.path.join(__PATH, "nohup.out")
        logging.debug(command)
        os.system(command)
    else:
        exit("Node seems to be inactive.")


def parser_config() -> argparse.ArgumentParser:
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
    start.add_argument('--ip', help="Your IP address. If you don't give this parameter jsonrpc and grpc will not be exposed.",
                       type=str, required=False, default=__LOCALHOST)
    start.add_argument('--jsonrpc', help="jsonrpc port",
                       type=int, required=False, default=8545)
    start.add_argument('--grpc', help="grpc port", type=int,
                       required=False, default=10000)
    # Halt node
    halt = subparser.add_parser("halt_node", help="Halts the running node.")
    # Prints the node status
    status = subparser.add_parser("status", help="Prints the node status")
    # Backup blockchain data command
    backup = subparser.add_parser(
        "backup", help="Backups blockchain data and genesis.json file.")
    backup.add_argument(
        "--backup_dest", help="The path in which the backup has to be saved.",
        default=__PATH, type=str, required=False)
    backup.add_argument(
        "--backup_prefix", help="The backup prefix name.",
        default="backup", type=str, required=False)
    # Restore data command
    restore = subparser.add_parser(
        "restore", help="Restores a blockchain backup.")
    restore.add_argument(
        "--backup_path", help="Fullpath to the backup folder.", type=str,
        required=True)
    # Reset blockchain data
    reset = subparser.add_parser("reset", help="Deletes the blockchain data.")
    reset.add_argument(
        "--hard_reset", help="Specifies if this is an hard reset. If is hard reset also the genesis.json is deleted.", type=str, required=False,
        default="False")
    reset.add_argument(
        "--make_backup", help="Whether to backup data before deletion or not.", type=str, required=False,
        default="True")
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
    return parser


def _str_to_bool(str: str) -> bool:
    if str == "True" or str == "true" or str == "y":
        return True
    return False


if __name__ == "__main__":
    logging.basicConfig(level=__LOG_LEVEL)
    parser = parser_config()
    # Parses the input
    args = parser.parse_args()
    # Executes the method
    if args.command == "init":
        sdk_init()
    elif args.command == "generate_genesis":
        generate_genesis(args.node_list, args.premine_list)
    elif args.command == "start_validator":
        start_validator(args.ip, args.jsonrpc, args.grpc)
    elif args.command == "halt_node":
        halt_node()
    elif args.command == "backup":
        backup_data(args.backup_dest, args.backup_prefix)
    elif args.command == "restore":
        restore_backup(args.backup_path)
    elif args.command == "reset":
        reset_chain(_str_to_bool(args.hard_reset),
                    _str_to_bool(args.make_backup))
    elif args.command == "loadbot":
        benchmark_chain(args.jsonrpc, args.sender,
                        args.receiver, args.tps, args.count)
    elif args.command == "status":
        node_status()
    else:
        exit("Command not recognized.")
