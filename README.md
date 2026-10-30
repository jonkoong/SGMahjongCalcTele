# SGMahjongCalcTele <img src="docs/huat-ah.gif" width="80">

Credit: this is a fork of [RyanTanYiWei/SGMahjongCalcTele](https://github.com/RyanTanYiWei/SGMahjongCalcTele) to add shared sessions.

Try it: https://telegram.me/mahjong_tele_bot

## Features
<gif of it being used - 2 tele players, 2 offline players ah gong, ah ma>

- 🧮 Balances are tracked automatically based on who wins
- 📱 All players see the balances on their own phone
- 💸 Automatically calculates who should pay who when the game ends
- 🀄 Does not need all 4 players to join the session

## To run your own bot
Needs ≥ python 3.12

1. Clone this project
   ```
   git clone https://github.com/jonkoong/SGMahjongCalcTele.git
   cd SGMahjongCalcTele
   ```
2. Create a virtualenv and install dependencies
   ```
   python -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   On Windows, use `.venv/Scripts/python.exe` instead of `.venv/bin/python`.
3. Copy `.env.example` to `.env` and set `MJ_TOKEN` to the token from [@BotFather](https://t.me/BotFather)
4. Run it
   ```
   .venv/bin/python mjbot.py
   ```
