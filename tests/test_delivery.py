"""Delivery: one Board message per chat, edited in place, keyboard and all."""

import random

import pytest

import mjbot
import table
from tests.support import GUEST, HOST, seated_table

from tests.fakes import FakeBot


def labels(markup):
    return [button.text for row in markup.inline_keyboard for button in row] if markup else []


def board_sends(bot):
    return {chat: markup for chat, text, markup in bot.sent if "seated" in text}


def board_texts(bot):
    return {chat: text for chat, text, _ in bot.sent if "seated" in text}


def score_a_win(r, t, ntai):
    """The holder taps all three stages: since drafts went private nobody else may finish."""
    r.tap(HOST, table.token("w", t.code, t.version, 0))
    r.tap(HOST, table.token("a", t.code, t.version, "t%d" % ntai))
    return r.tap(HOST, table.token("p", t.code, t.version, 1))


# S1.13
def test_three_wins_still_leave_one_board_message_per_chat():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    for ntai in (1, 2, 3):
        delivery.run(score_a_win(r, t, ntai))
        delivery.run(r.message(HOST, "/board"))

    assert len(t.log) == 3, "the three wins must actually have scored, or this proves nothing"
    boards = board_texts(bot)
    assert set(boards) == {HOST.user_id, GUEST.user_id}      # sent once each, never a second Board
    assert len(delivery.boards) == 2
    assert bot.edited                                        # later changes went in place
    assert {chat for chat, _, _, _ in bot.edited} <= set(boards)


# S1.14
def test_a_board_that_did_not_change_is_not_sent_again():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    before = _board_traffic(bot)
    delivery.run(r.message(HOST, "/board"))
    assert _board_traffic(bot) == before


def _board_traffic(bot):
    """Board traffic only — the one-line reply to a message is meant to repeat."""
    sent = [1 for chat, text, _ in bot.sent if "seated" in text]
    return (len(sent), len(bot.edited))


# S1.12 at the Telegram edge
def test_the_board_keyboard_travels_on_the_board_message():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    first_markup = board_sends(bot)[HOST.user_id]
    assert set(labels(first_markup)) == {"Al", "Bo"}         # tap a name to start a win

    delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)))
    edited = {chat: (message_id, markup) for chat, message_id, _, markup in bot.edited}
    assert edited[HOST.user_id][0] == delivery.boards[HOST.user_id].message_id
    assert labels(edited[HOST.user_id][1]), "the stage keyboard travels with the edit"
    # Which labels a stage offers is table.py's business (tests/test_amounts.py); this test only
    # proves the keyboard reaches Telegram attached to the Board message.


# refusals reach the tap, not the chat
def test_a_refusal_shows_as_a_notification_on_the_tap():
    r, t = seated_table()
    late = table.User(44, "Di")
    r.message(late, "/join " + t.code)
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    effects = r.tap(late, table.token("s", t.code, t.version, 0))   # 東 is the host's
    bot.sent.clear()
    bot.edited.clear()
    delivery.run(effects, callback_id="abc")
    assert len(bot.toasts) == 1 and bot.toasts[0][0] == "abc"
    assert "taken" in bot.toasts[0][1]
    assert not bot.edited and not bot.sent


# S3.11 — the seat offer rides the Board message, so seating edits that same message instead of
# leaving a spent row of wind buttons above the score (Q4, scratchpad.md).
def test_seating_edits_the_seat_offer_in_place():
    r = table.Room(rng=random.Random(7))
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/new"))
    code = r.table_of(HOST).code

    offered = board_sends(bot)[HOST.user_id]
    assert set(labels(offered)) == set(table.WINDS)          # the wind picker is on the Board

    delivery.run(r.tap(HOST, table.token("s", code, r.table_of(HOST).version, 0)))

    assert len([1 for chat, text, _ in bot.sent if "seated" in text]) == 1     # never a second one
    edited = {chat: (mid, text, markup) for chat, mid, text, markup in bot.edited}
    assert edited[HOST.user_id][0] == delivery.boards[HOST.user_id].message_id
    assert "東  Al" in edited[HOST.user_id][1]
    assert set(labels(edited[HOST.user_id][2])) == {"Al"}     # spent: now a score Board


# S3.15 — the 21:52 defect: /leave then /new wrote the fresh Board over the old "you have left
# table XYZA" message, so the live Board appeared buried up the chat instead of at the bottom.
def test_a_table_opened_after_leaving_is_sent_afresh_not_written_over_the_notice():
    r = table.Room(rng=random.Random(7))
    bot, delivery = FakeBot(), mjbot.Delivery(FakeBot())
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))            # a plain "not at a table" refusal line
    delivery.run(r.message(HOST, "/new"))
    first = delivery.boards[HOST.user_id].message_id
    delivery.run(r.tap(HOST, table.token("s", r.table_of(HOST).code, r.table_of(HOST).version, 0)))
    delivery.run(r.message(HOST, "/leave"))                             # spends the slot

    sent, edited = len(bot.sent), len(bot.edited)
    delivery.run(r.message(HOST, "/new"))                               # a second Table, same chat

    assert len(bot.sent) == sent + 1, "the new Board should be a fresh message at the bottom"
    assert delivery.boards[HOST.user_id].message_id != first
    assert len(bot.edited) == edited, "nothing may be written over the spent notice"


# S3.16 — Telegram takes about one message per second into a chat, and every call here costs ~0.7 s
# on this route with one worker behind it. A win now costs three stages of edits and nothing else.
def test_a_whole_win_costs_edits_and_no_messages_at_all():
    r, t = seated_table()
    bot, delivery = FakeBot(), mjbot.Delivery(FakeBot())
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    sent, edited = len(bot.sent), len(bot.edited)

    for kind, meaning in (("w", 0), ("a", "t3"), ("p", 1)):      # the holder taps all three stages
        delivery.run(r.tap(HOST, table.token(kind, t.code, t.version, meaning)))

    assert len(t.log) == 1
    assert len(bot.edited) == edited + 6                         # three stages, two seated DMs
    assert len(bot.sent) == sent                                 # nothing posted beneath the Board


# S3.22 — the slash menu belongs to the player, and a tap that changes nothing about it must not
# spend an API call on it.
def test_the_command_menu_is_set_per_chat_and_only_when_it_changes():
    r, t = seated_table()
    bot, delivery = FakeBot(), mjbot.Delivery(FakeBot())
    delivery = mjbot.Delivery(bot)

    delivery.run(r.message(HOST, "/board"))

    assert len(bot.menus) == 1                          # published once, for this chat
    scope, names = bot.menus[0]
    assert scope == HOST.user_id and "/close" in names   # HOST is the host of this table

    delivery.run(r.message(HOST, "/board"))
    delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)))    # a stage tap: same verbs
    assert len(bot.menus) == 1                          # nothing new to say, no call spent

    delivery.run(r.message(HOST, "/leave"))
    assert bot.menus[-1] == (HOST.user_id, ("/start", "/new", "/join"))


# S3.23 — closing dissolves everyone's Table, so everyone's menu has to move with it, not just the
# caller's.
def test_closing_resets_every_member_s_menu():
    r, t = seated_table()
    bot, delivery = FakeBot(), mjbot.Delivery(FakeBot())
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    delivery.run(r.message(GUEST, "/board"))

    delivery.run(r.message(HOST, "/close"))

    assert {scope for scope, _ in bot.menus[-2:]} == {HOST.user_id, GUEST.user_id}
    assert all(names == ("/start", "/new", "/join") for _, names in bot.menus[-2:])


# S4.13 — a Table's settings ride the chat's one live message. If a settings screen or a settings
# change posted its own message, the Board would climb away from the player scoring the next win — the
# exact defect FR12 exists for, so this counts messages rather than trusting the effect types.
def test_changing_a_setting_edits_the_one_message_and_posts_nothing_new():
    r, t = seated_table()
    bot, delivery = FakeBot(), mjbot.Delivery(FakeBot())
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))                       # both Boards out
    sent, edits = len(bot.sent), len(bot.edited)
    slot = {chat: board.message_id for chat, board in delivery.boards.items()}

    delivery.run(r.tap(HOST, table.token("g", t.code, t.version, "maxtai")))
    assert len(bot.sent) == sent, "a picker must not post"
    assert [c for c, _, _, _ in bot.edited[edits:]] == [HOST.user_id]   # only the host's keyboard moved

    delivery.run(r.tap(HOST, table.token("v", t.code, t.version, "maxtai3")))
    assert len(bot.sent) == sent, "a settings change must not post"
    assert sorted(c for c, _, _, _ in bot.edited[edits + 1:]) == sorted([HOST.user_id, GUEST.user_id])
    assert {c: b.message_id for c, b in delivery.boards.items()} == slot, "same messages, edited"


# S5.2 — reading the night is a read. A list posted under the Board would push the live Board up the chat
# and the player scoring the next win would have to scroll for it, which is the drift FR12 exists for, so
# this counts calls rather than trusting the effect types.
def test_reading_the_history_edits_the_one_message_and_posts_nothing():
    r, t = seated_table()
    for ntai in (1, 2, 3, 4):                         # longer than the Board's window, or nothing to read
        score_a_win(r, t, ntai)
    bot, delivery = FakeBot(), mjbot.Delivery(FakeBot())
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    sent, edits = len(bot.sent), len(bot.edited)
    slot = delivery.boards[HOST.user_id].message_id

    delivery.run(r.message(HOST, "/history"))

    assert len(bot.sent) == sent, "the night's list must not post"
    assert [c for c, _, _, _ in bot.edited[edits:]] == [HOST.user_id], "one chat read, one chat edited"
    assert "Al wins 4 Tai" in bot.edited[-1][2] and "Al wins 1 Tai" in bot.edited[-1][2]
    assert delivery.boards[HOST.user_id].message_id == slot, "same message, edited"


# S5.13 — the settlement is what the chat's spent message *becomes*, and the fresh zeroed Board is a new
# message beneath it. `Retired` and `Board` arriving in one batch is the pattern FR12 leans on here, and
# S3.15 only proved the pair across two separate updates.
def test_an_ended_night_leaves_one_live_message_beneath_the_settlement():
    r, t = seated_table()
    score_a_win(r, t, 3)
    bot, delivery = FakeBot(), mjbot.Delivery(FakeBot())
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    asked = {chat: b.message_id for chat, b in delivery.boards.items()}
    sent, edits = len(bot.sent), len(bot.edited)

    delivery.run(r.message(HOST, "/end"))                    # the ask: an edit, and only in one DM
    assert len(bot.sent) == sent, "asking must not post"
    assert [c for c, _, _, _ in bot.edited[edits:]] == [HOST.user_id]

    delivery.run(r.tap(HOST, table.token("k", t.code, t.version, "end")))

    said = bot.edited[edits + 1:]
    assert sorted(c for c, _, _, _ in said) == sorted([HOST.user_id, GUEST.user_id])
    assert [(c, mid) for c, mid, _, _ in said] == sorted(asked.items()), "the settlement used the old slot"
    assert all("pays" in text for _, _, text, _ in said)
    assert all(labels(markup) == [] for _, _, _, markup in said), "a spent Board carries no buttons"
    assert len(bot.sent) == sent + 2, "each chat earns one fresh live Board"
    assert len(delivery.boards) == 2 and all(b.message_id not in asked.values()
                                             for b in delivery.boards.values())
