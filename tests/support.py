"""Shared setup for the Table tests — a two-seat table is the same seven lines everywhere."""
import random

import table

HOST = table.User(11, "Al")
GUEST = table.User(22, "Bo")
CYD = table.User(33, "Cy")
DEB = table.User(44, "De")


def seated_table():
    """Host seated at 東, guest at 南, nothing pending."""
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


def tokens_of(effects):
    return [tok for e in effects for row in getattr(e, "rows", ()) for _, tok in row]


def seated_four():
    """All four winds filled — the night as it is actually played (AS4)."""
    r, t = seated_table()
    for wind, user in ((2, CYD), (3, DEB)):
        r.message(user, "/join " + t.code)
        r.tap(user, table.token("s", t.code, t.version, wind))
    return r, t
