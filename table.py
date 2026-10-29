"""Table state and rules. No Telegram here — see mjbot.py for that."""
import random
from typing import NamedTuple

import render
import score

WINDS = ["東", "南", "西", "北"]
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
HELP = "Send /new to open a table, or /join CODE to sit in at one."

# The amount buttons after the tai ladder, in today's exact order (AD15). Keys are score.AMOUNTS
# names, so a label can never drift away from a kernel and this dict doubles as the stage order.
SPECIAL_AMOUNTS = {"kang": "Kang", "kang_an": "Kang 暗", "animal": "🐈",
                   "animal_an": "🐈 暗", "flower": "🥀", "flower_an": "🥀 暗"}
CANCEL = "Cancel"
BACK = "Back"
# The two answers `/end` accepts (AD25). Named, because the words are the whole safety: `Keep playing`
# says what the player gets, where `Back` beside a destructive button would not.
CONFIRM_END = "Confirm end"
KEEP_PLAYING = "Keep playing"

# What a host may set, in the order /settings offers it — the same three the old bot's settings
# markup carried, in its own words (AD15).
SETTINGS = {"rate": "Pay Rate", "shooter": "Shooter", "maxtai": "Max Tai"}

# The taps that change something, and so have to name the version of the screen they were drawn for
# (FR16). `s` is exempt: whether a wind is free is the seat's own decision, and versioning those
# would lock out a joiner who has not seen the newest Board. `b` is exempt because it is the way out
# of a stale screen — versioning it would trap the player there.
VERSIONED = ("w", "a", "p", "x", "k", "g", "v")

# The verbs and what the slash menu says each one does — the spec's Command Surface table,
# in the one place both the menu and any help text can read it from.
COMMAND_HELP = {
    "/start": "Start the bot",
    "/new": "Open a table",
    "/join": "Join a table with its code",
    "/board": "Show the board",
    "/leave": "Free your seat and leave this table",
    "/history": "List tonight's wins",
    "/end": "Settle up and start the next round",
    "/settings": "Rate, shooter, max tai (host only)",
    "/close": "Close this table (host only)",
}

# Every verb the Command Surface promises is now built, so this filter is empty — kept deliberately, as
# the marker of the rule it encodes: a menu that offers a verb which only re-shows the Board teaches
# players that menus lie. Slice 5 emptied it; /prune may remove it once that rule lives elsewhere.
NOT_BUILT = ()


def amount_label(kind, ntai):
    """The words the entry line uses — the same words the button showed (AD15)."""
    return "%d Tai" % ntai if kind == "tai" else SPECIAL_AMOUNTS[kind]


class User(NamedTuple):
    user_id: int
    name: str


class Board(NamedTuple):
    chat_id: int
    text: str
    rows: tuple = ()


class Line(NamedTuple):
    """A fresh message. Only the Board ever carries buttons, so this one never does (FR12)."""
    chat_id: int
    text: str


class Toast(NamedTuple):
    text: str

class Retired(NamedTuple):
    """
    The chat's one live message is spent, because the Table behind it is over. Unlike a Board it is
    not a promise to keep that message current: delivery hands the slot straight back, so the next
    Board the player earns is sent fresh at the bottom of the chat instead of overwriting whatever
    that message has since become.
    """
    chat_id: int
    text: str


class Commands(NamedTuple):
    """
    Which verbs this player can use right now. Delivery puts them in Telegram's slash menu, and
    only spends a call when the answer has actually changed — a player tapping through the three
    stages of a win should not pay for three menu calls.
    """
    chat_id: int
    names: tuple


def commands_for(table, user_id):
    """
    The verbs one player can use. A player is bound to one live Table (FR4), so these resolve
    without a code; the host's two commands go only to the host (FR18, FR21) — and since nothing
    transfers the role, a host who has /leave'd still owns them.

    `/start` is offered only to a chat with no Table (FR26): it says the bot is running, which is news
    exactly once. After that the menu holds things a player at a Table does.
    """
    if table is None:
        wanted = ("/start", "/new", "/join")
    elif table.seat_of(user_id) is None:
        wanted = ("/board", "/leave")
    else:
        wanted = ["/board", "/leave", "/history", "/end"]
        if table.host_id == user_id:
            wanted += ["/settings", "/close"]
    return tuple(command for command in wanted if command not in NOT_BUILT)


def token(kind, code, version, meaning):
    """kind.code.version.meaning — the version is what makes an old keyboard refuse."""
    return "%s.%s.%s.%s" % (kind, code, version, meaning)


def parse_token(data):
    """
    kind.code.version.meaning, or None when the payload is not a token at all.

    The meaning stays a string, because the kinds disagree about what it holds (AD23). Checked here
    rather than left to the caller's `int()`: Telegram redelivers whatever an old keyboard carried,
    so a payload this file never wrote is a shape question, not a rules question, and the answer is
    one refusal — not a ValueError through the polling thread (F-03). A code that names no Table is
    deliberately left to the caller: "That table is gone." is the true answer there, and a player
    who closed the Table by another route deserves to hear it.
    """
    parts = data.split(".")
    if len(parts) != 4:
        return None
    kind, code, version, meaning = parts
    try:
        return kind, code.upper(), int(version), meaning
    except ValueError:
        return None


def new_code(live, rng=random):
    while True:
        code = "".join(rng.choice(CODE_ALPHABET) for _ in range(4))
        if code not in live:
            return code


class Table:
    # Money lives in the wind slot, not the person — see AD4.
    def __init__(self, code, host):
        self.code = code
        self.host_id = host.user_id
        self.members = set()
        self.names = {}
        self.occupants = [None, None, None, None]
        self.balances = [0.0, 0.0, 0.0, 0.0]
        self.rate = 0.1
        self.shooter = True
        self.maxtai = 5
        self.log = []
        self.pending = None
        self.version = 0

    def seat_of(self, user_id):
        return next((i for i, u in enumerate(self.occupants) if u == user_id), None)

    def tai_cap(self):
        """
        The highest amount this Table may offer, and the number it says it pays. The ceiling is the
        frozen ladder's, not the host's (AD23): a rung above it has no payout to give, so it is
        neither offered nor accepted however `maxtai` got its value.
        """
        return min(self.maxtai, score.MAX_TAI)

    def seated_ids(self):
        return [u for u in self.occupants if u is not None]

    def seated_winds(self):
        return [i for i, u in enumerate(self.occupants) if u is not None]

    def free_winds(self):
        return [i for i, u in enumerate(self.occupants) if u is None]

    def occupant_name(self, wind):
        return self.names[self.occupants[wind]] if self.occupants[wind] is not None else None

    def seats_view(self):
        """One row per wind: label, whoever holds it, and the money sitting there."""
        return [(WINDS[wind], self.occupant_name(wind), self.balances[wind])
                for wind in range(len(WINDS))]

    def add_member(self, user):
        self.members.add(user.user_id)
        self.names[user.user_id] = user.name

    def clear_round(self):
        """
        FR19 — the transfers have been said out loud, so the slate is wiped for the next round: every
        balance back to zero and the Entries gone. The roster, the host and the settings stay, because a
        Table is its players and not its arithmetic.

        `score.ZERO` is copied rather than aliased as hygiene, not as a covered risk: nothing here
        mutates a balance list in place (`_commit` rebinds a fresh one), so no test today can force an
        alias and none claims to. Aliasing it would be a latent shared-state bug across Tables (FR5),
        which is why the copy stays even unproven.
        """
        self.balances = list(score.ZERO)
        self.log = []

    def depart(self, user_id):
        """
        Leaving is not just standing up: the Table stops knowing them, so their binding is free for
        another Table (FR4). What stays is the balance in the wind slot they vacated (AD4).
        """
        self.members.discard(user_id)
        self.names.pop(user_id, None)


class Room:
    def __init__(self, rng=None):
        self.rng = rng or random
        self.tables = {}
        self.asked = {}                       # who was asked what, by user id — one question each (AD21)

    def table_of(self, user):
        return next((t for t in self.tables.values() if user.user_id in t.members), None)

    def message(self, user, text):
        return self._sync(user, self._dispatch(user, text))

    def _dispatch(self, user, text):
        parts = text.split()
        command = parts[0].lower() if text.startswith("/") else ""
        if not command:
            asked = self.asked.pop(user.user_id, None)          # one attempt per ask
            answer = text.strip()
            if asked and not answer:
                # A sticker, a photo, a forwarded nothing: it is input, so it ends the ask (AD21), but it
                # is not an attempt at an answer. Reading it as one refused a player for a message they
                # never typed — `No live table called .` — so they are shown where they stand instead.
                return self._board(user)
            if asked == "code":
                return self._join(user, answer)
            if asked == "rate":
                return self._apply_rate(user, answer)
            # /board, /start, a stray photo: anything else shows them where they stand.
            return self._board(user)
        self.asked.pop(user.user_id, None)                      # a command is never an answer
        if command == "/start":
            return self._start(user)
        if command == "/new":
            return self._open(user)
        if command == "/join":
            return self._join(user, parts[1]) if len(parts) > 1 else self._ask_for_code(user)
        if command == "/leave":
            return self._leave(user)
        if command == "/end":
            return self._end(user)
        if command == "/history":
            return self._history(user)
        if command == "/settings":
            return self._settings(user)
        if command == "/close":
            return self._close(user)
        return self._board(user)

    def _ask_for_code(self, user):
        """
        The command menu can only send /join with nothing after it, so the code has to be asked for
        rather than answered with generic help the player cannot act on.

        This is conversational state, which is the family that produced the old stuck chats, so it is
        kept as small as it can be: a set of user ids, and *any* further input from that player — a
        code, a wrong code, any command — clears it. A wrong code therefore costs one refusal and
        nothing else, and nobody can be left inside a prompt they never meant to enter.
        """
        held = self.table_of(user)
        if held:
            return [Line(user.user_id, "You are at table %s. /leave first." % held.code)]
        self.asked[user.user_id] = "code"
        return [Line(user.user_id, "What is the table code? Send it — four characters, like 4KHB.")]

    def tap(self, user, data):
        return self._sync(user, self._tap(user, data))

    def _sync(self, user, effects):
        """
        The slash menu follows the player. Recomputed after whatever just happened, so it describes
        where they stand now rather than where the last effect left them.
        """
        effects = list(effects)
        if not any(isinstance(e, Commands) and e.chat_id == user.user_id for e in effects):
            effects.append(Commands(user.user_id,
                                    commands_for(self.table_of(user), user.user_id)))
        return effects

    def _tap(self, user, data):
        parsed = parse_token(data)
        if parsed is None:
            return [Toast("Nothing is waiting for that tap.")]
        kind, code, version, meaning = parsed
        table = self.tables.get(code)
        if table is None:
            return [Toast("That table is gone.")]
        if user.user_id not in table.members:
            return [Toast("You are not at table %s." % code)]
        if kind in VERSIONED and version != table.version:
            # FR16 — a superseded token names a screen Telegram already replaced. What is exempt, and
            # why, is the VERSIONED list at the top of this file.
            return [Toast("That screen is out of date — send /board for the newest one.")]
        if kind == "s":
            wind = _seat_index(meaning)
            if wind is None:
                return [Toast("That tap makes no sense here.")]
            return self._seat(table, user, wind)
        if kind in ("w", "a", "p", "k") and table.seat_of(user.user_id) is None:
            return [Toast("Take a seat before scoring — pick a wind first.")]
        if kind in ("a", "p", "x") and table.pending is not None and (
                table.pending["holder"] != user.user_id):
            # A draft belongs to whoever started it — see the FR10 retirement in tasking.md.
            return [Toast("%s is entering that win — only they can finish or cancel it."
                          % table.names[table.pending["holder"]])]
        if kind in ("g", "v") and table.host_id != user.user_id:
            # FR18 at the tap, not only at the keyboard: Telegram replays the data an old button
            # carried, so whoever was shown the button decides nothing about who may use it. `b` is
            # exempt — it shows the player their own screen and changes nothing else.
            return [Toast(self._only_host_can(table, "change settings at"))]
        if kind == "g":
            return self._open_setting(table, user, meaning)
        if kind == "v":
            return self._apply_setting(table, user, meaning)
        if kind == "b":
            return self._step_back(table, user, meaning)
        if kind == "w":
            return self._pick_winner(table, user, meaning)
        if kind == "a":
            return self._pick_amount(table, user, meaning)
        if kind == "p":
            return self._pick_payer(table, user, meaning)
        if kind == "x":
            return self._cancel(table, user)
        if kind == "k":
            return self._settle_up(table, user)
        return [Toast("Nothing is waiting for that tap.")]

    def _pick_winner(self, table, user, meaning):
        wind = _seat_index(meaning)
        if wind is None:
            return [Toast("That tap makes no sense here.")]
        if table.pending is not None:
            return [Toast("%s is already entering a win." % table.names[table.pending["holder"]])]
        if table.occupants[wind] is None:
            return [Toast("Nobody sits at %s." % WINDS[wind])]
        table.pending = {"holder": user.user_id, "winner": wind, "amount": None}
        table.version += 1
        return self._show_board(table)

    def _pick_amount(self, table, user, meaning):
        if table.pending is None:
            return [Toast("Pick who won first.")]
        if meaning in SPECIAL_AMOUNTS:
            kind, ntai = meaning, None
        else:
            ntai = _tai_number(meaning, table.tai_cap())
            if ntai is None:
                return [Toast("That amount is not on the board.")]
            kind = "tai"
        table.pending["amount"] = (kind, ntai)
        if score.has_payer_stage(kind):
            table.version += 1
            return self._show_board(table)
        return self._commit(table, None)          # a concealed win never asks who fed

    def _pick_payer(self, table, user, meaning):
        pending = table.pending
        if pending is None or pending["amount"] is None:
            return [Toast("Nothing is waiting for a payer.")]
        if meaning != "z" and _seat_index(meaning) is None:
            # A meaning that is neither Zi Mo nor a seat is not a payer choice — the same rule the
            # amount stage follows (S4.20): the keyboard is not the rule, the tap is refused.
            return [Toast("Pick another seated player, or Zi Mo.")]
        payer = None if meaning == "z" else _seat_index(meaning)
        if payer is not None and (payer == pending["winner"] or table.occupants[payer] is None):
            return [Toast("Pick another seated player, or Zi Mo.")]
        return self._commit(table, payer)

    def _commit(self, table, payer):
        """The one place money moves: called by the amount tap or the payer tap, never both."""
        kind, ntai = table.pending["amount"]
        winner = table.pending["winner"]
        delta = score.amount_delta(kind, winner, payer, ntai=ntai,
                                   rate=table.rate, shooter=table.shooter)
        table.balances = [b + d for b, d in zip(table.balances, delta)]
        line = render.entry_line(table, winner, amount_label(kind, ntai), payer, delta,
                                 concealed=not score.has_payer_stage(kind))
        table.log.append(line)
        table.pending = None
        table.version += 1
        return self._show_board(table)     # the win reads on the Board itself — nothing to send

    def _cancel(self, table, user):
        """FR11 — discard the half-entered Entry: no money moves and nothing is logged."""
        if table.pending is None:
            return [Toast("Nothing is waiting to be cancelled.")]
        table.pending = None
        table.version += 1
        return self._show_board(table)

    def _open(self, user):
        held = self.table_of(user)
        if held:
            return [Line(user.user_id, "You are at table %s already." % held.code)]
        table = Table(new_code(set(self.tables), self.rng), user)
        table.add_member(user)
        self.tables[table.code] = table
        return [self._seat_offer(table, user)]

    def _join(self, user, code):
        held = self.table_of(user)
        if held:
            return [Line(user.user_id, "You are at table %s. /leave first." % held.code)]
        table = self.tables.get(code.upper())
        if table is None:
            return [Line(user.user_id, "No live table called %s. /new opens one." % code.upper())]
        table.add_member(user)
        return [self._seat_offer(table, user)]

    def _seat(self, table, user, wind):
        if table.seat_of(user.user_id) is not None:
            return [Toast("You already sit at %s." % WINDS[table.seat_of(user.user_id)])]
        if table.occupants[wind] is not None:
            return [Toast("%s is taken. Pick another seat." % WINDS[wind])]
        table.occupants[wind] = user.user_id
        table.version += 1
        return self._show_board(table)

    def _leave(self, user):
        """
        FR20 — the wind goes back to the pool and the money stays in it (AD4). A half-entered Entry
        goes with them: only its holder may cancel it, and they have just walked out of reach (Q2).
        A draft names a wind, so leaving as the winner abandons it just as much as starting it.
        """
        table = self.table_of(user)
        if table is None:
            return [Line(user.user_id, "You are not at a table. " + HELP)]
        draft = table.pending
        theirs = draft is not None and (draft["holder"] == user.user_id
                                        or table.occupants[draft["winner"]] == user.user_id)
        wind = table.seat_of(user.user_id)
        if wind is not None:
            table.occupants[wind] = None
        if theirs:
            table.pending = None
        if wind is not None or theirs:
            table.version += 1
        table.depart(user.user_id)
        gone = self._retired(user.user_id, "You have left table %s." % table.code)
        return self._show_board(table) + [gone]

    def _only_host_can(self, table, verb):
        """
        Host-only commands, and the refusal is worth more when it names the person to go and ask. The
        host keeps the role even after /leave (there is no host transfer anywhere in the spec), so by
        then the Table has forgotten their name, and the sentence has to work without it.
        """
        host = table.names.get(table.host_id)
        who = " the host, %s," % host if host else " the host"
        return "Only%s can %s table %s." % (who, verb, table.code)

    def _settings(self, user):
        """
        FR18 — what a Table pays is the host's call alone. The answer is the chat's own Board edited
        into the settings menu (FR12) and nothing else: the buttons changing under the player's eyes is
        the feedback, and a line sent alongside it would sit below the Board for the rest of the night.
        The refusal is a different matter — that one has to say who to go and ask.
        """
        table = self.table_of(user)
        if table is None:
            return [Line(user.user_id, "You are not at a table. " + HELP)]
        if table.host_id != user.user_id:
            return [Line(user.user_id, self._only_host_can(table, "change settings at"))]
        if table.seat_of(user.user_id) is None:
            # Settings ride the Board, and an unseated member is owed a seat picker instead of one.
            return self._take_a_seat(table, user, "set what it pays")
        return [Board(user.user_id, render.board(table), self._settings_rows(table))]

    def _take_a_seat(self, table, user, then):
        """
        One answer for a member who is bound to a Table but holding no wind: the picker they were owed
        anyway, plus the sentence that says why the verb is not theirs yet. The picker on its own can look
        like nothing happened, because that is what their screen already shows.
        """
        return [self._seat_offer(table, user),
                Line(user.user_id, "Take a seat first — pick a wind, then %s." % then)]

    def _settings_rows(self, table):
        """The three settings, then a way out that costs the host no typed command — the old bot's
        settings markup carried `Back` for the same reason."""
        return [[(label, token("g", table.code, table.version, key))
                 for key, label in SETTINGS.items()],
                self._back_row(table, "menu")]

    def _back_row(self, table, where, label=BACK):
        """The way out, labelled with the screen it leaves — so the Table never has to remember who is
        looking at what. `/end` relabels it, because beside a destructive button `Back` is ambiguous."""
        return [(label, token("b", table.code, table.version, where))]

    def _step_back(self, table, user, meaning):
        """
        One level up. `menu` goes back to wherever this player scores, `picker` back to the settings
        the picker came from. Which level a button stood on travels in the button: a Table that
        tracked open screens would be the `chatStatus` FSM this mission deleted (AD21).
        """
        rows = (self._settings_rows(table) if meaning == "picker"
                else self._table_rows(table, user.user_id))
        return [Board(user.user_id, render.board(table), rows)]

    def _apply_setting(self, table, user, meaning):
        """The value buttons. Two ways a tap can name something that is not on offer here; both are
        refusals, so nothing bumps and no one's screen moves."""
        setting, wanted = _setting_value(meaning)
        if setting is None:
            return [Toast("Nothing is waiting for that value.")]
        if wanted is None:
            # Only a stale or forged tap gets here — the picker is built from the same ceiling.
            return [Toast("A table's ladder runs 1 to %d tai." % score.MAX_TAI)]
        return self._write_setting(table, user, setting, wanted)

    def _write_setting(self, table, user, setting, wanted):
        """
        The one place a setting lands. A Table's money rules change and every seated DM is told in the
        same breath (AD24) — the two always move together, because the amount ladder a draft holder is
        offered is drawn from these numbers, and a bump with no fan-out would leave half the Table
        tapping rungs that are gone. A value that already holds costs nobody a call (AD9).
        """
        if wanted == getattr(table, setting):
            return self._settings_screen(table, user)           # nothing changed, so nobody is owed
        setattr(table, setting, wanted)
        table.version += 1
        return self._show_settings(table, user.user_id)

    def _apply_rate(self, user, text):
        """
        The typed answer to `Pay Rate`. Being asked grants nothing: if the Table is gone or the host
        has changed since, the message is treated as what it then is — a stray one.
        """
        table = self.table_of(user)
        if table is None or table.host_id != user.user_id:
            return self._board(user)
        wanted = _rate_value(text)
        if wanted is None:
            return [Line(user.user_id, "That is not a rate — type dollars per point, like 0.2.")]
        return self._write_setting(table, user, "rate", wanted)

    def _settings_screen(self, table, user):
        """The host's own Board, still showing the settings menu."""
        return [Board(user.user_id, render.board(table), self._settings_rows(table))]

    def _show_settings(self, table, viewer):
        """The Board for everyone at the Table, the one who changed it still on the settings menu."""
        return [Board(uid, render.board(table),
                      self._settings_rows(table) if uid == viewer else self._table_rows(table, uid))
                for uid in table.seated_ids()]

    def _open_setting(self, table, user, meaning):
        """One setting opened: pickers where a value is one tap, a question where it is a number."""
        if meaning == "rate":
            return self._ask_for_rate(table, user)
        rows = {"shooter": self._shooter_rows, "maxtai": self._maxtai_rows}.get(meaning)
        if rows is None:
            return [Toast("Nothing is waiting for that tap.")]
        return [Board(user.user_id, render.board(table),
                      rows(table) + [self._back_row(table, "picker")])]

    def _ask_for_rate(self, table, user):
        """
        The rate is the one setting typed rather than tapped: the old bot accepted any number, and a
        row of four buttons would quietly narrow what a host can run a night at. It is asked, not
        remembered as a mode — one outstanding question per player, cleared by whatever they send next
        (AD21). The board already shows the current rate, so the question needs no restating.
        """
        self.asked[user.user_id] = "rate"
        return [Line(user.user_id, "What rate? Type dollars per point, like 0.2.")]

    def _shooter_rows(self, table):
        return [[("On", token("v", table.code, table.version, "shooter1")),
                 ("Off", token("v", table.code, table.version, "shooter0"))]]

    def _maxtai_rows(self, table):
        """
        Every rung the frozen ladder can pay, two to a row like the specials. The ladder's whole span,
        not the Table's current cap: the picker exists to move the cap (AD23).
        """
        rungs = [("%d Tai" % n, token("v", table.code, table.version, "maxtai%d" % n))
                 for n in range(1, score.MAX_TAI + 1)]
        return [rungs[i:i + 2] for i in range(0, len(rungs), 2)]

    def _retired(self, chat_id, text):
        """What a chat is owed once its Table is gone: their message, saying so, no buttons."""
        return Retired(chat_id, text)

    def _close(self, user):
        """FR21 — dissolving a Table is the host's call alone."""
        table = self.table_of(user)
        if table is None:
            return [Line(user.user_id, "You are not at a table. " + HELP)]
        if table.host_id != user.user_id:
            return [Line(user.user_id, self._only_host_can(table, "close"))]
        del self.tables[table.code]
        gone = list(table.members)
        return ([self._retired(uid, "Table %s is closed." % table.code) for uid in gone]
                + [Commands(uid, commands_for(None, uid)) for uid in gone])

    def _start(self, user):
        """
        FR26 as amended (Jon, 2026-10-30) — `/start` starts the bot, and that is all it does. It used to
        print this player's verbs above their Board, which was the slash menu reprinted into the chat:
        `setMyCommands` already sends every verb with its `COMMAND_HELP` description (mjbot.py), so the
        listing was a second menu, one the player had to scroll to.

        A chat with a Table standing does not need a greeting, it needs a pointer, so the line names the
        Table and the verb that shows it. Neither branch touches the Board: a greeting that rewrote the
        chat's live message would replace a player's own stage buttons with the score for the sake of
        saying hello.
        """
        held = self.table_of(user)
        if held is None:
            return [Line(user.user_id, "You are not at a table. " + HELP)]
        return [Line(user.user_id, "You are at table %s — send /board to see it." % held.code)]

    def _board(self, user):
        table = self.table_of(user)
        if table is None:
            return [Line(user.user_id, "You are not at a table. " + HELP)]
        if table.seat_of(user.user_id) is None:
            return [self._seat_offer(table, user)]
        if table.pending is not None:
            return self._show_board(table) + [Line(user.user_id, self._holder_notice(table, user))]
        return self._show_board(table) + [Line(user.user_id, "Tap a name to start a win.")]

    def _holder_notice(self, table, user):
        """
        FR15 — the line names what *this* player can tap. Since the draft became private, the
        holder is told what is left to tap and everyone else is simply told who holds it (FR9).
        """
        pending = table.pending
        if pending["holder"] != user.user_id:
            return "%s is entering a win — only they can finish it." % (
                table.names[pending["holder"]])
        ask = "an amount" if pending["amount"] is None else "who fed it"
        return "You are entering a win — tap %s, or Cancel." % ask

    def _settle_up(self, table, user):
        """
        The confirmed `/end` (FR19): the night is said first, then the slate is wiped, and both halves
        reach every seated DM in the same move — the rule AD24 states for settings, for the same reason.

        The settlement cannot be a `Line`: a message posted under the Board pushes the live Board out of
        reach, which is the drift FR12 exists to prevent. It cannot live on the Board either, because
        FR19 zeroes the balances and clears the log the moment it is re-rendered. So the chat's own
        message *becomes* the settlement and hands its slot back (AD22), and the fresh zeroed Board is
        sent at the bottom as that chat's one live message.

        A half-entered Entry stops it (FR10): `/end` is offered to every seated player, so without this
        check a bystander's confirm could throw away an Entry someone else started, and no confirmation
        buys an override. The refuser's Board is re-rendered too, so the `⏳ Bo is entering a win` line
        shows them the reason next to the words that say it (FR9, FR15).
        """
        if table.pending is not None:
            return [Line(user.user_id, self._end_refusal(table, user)),
                    Board(user.user_id, render.board(table), self._table_rows(table, user.user_id))]
        settled = render.settlement(table)
        table.clear_round()
        table.version += 1
        return [effect for uid in table.seated_ids()
                for effect in (self._retired(uid, settled),
                               Board(uid, render.board(table), self._table_rows(table, uid)))]

    def _end_refusal(self, table, user):
        """
        FR27 (Jon, 2026-10-30) — what a refused `/end` reads. It names the rule the confirm ran into, where
        `_holder_notice`'s "only they can finish it" answers a question the refuser never asked.

        The holder is the exception and keeps the other wording: told that the game cannot end, they still
        need to know which tap they are standing at.
        """
        holder = table.pending["holder"]
        if holder == user.user_id:
            return self._holder_notice(table, user)
        return "Game cannot end when someone is entering a win — %s is entering a win." % (
            table.names[holder])

    def _end(self, user):
        """
        FR19, AD25 — the night's money is about to be said out loud and then forgotten, and there is no
        undo, so the verb asks first. The ask is this chat's own Board message, showing the very transfers
        and totals a confirm will erase, rather than a line beneath the Board (FR12).

        Nothing is stored about who was asked: the answer is a token, so an ask nobody answers is just the
        screen the next win replaces — no prompt to get stuck in, and no second piece of conversational
        state for the `chatStatus` family to grow back from (AD21).
        """
        table = self.table_of(user)
        if table is None:
            return [Line(user.user_id, "You are not at a table. " + HELP)]
        if table.seat_of(user.user_id) is None:
            return self._take_a_seat(table, user, "settle it up")
        return [Board(user.user_id, render.settlement(table), self._end_rows(table))]

    def _end_rows(self, table):
        """Confirm alone on its row: a destructive button never shares one with the way out."""
        return [[(CONFIRM_END, token("k", table.code, table.version, "end"))],
                self._back_row(table, "menu", KEEP_PLAYING)]

    def _history(self, user):
        """
        FR17 — the whole night, in the chat's own message. It cannot be a message of its own: a list
        posted beneath the Board pushes the live Board up the chat, which is the drift FR12 was written
        against, so the Board is edited into the list and `Back` edits it back (`b…menu`, the same escape
        the settings screens use). One Board, to one chat: how long the night was is this player's
        question, and nobody else's screen moves for it. A read, so nothing bumps — a stale nobody else's
        buttons is the one thing a read must never cause.
        """
        table = self.table_of(user)
        if table is None:
            return [Line(user.user_id, "You are not at a table. " + HELP)]
        if table.seat_of(user.user_id) is None:
            # The night's wins belong to the players sitting through them.
            return self._take_a_seat(table, user, "read the night back")
        return [Board(user.user_id, render.history(table), [self._back_row(table, "menu")])]

    def _seat_offer(self, table, user):
        """
        The seat picker rides the chat's own Board message rather than a note beside it, so seating
        edits those buttons away in place — a spent wind row cannot survive on screen (FR12).
        """
        return Board(user.user_id, render.board(table), self._seat_rows(table))

    def _seat_rows(self, table):
        return [[(WINDS[wind], token("s", table.code, table.version, wind))
                 for wind in table.free_winds()]]

    def _show_board(self, table):
        return [Board(uid, render.board(table), self._table_rows(table, uid))
                for uid in table.seated_ids()]

    def _table_rows(self, table, viewer):
        """
        The options one player sees. The score is shared by everyone; the buttons of a draft in
        progress go only to whoever started it (FR9), so nobody taps into a stranger's win.
        """
        pending = table.pending
        if pending is None or pending["holder"] != viewer:
            return [self._winner_row(table)]
        if pending["amount"] is None:
            return self._amount_rows(table) + [self._cancel_row(table)]
        return [self._payer_row(table), self._cancel_row(table)]

    def _winner_row(self, table):
        return [(table.occupant_name(w), token("w", table.code, table.version, w))
                for w in table.seated_winds()]

    def _payer_row(self, table):
        return [(table.occupant_name(w), token("p", table.code, table.version, w))
                for w in table.seated_winds() if w != table.pending["winner"]] + [
                ("Zi Mo", token("p", table.code, table.version, "z"))]

    def _amount_rows(self, table):
        """The tai ladder, then the specials two to a row — six across is unusable on a phone."""
        tai = [("%d Tai" % n, token("a", table.code, table.version, "t%d" % n))
               for n in range(1, table.tai_cap() + 1)]
        buttons = [(label, token("a", table.code, table.version, key))
                   for key, label in SPECIAL_AMOUNTS.items()]
        return [tai] + [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    def _cancel_row(self, table):
        return [(CANCEL, token("x", table.code, table.version, "c"))]


def _digits(text):
    """
    ASCII digits only. `str.isdigit()` also says yes to '²' and to the Arabic-Indic digits, and
    `int()` and `float()` then disagree about them — every tap parser below ends in one of those two,
    and S4.17 and S4.20 promise one refusal rather than a traceback (F-03).
    """
    return bool(text) and all(c in "0123456789" for c in text)


def _seat_index(meaning):
    return int(meaning) if _digits(meaning) and 0 <= int(meaning) < len(WINDS) else None

def _setting_value(meaning):
    """
    Which setting a value tap names, and what it asks for: `shooter1`, `maxtai7`.

    Two answers mean two different refusals. `(None, None)` is not a value any picker emits; `(name,
    None)` names a tai rung above the frozen ladder, which has no payout to give it (AD23).
    """
    for name in ("shooter", "maxtai"):
        digits = meaning[len(name):] if meaning.startswith(name) else ""
        if not _digits(digits):
            continue
        if name == "shooter":
            return (name, digits == "1") if digits in ("0", "1") else (None, None)
        rung = int(digits)
        return name, rung if 1 <= rung <= score.MAX_TAI else None
    return None, None


def _rate_value(text):
    """
    `0.2`, `1`, `.05` — the old bot's rule and no wider: one token, ASCII digits and at most one dot,
    and above zero. Anything else is not a rate, and the host is told rather than corrected.
    """
    if not _digits(text.replace(".", "")) or text.count(".") > 1:
        return None
    return float(text) or None


def _tai_number(meaning, cap):
    """`t3` is 3 tai, if this table can pay that many. Anything else is not an amount."""
    if not (meaning.startswith("t") and _digits(meaning[1:])):
        return None
    ntai = int(meaning[1:])
    return ntai if 1 <= ntai <= cap else None
