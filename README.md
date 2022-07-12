# This is a minter for the cardano blockchain, built with Python and [Koios](https://api.koios.rest/).

This minter work as a shell script that works with the cardano-cli to handle transactions

## Working directory

```
├── db.sqlite
│
├── keys
│   ├── payment.addr
│   ├── payment.skey
│   └── payment.vkey
│
├── main.py
│
├── metadata
│   └── example1.json
│
├── minted
│   ├── example2.json
│   └── example3.json
│
├── policy
│   ├── policy.script
│   ├── policy.skey
│   ├── policy.vkey
│   └── policyID
│
├── protocol.json
│
├── temp
│   └── temp.json
│
├── transactions
│   ├── matx.raw
│   └── matx.signed
│
└── utils.py
```

## .env

```
PAYMENT_ADDR = addr~
PROFIT_ADDR = addr~
POLICY_ID = ~
HALLPASS_POLICY_ID = ~
ROOT_PATH = "~"
```
