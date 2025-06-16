# whitelist_blueprint

**Purpose:**  \
This Python script is a prototype for reproducibly generating an Idena identity whitelist at the session day of each validation epoch.  \
The goal is to automate and document the filtering process for on-chain group access, reward distribution, and similar use cases—ensuring full transparency and reproducibility.

## What does it do?
 - Fetches all blocks from the last short session to extract all involved identities with tx in shortsession to allAddresses.txt
 - Saves the current discriminationStakeThreshold.txt
 - Filters out against allAdresses.txt and discriminationStakeThreshold.txt: shitflippers, Humans below min stake, and Newbies/Verifieds below 10k IDNA
 - Outputs an `idena_whitelist.jsonl` file (around 249 addresses in epoch 164, for example)

## Installation

These instructions assume a fresh Linux/Unix system (the commands work on Debian
or Ubuntu). They use a Python virtual environment so that `pip` does not attempt
to modify system packages.

1. **Install Python 3.10+ and the venv module.**
   ```sh
   sudo apt update
   sudo apt install python3 python3-venv git -y
   ```
   Windows/macOS users can simply install Python from <https://www.python.org/downloads/> and
   use a terminal/PowerShell for the remaining steps.

2. **Clone this repository.**
   ```sh
   git clone https://github.com/ubiubi18/whitelist_blueprint.git
   cd whitelist_blueprint
   ```

3. **Create and activate a virtual environment.**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install the required package inside the venv.**
   ```sh
   pip install requests
   ```

5. **Run the script.**
   ```sh
   python build_idena_identities_strict.py
   ```

   It will fetch data from the Idena API and produce:
   - `allAddresses.txt` – all addresses found with short-session transactions
   - `discriminationStakeThreshold.txt` – current minimum stake
   - `idena_whitelist.jsonl` – the filtered whitelist


## Legal

This project is a small demo and comes with no promises. Use it at your own risk and double-check results before relying on them.

## License

This repository is distributed under the MIT License. See [LICENSE](./LICENSE) for the full text.

