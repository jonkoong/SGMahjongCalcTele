"""/board, /start and the plain messages that mean "where do I stand?"."""
import random

import table
from tests.support import CYD, GUEST, HOST, board_text, keyboard_for, seated_table, tap


# S6.3 — 🔴 with a code ask outstanding, a sticker used to be read as a code and refused as a bad one:
# `No live table called .` blames a player for a message they never typed. AD21 says any further input
# *clears* the ask — it does not say an empty payload is an attempt at an answer.
def test_a_sticker_while_asked_for_a_code_is_not_read_as_a_code():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    r.message(GUEST, "/join")                      # the slash menu can only send a bare /join

    effects = r.message(GUEST, "")                 # Telegram gives a sticker no text at all

    texts = [e.text for e in effects if isinstance(e, table.Line)]
    assert not [t for t in texts if "no live table" in t.lower()], texts
    assert r.asked == {}, "any further input ends the ask"
    assert "not at a table" in texts[0].lower(), texts        # shown where they stand instead

    later = [e.text for e in r.message(GUEST, "hello") if isinstance(e, table.Line)]
    assert "not at a table" in later[0].lower(), "the next message is an ordinary one, not a retry"


# S6.4 — the same defect one setting over: a sticker is not a rate the host got wrong.
def test_a_sticker_while_asked_for_a_rate_is_not_read_as_a_rate():
    r, t = seated_table()
    r.message(HOST, "/settings")
    tap(r, t, HOST, "g", "rate")
    before = (t.rate, t.version)

    effects = r.message(HOST, "")

    assert not [e.text for e in effects if isinstance(e, table.Line) and "not a rate" in e.text.lower()]
    assert (t.rate, t.version) == before, "nothing was written, so nobody's screen moved on its own"
    assert isinstance(effects[0], table.Board), "the host is shown the Table they are still sitting at"


# S6.5 — FR26: /start re-shows help and current state. It had no branch of its own, so it was literally
# the same line of code as /board and no chat ever saw COMMAND_HELP. And it must change nothing.
def test_start_shows_the_verbs_this_player_can_use_and_the_board():
    r, t = seated_table()
    before = (list(t.balances), list(t.log), list(t.occupants), t.version)

    effects = r.message(HOST, "/start")

    assert [b.chat_id for b in e_boards(effects)] == [HOST.user_id], "one player asks, one screen moves"
    help_line = next(e.text for e in effects if isinstance(e, table.Line))
    for verb in table.commands_for(t, HOST.user_id):
        assert verb in help_line
    assert table.COMMAND_HELP["/history"] in help_line, "the words the menu carries, not just the verbs"
    assert (t.balances, t.log, t.occupants, t.version) == before, "no command in this bot wipes a night"

    member = next(e.text for e in r.message(GUEST, "/start") if isinstance(e, table.Line))
    assert "/close" not in member and "/settings" not in member   # AD20: a member's help, not the host's


# S6.6 — help is asked for mid-hand, so it cannot cost the player their draft.
def test_start_mid_draft_keeps_the_draft_and_the_ladder():
    r, t = seated_table()
    tap(r, t, GUEST, "w", 1)
    stage = t.version

    effects = r.message(GUEST, "/start")

    assert "Cancel" in keyboard_for(effects, GUEST.user_id)
    assert t.pending is not None and t.version == stage


# S6.7 — and from a chat with no Table it stays one line of help that opens and destroys nothing.
def test_start_from_an_unbound_chat_is_help_only():
    r = table.Room(rng=random.Random(7))

    effects = r.message(CYD, "/start")

    assert e_boards(effects) == [] and r.tables == {}
    assert "/new" in next(e.text for e in effects if isinstance(e, table.Line))


def e_boards(effects):
    return [e for e in effects if isinstance(e, table.Board)]


# S6.1 — FR15, absorbed by slice 2 early and pinned here: the line names what *this* player may tap.
def test_a_plain_message_names_what_this_player_can_tap():
    r, t = seated_table()

    effects = r.message(GUEST, "dinner at ten?")

    assert sorted(b.chat_id for b in e_boards(effects)) == sorted([HOST.user_id, GUEST.user_id])
    assert next(e.text for e in effects if isinstance(e, table.Line)) == "Tap a name to start a win."


# S6.2 — the manifest's headline: a photo or sticker counts as "they showed up". mjbot hands the Room
# `message.text or ''`, so the empty string is the whole of it, and the answer is the same as a word's.
def test_a_message_with_no_text_at_all_still_refreshes_and_names_the_options():
    r, t = seated_table()

    effects = r.message(GUEST, "")

    assert "Al" in board_text(effects, GUEST.user_id)
    assert next(e.text for e in effects if isinstance(e, table.Line)) == "Tap a name to start a win."


# S6.9 — the picker *is* their options. A line naming winner buttons they cannot tap yet would be the
# lying kind of option line (slice 4's ruling: the buttons are the feedback).
def test_a_plain_message_from_an_unseated_member_is_the_picker_they_already_hold():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)

    effects = r.message(CYD, "👍")

    assert set(keyboard_for(effects, CYD.user_id)) == {table.WINDS[w] for w in t.free_winds()}
    assert [e for e in effects if isinstance(e, table.Line)] == []


# S6.10 — FR15's other half, seen by a bystander: they are told who holds it, in words and on the Board.
def test_a_plain_message_names_who_holds_the_draft():
    r, t = seated_table()
    tap(r, t, GUEST, "w", 1)

    effects = r.message(HOST, "ready?")

    assert "Bo is entering a win" in next(e.text for e in effects if isinstance(e, table.Line))
    assert "⏳ Bo is entering a win" in board_text(effects, HOST.user_id)
    assert keyboard_for(effects, HOST.user_id) == ["Al", "Bo"]      # a bystander keeps winner buttons
