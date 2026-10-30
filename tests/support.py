"""Shared setup for the Table tests — a two-seat table is the same seven lines everywhere."""
import random

import table

HOST = table.User(11, "Al")
GUEST = table.User(22, "Bo")
CYD = table.User(33, "Cy")
DEB = table.User(44, "De")

# What the four seats read when nobody is sitting in them. Pinned here rather than imported from
# `table` so a test says what a player reads, not what the code calls it.
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
    """The one Board this chat is owed, the only view that carries buttons."""
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
    What the night's wins read, oldest first. Which Entry field holds the words lives here only, so
    a rename costs this file, not every test that quotes a win.
    """
    return [entry.text for entry in t.log]


def entry_deltas(t):
    """What the night's wins paid, one money vector per win, oldest first."""
    return [entry.delta for entry in t.log]


def shown_wins(text):
    """
    The win lines a screen shows, oldest first. The tell is the money figure each ends with
    (`render.entry_line`); prose like `Pick who won the round:` cannot imitate it.
    """
    return [ln for ln in text.splitlines() if ln.rstrip()[-1:].isdigit() and " wins " in ln]


def score_wins(r, t, n):
    """
    Score n wins, each with a different winner, rung and feeder, so a longer night has n distinct
    sentences.
    """
    for i in range(n):
        tap(r, t, HOST, "w", i % 4)
        tap(r, t, HOST, "a", "t%d" % (i // 4 + 1))
        tap(r, t, HOST, "p", (i + 1) % 4)


def fold(deltas):
    """
    The four totals a list of stored vectors adds up to, folded left to right from four zeros.

    The tests' own copy of the rule, not a call into `Table.balances`, so the two can disagree.
    The order matters here for the same float-residue reason.
    """
    total = [0.0, 0.0, 0.0, 0.0]
    for delta in deltas:
        total = [b + d for b, d in zip(total, delta, strict=True)]
    return total


def undo(r, t, who):
    """
    Tap `Undo last win` as this player on the current version. Stale tokens are written longhand
    where they are the point.
    """
    return tap(r, t, who, "u", "last")


def tap_end_exit(r, t, who, label):
    """
    Open the settle-up screen and tap an exit by the word printed on it. Tapping the label, not a
    hand-built `k` token, pins what a player reads and confines a token change to this function.
    """
    return r.tap(who, buttons_for(r.message(who, "/end"), who.user_id)[label])


def rename_picker(r, t, who):
    """
    Open the seat picker that `Change player names` draws, tapping the button by its label as
    `tap_end_exit` does, and return what the tap drew.
    """
    return r.tap(who, buttons_for(r.message(who, "/settings"), who.user_id)[table.CHANGE_NAMES])


def arm_rename(r, t, who, seat_label):
    """
    Reach the picker and tap the seat printed as `seat_label`, choosing it as a player reads it
    rather than hand-building an `n` token.
    """
    return r.tap(who, buttons_for(rename_picker(r, t, who), who.user_id)[seat_label])


def rename(r, t, who, seat_label, name):
    """
    Arm a rename for the seat printed as `seat_label`, then type `name` as the answer, so the ask,
    the tap and the write are all exercised for real.
    """
    arm_rename(r, t, who, seat_label)
    return r.message(who, name)


def tokens_of(effects):
    return [tok for e in effects for row in getattr(e, "rows", ()) for _, tok in row]


def menu_for(effects):
    """The verbs Telegram's slash menu now offers this chat."""
    return next(e.names for e in effects if isinstance(e, table.Commands))


def seated_four():
    """All four seats filled, the night as it is actually played."""
    r, t = seated_table()
    for seat, user in ((2, CYD), (3, DEB)):
        r.message(user, "/join " + t.code)
        r.tap(user, table.token("s", t.code, t.version, seat))
    return r, t
