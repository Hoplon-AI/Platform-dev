""""
Detection of properties that belong in the same building block based on parent UPRN
"""
from os_datahub_functions import *


def detect_block_properties(props: list[dict]) -> dict:
    """Group properties by their PARENT_UPRN to identify blocks of properties in the same building."""
    parent_to_block = {}
    blocks = {}
    block_count = 0

    for prop in props:
        parent_uprn = prop.get("PARENT_UPRN")
        if parent_uprn:
            if parent_uprn not in parent_to_block:
                block_count += 1
                key = f"block_{block_count}"
                parent_to_block[parent_uprn] = key
                blocks[key] = {"block_size": 0, "parent_uprn": parent_uprn, "properties": []}
            key = parent_to_block[parent_uprn]
            blocks[key]["block_size"] += 1
            blocks[key]["properties"].append(prop.get("UPRN"))

    return blocks


if __name__ == "__main__":
    test_addresses = ["13 ABBOTTS BARN CLOSE",
                      "Flat 1/1, 217 Clarkston Road, Cathcart, Glasgow, G44 3DS",
                      "Flat 2/2, 22 Brunton Street, Cathcart, Glasgow, G44 3DX",
                      "Flat 3/1, 22 Brunton Street, Cathcart, Glasgow, G44 3DX",
                      "2 BATH STREET, DERBY, DE1 3BU"]

    list = []

    for addr in test_addresses:
        list.append(get_uprn_from_address(addr, "Ajrj5AiJphBOM2GdP7KqVx6Ax6CTemtY"))

    print(detect_block_properties(list))