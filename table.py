"""Table state and rules. No Telegram here — see mjbot.py for that."""
import random
from typing import NamedTuple

import render
import score

# The default seat labels a fresh Table seeds itself from, and the count that sets how many seats
# a Table has. The live labels are the Table's own (`Table.seat_labels`). A seat is a place at the
# table, not a person, so a label and a name can appear together on the Board.
SEAT_LABELS = ["Player 1", "Player 2", "Player 3", "Player 4"]
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   # no O/o, I/i/l or 0/1
CODE_LENGTH = 6                                       # never dealt twice
NAME_LIMIT = 12                                       # max characters in a seat's label

# Every character `str.splitlines()` breaks a line on, which is how `render.py` measures a Board.
# There are nine, not the two a player would name: one U+2028 in a label split the settlement's
# money line into `Bo pays Wife` / `y (empty): $1.60`. Judged on the raw text before trimming,
# because anything that survives to the label can reach a screen.
LINE_BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"

# The whole naming rule in the one message a rejected name costs. The bound comes from
# `NAME_LIMIT` rather than being typed twice, and every clause is one `_seat_name` really applies.
NAME_CONDITIONS = ("Name not accepted: 1-%d characters after trimming, no line break, no leading @, not a "
                   "duplicate of another seat or a seated player, and not a reserved word this bot uses."
                   % NAME_LIMIT)
HELP = "Send /new to create a new session, or /join to join an existing one"

# The amount buttons after the tai ladder, in order. Keys are score.AMOUNTS names, so a label cannot
# drift from a kernel and this dict doubles as the stage order.
SPECIAL_AMOUNTS = {"kang": "Kang", "kang_an": "Kang 暗", "animal": "🐈",
                   "animal_an": "🐈 暗", "flower": "🥀", "flower_an": "🥀 暗"}
CANCEL = "Cancel"
BACK = "Back"
# The feeder button meaning *nobody* fed it. Read by the who-fed row and the reserved-name list;
# `render.entry_line`'s `" on Zi Mo"` is prose and cannot import it (`render.py` does not depend on
# `table.py`).
ZI_MO = "Zi Mo"
# `win`, not `round`: a round survives between two `/end`s, and this takes back one Entry.
UNDO_LAST = "Undo last win"
# The only `/settings` item that is not a money rule; it lives there because that is where a seated
# player already goes to change something about the night.
CHANGE_NAMES = "Change player names"
# The question that tap opens. It lives here, not in `render.py`, which holds only render-time tails.
ASK_SEAT_NAME = "Enter the player's name:"
# The three answers the settle-up screen accepts. The words are the safety: `Keep playing` says
# what the player gets, where `Back` beside a destructive button would not, and the other two say
# what they do to the night instead of "confirm".
RESET_SCOREBOARD = "Reset scoreboard"
CLOSE_SESSION = "Close session"
KEEP_PLAYING = "Keep playing"

# The one sentence for "the screen you tapped has already been replaced", used by the version check
# and by every guard whose only honest story is staleness. One wording, so the popup cannot drift
# from the screen it re-draws.
OUTDATED = "That message is outdated, tap on the new message or wait for it to be refreshed."

# What a seated player may set, in the order /settings offers it.
SETTINGS = {"rate": "Pay Rate", "shooter": "Shooter", "maxtai": "Max Tai"}

# The bot's own words that share a screen with a seat button, composed from the constants those
# screens draw so a hand-typed copy cannot go stale when a label moves. Matched `casefold()`ed
# for equality, never with `in`.
RESERVED_SEAT_NAMES = tuple(word.casefold() for word in (
    ZI_MO, CANCEL, BACK, KEEP_PLAYING, UNDO_LAST, RESET_SCOREBOARD, CLOSE_SESSION, CHANGE_NAMES,
    *SETTINGS.values()))

# The taps that change something, so they must name the version of the screen they were drawn for.
# `s` is exempt: whether a seat is free is the seat's own decision, and versioning it would lock out
# a joiner who has not seen the newest Board. `b` is exempt because it is the way out of a stale
# screen.
VERSIONED = ("w", "a", "p", "x", "k", "g", "v", "u", "n")

# Which taps need what, read by `_tap` in order. `_NEEDS_SEAT` is the night's money; `_NEEDS_RULES`
# is what the night pays out.
_NEEDS_SEAT = ("w", "a", "p", "k", "u")
_NEEDS_RULES = ("g", "v", "n")

# One refusal said at two doors, bare `/join` and `/join CODE`, so it cannot read differently
# between them. The `%s` is the code the player is already in.
IN_SESSION_LEAVE_FIRST = "You are in session %s. /leave it first to join another session."

# Another refusal with two doors: a seat someone else holds, met by a tap on the seat picker and by
# a name typed for a seat that filled meanwhile. A tap can show a popup and a typed message cannot,
# so each door chooses how to say these words.
SEAT_TAKEN = "%s is taken. Pick another seat."

# The verbs and what the slash menu says each one does.
COMMAND_HELP = {
    "/start": "Start the bot",
    "/new": "Create a session",
    "/join": "Join a session with its code",
    "/leave": "Leave this session",
    "/history": "List session's results",
    "/end": "Settle up, then reset scoreboard or close the session",
    "/settings": "Change player name or game settings",
}

def amount_label(kind, ntai):
    """The words the entry line uses, the same as the button showed."""
    return "%d Tai" % ntai if kind == "tai" else SPECIAL_AMOUNTS[kind]


class User(NamedTuple):
    user_id: int
    name: str


class Ask(NamedTuple):
    """
    The one question outstanding for a player, and the seat it is about, if any.

    The seat is readable only where the ask is popped, so it cannot outlive the question.
    See `Room.asked` for what ends an ask and why no Table rides on one.
    """
    kind: str
    seat: int = None


class Board(NamedTuple):
    chat_id: int
    text: str
    rows: tuple = ()


class Line(NamedTuple):
    """A fresh message. Only the Board carries buttons, so this never does."""
    chat_id: int
    text: str


class Toast(NamedTuple):
    text: str


class Entry(NamedTuple):
    """
    One committed win: the sentence the players read and the money that moved, written together.
    The pair makes undo a pop instead of a subtraction, and because the words are frozen here a
    past win is never re-credited to whoever holds the seat later.
    """
    text: str
    delta: tuple


class Retired(NamedTuple):
    """
    The chat's one live message is spent because its Table is over. Unlike a Board it is not kept
    current: delivery hands the slot straight back, so the next Board is sent fresh at the bottom
    of the chat instead of overwriting whatever that message has become.
    """
    chat_id: int
    text: str


class Commands(NamedTuple):
    """
    Which verbs this player can use right now. Delivery puts them in Telegram's slash menu and only
    spends a call when the answer changed.
    """
    chat_id: int
    names: tuple


def commands_for(table, user_id):
    """
    The verbs one player can use. A player is bound to one live Table, so these resolve without a
    code. No verb is reserved to a role; the seat is the only test. Everything offered to a seated
    player they may use, since a menu that offers a refused verb teaches players that menus lie.

    `/start` is offered only to a chat with no Table: it says the bot is running, which is news
    once.
    """
    if table is None:
        return ("/start", "/new", "/join")
    if table.seat_of(user_id) is None:
        return ("/leave",)
    return ("/leave", "/history", "/end", "/settings")


def token(kind, code, version, meaning):
    """kind.code.version.meaning — the version is what makes an old keyboard refuse."""
    return "%s.%s.%s.%s" % (kind, code, version, meaning)


def parse_token(data):
    """
    kind.code.version.meaning, or None when the payload is not a token at all.

    The meaning stays a string because the kinds disagree about what it holds. Checked here, not by
    the caller's `int()`: Telegram redelivers whatever an old keyboard carried, so a payload this
    file never wrote gets one refusal instead of a ValueError through the polling thread. A code
    naming no Table is left to the caller, whose "That session does not exist anymore." is the true
    answer for a player who closed it another way.
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
    Six characters of `CODE_ALPHABET`, never a code dealt before.

    The rng picks *positions in the alphabet*, never characters: `rng.choice` would return whatever
    the caller's rng returns, and a code with an `O` or a lowercase letter is a Table nobody can
    join. Only the alphabet spells a code; the rng just says which letter.

    A repeat is skipped: two live Tables on one code would seat a player at the wrong night.
    `Room` passes every code it has ever dealt, so a dissolved Table's code counts as a repeat too.
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
        # A copy, so each Table owns its labels.
        self.seat_labels = list(SEAT_LABELS)
        self.occupants = [None] * len(self.seat_labels)
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
        ladder's, not whoever set `maxtai`: a rung above it has no payout, so it is never offered
        or accepted.
        """
        return min(self.maxtai, score.MAX_TAI)

    def seated_ids(self):
        return [u for u in self.occupants if u is not None]

    def seat_label(self, seat):
        """
        What this Table calls the seat, whether or not anybody is in it. Every screen asks here, so
        none can disagree about a seat's name.
        """
        return self.seat_labels[seat]

    def is_free(self, seat):
        """
        Whether anybody holds the seat. Separate from the label on purpose: the seated count and
        the seat picker both ask this, and asking the label would report `4 of 4 seated` on an
        empty table.
        """
        return self.occupants[seat] is None

    def rename_taken(self, candidate, seat):
        """
        Whether this Table already calls somebody *else* by that name.

        Read off `seats_view`: every other seat's label plus the name of whoever sits in a seat.
        `names` is not that union, since it also holds seatless members, and refusing a name a
        bystander holds would blame this player for someone in no row. Compared `casefold()`ed.
        """
        words = set()
        for index, (_, label, name, _) in enumerate(self.seats_view()):
            if index != seat:
                words.add(label.casefold())
            if name is not None:
                words.add(name.casefold())
        return candidate.casefold() in words

    def free_seats(self):
        return [seat for seat in range(len(self.seat_labels)) if self.is_free(seat)]

    def occupant_name(self, seat):
        """Whoever holds the seat, or None. Never the slot's own label — see `is_free`."""
        return self.names[self.occupants[seat]] if self.occupants[seat] is not None else None

    def name_for(self, seat):
        """
        Who a button or sentence calls this seat: the player in it, or the slot itself.

        The one place the two are composed, since the winner and feeder rows and every Entry line
        need it, and a win must not read `from None`.
        """
        return self.occupant_name(seat) or self.seat_label(seat)

    @property
    def balances(self):
        """
        What each seat is up: the stored vectors folded left to right, in log order.

        Derived, with no setter, on purpose. Money lives in the seat, not the person, and the log is
        the night's only money fact: a total written on its own could drift from the wins behind it,
        and undo would be two jobs instead of one pop.

        The order is part of the contract: these are binary fractions, so another order leaves
        different residue and `/end` would print different cents. A stored vector is never re-priced
        either, or a rate change would rewrite earlier wins.
        """
        total = list(score.ZERO)
        for entry in self.log:
            total = [b + d for b, d in zip(total, entry.delta, strict=True)]
        return total

    def may_set_rules(self, user_id):
        """
        Who may change what this Table pays: anybody holding a seat. A seat implies membership, so
        the menu, the tap, `/settings` and the typed rate all ask this one question.
        """
        return self.seat_of(user_id) is not None

    def seats_view(self):
        """
        One row per seat: the slot's name, what this Table calls it, whoever holds it, and the money
        there.

        The slot (`Player 1` … `Player 4`) never changes, which keeps the Board a scannable grid; the
        label is this Table's own word for the seat, used by buttons and sentences.
        """
        balances = self.balances
        return [(SEAT_LABELS[seat], self.seat_labels[seat], self.occupant_name(seat), balances[seat])
                for seat in range(len(self.seat_labels))]

    def add_member(self, user):
        self.members.add(user.user_id)
        self.names[user.user_id] = user.name

    def clear_round(self):
        """
        Wipe the slate for the next round once the transfers have been said. Clearing the log is the
        whole job, since balances fold from it. The roster and settings stay.
        """
        self.log = []

    def depart(self, user_id):
        """
        Leaving frees the player's binding for another Table. Only the balance in the vacated seat
        stays; the name goes with the person, so no screen keeps calling an empty seat by it.
        """
        self.members.discard(user_id)
        self.names.pop(user_id, None)


class Room:
    def __init__(self, rng=None):
        self.rng = rng or random
        self.tables = {}
        # Every code this process has dealt, live or dissolved. Re-dealing a dissolved Table's code
        # would seat a player holding it in their chat history at a night they were never invited
        # to. The window is the process lifetime; a restart forgets these, which is accepted.
        self.spent = set()
        # Who was asked what, by user id: one question per player, with no Table on it. An ask dies
        # to any answer, tap or command. The one exception is a rejected name, which re-arms for the
        # same seat; that is safe only because every tap clears it. No Table is stored because
        # anything that could change a player's Table is a command or a tap, and both end the ask,
        # so an answer always lands on the Table the asker stands at.
        self.asked = {}

    def table_of(self, user):
        return next((t for t in self.tables.values() if user.user_id in t.members), None)

    def message(self, user, text):
        return self._sync(user, self._dispatch(user, text))

    def _dispatch(self, user, text):
        parts = text.split()
        command = parts[0].lower() if text.startswith("/") else ""
        if not command:
            asked = self.asked.pop(user.user_id, None)          # any answer ends the ask
            answer = text.strip()
            if asked is None or not answer:
                # No question was outstanding, or the answer is empty (a sticker, a photo). Empty
                # input ends the ask but is not an answer: treating it as one refused players with
                # `No live session with code .`, so they are shown where they stand. Checked before
                # any `asked.kind` read, since there may be no ask.
                return self._board(user)
            if asked.kind == "code":
                return self._join(user, answer)
            if asked.kind == "rate":
                return self._apply_rate(user, answer)
            if asked.kind == "name":
                return self._apply_name(user, asked.seat, answer)
            # Any other input (a stray photo, a verb the menu no longer offers) is not refused:
            # the answer is where they stand.
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
        The command menu can only send /join with nothing after it, so the code has to be asked for.

        Conversational state is what caused stuck chats before, so it is kept minimal: one `Ask` per
        player, ended by *any* further input (a code, a wrong code, any command, any tap); only a
        rejected name re-arms. A wrong code costs one refusal, and nobody is left in a prompt they
        never meant to enter.
        """
        held = self.table_of(user)
        if held:
            return [Line(user.user_id, IN_SESSION_LEAVE_FIRST % held.code)]
        self.asked[user.user_id] = Ask("code")
        # The ask doesn't describe the code's shape: a made-up code costs one refusal either way.
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
        # A tap is an answer to *something else*, so it ends this player's outstanding question. It
        # comes first, ahead of the gates, because a refused tap still happened. It lives here
        # rather than in public `Room.tap`, next to the command half of the same rule.
        self.asked.pop(user.user_id, None)
        parsed = parse_token(data)
        if parsed is None:
            # The payload names no session, so there is no screen to re-draw.
            return [Toast("Error, please try again.")]
        kind, code, version, meaning = parsed
        table = self.tables.get(code)
        if table is None:
            return [Toast("That session does not exist anymore.")]
        if user.user_id not in table.members:
            return [Toast("You are not in session %s." % code)]
        if kind in VERSIONED and version != table.version:
            # A superseded token names a screen Telegram already replaced (see VERSIONED for what is
            # exempt). Re-drawing the player's own screen makes "wait for it to be refreshed" true.
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        if kind == "s":
            seat = _seat_index(meaning)
            if seat is None:
                # No seat row this bot drew carried it, so the screen that did has been replaced.
                return [Toast(OUTDATED)] + self._where_you_stand(table, user)
            return self._seat(table, user, seat)
        if kind in _NEEDS_SEAT and table.seat_of(user.user_id) is None:
            # Every tap touching the night's money needs a seat, since that is where the money sits,
            # including undo (a member can still see its button after losing their seat). `x` is
            # absent because the draft check below owns it; `g` and `v` fall under _NEEDS_RULES.
            return self._where_you_stand(table, user)
        if kind in ("a", "p", "x") and table.pending is not None and (
                table.pending["holder"] != user.user_id):
            # A draft belongs to whoever started it; this stops a bystander setting the holder's
            # amount. The tapper's own Board answers, as its `⏳` line already says who holds it.
            return self._where_you_stand(table, user)
        if kind in _NEEDS_RULES and not table.may_set_rules(user.user_id):
            # Enforced at the tap, not only the keyboard: Telegram replays old button data. A member
            # with no seat gets the picker plus the missing reason, since a Toast alone would look
            # like nothing happened. `b` is exempt: it only shows the player their own screen.
            return self._take_a_seat(table, user, "changing settings")
        if kind == "g":
            return self._open_setting(table, user, meaning)
        if kind == "n":
            return self._arm_rename(table, user, meaning)
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
        # A token this bot never wrote (a `k` for a deleted button, a `g` for an unknown screen). It
        # parsed and the session is in scope, so the screen carrying it has been replaced.
        return [Toast(OUTDATED)] + self._where_you_stand(table, user)

    def _where_you_stand(self, table, user):
        """
        What a refused tap answers with instead of explaining itself: never `return []`, the screen
        answers and the popup explains.

        The picker for a member with no seat (a popup alone would leave nothing to press), their own
        Board for everybody else. One helper, since ten guards want exactly this.

        It never bumps `table.version`: a refusal that retires everybody else's keyboards is worse
        than the popup it replaced.
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
        # An empty seat may win, so a short-handed table can book a win for a slot nobody holds.
        table.pending = {"holder": user.user_id, "winner": seat, "amount": None}
        table.version += 1
        return self._show_board(table)

    def _pick_amount(self, table, user, meaning):
        if table.pending is None:
            # Amount buttons exist only above a draft, so this came from a replaced screen.
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
            # Neither Zi Mo nor a seat is not a payer choice, and the keyboard is not the rule.
            # Without this guard the junk would fall through to `payer = None`, which means Zi Mo,
            # and book a self-fed win.
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        payer = None if meaning == "z" else _seat_index(meaning)
        if payer is not None and payer == pending["winner"]:
            # Any seat but the winner's may feed, filled or empty: an empty one pays out of its own
            # slot as it earns into one. Naming yourself is a rule violation, not a stale screen, so
            # it re-draws quietly (the winner's seat is not offered on the row anyway).
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
        return self._show_board(table)     # the win reads on the Board itself

    def _cancel(self, table, user):
        """Discard the half-entered Entry: no money moves and nothing is logged."""
        if table.pending is None:
            # `Cancel` exists only under a draft, so this came from a replaced screen.
            return self._where_you_stand(table, user)
        table.pending = None
        table.version += 1
        return self._show_board(table)

    def _undo_last(self, table, user):
        """
        The newest win comes back out; the totals are whatever the rest of the log adds up to. No
        inverse is computed: the Entry went in as a vector and comes out as one, so the night ends
        where the one before it ended, cents and all.

        The version bumps and every seated Board is redrawn, which is the undo's feedback and
        retires the screens that showed the win.
        """
        if table.pending is not None:
            # Reachable by an honest tap, since `Undo last win` shows to every seated player. The
            # wording is `render.entering`, as on the Board's `⏳` line beside this button.
            return [Toast("Cannot undo while %s, wait for them to finish or cancel it."
                          % render.entering(table.names[table.pending["holder"]]))]
        if not table.log:
            # The keyboard hides the button on an empty log, but a replayed token still arrives, and
            # the alternative to refusing it is an `IndexError` through the polling thread. It comes
            # from a screen a settlement or reset already replaced.
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        table.log.pop()
        table.version += 1
        return self._show_board(table)

    def _open(self, user):
        """
        The code is dealt with the Table and lives on the Board's first line from then on, where a
        player can read it aloud to whoever is still outside. So `/new` says nothing extra: the seat
        picker already carries the header (one message, edited, not two sent).
        """
        held = self.table_of(user)
        if held:
            return [Line(user.user_id, "You are in session %s already. To create a new session, leave "
                                       "the current session first with /leave, then use /new."
                         % held.code)]
        # Drawn against every code ever dealt: `tables` alone would let a closed Table's code come
        # back, and whoever kept the old one could walk in.
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
            # popup alone would leave nothing on screen to pick. The fresh offer is a convenience:
            # `/leave` then `/join CODE` also works.
            return [Toast(SEAT_TAKEN % table.seat_label(seat)),
                    self._seat_offer(table, user)]
        table.occupants[seat] = user.user_id
        table.version += 1
        return self._show_board(table)

    def _leave(self, user):
        """
        The seat goes back to the pool and the money stays in it. A half-entered Entry goes with
        them: only its holder may cancel it, and they have walked out of reach. A draft also names
        a seat, so leaving as the winner abandons it too.
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
        Whoever sits at the Table decides what it pays. The answer is the chat's Board edited into
        the settings menu and nothing else: the buttons changing is the feedback, and a line sent
        alongside would sit below the Board all night. A member with no seat gets the picker instead.
        """
        table = self.table_of(user)
        if table is None:
            return self._no_table(user)
        if not table.may_set_rules(user.user_id):
            # Settings ride the Board, so an unseated member gets a seat picker instead.
            return self._take_a_seat(table, user, "accessing /settings")
        return [Board(user.user_id, render.board(table), self._settings_rows(table))]

    def _take_a_seat(self, table, user, then):
        """
        One answer for a member bound to a Table but holding no seat: the seat picker plus the reason
        the verb isn't theirs yet (the picker alone can look like nothing happened). The sentence is
        written once; each call site supplies only `then`.
        """
        return [self._seat_offer(table, user),
                Line(user.user_id, "Pick a seat before %s." % then)]

    def _no_table(self, user):
        """
        The one answer a chat with no session gets, whichever verb it asked with.
        """
        return [Line(user.user_id, "You are not in a session. " + HELP)]

    def _settings_rows(self, table):
        """
        The three settings, then a way out that needs no typed command.

        The rename button sits above it, alone on its row, and only while some seat is free: with
        none, the picker would have no buttons. Hiding it is only the offer; the tap is guarded
        again at `_open_rename`.
        """
        rows = [[(label, token("g", table.code, table.version, key)) for key, label in SETTINGS.items()]]
        if table.free_seats():
            rows.append([(CHANGE_NAMES, token("g", table.code, table.version, "names"))])
        rows.append(self._back_row(table, "menu"))
        return rows

    def _back_row(self, table, where, label=BACK):
        """The way out, tagged with the screen it leaves so the Table needn't track who is looking at
        what. `/end` relabels it, since `Back` beside a destructive button is ambiguous."""
        return [(label, token("b", table.code, table.version, where))]

    def _step_back(self, table, user, meaning):
        """
        One level up. `menu` goes back to wherever this player scores, `picker` to the settings it
        came from. The level travels in the button, so the Table needn't track open screens.
        """
        rows = (self._settings_rows(table) if meaning == "picker"
                else self._table_rows(table, user.user_id))
        return [Board(user.user_id, render.board(table), rows)]

    def _apply_setting(self, table, user, meaning):
        """The value buttons. A tap naming something not on offer is no rule the player broke, so it
        costs no words, and nothing bumps."""
        setting, wanted = _setting_value(meaning)
        if setting is None:
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        if wanted is None:
            # Only a stale or forged tap gets here: the picker offers all ten rungs whatever the
            # session caps at, so the picker itself is the answer.
            return self._where_you_stand(table, user)
        return self._write_setting(table, user, setting, wanted)

    def _write_setting(self, table, user, setting, wanted):
        """
        The one place a setting lands. The rule changes and every seated DM is told together: the
        ladder a draft holder sees is drawn from these numbers, and a bump without fan-out would
        leave half the Table tapping rungs that are gone. A value that already holds costs nobody a
        call.

        A rate change also clears the rung the draft holder already chose: money is priced at
        commit, so keeping it would commit at a price nobody tapped. The winner stays picked. A Max
        Tai change does not clear it, since a cap constrains only what is chosen from now on; the
        same goes for Shooter.
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
        The typed answer to `Pay Rate`. Being asked grants nothing: the seat rule is checked again,
        since the seat could have been given up between ask and answer. A player who lost the right
        lands on the settings screen they opened, not on the score.
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

    def _apply_name(self, user, seat, text):
        """
        The typed answer to `Enter the player's name:`.

        Being asked grants nothing: the rules are read again one message later, since the seat could
        have been given up, and the player lands on a screen they can act on. The Table written to is
        the one this message arrives at, as none is stored on the ask.

        The write has `_write_setting`'s shape: the label and version move and every seated Board is
        redrawn, leaving the actor on the settings menu.

        The asker's own draft is not re-checked: starting one takes a tap, and every tap ends an ask,
        so no answer can come from a player halfway through a win. Only what can change in the gap
        (the chat's Table and the seat holder) is read again.
        """
        table = self.table_of(user)
        if table is None:
            return self._board(user)
        if not table.may_set_rules(user.user_id):
            return self._take_a_seat(table, user, "changing player names")
        if not table.is_free(seat):
            # Freeness is read at the answer: the seat was taken while the question was outstanding.
            # No popup, as a typed message has no receipt to show one on, so the screen answers with
            # the seats still free.
            refusal = [Line(user.user_id, SEAT_TAKEN % table.seat_label(seat))]
            return refusal + ([self._name_picker(table, user)] if table.free_seats() else [])
        label = _seat_name(text)
        if label is None or table.rename_taken(label, seat):
            # Shape and availability are two checks but one refusal that names every rule at once,
            # so a player needn't discover them one message at a time.
            #
            # The one ask that survives its own answer: the next message is the retry, so the player
            # needn't find the button again. Safe because any tap ends an ask, so a player who wanders
            # off is never stuck in a question.
            self.asked[user.user_id] = Ask("name", seat)
            return [Line(user.user_id, NAME_CONDITIONS)]
        if label == table.seat_label(seat):
            return self._settings_screen(table, user)            # nothing changed, nobody is owed
        table.seat_labels[seat] = label
        table.version += 1
        return self._show_settings(table, user.user_id)

    def _settings_screen(self, table, user):
        """The one Board that stays on the settings menu, while the others show the score."""
        return [Board(user.user_id, render.board(table), self._settings_rows(table))]

    def _show_settings(self, table, viewer):
        """The Board for everyone at the Table, the one who changed it still on the settings menu."""
        return [Board(uid, render.board(table),
                      self._settings_rows(table) if uid == viewer else self._table_rows(table, uid))
                for uid in table.seated_ids()]

    def _open_setting(self, table, user, meaning):
        """One setting opened: a picker where a value is one tap, a question where it is a number.
        Renaming is not a setting; it picks a seat, so it gets its own picker."""
        if meaning == "names":
            return self._open_rename(table, user)
        if meaning == "rate":
            return self._ask_for_rate(table, user)
        rows = {"shooter": self._shooter_rows, "maxtai": self._maxtai_rows}.get(meaning)
        if rows is None:
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        return [Board(user.user_id, render.board(table),
                      rows(table) + [self._back_row(table, "picker")])]

    def _open_rename(self, table, user):
        """
        The picker, with two guards in front of it.

        **The tapper's own draft**: someone halfway through a win does not also rename the Table the
        win is written into. This is the only place that rule is checked, since starting a draft is a
        tap and every tap ends an ask. The popup quotes `render.entering`, as the `⏳` line on the
        redrawn screen does.

        **No seat free**: `Pick whose name to change:` above zero buttons would misstate what is on
        offer. The button hides itself, but a replayed tap gets the shared line and the player's
        own Board.
        """
        pending = table.pending
        if pending is not None and pending["holder"] == user.user_id:
            return [Toast("Cannot change player names while %s."
                          % render.entering(table.names[pending["holder"]]))] + self._where_you_stand(table, user)
        if not table.free_seats():
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        return [self._name_picker(table, user)]

    def _name_picker(self, table, user):
        """Whose name to change, drawn on this player's own Board message."""
        return Board(user.user_id, render.board(table, render.PICK_SEAT_TO_RENAME),
                     self._rename_rows(table))

    def _rename_rows(self, table):
        """
        One free seat per row, then the way out. One per row because a mistap costs the player a
        typed message.

        Labelled by `seat_label` but carrying the seat's *index*: a label in callback data could be
        redelivered after it stopped being true.
        """
        return [[(table.seat_label(seat), token("n", table.code, table.version, seat))]
                for seat in table.free_seats()] + [self._back_row(table, "picker")]

    def _arm_rename(self, table, user, meaning):
        """
        One seat of the picker tapped: the name is typed, so this arms the ask and says what it
        wants. Nothing else moves: a pick renames nobody, and a bump would retire the picker the
        player is looking at.

        The seat rides on the ask, not the Table, so it cannot outlive the question.
        """
        seat = _seat_index(meaning)
        if seat is None:
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        self.asked[user.user_id] = Ask("name", seat)
        return [Line(user.user_id, ASK_SEAT_NAME)]

    def _ask_for_rate(self, table, user):
        """
        The rate is the one setting typed rather than tapped, since a row of buttons would narrow
        what a night can be run at. It is an ask, not a mode: ended by whatever the player sends
        next. The Board already shows the current rate.
        """
        self.asked[user.user_id] = Ask("rate")
        return [Line(user.user_id, "What rate? Eg: 0.2 for 20 cents, 1.5 for $1.50.")]

    def _shooter_rows(self, table):
        return [[("On", token("v", table.code, table.version, "shooter1")),
                 ("Off", token("v", table.code, table.version, "shooter0"))]]

    def _maxtai_rows(self, table):
        """
        Every rung the ladder can pay, two to a row. The whole span, not the current cap, since the
        picker exists to move the cap.
        """
        rungs = [(amount_label("tai", n), token("v", table.code, table.version, "maxtai%d" % n))
                 for n in range(1, score.MAX_TAI + 1)]
        return [rungs[i:i + 2] for i in range(0, len(rungs), 2)]

    def _retired(self, chat_id, text):
        """What a chat is owed once its Table is gone: their message, saying so, no buttons."""
        return Retired(chat_id, text)

    def _close_session(self, table, user):
        """
        The Table is destroyed and every member freed, seated or not: a binding outliving its Table
        would leave a player unable to `/new` or `/join`.

        A bystander is normally stopped at the ask, with `_end`'s sentence. This guards the same
        fact from behind: a settle-up screen left open across somebody's win is outdated, so it gets
        the shared line rather than destroying the Table under a half-entered Entry. The holder is
        not stopped; the draft dies with the Table.
        """
        if self._others_draft(table, user):
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        del self.tables[table.code]
        gone = list(table.members)
        farewell = render.session_closed(table)
        return ([self._retired(uid, farewell) for uid in gone]
                + [Commands(uid, commands_for(None, uid)) for uid in gone])

    def _start(self, user):
        """
        `/start` starts the bot and does nothing else: the slash menu already lists every verb via
        `setMyCommands` (mjbot.py), so printing them again would be a second menu.

        A chat with a Table standing gets nothing at all: its Board is already on screen and newest.
        Neither branch touches it, as a greeting that rewrote the live message would replace the
        player's stage buttons with the score.
        """
        if self.table_of(user) is None:
            return self._no_table(user)
        return []

    def _board(self, user):
        """
        The answer to anything the bot has no verb for (plain text, a photo, a stale `/board`) is
        the player's own Board and nothing else. Its last line already says what to tap and its `⏳`
        line says who holds a draft, so extra lines would only repeat them.
        """
        table = self.table_of(user)
        if table is None:
            return self._no_table(user)
        if table.seat_of(user.user_id) is None:
            return [self._seat_offer(table, user)]
        return self._show_board(table)

    def _others_draft(self, table, user):
        """
        The open Entry this player did not start, or None.

        One predicate for the three places that ask: the holder may settle over their own draft at
        either exit, but may not discard *another* player's entry.
        """
        pending = table.pending
        return pending if pending is not None and pending["holder"] != user.user_id else None

    def _settle_up(self, table, user):
        """
        The confirmed `/end`: the night is said first, then the slate is wiped, and both reach
        every seated DM together.

        The settlement cannot be a `Line`, since a message under the Board pushes the live Board out
        of reach. Nor can it live on the Board, which is zeroed on re-render. So the chat's message
        *becomes* the settlement and hands its slot back, and the zeroed Board is sent fresh at the
        bottom as the chat's one live message.

        A half-entered Entry stops a **bystander**, normally at the ask (`_end`). This guard is the
        backstop: starting a draft bumps the version, so a tap reaching here came from a screen the
        bot has moved past and gets the shared out-of-date line.

        The holder is not stopped, and their draft goes with the slate: a draft left pointing at a
        wiped log would judge the next tap against a win that no longer exists.
        """
        if self._others_draft(table, user):
            return [Toast(OUTDATED)] + self._where_you_stand(table, user)
        settled = render.settlement(table)
        table.clear_round()
        table.pending = None
        table.version += 1
        return [effect for uid in table.seated_ids()
                for effect in (self._retired(uid, settled),
                               Board(uid, render.board(table), self._table_rows(table, uid)))]

    def _end(self, user):
        """
        `/end` moves nothing. It edits the chat's Board into the night's money, the transfers and
        totals one of its two exits is about to erase, with both exits underneath. The screen showing
        the cost *is* the confirmation.

        Nothing is stored about who looked: the exits are tokens, so an unanswered screen is just
        replaced by the next win, with no prompt to get stuck in.

        A half-entered Entry stops a **bystander here**, at the ask, rather than after showing them
        the exits: offering `Reset scoreboard` over someone else's win and refusing it a tap later
        teaches players the bot offers things it won't allow. The sentence sits beside their own
        Board, whose `⏳` line names the reason. The holder is not stopped.

        A popup is unavailable because a typed verb hands over no receipt to show one on, so the
        refusal is a message. The tap path, which has a receipt, uses the shared out-of-date line.
        """
        table = self.table_of(user)
        if table is None:
            return self._no_table(user)
        if table.seat_of(user.user_id) is None:
            return self._take_a_seat(table, user, "accessing /end")
        blocked = self._others_draft(table, user)
        if blocked:
            return [Line(user.user_id,
                         "Game cannot end when someone is entering a win — %s."
                         % render.entering(table.names[blocked["holder"]])),
                    *self._where_you_stand(table, user)]
        return [Board(user.user_id, render.settlement(table), self._end_rows(table))]

    def _end_rows(self, table):
        """
        The two exits and the way out, each alone on its row, so a destructive button never shares
        one with the way out. In ascending damage (slate first, Table last), so the button under a
        thumb that stopped reading loses least.
        """
        return [[(RESET_SCOREBOARD, token("k", table.code, table.version, "reset"))],
                [(CLOSE_SESSION, token("k", table.code, table.version, "close"))],
                self._back_row(table, "menu", KEEP_PLAYING)]

    def _history(self, user):
        """
        The whole night, in the chat's own message: a list posted beneath the Board would push the
        live Board up the chat, so the Board is edited into the list and `Back` edits it back
        (`b…menu`, as on the settings screens). Only this chat's screen changes. A read never
        bumps, so nobody else's buttons go stale.
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
        The seat picker rides the chat's Board message, so seating edits its buttons away in place
        and a spent seat row cannot survive on screen.

        Its last line asks about the buttons it carries: `Pick who won the round:` over seat buttons
        would ask a seatless member to score. `render.seat_ask` picks between choosing and leaving.
        """
        return Board(user.user_id, render.board(table, render.seat_ask(table)), self._seat_rows(table))

    def _seat_rows(self, table):
        """Only the free seats are offered, each by its number. With none free there is no row at all
        rather than an empty one: `mjbot.keyboard` turns no rows into no keyboard, and Telegram drawing
        zero buttons is a write nothing here can test."""
        rows = [[(table.seat_label(seat), token("s", table.code, table.version, seat))
                 for seat in table.free_seats()]]
        return [row for row in rows if row]

    def _show_board(self, table):
        return [Board(uid, render.board(table), self._table_rows(table, uid))
                for uid in table.seated_ids()]

    def _table_rows(self, table, viewer):
        """
        The options one player sees. The score is shared; the buttons of a draft in progress go only
        to whoever started it, so nobody taps into a stranger's win.
        """
        pending = table.pending
        if pending is None or pending["holder"] != viewer:
            # Undo sits under the seats, only while there is a win to take back. On the draft
            # screens below it would read as a way out of the win being entered.
            return [self._winner_row(table)] + ([self._undo_row(table)] if table.log else [])
        if pending["amount"] is None:
            return self._amount_rows(table) + [self._cancel_row(table)]
        return [self._payer_row(table), self._cancel_row(table)]

    def _winner_row(self, table):
        """
        All four seats, whoever holds them. An empty one is offered by its slot name; the win is
        booked into the slot all the same.
        """
        return [(table.name_for(seat), token("w", table.code, table.version, seat))
                for seat in range(len(table.seat_labels))]

    def _payer_row(self, table):
        """Every seat but the winner's, filled or empty, plus Zi Mo."""
        return [(table.name_for(seat), token("p", table.code, table.version, seat))
                for seat in range(len(table.seat_labels)) if seat != table.pending["winner"]] + [
                (ZI_MO, token("p", table.code, table.version, "z"))]

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
        """One button. Undoing is a write, so its token is versioned like the others."""
        return [(UNDO_LAST, token("u", table.code, table.version, "last"))]


def _digits(text):
    """
    ASCII digits only. `str.isdigit()` also accepts '²' and Arabic-Indic digits, which `int()` and
    `float()` then disagree about; every tap parser below ends in one of them and must refuse
    rather than raise.
    """
    return bool(text) and all(c in "0123456789" for c in text)


def _seat_index(meaning):
    """A seat token carries an index, judged against the seat count; this parser holds no Table."""
    return int(meaning) if _digits(meaning) and 0 <= int(meaning) < len(SEAT_LABELS) else None


def _setting_value(meaning):
    """
    Which setting a value tap names, and what it asks for: `shooter1`, `maxtai7`.

    `(None, None)` is a value no picker emits; `(name, None)` names a tai rung above the ladder,
    which has no payout.
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
    `0.2`, `1`, `.05`: one token of ASCII digits with at most one dot, above zero. Anything else
    is refused, not corrected.
    """
    if not _digits(text.replace(".", "")) or text.count(".") > 1:
        return None
    return float(text) or None


def _seat_name(text):
    """
    `Wifey`, or None: the shape a seat's name must fill before asking whether the Table can spare
    it. Text in, value out, like `_rate_value`; it takes no Table.

    Line breaks are judged on the raw text **first**: `str.splitlines()`, which `render.py` measures
    a Board by, breaks on nine characters, so anything that would add a screen line is refused
    before the rest. Then trim, collapse interior runs with `str.split()`, and measure the
    collapsed form, since the words a player reads are what count, not their keystrokes.

    Then no leading `@` (that tags a person) and none of the bot's own vocabulary
    (`RESERVED_SEAT_NAMES`, matched for equality, so `Backpacking` is a name and `Back` is not).

    Whether the name is *available* is a Table's fact; see `Table.rename_taken`.
    """
    if any(c in LINE_BREAKS for c in text):
        return None
    label = " ".join(text.split())
    if not (1 <= len(label) <= NAME_LIMIT):
        return None
    if label.startswith("@") or label.casefold() in RESERVED_SEAT_NAMES:
        return None
    return label


def _tai_number(meaning, cap):
    """`t3` is 3 tai, if this table can pay that many. Anything else is not an amount."""
    if not (meaning.startswith("t") and _digits(meaning[1:])):
        return None
    ntai = int(meaning[1:])
    return ntai if 1 <= ntai <= cap else None
