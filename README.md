# SGMahjongCalcTele
Telegram bot that helps track winnings based on the Singaporean mahjong rules <br>
https://telegram.me/sg_mj_bot  <br>
Runs on long polling by default; the webhook target is still there for a deploy.

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
| `MJ_MAX_RETRIES` | `4` | API-layer retries per request (polls only — a write is never resent) |
| `MJ_CONNECT_TIMEOUT` | `10` | Seconds to wait for the connection to api.telegram.org |
| `MJ_READ_TIMEOUT` | `10` | Seconds to wait for the response; one stalled call blocks every player, because there is one worker |
| `MJ_BREAKER_AFTER` | `2` | Consecutive failures before writes are held |
| `MJ_BREAKER_COOLDOWN` | `15` | Seconds to hold writes for; a reconciliation beat re-pushes whatever never landed |
| `MJ_RECONCILE_SECONDS` | `5` | How often the beat re-pushes a Board that never landed, and flushes writes the breaker held |
| `MJ_DEBUG` | off | `1` logs each batch of incoming updates (telebot diagnostics) |

`MJ_POLL_TIMEOUT` is deliberately short. Some networks drop long-held connections to
`api.telegram.org`, and telebot has historically let a `ReadTimeout` escape `polling()` and kill the
process — `non_stop=True` does not prevent this. `mjbot.py` therefore retries inside the API
layer and restarts polling if it still drops.

Two more knobs exist for the route rather than the polling: the connect/read timeouts, and the breaker
that holds writes after a couple of failures in a row instead of making every player queue behind a dead
attempt. All of them are in the table above.

## Deploying (webhook)

Set `MJ_MODE=webhook`, `MJ_WEBHOOK_URL=https://<your-host>/` and run `python mjbot.py`.
The Flask app serves `POST /<token>`; the original deployment target was Heroku.

## Flow diagrams

`docs/flow.md` maps the Table flow: opening and joining, seating, the three-stage Entry (winner →
amount → who fed it), the keyboard states the Board moves between, one tap end to end, the money per
tap, and how `/end` settles a night and then wipes it.

## Commands

One Table per night, four private DMs, one shared Board. A player is bound to one live Table, so the
verbs below need no table code after them.

| Command | Who | What it does |
| --- | --- | --- |
| `/start` | anyone | Help — the verbs *you* can use — and where you stand |
| `/new` | anyone not at a Table | Open a Table, become its host, pick a wind |
| `/join CODE` | anyone not at a Table | Sit in at someone else's Table; a bare `/join` asks for the code first |
| `/board` | seated | Refresh the Board and name what you can tap |
| `/history` | seated | Every win of the night, oldest first |
| `/settings` | host | Pay rate, shooter pay, max tai |
| `/end` | seated | Settle up — it asks first — then zero the balances and keep the players |
| `/leave` | seated | Free your wind seat; the money in that seat stays there |
| `/close` | host | Dissolve the Table and free everyone |

The **Board** is the only message the bot keeps editing in your chat: the four winds, who sits where,
each seat's balance, what the Table pays, and the last three wins. Older wins are counted, not hidden —
`… 4 earlier — /history`. Every button carries the Table's version, so a screen you left open is refused
as out of date instead of scoring a second time.

Payouts are the numbers the bot has always produced, quirks included — `docs/flow.md` § Money per tap
is the table of factors.

## Screenshots

_The 2022 reply-keyboard UI, retired: one chat, one game, and a keyboard that had to be resent after
every tap. The bot now runs on inline buttons carried by one Board message per player. Kept for history._

<p align="center">
  /start <br>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/start.jpg/>
</p>
<p align="center">
  /settings <br>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/settings.jpg/>
</p>
<p align="center">
  scoring keypad <br>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/play1.jpg/>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/play2.jpg/>
 </p>

<p align="center">
  /end <br>
  <img height = "400" src=https://github.com/RyanTanYiWei/SGMahjongCalcTele/blob/main/pics/end.jpg/>
</p>
