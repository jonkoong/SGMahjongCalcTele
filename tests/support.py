"""Shared setup for the Table tests — a two-seat table is the same seven lines everywhere."""
import random

import table

HOST = table.User(11, "Al")
GUEST = table.User(22, "Bo")
CYD = table.User(33, "Cy")
DEB = table.User(44, "De")

# What the four seats read when nobody is sitting in them (AD5). Pinned here rather than imported from
# `table` so a test that names a seat says what a player reads, not what the code calls it.
PLAYER = ["Player 1", "Player 2", "Player 3", "Player 4"]


def seated_table():
    """Host in seat 1, guest in seat 2, nothing pending."""
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    t = r.table_of(HOST)
    r.tap(HOST, table.token("s", t.code, t.version, 0))
    r.message(GUEST, "/join " + t.code)
    r.tap(GUEST, table.token("s", t.code, t.version, 1))
    return r, t


def tap(r, t, who, kind, meaning):
    """Tap a live token on the current version of this table."""
    return r.tap(who, table.token(kind, t.code, t.version, meaning))


def buttons(effects):
    """The keyboard every seated player now sees, as {label: token}."""
    board = next(e for e in effects if isinstance(e, table.Board))
    return {label: tok for row in board.rows for label, tok in row}


def board_for(effects, chat_id):
    """The one Board this chat is owed — the only view that ever carries buttons (FR12)."""
    return next(e for e in effects if isinstance(e, table.Board) and e.chat_id == chat_id)


def board_text(effects, chat_id=HOST.user_id):
    return board_for(effects, chat_id).text


def keyboard_for(effects, chat_id):
    """The buttons this chat is now offered, in order."""
    return [label for row in board_for(effects, chat_id).rows for label, _ in row]


def buttons_for(effects, chat_id):
    return {label: tok for row in board_for(effects, chat_id).rows for label, tok in row}


def entry_texts(t):
    """
    What the night's wins read, oldest first.

    The ledger holds a record per win, not a bare sentence: which field of that record holds the
    words lives here and nowhere else, so a record rename costs this file, not every test that
    quotes a win.
    """
    return [entry.text for entry in t.log]


def entry_deltas(t):
    """What the night's wins paid, one money vector per win, oldest first."""
    return [entry.delta for entry in t.log]


def shown_wins(text):
    """
    The win lines a screen actually shows, oldest first.

    The tell is the money figure every one ends with (`render.entry_line`) — prose like
    `Pick who won the round:` cannot imitate it, which `" wins " in text` on its own can.
    """
    return [ln for ln in text.splitlines() if ln.rstrip()[-1:].isdigit() and " wins " in ln]


def score_wins(r, t, n):
    """
    Score n wins, each a different winner on a different rung of the ladder and fed by a different
    seat, so a longer night has n distinct sentences to show rather than the same line n times.
    """
    for i in range(n):
        tap(r, t, HOST, "w", i % 4)
        tap(r, t, HOST, "a", "t%d" % (i // 4 + 1))
        tap(r, t, HOST, "p", (i + 1) % 4)


def fold(deltas):
    """
    The four totals a list of stored vectors adds up to, folded left to right from four zeros.

    This is the tests' own copy of the rule, not a call into `Table.balances`: the point of comparing
    the two is that they can disagree (S1.3), and the same order matters here for the same reason (AD3).
    """
    total = [0.0, 0.0, 0.0, 0.0]
    for delta in deltas:
        total = [b + d for b, d in zip(total, delta)]
    return total


def undo(r, t, who):
    """
    Tap `Undo last win` as this player, on the current version of the Table.

    The one way these tests undo, so none of them can accidentally test a stale token instead — the
    stale ones are written out longhand where a stale token is the point.
    """
    return tap(r, t, who, "u", "last")


def tap_end_exit(r, t, who, label):
    """
    Open the settle-up screen and tap one of its exits by the word printed on the button.

    The one way these tests leave that screen, and they tap the label rather than hand-build a `k` token:
    the words on the buttons are what a player reads, so that is the contract worth pinning, and a token
    scheme change costs this function instead of every test that settles a night.
    """
    return r.tap(who, buttons_for(r.message(who, "/end"), who.user_id)[label])


def tokens_of(effects):
    return [tok for e in effects for row in getattr(e, "rows", ()) for _, tok in row]


def menu_for(effects):
    """The verbs Telegram's slash menu now offers this chat (AD20)."""
    return next(e.names for e in effects if isinstance(e, table.Commands))


def seated_four():
    """All four seats filled — the night as it is actually played (AS4)."""
    r, t = seated_table()
    for seat, user in ((2, CYD), (3, DEB)):
        r.message(user, "/join " + t.code)
        r.tap(user, table.token("s", t.code, t.version, seat))
    return r, t
