import shutil
import requests
import tarfile
import os
import logging
import sys
import pandas as pd


class Node:
    # 1478 is the default libp2p port
    def __init__(self, ip: str, id: str, key: str, port: str = "1478", bootnode: bool = False):
        self.ip = ip
        self.id = id
        self.key = key
        self.port = port
        self.bootnode = bootnode

    def is_bootnode(self):
        return self.bootnode

    def get_multiaddr(self):
        return '/ip4/' + self.ip + "/tcp/" + self.port + "/p2p/" + self.id


__URL = "https://github.com/0xPolygon/polygon-edge/releases/download/v0.1.0/polygon-sdk_0.1.0_linux_amd64.tar.gz"
__PATH = "edge"
__SDK_NAME = "polygon-sdk"
__LOG_LEVEL = logging.INFO
# __NODES = [Node("node ip","node id", ...), Node("node ip","node id", ...), ...]
__NODES = []


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
        os.system("./"+__SDK_NAME +
                  " secrets init --data-dir chain-data > node.info")
    else:
        print("Unable to download the SDK. Try again later or check the URL.")


def node_config(path: str):
    # If a path for a .csv file configuration is given the csv is parsed and then nodes are added
    if path:
        if os.path.exists(path):
            df = pd.read_csv(path)
            nodes = []
            for index, data in df.iterrows():
                nodes.append(
                    Node(data["ip"], data["id"], data["key"], data["port"], data["bootnode"]))
        else:
            exit("Config file not found. Path may be wrong.")
    else:
        if len(__NODES):
            nodes = __NODES
        else:
            exit("You have not provided a path to a file containing a list of nodes nor a list of nodes in the script. Please do one of these two things.")
    bootnodes = [node for node in nodes if node.is_bootnode()]
    logging.info("Found " + str(len(bootnodes)) +
                 " bootnodes out of " + str(len(nodes)) + ".")


if __name__ == "__main__":
    logging.basicConfig(level=__LOG_LEVEL)
    if len(sys.argv) > 1:
        if sys.argv[1] == "init":
            sdk_init()
        elif sys.argv[1] == "config":
            if len(sys.argv) > 2:
                node_config(sys.argv[2])
            else:
                node_config(None)
    else:
        print("No args passed.")
