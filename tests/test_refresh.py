"""/board, /start and the plain messages that mean "where do I stand?"."""
import random

import render
import table
from tests.support import CYD, GUEST, HOST, board_text, keyboard_for, menu_for, PLAYER, \
    seated_table, tap


# S6.3 — 🔴 with a code ask outstanding, a sticker used to be read as a code and refused as a bad one:
# `No live session with code .` blames a player for a message they never typed. AD21 says any further input
# *clears* the ask — it does not say an empty payload is an attempt at an answer.
def test_a_sticker_while_asked_for_a_code_is_not_read_as_a_code():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    r.message(GUEST, "/join")                      # the slash menu can only send a bare /join

    effects = r.message(GUEST, "")                 # Telegram gives a sticker no text at all

    texts = [e.text for e in effects if isinstance(e, table.Line)]
    assert not [t for t in texts if "no live session" in t.lower()], texts
    assert r.asked == {}, "any further input ends the ask"
    assert "not in a session" in texts[0].lower(), texts        # shown where they stand instead

    later = [e.text for e in r.message(GUEST, "hello") if isinstance(e, table.Line)]
    assert "not in a session" in later[0].lower(), "the next message is an ordinary one, not a retry"


# S6.4 — the same defect one setting over: a sticker is not a rate the host got wrong.
def test_a_sticker_while_asked_for_a_rate_is_not_read_as_a_rate():
    r, t = seated_table()
    r.message(HOST, "/settings")
    tap(r, t, HOST, "g", "rate")
    before = (t.rate, t.version)

    effects = r.message(HOST, "")

    assert not [e.text for e in effects if isinstance(e, table.Line) and "not accepted" in e.text.lower()]
    assert (t.rate, t.version) == before, "nothing was written, so nobody's screen moved on its own"
    assert isinstance(effects[0], table.Board), "the host is shown the Table they are still sitting at"


# S6.5 — FR26 as amended (Jon, 2026-10-30): `/start` starts the bot, and nothing else. Telegram's own
# slash menu already carries every verb *with* its description, straight from COMMAND_HELP (mjbot.py:200),
# so the listing /start printed was that menu reprinted into the chat. 02b/D6b took the second half: the
# one line `/start` did send was a pointer at `/board`, so a chat already in a session now hears nothing.
# It changes nothing either way — a command that wipes a live session is the one thing this bot has never
# allowed.
def test_start_is_a_greeting_that_touches_no_screen():
    r, t = seated_table()
    before = (list(t.balances), list(t.log), list(t.occupants), t.version)

    effects = r.message(HOST, "/start")

    assert [e for e in effects if not isinstance(e, table.Commands)] == [], \
        "a chat with a Board on screen is told nothing (the slash menu is recomputed for every verb)"
    assert (t.balances, t.log, t.occupants, t.version) == before, "no command in this bot wipes a night"


# S6.6 — help is asked for mid-hand, so it cannot cost the player their draft. It cannot re-put their
# stage buttons either: a greeting that repaints the Board would bump the version and stale the ladder
# the player is one tap from.
def test_start_mid_draft_keeps_the_draft_and_costs_nothing():
    r, t = seated_table()
    tap(r, t, GUEST, "w", 1)
    stage = t.version

    effects = r.message(GUEST, "/start")

    assert e_boards(effects) == []
    assert t.pending is not None and t.version == stage


# S6.7 — from a chat with no Table it is the one line that tells them how to get to a Table, and it
# creates nothing.
def test_start_from_an_unbound_chat_opens_nothing():
    r = table.Room(rng=random.Random(7))

    effects = r.message(CYD, "/start")

    assert e_boards(effects) == [] and r.tables == {}
    line = next(e.text for e in effects if isinstance(e, table.Line))
    assert "/new" in line and "/join" in line, line


# S6.8 — the greeting is for a chat that has no conversation yet. Once a chat is bound, `/start` leaves
# the menu: the verbs that remain are all things a player at a Table does, and a verb that only says
# "Bot is running" beside them is noise in the one place players look for what to do next (AD20).
def test_start_is_offered_only_to_a_chat_that_has_no_table_yet():
    r = table.Room(rng=random.Random(7))

    assert "/start" in menu_for(r.message(CYD, "/start"))
    r.message(CYD, "/new")
    assert "/start" not in menu_for(r.message(CYD, "/board")), \
        "a chat with a Table standing is not offered a greeting"


def e_boards(effects):
    return [e for e in effects if isinstance(e, table.Board)]


# S6.1 — FR15, absorbed by slice 2 early and pinned here: the line names what *this* player may tap.
# 02b/D2 changed which channel that line lives on: the invitation is the Board's own last line now, so the
# answer to an ordinary message is the Board alone — the same words, costing the chat nothing.
def test_a_plain_message_refreshes_the_boards_and_costs_the_chat_nothing():
    r, t = seated_table()

    effects = r.message(GUEST, "dinner at ten?")

    assert sorted(b.chat_id for b in e_boards(effects)) == sorted([HOST.user_id, GUEST.user_id])
    assert [e for e in effects if isinstance(e, table.Line)] == [], "an ordinary message posts no message"
    assert all(b.text.endswith("\n" + render.PICK_WINNER) for b in e_boards(effects)), \
        "the Board ends by naming what to tap"


# S6.2 — the manifest's headline: a photo or sticker counts as "they showed up". mjbot hands the Room
# `message.text or ''`, so the empty string is the whole of it, and the answer is the same as a word's.
def test_a_message_with_no_text_at_all_still_refreshes_the_board():
    r, t = seated_table()

    effects = r.message(GUEST, "")

    assert "Al" in board_text(effects, GUEST.user_id)
    assert [e for e in effects if isinstance(e, table.Line)] == []


# S6.9 — the picker *is* their options. A line naming winner buttons they cannot tap yet would be the
# lying kind of option line (slice 4's ruling: the buttons are the feedback).
def test_a_plain_message_from_an_unseated_member_is_the_picker_they_already_hold():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)

    effects = r.message(CYD, "👍")

    assert set(keyboard_for(effects, CYD.user_id)) == {PLAYER[w] for w in t.free_seats()}
    assert [e for e in effects if isinstance(e, table.Line)] == []


# S6.10 / 02b-D8 — FR15's other half, seen by a bystander, is now said in one place instead of two: the
# Board they get carries the `⏳` line, and the separate sentence naming the holder is gone with the other
# two copies of it.
def test_a_plain_message_names_who_holds_the_draft():
    r, t = seated_table()
    tap(r, t, GUEST, "w", 1)

    effects = r.message(HOST, "ready?")

    assert [e for e in effects if isinstance(e, table.Line)] == [], "the Board is the whole reply"
    assert "⏳ Bo is entering a win" in board_text(effects, HOST.user_id)
    assert keyboard_for(effects, HOST.user_id) == ["Al", "Bo", "Player 3", "Player 4"]  # winner row
