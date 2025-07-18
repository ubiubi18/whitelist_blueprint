## Purpose

This Python project generates transparent, reproducible Idena identity whitelists for on-chain group access, reward distribution, or similar trust-based use cases. You can use it to snapshot the eligible participant set at any validation epoch—fully automated, with all eligibility and filtering logic documented in code.

### What does it do?

* **Fetches** all Idena addresses that sent a transaction during the last short session of a validation epoch.
* **Records** eligibility criteria: current DiscriminationStakeThreshold and epoch meta info.
* **Filters for:**

  * Correct identity state (Human, Verified, Newbie)
  * Enough stake (above DiscriminationStakeThreshold) at session start
  * No known “bad flip” penalties
* **Outputs:**

  * A full whitelist with all metadata (`idena_whitelist.jsonl`)
  * Plain address list (`whitelist.txt`)
  * Meta file with epoch info and Merkle root (`whitelist_meta.json`)
  * Merkle root (as a txt file, in historic mode)
* **For historic analysis:** Produces one result set per epoch, plus a summary CSV.

---

## Installation

**Assumptions:**

* You’re on a fresh Linux/Unix system (Debian/Ubuntu).
* All dependencies are installed in a Python virtual environment.

### 1. Install Python 3.10+ and venv

```bash
sudo apt update
sudo apt install python3 python3-venv git -y
```

**Windows/macOS:** Download Python from [python.org/downloads](https://www.python.org/downloads/) and use a terminal or PowerShell for all commands below.

### 2. Clone this repository

```bash
git clone https://github.com/ubiubi18/whitelist_blueprint.git
cd whitelist_blueprint
```

### 3. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:** `venv\Scripts\activate`

### 4. Install dependencies

```bash
pip install requests eth-utils
python -m pip install "eth-hash[pycryptodome]"
```
---

## Usage

### Generate the current epoch’s whitelist

```bash
python IdenaWhitelistGen.py
```

Creates:

* `allAddresses.txt` – all addresses with tx in short session (, including bad actors and failed/killed IDs)
* `idena_whitelist.jsonl` – eligible addresses, full info
* `whitelist.txt` – plain eligible addresses (CSV)
* `whitelist_meta.json` – epoch meta, stake threshold, Merkle root

### Generate historic whitelists and stats

```bash
python IdenaWhitelistHistoricGen.py

```

This will:

* Loop over previous epochs (default: 5 back, configurable in script)
* For each: create per-epoch whitelist, meta, and Merkle root files (named with epoch number)
* Write a summary table: `eligible_identities_per_epoch.csv`

**File outputs (historic mode):**

* `idena_whitelist_epoch164.jsonl`
* `whitelist_meta_epoch164.json`
* `merkle_root_epoch_164.txt`
* ...and so on for each epoch

### Customization

* **Epoch lookback:**
  Edit `EPOCHS_TO_LOOK_BACK` at the top of the historic script.
* **Eligibility logic:**
  All rules are documented in code. Adjust states, penalty, and stake checks as needed.

### Example Console Session

```bash
python IdenaWhitelistGen.py
python IdenaWhitelistHistoricGen.py
cat eligible_identities_per_epoch.csv
```

---

## Validation rules

* Address must be a valid Idena identity
* Stake at session start must be above the epoch's discrimination stake threshold
* Only Human, Verified, or Newbie state included
* Excludes penalized identities (bad flips)

---

## License

MIT License. See LICENSE for details.

> Use at your own risk. Double-check results before production use!
> Questions or issues? Open an issue on GitHub.

---
