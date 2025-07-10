###############################################################
# CONFIG & FAQ - MerkleProofAddressChecker.py
#
# How do I check if an address is in the latest Merkle root?
#
# 1. Edit ADDRESSES_TO_CHECK below.
#    - Put each address in quotes, separated by commas.
#    - Upper/lowercase doesn't matter.
#    - You CAN leave a comma after the last address or not.
#      Both styles are valid in Python lists!
#
#    Examples:
#      ADDRESSES_TO_CHECK = [
#          "0x7eC55A0200671F83A4acA56CdDb14A5Dc13db593",
#          "0xcbb98843270812eeCE07BFb82d26b4881a33aA91",
#          "0x0000000000000000000000000000000000000000",
#      ]
#
#      ...or...
#      ADDRESSES_TO_CHECK = [
#          "0x7eC55A0200671F83A4acA56CdDb14A5Dc13db593"
#      ]
#
# 2. Run the script: python MerkleProofAddressChecker.py
#    It will auto-detect the most recent epoch and use the corresponding Merkle root file.
#
###############################################################

ADDRESSES_TO_CHECK = [
    "0x7eC55A0200671F83A4acA56CdDb14A5Dc13db593",
    "0xcbb98843270812eeCE07BFb82d26b4881a33aA91",
    "0x0000000000000000000000000000000000000000",
    # Add more addresses as needed,
]

import glob
import re
import os
import json
from eth_utils import keccak

def get_latest_epoch_root_file():
    files = glob.glob("merkle_root_epoch_*.txt")
    max_epoch = -1
    selected = None
    for f in files:
        match = re.search(r"merkle_root_epoch_(\d+)\.txt", f)
        if match:
            epoch = int(match.group(1))
            if epoch > max_epoch:
                max_epoch = epoch
                selected = f
    return selected, max_epoch

def get_matching_whitelist_file(epoch):
    alt = f"whitelist_epoch{epoch}.txt"
    if os.path.exists(alt):
        return alt
    # fallback
    return "whitelist.txt"

def hash_leaf(addr):
    """Hash an address (as string, any case) with keccak256. Returns bytes."""
    return keccak(text=addr.lower())

def hash_pair(a: bytes, b: bytes):
    return keccak(a + b)

def build_merkle_tree(leaves):
    """Returns a list of all tree layers, [leaves, layer1, layer2, ..., root_layer]"""
    layers = []
    current = leaves[:]
    while len(current) > 1:
        next_layer = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i+1] if i+1 < len(current) else left
            next_layer.append(hash_pair(left, right))
        layers.append(current)
        current = next_layer
    layers.append(current)
    return layers

def get_merkle_proof(leaves, index):
    """Returns a Merkle proof for leaves[index]. Output: list of {'left':hex} or {'right':hex}"""
    proof = []
    current_index = index
    current_layer = leaves[:]
    while len(current_layer) > 1:
        next_layer = []
        for i in range(0, len(current_layer), 2):
            left = current_layer[i]
            if i+1 < len(current_layer):
                right = current_layer[i+1]
            else:
                right = left
            pair_hash = hash_pair(left, right)
            next_layer.append(pair_hash)
            # Check if our leaf is part of this pair
            if i == current_index or i+1 == current_index:
                if current_index == i:
                    sibling = right
                    proof.append({"right": sibling.hex()})
                else:
                    sibling = left
                    proof.append({"left": sibling.hex()})
                current_index = len(next_layer)-1
        current_layer = next_layer
    return proof

def verify_merkle_proof(leaf_hash, proof, root_hex):
    """Recalculate merkle root from leaf_hash and proof, and check against root_hex."""
    h = leaf_hash
    for step in proof:
        if "left" in step:
            h = hash_pair(bytes.fromhex(step["left"]), h)
        elif "right" in step:
            h = hash_pair(h, bytes.fromhex(step["right"]))
    return ("0x" + h.hex()).lower() == root_hex.lower()

def main():
    MERKLE_ROOT_FILE, LATEST_EPOCH = get_latest_epoch_root_file()
    if MERKLE_ROOT_FILE is None:
        print("[ERROR] No merkle_root_epoch_*.txt file found.")
        return

    WHITELIST_FILE = get_matching_whitelist_file(LATEST_EPOCH)

    with open(MERKLE_ROOT_FILE, "r") as f:
        merkle_root = f.read().strip()
    print(f"[i] Loaded Merkle root: {merkle_root} (epoch {LATEST_EPOCH})")
    print(f"[i] Loading whitelist from: {WHITELIST_FILE}")

    # Read whitelist (one address per line, or CSV)
    with open(WHITELIST_FILE, "r") as f:
        content = f.read()
        if "," in content:
            whitelist = [a.strip() for a in content.split(",") if a.strip()]
        else:
            whitelist = [a.strip() for a in content.splitlines() if a.strip()]
    if not whitelist:
        print("[ERROR] No addresses found in whitelist!")
        return

    # Build leaf hashes and lookup table
    leaf_hashes = [hash_leaf(addr) for addr in whitelist]
    addr_map = {addr.lower(): i for i, addr in enumerate(whitelist)}

    for address in ADDRESSES_TO_CHECK:
        addr_l = address.lower()
        if addr_l not in addr_map:
            print(f"[NOT FOUND IN WHITELIST] {address}")
            continue
        idx = addr_map[addr_l]
        leaf = leaf_hashes[idx]
        proof = get_merkle_proof(leaf_hashes, idx)
        valid = verify_merkle_proof(leaf, proof, merkle_root)
        print(f"Address: {address}")
        print(f"  Included in Merkle root: {'YES' if valid else 'NO'}")
        print(f"  Merkle Proof: {json.dumps(proof, indent=2)}\n")

    print("Done.")

if __name__ == "__main__":
    main()
