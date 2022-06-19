# DiscordCryptoBot
My cryptobot, does price alerts, paper trading, crypto rankings, and new crypto listings using the CoinGecko API

Still a work in progress but if you wish to try it out, set up a Discord Bot and get a token.

Required packages
---
* py-cord
* Pillow
* markdownify
* pyyaml

Rename template.yaml to cryptobot-config.yaml and copy the token to this config.
Delete channels/logging/channel and channels/new_crypto/channel if you wish to disable loogging and new crypto reporting. Otherwise set these fields to channel ids where respective messages get posted.

Currently only does price reporting, crypto info, and automated posting of new crypto listings on coingecko.

TODO organize into a python package and put up on pypi or cloud hosting or something.
