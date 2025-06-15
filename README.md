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
