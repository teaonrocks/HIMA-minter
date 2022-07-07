# This is a minter for the cardano blockchain, built with Python and [Koios](https://api.koios.rest/).

This minter work as a shell script that works with the cardano-cli to handle transactions

## Working directory

```
├── keys  # Created by Cardano-CLI
│   ├── payment.addr
│   ├── payment.skey
│   └── payment.vkey
│
├── main.py
│
├── metadata  # Metadata for individual NFTs
│   ├── NFT1.json
│   └── NFT2.json
│
├── policy  # Created by Cardano-CLI
│   ├── policy.script
│   ├── policy.skey
│   ├── policy.vkey
│   └── policyID
│
├── protocol.json  # Created by Cardano-CLI
│
├── temp  # Temporary json metadata for minting multiple NFTs
│   └── temp.json
│
└── utils.py
```
