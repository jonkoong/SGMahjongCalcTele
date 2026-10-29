# SGMahjongCalcTele
Telegram bot that helps track winnings based on the Singaporean mahjong rules <br>
https://telegram.me/sg_mj_bot  <br>
Deployed via Heroku webhook

## How to use
1. Clone this project.
    > git clone https://github.com/jonkoong/SGMahjongCalcTele.git
2. Create a virtualenv and install python dependencies.
    > python -m venv .venv <br>
    > .venv/Scripts/python.exe -m pip install -r requirements.txt

   On Linux, where `python3-venv` is missing, `uv` does both steps:
    > uv venv .venv && uv pip install -r requirements.txt
3. Configure via environment variables. Copy `.env.example` to `.env` and set `MJ_TOKEN`
   from [@BotFather](https://t.me/BotFather). `.env` is gitignored — never commit a real token.

## Running locally

Polling is the default mode and needs no public URL:

```
MJ_TOKEN=<your token> .venv/Scripts/python.exe mjbot.py
```

On Linux/macOS the venv binary is `.venv/bin/python`. Use `-u` when redirecting
output to a file, otherwise Python buffers the log until the process exits.

On Windows PowerShell, export `MJ_TOKEN` first, or let `config.py` read `.env`.
Set `PYTHONIOENCODING=utf-8` if the console raises `UnicodeEncodeError` on the
東/南/西/北 seat names — that is a Windows `cp1252` console limitation, not a bug.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MJ_TOKEN` | — | Bot token from @BotFather (required) |
| `MJ_MODE` | `polling` | `polling` for local, `webhook` for deploy |
| `MJ_WEBHOOK_URL` | — | Public HTTPS base URL, webhook mode only |
| `MJ_POLL_TIMEOUT` | `5` | `getUpdates` hold time in seconds |
| `MJ_MAX_RETRIES` | `4` | API-layer retries per request |
| `MJ_DEBUG` | off | `1` logs each batch of incoming updates (telebot diagnostics) |

`MJ_POLL_TIMEOUT` is deliberately short. Some networks drop long-held connections to
`api.telegram.org`, and telebot 4.5.1 lets a `ReadTimeout` escape `polling()` and kill the
process — `non_stop=True` does not prevent this. `mjbot.py` therefore retries inside the API
layer and restarts polling if it still drops.

## Deploying (webhook)

Set `MJ_MODE=webhook`, `MJ_WEBHOOK_URL=https://<your-host>/` and run `python mjbot.py`.
The Flask app serves `POST /<token>`; the original deployment target was Heroku.

## Flow diagrams

`docs/flow.md` maps the play flow and the four reply keyboards as mermaid diagrams:
the tap-a-win → payer → totals loop, the Kang / 🐈 / 🥀 bonus rows, and `/end` settlement.

## Commands
**/start:** Restart the Bot<br>
**/settings:** Manage Settings<br>
    > payrate, shooter, maxtai<br>
**/play:** Play the Game (start counting)<br>
    > tai, kang, animals, flowers, manual edits<br>
**/end:** End the Game (allocate payment) <br>

## Screenshots
<p align="center">
  /start <br>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/start.jpg/>
</p>
<p align="center">
  /settings <br>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/settings.jpg/>
</p>
<p align="center">
  /play <br>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/play1.jpg/>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/play2.jpg/>
 </p>

<p align="center">
  /end <br>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/end.jpg/>
</p>
