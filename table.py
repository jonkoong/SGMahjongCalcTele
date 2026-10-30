"""Table state and rules. No Telegram here — see mjbot.py for that."""
import random
from typing import NamedTuple

import render
import score

# How to read the ids in this file: a bare FR/AD/AS/S-number names mission `01-pooled-table`, the spec
# this code was written against; `02/…` marks the `02-uiux-overhaul` fact that owns the line, and ERR-nn
# is that mission's scrutiny list. Both specs are working documents kept outside this repo.

# The four seats, named by slot. A seat is a place at the table, not a person: two of these labels can
# be on the Board and in a log line at the same time as a name (02/AD5, 02/AD16 — prose says seat, never wind).
SEATS = ["Player 1", "Player 2", "Player 3", "Player 4"]
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   # no O/o, no I/i/l, no 0/1 — 01/FR3
CODE_LENGTH = 6                                       # 02/FR13 — six of them, and never dealt twice
HELP = "Send /new to create a new session, or /join to join an existing one"

# The amount buttons after the tai ladder, in today's exact order (01/AD15). Keys are score.AMOUNTS
# names, so a label can never drift away from a kernel and this dict doubles as the stage order.
SPECIAL_AMOUNTS = {"kang": "Kang", "kang_an": "Kang 暗", "animal": "🐈",
                   "animal_an": "🐈 暗", "flower": "🥀", "flower_an": "🥀 暗"}
CANCEL = "Cancel"
BACK = "Back"
# 02/AD12 — `win`, not `round`: a round is what survives between two `/end`s, and this button takes back
# one scored Entry, not the night.
UNDO_LAST = "Undo last win"
# The three answers the settle-up screen accepts (04/D1). Named, because the words are the whole safety:
# `Keep playing` says what the player gets, where `Back` beside a destructive button would not, and each
# of the other two names what it does to the night instead of saying "confirm".
RESET_SCOREBOARD = "Reset scoreboard"
CLOSE_SESSION = "Close session"
KEEP_PLAYING = "Keep playing"

# The one sentence for "the screen you tapped has already been replaced" (02b/D9, 02b/D10). The version
# check says it, and so does every guard whose only honest story is staleness — a button that exists at
# another stage arriving at this one, a token naming a screen this bot never drew. Ten sites, one wording:
# named so the popup cannot drift from the screen it re-draws beside itself.
OUTDATED = "That message is outdated, tap on the new message or wait for it to be refreshed."

# What a seated player may set, in the order /settings offers it — the same three the old bot's settings
# markup carried, in its own words (01/AD15).
SETTINGS = {"rate": "Pay Rate", "shooter": "Shooter", "maxtai": "Max Tai"}

# The taps that change something, and so have to name the version of the screen they were drawn for
# (01/FR16). `s` is exempt: whether a seat is free is the seat's own decision, and versioning those
# would lock out a joiner who has not seen the newest Board. `b` is exempt because it is the way out
# of a stale screen — versioning it would trap the player there.
VERSIONED = ("w", "a", "p", "x", "k", "g", "v", "u")

# Which taps ask for what (02/FR11). Named because they are read by `_tap` in order, and a fourth hand-
# maintained tuple of kinds is the trap that let the four settings rules drift apart in four places.
# `_NEEDS_SEAT` is the night's money; `_NEEDS_RULES` is what the night pays out.
_NEEDS_SEAT = ("w", "a", "p", "k", "u")
_NEEDS_RULES = ("g", "v")

# One refusal, said at two doors (02b/D13): a bare `/join` and `/join CODE` both land on it when the player
# is already bound to a session, and the sentence cannot be allowed to read differently between them.
# The `%s` is the code they are already in.
IN_SESSION_LEAVE_FIRST = "You are in session %s. /leave it first to join another session."

# The verbs and what the slash menu says each one does — the spec's Command Surface table,
# in the one place both the menu and any help text can read it from.
COMMAND_HELP = {
    "/start": "Start the bot",
    "/new": "Create a session",
    "/join": "Join a session with its code",
    "/leave": "Free your seat and leave this session",
    "/history": "List tonight's wins",
    "/end": "Settle up — reset the scoreboard or close the session",
    "/settings": "Rate, shooter, max tai",
}

# Every verb the Command Surface promises is now built, so this filter is empty — kept deliberately, as
# the marker of the rule it encodes: a menu that offers a verb which only re-shows the Board teaches
# players that menus lie. Slice 5 emptied it; /prune may remove it once that rule lives elsewhere.
NOT_BUILT = ()


def amount_label(kind, ntai):
    """The words the entry line uses — the same words the button showed (01/AD15)."""
    return "%d Tai" % ntai if kind == "tai" else SPECIAL_AMOUNTS[kind]


class User(NamedTuple):
    user_id: int
    name: str


class Board(NamedTuple):
    chat_id: int
    text: str
    rows: tuple = ()


class Line(NamedTuple):
    """A fresh message. Only the Board ever carries buttons, so this one never does (01/FR12)."""
    chat_id: int
    text: str


class Toast(NamedTuple):
    text: str


class Entry(NamedTuple):
    """
    One committed win: the sentence the players read, and the money that moved behind it, written in
    the same breath (01/FR14, 02/AD1). The pair is what makes undo a pop instead of a subtraction — and
    because the words are frozen here, a past win never gets re-credited to whoever holds the seat
    later (ERR-01).
    """
    text: str
    delta: tuple

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
    The verbs one player can use. A player is bound to one live Table (01/FR4), so these resolve
    without a code. No verb is reserved to a role any more — `/settings` stopped being one with 02/FR11 and
    `/close` stopped being one with 04/D4, leaving the seat as the only test the bot applies — and a player
    who is not at the Table is offered none of it, because `table_of` finds nothing for them any more.

    Everything else a seated player is offered, they may use: `/settings` joined the seated menu with
    02/FR11, since a menu that offers a verb which refuses the tap teaches players that menus lie.

    `/start` is offered only to a chat with no Table (FR26): it says the bot is running, which is news
    exactly once. After that the menu holds things a player at a Table does.
    """
    if table is None:
        wanted = ("/start", "/new", "/join")
    elif table.seat_of(user_id) is None:
        wanted = ("/leave",)
    else:
        wanted = ["/leave", "/history", "/end", "/settings"]
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
    deliberately left to the caller: "That session does not exist anymore." is the true answer there, and a
    player who closed it by another route deserves to hear it.
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
    """
    Six characters of `CODE_ALPHABET`, and never the code before (02/FR13, 01/FR3).

    The random source picks *positions in the alphabet*, never characters: `rng.choice(alphabet)` would
    hand back whatever the caller's rng hands back, and a code that reaches a player with an `O` in it,
    or a lowercase letter that no keyboard will match, is a Table nobody can join. The alphabet stays
    the only thing that can spell a code, and the rng only ever says which letter of it.

    A repeat is stepped over, not written down (01/FR3): two live Tables on one code would mean a `/join`
    that seats a player at the wrong night, and the letters are the whole address. `Room` passes it every
    code it has ever dealt, so a dissolved Table's letters are repeats too (02/AD8).
    """
    while True:
        code = "".join(CODE_ALPHABET[rng.randrange(len(CODE_ALPHABET))] for _ in range(CODE_LENGTH))
        if code not in live:
            return code


class Table:
    def __init__(self, code):
        self.code = code
        self.members = set()
        self.names = {}
        self.occupants = [None] * len(SEATS)
        self.rate = 0.1
        self.shooter = True
        self.maxtai = 5
        self.log = []          # the night's only money fact — see `balances`
        self.pending = None
        self.version = 0

    def seat_of(self, user_id):
        return next((i for i, u in enumerate(self.occupants) if u == user_id), None)

    def tai_cap(self):
        """
        The highest amount this Table may offer, and the number it says it pays. The ceiling is the
        frozen ladder's, not whoever set it (AD23): a rung above it has no payout to give, so it is
        neither offered nor accepted however `maxtai` got its value.
        """
        return min(self.maxtai, score.MAX_TAI)

    def seated_ids(self):
        return [u for u in self.occupants if u is not None]

    def seat_label(self, seat):
        """What the seat is called — a slot name, whether or not anybody is in it (02/AD6)."""
        return SEATS[seat]

    def is_free(self, seat):
        """
        Whether anybody holds the seat. A separate read from the label on purpose (ERR-03): the seated
        count and the seat picker both ask this, and if either asked the label instead, an empty table
        would cheerfully report `4 of 4 seated`.
        """
        return self.occupants[seat] is None

    def free_seats(self):
        return [seat for seat in range(len(SEATS)) if self.is_free(seat)]

    def occupant_name(self, seat):
        """Whoever holds the seat, or None. Never the slot's own label — see `is_free`."""
        return self.names[self.occupants[seat]] if self.occupants[seat] is not None else None

    def name_for(self, seat):
        """
        Who a button or a sentence calls this seat: the player in it, or the slot itself (02/FR5, 02/AD5).

        The one place the two are composed, because the rule shows up twice over — on the winner and
        feeder rows, and in every Entry line — and a win must not read `from None` in one of them.
        """
        return self.occupant_name(seat) or self.seat_label(seat)

    @property
    def balances(self):
        """
        What each seat is up: the stored vectors folded left to right, in log order (02/AD2).

        Derived, and with no setter, on purpose. Money lives in the seat, not the person (01/AD4), and the
        ledger is the night's only money fact — the moment a total could be written on its own it could
        also drift from the wins that made it, and undo would be two jobs instead of one pop.

        Left to right is part of the contract, not a preference: these are binary fractions, so a
        different order leaves different residue, and `/end` prints cents off the frozen numbers (02/AD3).
        A stored vector is never re-priced either — replaying the Entries through `score` at the live
        rate would let tomorrow's rate change rewrite last night's wins.
        """
        total = list(score.ZERO)
        for entry in self.log:
            total = [b + d for b, d in zip(total, entry.delta)]
        return total

    def may_set_rules(self, user_id):
        """
        Who may change what this Table pays (02/FR11): anybody holding a seat. The seat is the whole test —
        the only way into one is through the roster, so it implies membership — which is why the rule is
        one read asked one way by the menu, the tap, `/settings` and the typed rate (ERR-04).
        """
        return self.seat_of(user_id) is not None

    def seats_view(self):
        """One row per seat: its label, whoever holds it, and the money sitting there."""
        balances = self.balances
        return [(self.seat_label(seat), self.occupant_name(seat), balances[seat])
                for seat in range(len(SEATS))]

    def add_member(self, user):
        self.members.add(user.user_id)
        self.names[user.user_id] = user.name

    def clear_round(self):
        """
        FR19 — the transfers have been said out loud, so the slate is wiped for the next round. Clearing
        the ledger is the whole of it: the balances are what the fold of an empty ledger gives, so there
        is no second thing to zero and nothing to forget to zero. The roster and the settings stay,
        because a Table is its players and not its arithmetic.
        """
        self.log = []

    def depart(self, user_id):
        """
        Leaving is not just standing up: the Table stops knowing them, so their binding is free for another
        Table (01/FR4). What stays is the balance in the seat they vacated (01/AD4) and nothing else — the
        name goes with the person, so no screen goes on calling an empty seat by it.
        """
        self.members.discard(user_id)
        self.names.pop(user_id, None)


class Room:
    def __init__(self, rng=None):
        self.rng = rng or random
        self.tables = {}
        # Every code this process has ever dealt, live or dissolved (02/AD8, 02/FR13). A code is a key: re-dealing
        # a dissolved Table's letters would seat a player who kept an old code in their chat history at a
        # night they were never invited to, and they would never know it was a different night.
        # The window is the process lifetime — a deploy forgets these, and that gap is accepted (02/AS3).
        self.spent = set()
        self.asked = {}                       # who was asked what, by user id — one question each (01/AD21)

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
                # A sticker, a photo, a forwarded nothing: it is input, so it ends the ask (01/AD21), but it
                # is not an attempt at an answer. Reading it as one refused a player for a message they
                # never typed — `No live session with code .` — so they are shown where they stand instead.
                return self._board(user)
            if asked == "code":
                return self._join(user, answer)
            if asked == "rate":
                return self._apply_rate(user, answer)
            # /start, a stray photo, and any verb the menu no longer offers — including a typed /board
            # and the /close this bot deleted. None of them is refused: the answer is where they stand.
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
            return [Line(user.user_id, IN_SESSION_LEAVE_FIRST % held.code)]
        self.asked[user.user_id] = "code"
        # 02b/D12 — the ask is a command, not a question. It used to name the six-character shape and show
        # an example of it (02/FR14), which is why CODE_EXAMPLE existed; the shape is on a seated player's
        # Board, and a made-up code costs exactly one refusal either way, so the example carried nothing
        # but characters. The length rule itself (02/FR13) is untouched.
        return [Line(user.user_id, "Enter the session code.")]

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
            # The only refusal in this channel with words of its own and no screen to show with them: the
            # payload names no session, so there is no screen to re-draw (02b/D9).
            return [Toast("Error, please try again.")]
        kind, code, version, meaning = parsed
        table = self.tables.get(code)
        if table is None:
            return [Toast("That session does not exist anymore.")]
        if user.user_id not in table.members:
            return [Toast("You are not in session %s." % code)]
        if kind in VERSIONED and version != table.version:
            # 01/FR16 — a superseded token names a screen Telegram already replaced. What is exempt, and
            # why, is the VERSIONED list at the top of this file. The heal is what makes the sentence's
            # "wait for it to be refreshed" true (02b/D6a): this tap re-draws this player's own screen.
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        if kind == "s":
            seat = _seat_index(meaning)
            if seat is None:
                # The same story as a winner token naming a seat outside 0-3: no seat row this bot drew
                # ever carried it, so the screen that did has been replaced (02b/D9).
                return [Toast(OUTDATED)] + self._where_you_stand(table, user)
            return self._seat(table, user, seat)
        if kind in _NEEDS_SEAT and table.seat_of(user.user_id) is None:
            # Every tap that touches the night's money needs a seat, because that is where the money
            # sits (01/AD4) — including undo, whose button a member can still be looking at when they stop
            # holding one. `x` is absent because only the holder of a draft may cancel one, which the
            # check below owns; `g` and `v` are gated by _NEEDS_RULES below. The answer is the picker
            # itself rather than a sentence about it (02b/D9).
            return self._where_you_stand(table, user)
        if kind in ("a", "p", "x") and table.pending is not None and (
                table.pending["holder"] != user.user_id):
            # A draft belongs to whoever started it — the rule that used to make the first player to
            # open a win the only one who could finish it was retired. The guard is what stops a
            # bystander setting the holder's amount (01/FR9); since 02b/D9 the tapper's own Board is what
            # answers, because the `⏳` line on it already says who holds it.
            return self._where_you_stand(table, user)
        if kind in _NEEDS_RULES and not table.may_set_rules(user.user_id):
            # 02/FR11 at the tap, not only at the keyboard: Telegram replays the data an old button
            # carried, so whoever was shown the button decides nothing about who may use it. A member
            # bound to the session with no seat is owed the picker plus the words that say what is missing
            # — a Toast alone would look like nothing happened. `b` is exempt: it shows the player their
            # own screen and changes nothing else.
            return self._take_a_seat(table, user, "changing settings")
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
        if kind == "k" and meaning == "reset":
            return self._settle_up(table, user)
        if kind == "k" and meaning == "close":
            return self._close_session(table, user)
        if kind == "u":
            return self._undo_last(table, user)
        # A token this bot never wrote: a `k` naming the confirm button 04 deleted, a `g` for a screen
        # that is not one of the three. It parsed, the session is in scope, and the honest story is that
        # the screen carrying it has already been replaced (02b/D9).
        return [Toast(OUTDATED)] + self._where_you_stand(table, user)

    def _where_you_stand(self, table, user):
        """
        What a refused tap answers with instead of explaining itself (02b/D9, 02b/D11) — the heal behind
        "silence", which is never `return []`: the screen answers, the popup explains.

        The picker for a member holding no seat, because a popup alone would tell them something is
        missing with nothing on screen to press; their own Board for everybody else. One helper, because
        ten guards want exactly this and a hand-rolled ninth copy is how the four settings rules drifted
        apart once already.

        It never bumps `table.version`. A refusal that retires everybody else's keyboards is a worse bug
        than the popup it replaced, and the suite says so from four different angles.
        """
        if table.seat_of(user.user_id) is None:
            return [self._seat_offer(table, user)]
        return [Board(user.user_id, render.board(table), self._table_rows(table, user.user_id))]

    def _pick_winner(self, table, user, meaning):
        seat = _seat_index(meaning)
        if seat is None:
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        if table.pending is not None:
            return [Toast("%s is already entering a win." % table.names[table.pending["holder"]])]
        # 02/FR3 — an empty seat may win. What used to be refused here did not just withhold a tap: it left
        # a short-handed table unable to book a win that belonged to a slot they were not sitting in.
        table.pending = {"holder": user.user_id, "winner": seat, "amount": None}
        table.version += 1
        return self._show_board(table)

    def _pick_amount(self, table, user, meaning):
        if table.pending is None:
            # Amount buttons exist only above a draft, so this arrives from a replaced screen — and the
            # Board this tap re-draws already ends by asking for the winner (02b/D2, 02b/D9).
            return self._where_you_stand(table, user)
        if meaning in SPECIAL_AMOUNTS:
            kind, ntai = meaning, None
        else:
            ntai = _tai_number(meaning, table.tai_cap())
            if ntai is None:
                return [Toast(OUTDATED)] + self._where_you_stand(table, user)
            kind = "tai"
        table.pending["amount"] = (kind, ntai)
        if score.has_payer_stage(kind):
            table.version += 1
            return self._show_board(table)
        return self._commit(table, None)          # a concealed win never asks who fed

    def _pick_payer(self, table, user, meaning):
        pending = table.pending
        if pending is None or pending["amount"] is None:
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        if meaning != "z" and _seat_index(meaning) is None:
            # A meaning that is neither Zi Mo nor a seat is not a payer choice — the same rule the
            # amount stage follows (S4.20): the keyboard is not the rule, the tap is refused. Cut the
            # guard and the junk falls through to `payer = None`, which is exactly what Zi Mo means,
            # and books a self-fed win (F-05). 02b/D15: it shares the out-of-date line.
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        payer = None if meaning == "z" else _seat_index(meaning)
        if payer is not None and payer == pending["winner"]:
            # 02/FR4 — any seat but the winner's may feed, filled or empty: an empty one pays out of its
            # own slot, exactly as it earns into one (01/AD4). Naming yourself is still not a feeder, and
            # that is a rule rather than a stale screen — so it goes quiet with a re-draw (02b/D9) and
            # the winner's own seat is not offered on the row in the first place.
            return self._where_you_stand(table, user)
        return self._commit(table, payer)

    def _commit(self, table, payer):
        """The one place money moves: called by the amount tap or the payer tap, never both."""
        kind, ntai = table.pending["amount"]
        winner = table.pending["winner"]
        delta = score.amount_delta(kind, winner, payer, ntai=ntai,
                                   rate=table.rate, shooter=table.shooter)
        line = render.entry_line(table, winner, amount_label(kind, ntai), payer, delta,
                                 concealed=not score.has_payer_stage(kind))
        table.log.append(Entry(line, tuple(delta)))
        table.pending = None
        table.version += 1
        return self._show_board(table)     # the win reads on the Board itself — nothing to send

    def _cancel(self, table, user):
        """01/FR11 — discard the half-entered Entry: no money moves and nothing is logged."""
        if table.pending is None:
            # `Cancel` exists only under a draft. Nothing corrupts here, so the tap is genuinely one that
            # arrived from a replaced screen — and the heal is what keeps it from looking like nothing
            # happened (02b/D9).
            return self._where_you_stand(table, user)
        table.pending = None
        table.version += 1
        return self._show_board(table)

    def _undo_last(self, table, user):
        """
        02/FR7 — the newest win comes back out, and the four totals are whatever the rest of the ledger
        adds up to. No inverse is computed, because there is nothing to invert: the Entry went in as a
        vector and comes out as one, so the night ends where the one before it ended, cents and all.

        The version moves with it and every seated Board is re-drawn (02/FR9) — the Board is the undo's
        feedback (02/AD14), and the bump is also what retires the screens that showed the win.
        """
        if table.pending is not None:
            # Reachable by an honest tap: `Undo last win` shows to every seated player. It keeps words,
            # and they are the ones 02b/D10 ruled — the clause is `render.entering`, the same words the
            # Board's `⏳` line prints beside this very button.
            return [Toast("Cannot undo while %s, wait for them to finish or cancel it."
                          % render.entering(table.names[table.pending["holder"]]))]
        if not table.log:
            # 02b/D9 — the keyboard hides the button with an empty ledger, but the keyboard is not the
            # rule: a replayed token still arrives here, and the alternative to refusing it is an
            # `IndexError` through the polling thread. What it arrives from is a screen the settlement or
            # a reset already replaced, which is the one true sentence here.
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        table.log.pop()
        table.version += 1
        return self._show_board(table)

    def _open(self, user):
        """
        02/FR13 — the code is dealt with the Table: six characters, never dealt twice while the process
        lives. It lives on the Board's first line from then on (not a requirement — Jon reverted the
        hiding rule, 2026-10-30): that message is already in every seated chat, it is
        not going anywhere, and it is the only place a player can read it aloud to whoever is still
        outside. So `/new` adds nothing to say — the seat picker below already carries the header
        (01/FR12: one message, edited, not two sent).
        """
        held = self.table_of(user)
        if held:
            return [Line(user.user_id, "You are in session %s already. To create a new session, leave "
                                       "the current session first with /leave, then use /new."
                         % held.code)]
        # Drawn against every code ever dealt, not just the live ones: `tables` alone would let a closed
        # Table's letters come back round, and a re-cut key opens the door to whoever kept the old copy
        # (02/AD8, 02/FR13). Six characters is what makes that collision-resistant enough to matter.
        table = Table(new_code(self.spent, self.rng))
        table.add_member(user)
        self.spent.add(table.code)
        self.tables[table.code] = table
        return [self._seat_offer(table, user)]

    def _join(self, user, code):
        held = self.table_of(user)
        if held:
            return [Line(user.user_id, IN_SESSION_LEAVE_FIRST % held.code)]
        table = self.tables.get(code.upper())
        if table is None:
            return [Line(user.user_id, "No live session with code %s. Re-enter the code."
                                      % code.upper())]
        table.add_member(user)
        return [self._seat_offer(table, user)]

    def _seat(self, table, user, seat):
        held = table.seat_of(user.user_id)
        if held is not None:
            return [Toast("You already sit at %s." % table.seat_label(held))]
        if not table.is_free(seat):
            # A seatless player's Board is never edited again (`_show_board` walks the seated), so a
            # popup alone would say "pick another" with nothing left on screen to pick. The fresh offer
            # beside it is convenience, not rescue: `/leave` then `/join CODE` already works (02b/D6c).
            return [Toast("%s is taken. Pick another seat." % table.seat_label(seat)),
                    self._seat_offer(table, user)]
        table.occupants[seat] = user.user_id
        table.version += 1
        return self._show_board(table)

    def _leave(self, user):
        """
        01/FR20 — the seat goes back to the pool and the money stays in it (01/AD4). A half-entered Entry
        goes with them: only its holder may cancel it, and they have just walked out of reach (Q2).
        A draft names a seat, so leaving as the winner abandons it just as much as starting it.
        """
        table = self.table_of(user)
        if table is None:
            return self._no_table(user)
        draft = table.pending
        theirs = draft is not None and (draft["holder"] == user.user_id
                                        or table.occupants[draft["winner"]] == user.user_id)
        seat = table.seat_of(user.user_id)
        if seat is not None:
            table.occupants[seat] = None
        if theirs:
            table.pending = None
        if seat is not None or theirs:
            table.version += 1
        table.depart(user.user_id)
        gone = self._retired(user.user_id, "You have left session %s." % table.code)
        return self._show_board(table) + [gone]

    def _settings(self, user):
        """
        02/FR11 — what a Table pays is decided by whoever is sitting at it. The answer is the chat's own
        Board message edited into the settings menu (01/FR12) and nothing else: the buttons changing under
        the player's eyes is the feedback, and a line sent alongside it would sit below the Board for the
        rest of the night. There is no refusal left that has to say who to go and ask: the seat is the
        whole rule, and a member with no seat is shown the picker they were owed anyway.
        """
        table = self.table_of(user)
        if table is None:
            return self._no_table(user)
        if not table.may_set_rules(user.user_id):
            # Settings ride the Board, and an unseated member is owed a seat picker instead of one.
            return self._take_a_seat(table, user, "accessing /settings")
        return [Board(user.user_id, render.board(table), self._settings_rows(table))]

    def _take_a_seat(self, table, user, then):
        """
        One answer for a member who is bound to a Table but holding no seat: the picker they were owed
        anyway, plus the sentence that says why the verb is not theirs yet. The picker on its own can look
        like nothing happened, because that is what their screen already shows.

        One stem, five endings (02b/D7): what you were reaching for is the fact, and the sentence around it
        is the same five ways. Written once, here — the five call sites supply the only variable part.
        """
        return [self._seat_offer(table, user),
                Line(user.user_id, "Pick a seat before %s." % then)]

    def _no_table(self, user):
        """
        The one answer a chat with no session gets, whichever verb it asked with. Five typed verbs end
        here — `/start`, `/leave`, `/settings`, `/end`, `/history` — and the catch-all beside them, so the
        sentence lives once: the same move 02b/D7 made of the seat refusal above.
        """
        return [Line(user.user_id, "You are not in a session. " + HELP)]

    def _settings_rows(self, table):
        """The three settings, then a way out that costs the player no typed command — the old bot's
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
        tracked open screens would be the `chatStatus` FSM this mission deleted (02/AD21).
        """
        rows = (self._settings_rows(table) if meaning == "picker"
                else self._table_rows(table, user.user_id))
        return [Board(user.user_id, render.board(table), rows)]

    def _apply_setting(self, table, user, meaning):
        """The value buttons. Two ways a tap can name something that is not on offer here; neither is a
        rule the player broke, so neither costs words (02b/D9) — and nothing bumps, so no one's screen
        moves on its own."""
        setting, wanted = _setting_value(meaning)
        if setting is None:
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        if wanted is None:
            # Only a stale or forged tap gets here — the picker offers all ten rungs whatever the session
            # caps at, so the picker is the answer, and it shows the span far better than the sentence
            # that used to describe it (02b/D9).
            return self._where_you_stand(table, user)
        return self._write_setting(table, user, setting, wanted)

    def _write_setting(self, table, user, setting, wanted):
        """
        The one place a setting lands. A Table's money rules change and every seated DM is told in the
        same breath (AD24) — the two always move together, because the amount ladder a draft holder is
        offered is drawn from these numbers, and a bump with no fan-out would leave half the Table
        tapping rungs that are gone. A value that already holds costs nobody a call (01/AD9).

        A rate change also hands back whatever rung the draft holder had already chosen: money is
        priced at commit, so a rung kept over a rate move would commit at a price nobody tapped, and
        the rung is not shown on the who-fed screen. The winner stays picked (Jon's ruling,
        2026-10-30). A Max Tai change does not: S4.15 rules a cap constrains what
        may be chosen from now on, not what was already tapped, and Shooter is left as it was.
        """
        if wanted == getattr(table, setting):
            return self._settings_screen(table, user)           # nothing changed, so nobody is owed
        setattr(table, setting, wanted)
        if setting == "rate" and table.pending is not None:
            table.pending["amount"] = None                      # back to the ladder, at the new rate
        table.version += 1
        return self._show_settings(table, user.user_id)

    def _apply_rate(self, user, text):
        """
        The typed answer to `Pay Rate`. Being asked grants nothing: the rule is the same one the menu,
        the tap and `/settings` ask (02/FR11), because the ask and the answer arrive a message apart and the
        seat could have been given up in between. The answer is not thrown away either: a player who lost
        the right in between is landed on the settings screen they opened, not on the score (ERR-04).
        """
        table = self.table_of(user)
        if table is None:
            return self._board(user)
        if not table.may_set_rules(user.user_id):
            return self._take_a_seat(table, user, "changing the pay rate")
        wanted = _rate_value(text)
        if wanted is None:
            return [Line(user.user_id, "Rate not accepted. Enter a number greater than 0, like 0.5 "
                                      "for 50 cents.")]
        return self._write_setting(table, user, "rate", wanted)

    def _settings_screen(self, table, user):
        """The one Board that stays on the settings menu, while the others show the score."""
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
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        return [Board(user.user_id, render.board(table),
                      rows(table) + [self._back_row(table, "picker")])]

    def _ask_for_rate(self, table, user):
        """
        The rate is the one setting typed rather than tapped: the old bot accepted any number, and a
        row of four buttons would quietly narrow what a night can be run at. It is asked, not
        remembered as a mode — one outstanding question per player, cleared by whatever they send next
        (01/AD21). The board already shows the current rate, so the question needs no restating.
        """
        self.asked[user.user_id] = "rate"
        return [Line(user.user_id, "What rate? Eg: 0.2 for 20 cents, 1.5 for $1.50.")]

    def _shooter_rows(self, table):
        return [[("On", token("v", table.code, table.version, "shooter1")),
                 ("Off", token("v", table.code, table.version, "shooter0"))]]

    def _maxtai_rows(self, table):
        """
        Every rung the frozen ladder can pay, two to a row like the specials. The ladder's whole span,
        not the Table's current cap: the picker exists to move the cap (AD23).
        """
        rungs = [(amount_label("tai", n), token("v", table.code, table.version, "maxtai%d" % n))
                 for n in range(1, score.MAX_TAI + 1)]
        return [rungs[i:i + 2] for i in range(0, len(rungs), 2)]

    def _retired(self, chat_id, text):
        """What a chat is owed once its Table is gone: their message, saying so, no buttons."""
        return Retired(chat_id, text)

    def _close_session(self, table, user):
        """
        04/D3 — the Table is destroyed and every member is freed from it, seated or not (01/FR4): a member
        who joined and never sat is bound to it all the same, and a binding outliving its Table is a player
        stuck unable to `/new` or `/join` anything.

        A half-entered Entry stops a bystander at either exit, exactly as it stops the reset (02b/D8):
        the confirmation 04/D5 moved onto this screen was never what bought the right to discard someone
        else's win. The holder is not stopped — closing destroys the `Table` outright, and the draft dies
        with it, which is the one exit that needs no clearing.
        """
        refused = self._draft_stops(table, user)
        if refused:
            return refused
        del self.tables[table.code]
        gone = list(table.members)
        farewell = render.session_closed(table)
        return ([self._retired(uid, farewell) for uid in gone]
                + [Commands(uid, commands_for(None, uid)) for uid in gone])

    def _start(self, user):
        """
        FR26 as amended (Jon, 2026-10-30) — `/start` starts the bot, and that is all it does. It used to
        print this player's verbs above their Board, which was the slash menu reprinted into the chat:
        `setMyCommands` already sends every verb with its `COMMAND_HELP` description (mjbot.py), so the
        listing was a second menu, one the player had to scroll to.

        A chat with a Table standing gets **nothing at all** (02b/D6b). Its whole message used to be a
        pointer at `/board`, a verb the menu no longer advertises — and when the bot's Board is already
        current, `/board` produces an identical edit Telegram rejects, so the pointer could not even help.
        Nothing is silence's cost here: the Board is on screen already, and it is the newest thing in the
        chat. Neither branch touches it — a greeting that rewrote the chat's live message would replace a
        player's own stage buttons with the score for the sake of saying hello.
        """
        if self.table_of(user) is None:
            return self._no_table(user)
        return []

    def _board(self, user):
        """
        The answer to anything the bot has no verb for — plain text, a photo, a stale `/board` — is the
        player's own Board, and nothing else (02b/D8). It used to append a line naming what this player
        could tap, and a second one naming whoever held a draft; the Board's last line has always said the
        first (02b/D2) and its `⏳` line has always said the second (01/FR9), in the message they already
        have. A night mid-draft now reads exactly like a night without one from the chat's side: the
        holder's buttons are the instruction, and everyone else can see a win is open.
        """
        table = self.table_of(user)
        if table is None:
            return self._no_table(user)
        if table.seat_of(user.user_id) is None:
            return [self._seat_offer(table, user)]
        return self._show_board(table)

    def _draft_stops(self, table, user):
        """
        The one refusal both exits answer to (01/FR10), said once.

        A half-entered Entry stops a **bystander**, and that is the whole of it now (02b/D8, 02b/D17): the
        holder may settle over the top of their own draft at either exit, because no confirmation was ever
        what bought the right to discard *another* player's entry — and their own thumb reaching Reset or
        Close says more about wanting it gone than an error line ever did.

        The refusal carries the Board with it, so the `⏳` line sits beside the words that name the reason
        (01/FR9, 01/FR15) — the same heal every other quiet guard gives, and for the same reason.
        """
        pending = table.pending
        if pending is None or pending["holder"] == user.user_id:
            return None
        return [Line(user.user_id,
                     "Game cannot end when someone is entering a win — %s."
                     % render.entering(table.names[pending["holder"]])),
                *self._where_you_stand(table, user)]

    def _settle_up(self, table, user):
        """
        The confirmed `/end` (FR19): the night is said first, then the slate is wiped, and both halves
        reach every seated DM in the same move — the rule AD24 states for settings, for the same reason.

        The settlement cannot be a `Line`: a message posted under the Board pushes the live Board out of
        reach, which is the drift 01/FR12 exists to prevent. It cannot live on the Board either, because
        FR19 zeroes the balances and clears the log the moment it is re-rendered. So the chat's own
        message *becomes* the settlement and hands its slot back (AD22), and the fresh zeroed Board is
        sent at the bottom as that chat's one live message.

        A half-entered Entry stops a **bystander** (01/FR19, narrowed by 02b/D8): `/end` is offered to
        every seated player, so without that check one player's tap could throw away an Entry somebody
        else started, and no confirmation buys an override. The holder is not stopped — their own exit over
        their own draft is allowed, and the draft goes with the slate, because `clear_round` empties the
        ledger and nothing else. Leaving a draft pointing at a wiped ledger would judge the next tap
        against a win that no longer exists (02b/D17). The refuser's Board comes back with the refusal, so
        the `⏳ Bo is entering a win` line sits next to the words that say why (01/FR9, 01/FR15).
        """
        refused = self._draft_stops(table, user)
        if refused:
            return refused
        settled = render.settlement(table)
        table.clear_round()
        table.pending = None
        table.version += 1
        return [effect for uid in table.seated_ids()
                for effect in (self._retired(uid, settled),
                               Board(uid, render.board(table), self._table_rows(table, uid)))]

    def _end(self, user):
        """
        04/D1 — `/end` moves nothing. It edits this chat's own Board message into the night's money — the
        very transfers and totals one of its two exits is about to erase — and puts both exits underneath
        them rather than a line beneath the Board (01/FR12). The screen showing the cost *is* the
        confirmation, which is what AD25 wanted from an ask (04/D5).

        Nothing is stored about who looked: the exits are tokens, so a screen nobody answers is just the
        screen the next win replaces — no prompt to get stuck in, and no second piece of conversational
        state for the `chatStatus` family to grow back from (02/AD21).
        """
        table = self.table_of(user)
        if table is None:
            return self._no_table(user)
        if table.seat_of(user.user_id) is None:
            return self._take_a_seat(table, user, "accessing /end")
        return [Board(user.user_id, render.settlement(table), self._end_rows(table))]

    def _end_rows(self, table):
        """
        The two exits and the way out, each alone on its row — a destructive button never shares one with
        the way out (04/D1). Ascending damage: the slate first, the Table last, so the button under a thumb
        that stopped reading is the one that loses least.
        """
        return [[(RESET_SCOREBOARD, token("k", table.code, table.version, "reset"))],
                [(CLOSE_SESSION, token("k", table.code, table.version, "close"))],
                self._back_row(table, "menu", KEEP_PLAYING)]

    def _history(self, user):
        """
        01/FR17 — the whole night, in the chat's own message. It cannot be a message of its own: a list
        posted beneath the Board pushes the live Board up the chat, which is the drift 01/FR12 was written
        against, so the Board is edited into the list and `Back` edits it back (`b…menu`, the same escape
        the settings screens use). One Board, to one chat: how long the night was is this player's
        question, and nobody else's screen moves for it. A read, so nothing bumps — a stale nobody else's
        buttons is the one thing a read must never cause.
        """
        table = self.table_of(user)
        if table is None:
            return self._no_table(user)
        if table.seat_of(user.user_id) is None:
            # The night's wins belong to the players sitting through them.
            return self._take_a_seat(table, user, "accessing /history")
        return [Board(user.user_id, render.history(table), [self._back_row(table, "menu")])]

    def _seat_offer(self, table, user):
        """
        The seat picker rides the chat's own Board message rather than a note beside it, so seating
        edits those buttons away in place — a spent seat row cannot survive on screen (01/FR12).
        """
        return Board(user.user_id, render.board(table), self._seat_rows(table))

    def _seat_rows(self, table):
        """Only the free seats are offered (01/FR14), and each is offered by its number. With none free the
        offer carries no row at all rather than one empty row: `mjbot.keyboard` turns no rows into no
        keyboard, and asking Telegram to draw a keyboard of zero buttons is a write nothing here can test.
        A member who joined a full session is shown the score and the `/leave` the menu already offers."""
        rows = [[(table.seat_label(seat), token("s", table.code, table.version, seat))
                 for seat in table.free_seats()]]
        return [row for row in rows if row]

    def _show_board(self, table):
        return [Board(uid, render.board(table), self._table_rows(table, uid))
                for uid in table.seated_ids()]

    def _table_rows(self, table, viewer):
        """
        The options one player sees. The score is shared by everyone; the buttons of a draft in
        progress go only to whoever started it (01/FR9), so nobody taps into a stranger's win.
        """
        pending = table.pending
        if pending is None or pending["holder"] != viewer:
            # 02/FR6 — the way back sits under the seats, and only while the night holds something to take
            # back. On the two draft screens below it would read as a way out of a win being entered.
            return [self._winner_row(table)] + ([self._undo_row(table)] if table.log else [])
        if pending["amount"] is None:
            return self._amount_rows(table) + [self._cancel_row(table)]
        return [self._payer_row(table), self._cancel_row(table)]

    def _winner_row(self, table):
        """
        All four seats, whoever holds them (02/FR3). An empty one is offered by its slot name, because
        there is no person to name and the win is booked into the slot all the same (02/AD5).
        """
        return [(table.name_for(seat), token("w", table.code, table.version, seat))
                for seat in range(len(SEATS))]

    def _payer_row(self, table):
        """Every seat but the winner's, filled or empty (02/FR4), plus Zi Mo."""
        return [(table.name_for(seat), token("p", table.code, table.version, seat))
                for seat in range(len(SEATS)) if seat != table.pending["winner"]] + [
                ("Zi Mo", token("p", table.code, table.version, "z"))]

    def _amount_rows(self, table):
        """The tai ladder, then the specials two to a row — six across is unusable on a phone."""
        tai = [(amount_label("tai", n), token("a", table.code, table.version, "t%d" % n))
               for n in range(1, table.tai_cap() + 1)]
        buttons = [(label, token("a", table.code, table.version, key))
                   for key, label in SPECIAL_AMOUNTS.items()]
        return [tai] + [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    def _cancel_row(self, table):
        return [(CANCEL, token("x", table.code, table.version, "c"))]

    def _undo_row(self, table):
        """One row, one button: undoing is a write, so its token is versioned like the others (02/AD11)."""
        return [(UNDO_LAST, token("u", table.code, table.version, "last"))]


def _digits(text):
    """
    ASCII digits only. `str.isdigit()` also says yes to '²' and to the Arabic-Indic digits, and
    `int()` and `float()` then disagree about them — every tap parser below ends in one of those two,
    and S4.17 and S4.20 promise one refusal rather than a traceback.
    """
    return bool(text) and all(c in "0123456789" for c in text)


def _seat_index(meaning):
    return int(meaning) if _digits(meaning) and 0 <= int(meaning) < len(SEATS) else None

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
    and above zero. Anything else is not a rate, and the player is told rather than corrected.
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
