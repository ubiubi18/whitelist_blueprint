# whitelist_blueprint

Purpose:
This little python script is meant as a prototype for reproducibly generating an Idena identity whitelist at the end of each validation epoch. The motivation is to automate and document the filtering process for on-chain group access, reward distribution, or similar use cases—ensuring full transparency and reproducibility.

What it does:

    Fetches all blocks from the last short session and extracts every address with a transaction, writing them to allAddresses.txt

    Saves the current discriminationStakeThreshold to stake_threshold.txt for reference

    Filters all addresses in allAddresses.txt:

        Removes “shitflipper” identities

        Excludes Human identities with stake below the minimum threshold

        Excludes Newbie/Verified identities with less than 10,000 IDNA staked

    Outputs a filtered idena_strict_whitelist.jsonl (currently, this epoch, there should be 249 eligible addresses)

Note:
This script is just a temporary proof of concept (“blueprint”) and will be deleted after evaluation.

## Installation

These instructions assume you are new to Python and simply want to run the
`build_idena_identities_strict.py` script locally.

1. **Install Python 3.8 or newer.**
   - Windows/macOS users can download it from <https://www.python.org/downloads/>.
   - Linux users should install it via their package manager (e.g. `apt install python3`).
2. **Install the required Python package.**
   Open a terminal (or command prompt) and run:

   ```bash
   pip install requests
   ```

   This installs the only third‑party dependency used by the script.
3. **Download this repository.**

   ```bash
   git clone https://github.com/ubiubi18/whitelist_blueprint.git
   cd whitelist_blueprint
   ```

4. **Run the script.**

   ```bash
   python build_idena_identities_strict.py
   ```

   The script will fetch data from the Idena API and produce a file called
   `idena_whitelist.jsonl` containing the filtered identities. Auxiliary files
   such as `allAddresses.txt` and `discriminationStakeThreshold.txt` will be
   created in the same folder.

## Legal

This project is a small demo and comes with no promises. Use it at your own risk and double-check results before relying on them.

## License

This repository is distributed under the MIT License. See [LICENSE](./LICENSE) for the full text.
