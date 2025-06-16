import requests
import json
import time

# --- CONFIG ---
ADDRESS_FILE = "allAddresses.txt"
OUT_FILE = "idena_whitelist.jsonl"
STAKE_THRESHOLD_FILE = "discriminationStakeThreshold.txt"
NEWBIE_MIN_STAKE = 10000
VERIFIED_MIN_STAKE = 10000
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
    return data.get("flags", [])

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
        flags = get_block_flags(h)
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
        data = r.json()
        for entry in data.get("result", []):
            bad_addrs.add(entry["address"].lower())
        next_token = data.get("continuationToken")
        if not next_token:
            break
        time.sleep(0.1)
    print(f"Loaded {len(bad_addrs)} bad addresses")
    return bad_addrs

def collect_shortsession_addresses(required_blocks_with_txs=REQUIRED_BLOCKS_WITH_TXS):
    print("Fetching latest epoch info...")
    latest_epoch, current_threshold = get_latest_epoch_info()
    print(f"Latest epoch: {latest_epoch}, discriminationStakeThreshold: {current_threshold}")
    with open(STAKE_THRESHOLD_FILE, "w") as f:
        f.write(str(current_threshold))

    last_epoch = latest_epoch - 1
    first_block_base, last_epoch_data = get_epoch_info(last_epoch)
    print(f"Last epoch: {last_epoch}, validationFirstBlockHeight: {first_block_base}")

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

    with open(ADDRESS_FILE, "w") as f:
        f.write(",".join(sorted(unique_addresses)))

    print(f"\nDone! {len(unique_addresses)} unique addresses written to {ADDRESS_FILE}")
    print(f"DiscriminationStakeThreshold ({current_threshold}) written to {STAKE_THRESHOLD_FILE}")

def main():
    # Step 1: Collect addresses from short session blocks
    collect_shortsession_addresses(REQUIRED_BLOCKS_WITH_TXS)

    # Step 2: Determine previous epoch and get discrimination threshold & bad flips
    epoch_resp = requests.get("https://api.idena.io/api/Epoch/Last", timeout=10)
    last_epoch = int(epoch_resp.json()["result"]["epoch"]) - 1
    _, discrimination_stake_threshold = get_latest_epoch_info()
    bad_addresses = fetch_bad_addresses(last_epoch)

    # Step 3: Load addresses from file (dynamic length)
    with open(ADDRESS_FILE) as f:
        addresses = [a.strip() for a in f.read().split(",") if a.strip()]
    max_addresses = len(addresses)
    print(f"Processing {max_addresses} addresses from {ADDRESS_FILE}")

    out = open(OUT_FILE, "w", encoding="utf-8")
    errors = []
    whitelisted = 0

    print(f"Checking final states using /Epoch/{last_epoch}/Identity/{{addr}}/ValidationSummary ...")
    for i, addr in enumerate(addresses):
        addr_l = addr.lower()
        reason = None
        # Exclude bad flip addresses first
        if addr_l in bad_addresses:
            reason = "EXCLUDED (address is in Bad Authors list / reported for bad flips)"
        try:
            url = f"https://api.idena.io/api/Epoch/{last_epoch}/Identity/{addr}/ValidationSummary"
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                raise Exception(f"API returned {r.status_code}")
            result = r.json().get("result", {})
            if not result:
                raise Exception("Empty ValidationSummary result")
            state = result.get("state")
            penalized = result.get("penalized", False)
            approved = result.get("approved", False)
            stake = float(result.get("stake", 0))
            if reason is None:
                if penalized or not approved:
                    reason = f"EXCLUDED (not approved or penalized: approved={approved}, penalized={penalized})"
                elif state == "Human":
                    if stake < discrimination_stake_threshold:
                        reason = f"EXCLUDED (Human, but Stake below DiscriminationStakeThreshold: {stake:.4f} < {discrimination_stake_threshold:.4f})"
                elif state == "Newbie":
                    if stake < NEWBIE_MIN_STAKE:
                        reason = f"EXCLUDED (Newbie and Stake below {NEWBIE_MIN_STAKE} iDNA: {stake:.4f})"
                elif state == "Verified":
                    if stake < VERIFIED_MIN_STAKE:
                        reason = f"EXCLUDED (Verified and Stake below {VERIFIED_MIN_STAKE} iDNA: {stake:.4f})"
                else:
                    reason = f"EXCLUDED (wrong state: {state})"
            if reason:
                print(f"[{i+1}/{max_addresses}] {reason}: {addr} - state={state}, stake={stake}")
                continue
            # Passed all checks
            out.write(json.dumps({
                "address": addr,
                "state": state,
                "stake": stake
            }) + "\n")
            whitelisted += 1
            print(f"[{i+1}/{max_addresses}] OK: {addr} - state={state}, stake={stake}")
        except Exception as e:
            errors.append((addr, str(e)))
            print(f"[{i+1}/{max_addresses}] ERROR: {addr} - {e}")
        time.sleep(0.2)

    out.close()
    print(f"Done. Whitelisted: {whitelisted} addresses. Errors: {len(errors)}")
    if errors:
        print("Errors:")
        for addr, msg in errors:
            print(f"  {addr}: {msg}")

if __name__ == "__main__":
    main()
