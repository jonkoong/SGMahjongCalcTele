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
`🐈` / `🥀` / `暗` win names — that is a Windows `cp1252` console limitation, not a bug.

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

**Polling is the supported mode**, and this block is the 2022 bot's, kept so a deploy that already
points at it still runs. It does not carry what the night now leans on: the reconciliation beat does
not start in this mode, Flask's own server is threaded so the one-worker rule that keeps two players
from interleaving a win does not hold, and nothing but the token in the request path guards the route.
Running it means running the bot before slice 2 in those three respects.

## Flow diagrams

`docs/flow.md` maps the session flow: opening and joining, seating, the Entry (winner → amount → who fed
it, and the kinds that commit without asking), undoing the newest win, the keyboard states the Board moves
between, one tap end to end, the money per tap, and how `/end` settles a night and then wipes it.

## Commands

One session per night, four private DMs, one shared Board. A player is bound to one live session, so the
verbs below need no session code after them.

| Command | Who | What it does |
| --- | --- | --- |
| `/start` | new chat only | Starts the bot — the greeting a chat gets before it has a session |
| `/new` | anyone not in a session | Create a session and pick a seat. Its six-character code goes on the first line of the Board, so anyone seated can read it out to whoever is still outside |
| `/join CODE` | anyone not in a session | Join someone else's session with its six-character code, typed whole and in any case; a bare `/join` asks for the code first. Codes are dealt once and never re-dealt while the bot runs, so an old code from last week joins nothing |
| `/history` | seated | Every win of the night, oldest first |
| `/settings` | seated | Pay rate, shooter pay, max tai — anyone holding a seat may set them, because the seat is what makes the night's money theirs |
| `/end` | seated | Open the settle-up screen — the night's totals and every transfer — with the two exits underneath it: **Reset scoreboard** keeps the players in their seats for the next round, **Close session** dissolves the session and frees everyone |
| `/leave` | in a session | Free your seat and leave; the money that seat earned stays there |

The **Board** is the only message the bot keeps editing in your chat: the four seats — `Player 1` to
`Player 4`, filled or empty — who sits where, each seat's balance, what the session pays, and the last three
wins. Older wins are counted, not hidden — `… 4 earlier — /history`. An empty seat is still a seat: it may
win, it may feed, and it owes and is owed in its own slot.

Every button carries the session's version, so a screen you left open is refused as out of date instead of
scoring a second time. Two buttons are excepted: a seat you sit at is judged on whether the seat is free,
and **Back** is how you leave a screen that *is* out of date.

**`Undo last win`** sits under the seats whenever the night holds something to take back. It pops the
newest win and the four totals become whatever the rest of the night adds up to. The button is offered to
every seated player, and the undo shows up in everyone's Board at once, because it is a change to the score
and not one player's private correction. Neither exit on `/end`'s screen is something it can walk back:
resetting empties the ledger the undo works from, and closing destroys the session the ledger lived in. Both
of them print the settlement first and leave it readable, so the numbers survive the thing that erases them.

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
