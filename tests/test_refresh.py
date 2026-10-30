"""/board, /start and the plain messages that mean "where do I stand?"."""
import random

import render
import table
from tests.support import CYD, GUEST, HOST, board_text, keyboard_for, menu_for, PLAYER, \
    seated_table, tap


# 🔴 with a code ask outstanding, a sticker used to be read as a code and refused as a bad one:
# `No live session with code .` blames a player for a message they never typed. Further input
# *clears* the ask; an empty payload is not an attempt at an answer.
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


# The same defect one setting over: a sticker is not a rate the host got wrong.
def test_a_sticker_while_asked_for_a_rate_is_not_read_as_a_rate():
    r, t = seated_table()
    r.message(HOST, "/settings")
    tap(r, t, HOST, "g", "rate")
    before = (t.rate, t.version)

    effects = r.message(HOST, "")

    assert not [e.text for e in effects if isinstance(e, table.Line) and "not accepted" in e.text.lower()]
    assert (t.rate, t.version) == before, "nothing was written, so nobody's screen moved on its own"
    assert isinstance(effects[0], table.Board), "the host is shown the Table they are still sitting at"


# `/start` starts the bot and nothing else: the slash menu already carries every verb with its
# COMMAND_HELP description, and a chat already in a session hears nothing. It never changes the
# session either way.
def test_start_is_a_greeting_that_touches_no_screen():
    r, t = seated_table()
    before = (list(t.balances), list(t.log), list(t.occupants), t.version)

    effects = r.message(HOST, "/start")

    assert [e for e in effects if not isinstance(e, table.Commands)] == [], \
        "a chat with a Board on screen is told nothing (the slash menu is recomputed for every verb)"
    assert (t.balances, t.log, t.occupants, t.version) == before, "no command in this bot wipes a night"


# Help asked for mid-hand must not cost the player their draft, nor repaint the Board: that would
# bump the version and stale the ladder they are one tap from.
def test_start_mid_draft_keeps_the_draft_and_costs_nothing():
    r, t = seated_table()
    tap(r, t, GUEST, "w", 1)
    stage = t.version

    effects = r.message(GUEST, "/start")

    assert e_boards(effects) == []
    assert t.pending is not None and t.version == stage


# From a chat with no Table it is the one line that tells them how to get to a Table, and it
# creates nothing.
def test_start_from_an_unbound_chat_opens_nothing():
    r = table.Room(rng=random.Random(7))

    effects = r.message(CYD, "/start")

    assert e_boards(effects) == [] and r.tables == {}
    line = next(e.text for e in effects if isinstance(e, table.Line))
    assert "/new" in line and "/join" in line, line


# The greeting is for a chat with no conversation yet. Once bound, `/start` leaves the menu: a verb
# that only says "Bot is running" is noise where players look for what to do next.
def test_start_is_offered_only_to_a_chat_that_has_no_table_yet():
    r = table.Room(rng=random.Random(7))

    assert "/start" in menu_for(r.message(CYD, "/start"))
    r.message(CYD, "/new")
    assert "/start" not in menu_for(r.message(CYD, "/board")), \
        "a chat with a Table standing is not offered a greeting"


def e_boards(effects):
    return [e for e in effects if isinstance(e, table.Board)]


# The invitation naming what *this* player may tap is the Board's own last line, so the answer to
# an ordinary message is the Board alone.
def test_a_plain_message_refreshes_the_boards_and_costs_the_chat_nothing():
    r, t = seated_table()

    effects = r.message(GUEST, "dinner at ten?")

    assert sorted(b.chat_id for b in e_boards(effects)) == sorted([HOST.user_id, GUEST.user_id])
    assert [e for e in effects if isinstance(e, table.Line)] == [], "an ordinary message posts no message"
    assert all(b.text.endswith("\n" + render.PICK_WINNER) for b in e_boards(effects)), \
        "the Board ends by naming what to tap"


# A photo or sticker counts as showing up. mjbot hands the Room `message.text or ''`, so the
# answer to an empty string is the same as to a word.
def test_a_message_with_no_text_at_all_still_refreshes_the_board():
    r, t = seated_table()

    effects = r.message(GUEST, "")

    assert "Al" in board_text(effects, GUEST.user_id)
    assert [e for e in effects if isinstance(e, table.Line)] == []


# A tap is an answer to *something else*. A rate left armed while the player taps a winner would
# eat the number they type next, sticking the chat.
def test_a_tap_ends_the_rate_ask_so_the_next_number_is_an_ordinary_message():
    r, t = seated_table()
    tap(r, t, HOST, "g", "rate")

    tap(r, t, HOST, "w", 1)                            # any tap, on any screen
    effects = r.message(HOST, "0.2")

    assert t.rate == 0.1, "nothing was written — the ask was already over"
    assert any(isinstance(e, table.Board) for e in effects), "the ordinary message is answered where they stand"
    assert [e for e in effects if isinstance(e, table.Line)] == [], "and nobody is refused for a rate"


# The rule is about tapping, whatever question was open or Table the button belonged to. Cy was
# never in Al's session, so the tap is refused, but it still happened: the code ask is gone, and the
# code Cy types next is an ordinary message, not a `/join` by the back door.
def test_a_tap_aimed_at_a_session_the_player_is_not_in_still_ends_the_code_ask():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    code = r.table_of(HOST).code
    r.message(CYD, "/join")                           # the slash menu can only send a bare /join

    refused = r.tap(CYD, table.token("s", code, 0, 0))
    assert r.asked == {}, "the ask died to the tap, not to the answer"
    effects = r.message(CYD, code)

    assert "not in session" in next(e.text for e in refused if isinstance(e, table.Toast)).lower()
    assert r.table_of(CYD) is None, "and no seat was taken by the typed code either"
    assert "not in a session" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# The picker *is* their options; a line naming winner buttons they cannot tap yet would mislead.
def test_a_plain_message_from_an_unseated_member_is_the_picker_they_already_hold():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)

    effects = r.message(CYD, "👍")

    assert set(keyboard_for(effects, CYD.user_id)) == {PLAYER[w] for w in t.free_seats()}
    assert [e for e in effects if isinstance(e, table.Line)] == []


# A bystander learns who holds a draft from the `⏳` line on their Board, with no separate sentence.
def test_a_plain_message_names_who_holds_the_draft():
    r, t = seated_table()
    tap(r, t, GUEST, "w", 1)

    effects = r.message(HOST, "ready?")

    assert [e for e in effects if isinstance(e, table.Line)] == [], "the Board is the whole reply"
    assert "⏳ Bo is entering a win" in board_text(effects, HOST.user_id)
    assert keyboard_for(effects, HOST.user_id) == ["Al", "Bo", "Player 3", "Player 4"]  # winner row
