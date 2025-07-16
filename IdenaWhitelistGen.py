import requests
import json
import time
from eth_utils import keccak  # pure-python Keccak-256

# --- CONFIG ---
ADDRESS_FILE = "allAddresses.txt"
OUT_FILE = "idena_whitelist.jsonl"
WHITELIST_LIST_FILE = "whitelist.txt"
WHITELIST_META_FILE = "whitelist_meta.json"
REQUIRED_BLOCKS_WITH_TXS = 7

def get_latest_epoch_info():
    url = "https://api.idena.io/api/Epoch/Last"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()["result"]
    return int(data["epoch"]), float(data["discriminationStakeThreshold"])

def get_epoch_info(epoch):
    url = f"https://api.idena.io/api/Epoch/{epoch}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()["result"]
    return int(data["validationFirstBlockHeight"]), data

def get_block_flags(block_height):
    url = f"https://api.idena.io/api/Block/{block_height}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    data = resp.json().get("result", {})
    flags = data.get("flags") or []
    return flags

def fetch_all_txs(block_height, limit=100):
    url = f"https://api.idena.io/api/Block/{block_height}/Txs"
    params = {"limit": limit}
    headers = {"accept": "application/json"}
    all_txs = []
    continuation = None
    while True:
        if continuation:
            params["continuationToken"] = continuation
        else:
            params.pop("continuationToken", None)
        resp = requests.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            print(f"Error {resp.status_code} for block {block_height}")
            break
        data = resp.json()
        txs = data.get("result", [])
        if txs is None:
            txs = []
        all_txs.extend(txs)
        continuation = data.get("continuationToken")
        if not continuation:
            break
        time.sleep(0.1)
    return all_txs

def find_short_session_block(start_height):
    for h in range(start_height, start_height + 20):
        flags = get_block_flags(h) or []
        if not flags:
            print(f"[WARN] No flags found in block {h} (may be an old block or API inconsistency)")
        if "ShortSessionStarted" in flags:
            print(f"ShortSessionStarted found at block {h}")
            return h
    raise Exception("No ShortSessionStarted block found in search range!")

def fetch_bad_addresses(epoch, limit=100):
    bad_addrs = set()
    next_token = None
    print(f"Fetching bad authors for epoch {epoch} ...")
    while True:
        url = f"https://api.idena.io/api/Epoch/{epoch}/Authors/Bad?limit={limit}"
        if next_token:
            url += f"&continuationToken={next_token}"
        r = requests.get(url, timeout=10)
        data = r.json() or {}
        for entry in (data.get("result") or []):
            # fix: use .get("address", "author")
            addr = entry.get("address") or entry.get("author")
            if addr:
                bad_addrs.add(addr.lower())
        next_token = data.get("continuationToken")
        if not next_token:
            break
        time.sleep(0.1)
    print(f"Loaded {len(bad_addrs)} bad addresses")
    return bad_addrs

def collect_shortsession_addresses(
    epoch, required_blocks_with_txs=REQUIRED_BLOCKS_WITH_TXS, write_file=True
):
    print(f"Fetching info for epoch {epoch}...")
    first_block_base, epoch_data = get_epoch_info(epoch)
    print(
        f"Epoch {epoch}, validationFirstBlockHeight: {first_block_base}"
    )

    candidate_block = first_block_base + 15
    short_session_block = find_short_session_block(candidate_block)

    limit = 100
    unique_addresses = set()
    blocks_found = 0
    current_block = short_session_block

    print(f"Collecting {required_blocks_with_txs} blocks with transactions (may scan more due to empty blocks)...")

    while blocks_found < required_blocks_with_txs:
        txs = fetch_all_txs(current_block, limit=limit)
        if len(txs) > 0:
            print(f"Block {current_block} - {len(txs)} txs found")
            blocks_found += 1
            for tx in txs:
                addr = tx.get("from")
                if addr:
                    unique_addresses.add(addr)
        else:
            print(f"Block {current_block} - empty, skipped")
        current_block += 1

    if write_file:
        with open(ADDRESS_FILE, "w") as f:
            f.write(",".join(sorted(unique_addresses)))

    print(f"\nDone! {len(unique_addresses)} unique addresses written to {ADDRESS_FILE}")

def sum_session_reward_stake(epoch, addr):
    """Return total session reward stake and breakdown by type.

    The API sometimes returns ``null`` or fails. This helper never raises and
    always returns ``(total, by_type)``. A short note is printed when no rewards
    are available.
    """

    url = f"https://api.idena.io/api/Epoch/{epoch}/Identity/{addr}/Rewards"
    try:
        r = requests.get(url, timeout=10)
        rewards = r.json().get("result", [])
        if rewards is None:
            print(f"No rewards found for {addr}.")
            rewards = []
    except Exception as e:
        print(f"WARNING: Failed to fetch rewards for {addr}: {e}")
        rewards = []

    reward_stake_sum = 0.0
    by_type = {}
    for reward in rewards:
        typ = reward.get("type", "Unknown")
        amount = float(reward.get("stake", 0) or 0)
        reward_stake_sum += amount
        by_type[typ] = by_type.get(typ, 0) + amount

    if not rewards:
        print(f"No session rewards returned for {addr} (epoch {epoch})")

    return reward_stake_sum, by_type

# ---------- Merkle helpers ----------
def build_merkle_root(addresses):
    """
    Build a Merkle root using Keccak-256.
    Accepts a list of addresses (strings).
    Returns the Merkle root as a 0x-prefixed hex string.
    """
    from eth_utils import keccak

    def hash_leaf(leaf):
        # Accepts a string, returns bytes
        return keccak(text=leaf.lower())

    def hash_pair(a, b):
        # Concatenate and hash
        return keccak(a + b)

    # Hash leaves
    layer = [hash_leaf(addr) for addr in addresses]
    if not layer:
        return None, None  # Empty list

    # Build up the tree
    while len(layer) > 1:
        next_layer = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            if i + 1 < len(layer):
                right = layer[i + 1]
            else:
                right = left  # duplicate last
            next_layer.append(hash_pair(left, right))
        layer = next_layer

    root = layer[0]
    return "0x" + root.hex(), None  # second value is None for compatibility

def main():
    # Step 1: Collect addresses from short session blocks
    last_epoch, _ = get_latest_epoch_info()
    target_epoch = last_epoch - 1

    collect_shortsession_addresses(
        target_epoch,
        REQUIRED_BLOCKS_WITH_TXS,
        write_file=True
    )

    # Step 2: Determine previous epoch and get discrimination threshold & bad flips
    _, epoch_data = get_epoch_info(last_epoch)
    discrimination_stake_threshold = float(
        epoch_data.get("discriminationStakeThreshold", 0)
    )
    print(f"\nCurrent discriminationStakeThreshold (DiscriminationStakeThreshold): {discrimination_stake_threshold}")

    bad_addresses = fetch_bad_addresses(target_epoch)

    # Step 3: Load addresses from file (dynamic length)
    with open(ADDRESS_FILE) as f:
        addresses = [a.strip() for a in f.read().split(",") if a.strip()]
    max_addresses = len(addresses)
    print(f"Processing {max_addresses} addresses from {ADDRESS_FILE}")

    out = open(OUT_FILE, "w", encoding="utf-8")
    errors = []
    whitelisted = 0
    whitelist_addresses = []

    print(f"\nChecking eligibility for all session addresses ...")
    for i, addr in enumerate(addresses):
        addr_l = addr.lower()
        reason = None
        short_points = None
        long_points = None
        by_type = {}
        state = None
        # Exclude bad flip addresses first
        if addr_l in bad_addresses:
            reason = "Penalized (bad flips)"
        try:
            # 1. Fetch validation summary
            url = f"https://api.idena.io/api/Epoch/{target_epoch}/Identity/{addr_l}/ValidationSummary"
            r = requests.get(url, timeout=15)
            if r.status_code == 404:
                # Usually means the identity never paid or candidate failed
                id_resp = requests.get(
                    f"https://api.idena.io/api/Identity/{addr_l}", timeout=10
                )
                if id_resp.status_code == 200:
                    state = id_resp.json().get("result", {}).get("state")
                    if state:
                        reason = f"Not paid / Candidate failed (state={state})"
                    else:
                        reason = "Not paid / Candidate failed"
                else:
                    reason = "No info found for address"
                print(
                    f"[{i+1}/{max_addresses}] {addr} - NOT ELIGIBLE: {reason} | byType={by_type}"
                )
                continue
            r.raise_for_status()
            result = r.json().get("result", {}) or {}
            state = result.get("state")
            penalized = result.get("penalized", False)
            approved = result.get("approved", False)
            missed = result.get("missed", False)
            wrong_grades = result.get("wrongGrades") or result.get("wrongGrade")
            base_stake = float(result.get("stake", 0) or 0)
            short_points = result.get("shortFlipPoints") or result.get("shortAnswersScore")
            long_points = result.get("longFlipPoints") or result.get("longAnswersScore")

            # 2. Get all session reward stakes (all types)
            reward_stake_sum, by_type = sum_session_reward_stake(target_epoch, addr_l)
            epoch_start_stake = base_stake + reward_stake_sum

            if reason is None:
                if penalized:
                    reason = "Penalized"
                elif not approved:
                    reason = "Not approved"
                elif missed:
                    reason = "Missed validation"
                elif wrong_grades:
                    reason = "Low score / wrong grades"
                elif state == "Candidate":
                    reason = "Candidate"
                elif state == "Suspended":
                    reason = "Suspended"
                elif state not in ("Human", "Newbie", "Verified"):
                    reason = f"State not eligible ({state})"
                elif epoch_start_stake < discrimination_stake_threshold:
                    reason = (
                        "Stake below threshold "
                        f"(baseStake={base_stake:.4f}, sessionRewards={reward_stake_sum:.4f}, "
                        f"epochStartStake={epoch_start_stake:.4f}, DiscriminationStakeThreshold={discrimination_stake_threshold:.4f})"
                    )
            if reason:
                print(
                    f"[{i+1}/{max_addresses}] {addr} - NOT ELIGIBLE: {reason} | "
                    f"shortPts={short_points} longPts={long_points} | byType={by_type}"
                )
                continue

            # Passed all checks
            out.write(
                json.dumps(
                    {
                        "address": addr,
                        "state": state,
                        "baseStake": base_stake,
                        "sessionStakeRewardsSum": reward_stake_sum,
                        "byType": by_type,
                        "epochStartStake": epoch_start_stake,
                    }
                )
                + "\n"
            )
            whitelisted += 1
            whitelist_addresses.append(addr)
            print(
                f"[{i+1}/{max_addresses}] {addr} - OK | "
            )
        except Exception as e:
            errors.append((addr, str(e)))
            print(
                f"[{i+1}/{max_addresses}] ERROR for {addr}: {e} | "
                f"shortPts={short_points} longPts={long_points}"
            )
        time.sleep(0.18)

    out.close()

    # Write simple address list
    with open(WHITELIST_LIST_FILE, "w") as wl_out:
        wl_out.write(",\n".join(whitelist_addresses))

    # Write metadata with DiscriminationStakeThreshold and epoch
    with open(WHITELIST_META_FILE, "w") as meta_out:
        json.dump(
            {
                "DiscriminationStakeThreshold": discrimination_stake_threshold,
                "epoch": target_epoch,
            },
            meta_out,
        )

    # ---------- Merkle tree ----------
    merkle_root, _ = build_merkle_root(whitelist_addresses)
    print("\nMERKLE_ROOT =", merkle_root)

    # Write Merkle root to a file named after the latest epoch
    epoch_root_file = f"merkle_root_epoch_{target_epoch}.txt"
    with open(epoch_root_file, "w") as f:
        f.write(merkle_root + "\n")
    print(f"Merkle root written to {epoch_root_file}")

    # append root to whitelist_meta.json
    with open(WHITELIST_META_FILE, "r+") as meta_out:
        meta = json.load(meta_out)
        meta["merkleRoot"] = merkle_root
        meta_out.seek(0), meta_out.truncate(0)
        json.dump(meta, meta_out, indent=2)

    print(
        f"\nDone. Whitelisted: {whitelisted} addresses. "
        f"Errors: {len(errors)} | Merkle root written to {WHITELIST_META_FILE}"
    )
    if errors:
        print("Errors:")
        for addr, msg in errors:
            print(f"  {addr}: {msg}")

if __name__ == "__main__":
    main()
