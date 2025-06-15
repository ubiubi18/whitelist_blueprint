# whitelist_blueprint
What it does:
- Fetches all blocks from the last short session to extract all involved identities with tx in shortsession to allAddresses.txt
- Saves the current discriminationStakeThreshold.txt
- Filters out against allAdresses.txt: shitflippers, Humans below min stake, and Newbies/Verifieds below 10k IDNA
- Outputs a idena_strict_whitelist.jsonl (should be 249 addresses this epoch)

just a blueprint, will be deleted again
