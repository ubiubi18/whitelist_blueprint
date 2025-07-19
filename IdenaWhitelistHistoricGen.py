#!/usr/bin/env python3
import json
import time
import requests
from eth_utils import keccak

REQUIRED_BLOCKS_WITH_TXS = 7
EPOCHS_TO_LOOK_BACK = 5
ADDRESS_FILE = "allAddresses.txt"


def log_status(idx, total, addr, tag, reason=None, short_pts=None, long_pts=None, extra=None):
    parts = [f"[{idx + 1}/{total}] {addr} - {tag}"]
    if reason:
        parts.append(reason)
    extras = []
    if short_pts is not None:
        extras.append(f"shortPts={short_pts}")
    if long_pts is not None:
        extras.append(f"longPts={long_pts}")
    if extra:
        extras.append(str(extra))
    if extras:
        parts.append("| " + " ".join(extras))
    print(" ".join(parts))


def get_latest_epoch_info():
    d = requests.get("https://api.idena.io/api/Epoch/Last").json()["result"]
    return int(d["epoch"]), float(d["discriminationStakeThreshold"])


def get_epoch_info(epoch):
    d = requests.get(f"https://api.idena.io/api/Epoch/{epoch}").json()["result"]
    return int(d["validationFirstBlockHeight"]), d


def get_block_flags(height):
    r = requests.get(f"https://api.idena.io/api/Block/{height}")
    if r.status_code != 200:
        return []
    return (r.json().get("result") or {}).get("flags") or []


def fetch_all_txs(height, limit=100):
    url = f"https://api.idena.io/api/Block/{height}/Txs"
    params, hdr, all_txs, token = {"limit": limit}, {"accept": "application/json"}, [], None
    while True:
        if token:
            params["continuationToken"] = token
        else:
            params.pop("continuationToken", None)
        r = requests.get(url, params=params, headers=hdr)
        if r.status_code != 200:
            print(f"Error {r.status_code} for block {height}")
            break
        d = r.json()
        all_txs.extend(d.get("result") or [])
        token = d.get("continuationToken")
        if not token:
            break
        time.sleep(0.1)
    return all_txs


def find_short_session_block(start_height):
    for h in range(start_height, start_height + 20):
        if "ShortSessionStarted" in get_block_flags(h):
            print(f"ShortSessionStarted found at block {h}")
            return h
    raise RuntimeError("No ShortSessionStarted block found")


def fetch_bad_addresses(epoch, limit=100):
    bad, token = set(), None
    print(f"Fetching bad authors for epoch {epoch} …")
    while True:
        url = f"https://api.idena.io/api/Epoch/{epoch}/Authors/Bad?limit={limit}"
        if token:
            url += f"&continuationToken={token}"
        d = (requests.get(url, timeout=10).json()) or {}
        for e in d.get("result") or []:
            a = e.get("address") or e.get("author")
            if a:
                bad.add(a.lower())
        token = d.get("continuationToken")
        if not token:
            break
        time.sleep(0.1)
    print(f"Loaded {len(bad)} bad addresses")
    return bad


def collect_shortsession_addresses(epoch, blocks_needed=REQUIRED_BLOCKS_WITH_TXS):
    print(f"Fetching info for epoch {epoch} …")
    base, _ = get_epoch_info(epoch)
    ss_block = find_short_session_block(base + 15)
    uniq, found, h = set(), 0, ss_block
    print(f"Collecting {blocks_needed} short‑session blocks containing all addresses with validation attempts…")
    while found < blocks_needed:
        txs = fetch_all_txs(h)
        if txs:
            print(f"Block {h} – {len(txs)} txs")
            found += 1
            uniq.update(t["from"] for t in txs if t.get("from"))
        else:
            print(f"Block {h} – empty")
        h += 1
    with open(ADDRESS_FILE, "w") as f:
        f.write(",".join(sorted(uniq)))
    print(f"{len(uniq)} unique addresses saved to {ADDRESS_FILE}")
    return sorted(uniq)


def sum_session_reward_stake(epoch, addr):
    url = f"https://api.idena.io/api/Epoch/{epoch}/Identity/{addr}/Rewards"
    try:
        rewards = (requests.get(url, timeout=10).json().get("result")) or []
    except Exception as e:
        print(f"WARNING: rewards fetch failed for {addr}: {e}")
        rewards = []
    return sum(float(r.get("stake") or 0) for r in rewards)


def build_merkle_root(addresses):
    h_leaf = lambda x: keccak(text=x.lower())
    h_pair = lambda a, b: keccak(a + b)
    layer = [h_leaf(a) for a in addresses]
    if not layer:
        return None, None
    while len(layer) > 1:
        layer = [h_pair(layer[i], layer[i + 1] if i + 1 < len(layer) else layer[i]) for i in range(0, len(layer), 2)]
    return "0x" + layer[0].hex(), None


def process_epoch(epoch):
    out_file = f"idena_whitelist_epoch{epoch}.jsonl"
    list_file = f"whitelist_epoch{epoch}.txt"
    meta_file = f"whitelist_meta_epoch{epoch}.json"

    collect_shortsession_addresses(epoch)

    _, ep_next = get_epoch_info(epoch + 1)
    dst = float(ep_next.get("discriminationStakeThreshold", 0))
    print(f"\nDiscriminationStakeThreshold for epoch {epoch}: {dst}")

    bad_addrs = fetch_bad_addresses(epoch)

    with open(ADDRESS_FILE) as f:
        addresses = [a for a in f.read().split(",") if a]
    total = len(addresses)
    print(f"Processing {total} addresses")

    out = open(out_file, "w")
    errors, whitelist = [], []

    print("\nChecking eligibility …")
    for i, addr in enumerate(addresses):
        al = addr.lower()
        reason = None
        short_pts = long_pts = None
        state = None

        if al in bad_addrs:
            reason = "Penalized (bad flips)"

        try:
            vs_url = f"https://api.idena.io/api/Epoch/{epoch}/Identity/{al}/ValidationSummary"
            r = requests.get(vs_url, timeout=15)
            if r.status_code == 404:
                idr = requests.get(f"https://api.idena.io/api/Identity/{al}", timeout=10)
                if idr.status_code == 200:
                    state = (idr.json().get("result") or {}).get("state")
                    reason = f"Not paid / Candidate failed (state={state})" if state else "Not paid / Candidate failed"
                else:
                    reason = "No info"
                log_status(i, total, addr, "EXCLUDED. Reason:", reason)
                continue

            r.raise_for_status()
            rs = r.json().get("result") or {}
            state = rs.get("state")
            penalized = rs.get("penalized", False)
            approved = rs.get("approved", False)
            missed = rs.get("missed", False)
            wrong = rs.get("wrongGrades") or rs.get("wrongGrade")
            base_stake = float(rs.get("stake", 0) or 0)
            short_pts = rs.get("shortFlipPoints") or rs.get("shortAnswersScore")
            long_pts = rs.get("longFlipPoints") or rs.get("longAnswersScore")

            rew_sum = sum_session_reward_stake(epoch, al)
            epoch_stake = base_stake + rew_sum

            if reason is None:
                if penalized:
                    reason = "Penalized"
                elif not approved:
                    reason = "Not approved"
                elif missed:
                    reason = "Missed validation"
                elif wrong:
                    reason = "Low score / wrong grades"
                elif state in ("Candidate", "Suspended"):
                    reason = state
                elif state not in ("Human", "Newbie", "Verified"):
                    reason = f"State {state}"
                elif epoch_stake < dst:
                    reason = f"Stake below threshold (epochStartStake={epoch_stake:.4f} < {dst:.4f})"

            if reason:
                log_status(i, total, addr, "EXCLUDED. Reason:", reason, short_pts, long_pts)
                continue

            out.write(json.dumps({"address": addr, "state": state, "baseStake": base_stake,
                                  "sessionStakeRewardsSum": rew_sum, "epochStartStake": epoch_stake,
                                  "DST": dst}) + "\n")
            whitelist.append(addr)
            log_status(i, total, addr, "OK")
        except Exception as e:
            errors.append((addr, str(e)))
            log_status(i, total, addr, "ERROR", extra=e, short_pts=short_pts, long_pts=long_pts)
        time.sleep(0.18)

    out.close()

    with open(list_file, "w") as f:
        f.write(",\n".join(whitelist))

    with open(meta_file, "w") as f:
        json.dump({"DiscriminationStakeThreshold": dst, "epoch": epoch}, f)

    root, _ = build_merkle_root(whitelist)
    print("\nMERKLE_ROOT =", root)
    with open(f"merkle_root_epoch_{epoch}.txt", "w") as f:
        f.write(root + "\n")

    with open(meta_file, "r+") as f:
        meta = json.load(f)
        meta["merkleRoot"] = root
        f.seek(0), f.truncate(0)
        json.dump(meta, f, indent=2)

    print(f"\nDone. Whitelisted: {len(whitelist)} | Errors: {len(errors)}")
    if errors:
        print("Errors:")
        for a, msg in errors:
            print(f"  {a}: {msg}")

    return len(whitelist)


def main():
    last_epoch, _ = get_latest_epoch_info()
    summary = []
    for offset in range(EPOCHS_TO_LOOK_BACK):
        ep = last_epoch - 1 - offset
        if ep < 0:
            break
        cnt = process_epoch(ep)
        summary.append((ep, cnt))
    with open("eligible_identities_per_epoch.csv", "w") as f:
        f.write("Epoch,EligibleCount\n")
        for ep, cnt in summary:
            f.write(f"{ep},{cnt}\n")
    print("eligible_identities_per_epoch.csv written")


if __name__ == "__main__":
    main()
