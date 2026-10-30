"""Delivery: one Board message per chat, edited in place, keyboard and all."""

import random
import threading
import time

import pytest
from telebot.apihelper import ApiTelegramException

import mjbot
import table
from tests.support import GUEST, HOST, PLAYER, seated_four, seated_table, tap_end_exit

from tests.fakes import FakeBot


def labels(markup):
    return [button.text for row in markup.inline_keyboard for button in row] if markup else []


def board_sends(bot):
    return {chat: markup for chat, text, markup in bot.boards()}


def board_texts(bot):
    return {chat: text for chat, text, _ in bot.boards()}


def score_a_win(r, t, ntai):
    """The holder taps all three stages: since drafts went private nobody else may finish."""
    r.tap(HOST, table.token("w", t.code, t.version, 0))
    r.tap(HOST, table.token("a", t.code, t.version, "t%d" % ntai))
    return r.tap(HOST, table.token("p", t.code, t.version, 1))


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
    return (len(bot.boards()), len(bot.edited))


def test_the_board_keyboard_travels_on_the_board_message():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    first_markup = board_sends(bot)[HOST.user_id]
    assert set(labels(first_markup)) == {"Al", "Bo", PLAYER[2], PLAYER[3]}   # tap a seat to start

    delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)))
    edited = {chat: (message_id, markup) for chat, message_id, _, markup in bot.edited}
    assert edited[HOST.user_id][0] == delivery.boards[HOST.user_id].message_id
    assert labels(edited[HOST.user_id][1]), "the stage keyboard travels with the edit"
    # Which labels a stage offers is table.py's business (tests/test_amounts.py); this test only
    # proves the keyboard reaches Telegram attached to the Board message.


# Refusals reach the tap, not the chat, as an alert that must be dismissed: the quiet notification
# at the top of the chat went unseen.
def test_a_refusal_shows_as_an_alert_on_the_tap():
    r, t = seated_table()
    late = table.User(44, "Di")
    r.message(late, "/join " + t.code)
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    effects = r.tap(late, table.token("s", t.code, t.version, 0))   # seat 1 is the host's already
    bot.sent.clear()
    bot.edited.clear()
    delivery.run(effects, callback_id="abc")
    assert len(bot.toasts) == 1 and bot.toasts[0][0] == "abc"
    assert "taken" in bot.toasts[0][1]
    assert bot.toasts[0][2].get("show_alert") is True              # a popup, not a flash
    assert not bot.edited, "a refusal moves nobody's live Board"
    # The tapper also gets a fresh seat offer: a seatless chat's Board is never edited again, so
    # words alone would leave nothing on screen to pick.
    assert len(bot.sent) == 1, bot.sent


# A seatless tapper is handed a fresh seat offer, which can arrive at a full session.
# `_seat_rows` then offers no row, and this is where Telegram is spared a zero-button keyboard:
# `keyboard()` returns None and the Board goes out as plain text (`/leave` is in the menu).
def test_a_seat_offer_with_no_seats_free_sends_a_board_and_no_keyboard():
    r, t = seated_four()
    late = table.User(55, "Eve")                         # a fifth account; 44 is De's seat already
    r.message(late, "/join " + t.code)
    assert t.free_seats() == [] and t.seat_of(55) is None, "four seats, all held — Eve has nothing to pick"
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)

    delivery.run(r.tap(late, table.token("p", t.code, t.version, 1)))   # a money tap with no seat

    sent = [s for s in bot.sent if s[0] == late.user_id]
    assert len(sent) == 1, "one message, and it did not raise on the way out"
    assert "seated" in sent[0][1], "the Board text arrived"
    assert sent[0][2] is None, "zero buttons is no keyboard, not an empty one"
    assert not bot.toasts, "the picker answers a seatless tap, so there is nothing to say"


# The seat offer rides the Board message, so seating edits that same message instead of
# leaving a spent row of seat buttons above the score.
def test_seating_edits_the_seat_offer_in_place():
    r = table.Room(rng=random.Random(7))
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/new"))
    code = r.table_of(HOST).code

    offered = board_sends(bot)[HOST.user_id]
    assert set(labels(offered)) == set(PLAYER)               # the seat picker is on the Board

    delivery.run(r.tap(HOST, table.token("s", code, r.table_of(HOST).version, 0)))

    assert len(bot.boards()) == 1                             # never a second one
    edited = {chat: (mid, text, markup) for chat, mid, text, markup in bot.edited}
    assert edited[HOST.user_id][0] == delivery.boards[HOST.user_id].message_id
    assert "Player 1  Al" in edited[HOST.user_id][1]
    assert set(labels(edited[HOST.user_id][2])) == {"Al", "Player 2", "Player 3", "Player 4"}


# /leave then /new once wrote the fresh Board over the old "you have left table XYZA" message,
# burying the live Board up the chat instead of at the bottom.
def test_a_table_opened_after_leaving_is_sent_afresh_not_written_over_the_notice():
    r = table.Room(rng=random.Random(7))
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))            # a plain "not in a session" refusal line
    delivery.run(r.message(HOST, "/new"))
    first = delivery.boards[HOST.user_id].message_id
    delivery.run(r.tap(HOST, table.token("s", r.table_of(HOST).code, r.table_of(HOST).version, 0)))
    delivery.run(r.message(HOST, "/leave"))                             # spends the slot

    sent, edited = len(bot.sent), len(bot.edited)
    delivery.run(r.message(HOST, "/new"))                               # a second Table, same chat

    assert len(bot.sent) == sent + 1, "the new Board should be a fresh message at the bottom"
    assert delivery.boards[HOST.user_id].message_id != first
    assert len(bot.edited) == edited, "nothing may be written over the spent notice"


# Telegram takes about one message per second into a chat and each call costs ~0.7s on this route
# with one worker, so a win costs three stages of edits and nothing else.
def test_a_whole_win_costs_edits_and_no_messages_at_all():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    sent, edited = len(bot.sent), len(bot.edited)

    for kind, meaning in (("w", 0), ("a", "t3"), ("p", 1)):      # the holder taps all three stages
        delivery.run(r.tap(HOST, table.token(kind, t.code, t.version, meaning)))

    assert len(t.log) == 1
    assert len(bot.edited) == edited + 6                         # three stages, two seated DMs
    assert len(bot.sent) == sent                                 # nothing posted beneath the Board


# The slash menu belongs to the player; a tap that doesn't change it must not spend an API call.
def test_the_command_menu_is_set_per_chat_and_only_when_it_changes():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)

    delivery.run(r.message(HOST, "/board"))

    assert len(bot.menus) == 1                          # published once, for this chat
    scope, names = bot.menus[0]
    assert scope == HOST.user_id and "/end" in names   # HOST is seated, so the verbs of the night are there

    delivery.run(r.message(HOST, "/board"))
    delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)))    # a stage tap: same verbs
    assert len(bot.menus) == 1                          # nothing new to say, no call spent

    delivery.run(r.message(HOST, "/leave"))
    assert bot.menus[-1] == (HOST.user_id, ("/start", "/new", "/join"))


# Closing dissolves everyone's Table, so everyone's menu must move, not just the caller's.
def test_closing_resets_every_member_s_menu():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    delivery.run(r.message(GUEST, "/board"))

    delivery.run(tap_end_exit(r, t, HOST, table.CLOSE_SESSION))

    assert {scope for scope, _ in bot.menus[-2:]} == {HOST.user_id, GUEST.user_id}
    assert all(names == ("/start", "/new", "/join") for _, names in bot.menus[-2:])


# Settings ride the chat's one live message. A separate message would push the Board up the chat
# away from the player scoring, so this counts messages rather than trusting effect types.
def test_changing_a_setting_edits_the_one_message_and_posts_nothing_new():
    r, t = seated_table()
    bot = FakeBot()
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


# Reading the night is a read. A list posted under the Board would push it up the chat, so this
# counts calls rather than trusting effect types.
def test_reading_the_history_edits_the_one_message_and_posts_nothing():
    r, t = seated_table()
    for ntai in (1, 2, 3, 4):                         # longer than the Board's window, or nothing to read
        score_a_win(r, t, ntai)
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    sent, edits = len(bot.sent), len(bot.edited)
    slot = delivery.boards[HOST.user_id].message_id

    delivery.run(r.message(HOST, "/history"))

    assert len(bot.sent) == sent, "the night's list must not post"
    assert [c for c, _, _, _ in bot.edited[edits:]] == [HOST.user_id], "one chat read, one chat edited"
    assert "Al wins 4 Tai" in bot.edited[-1][2] and "Al wins 1 Tai" in bot.edited[-1][2]
    assert delivery.boards[HOST.user_id].message_id == slot, "same message, edited"


# The settlement is what the chat's spent message *becomes*, with the zeroed Board a new message
# beneath it. This covers `Retired` and `Board` arriving in one batch, not across two updates.
def test_an_ended_night_leaves_one_live_message_beneath_the_settlement():
    r, t = seated_table()
    score_a_win(r, t, 3)
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    asked = {chat: b.message_id for chat, b in delivery.boards.items()}
    sent, edits = len(bot.sent), len(bot.edited)

    delivery.run(r.message(HOST, "/end"))                    # the ask: an edit, and only in one DM
    assert len(bot.sent) == sent, "asking must not post"
    assert [c for c, _, _, _ in bot.edited[edits:]] == [HOST.user_id]

    delivery.run(r.tap(HOST, table.token("k", t.code, t.version, "reset")))

    said = bot.edited[edits + 1:]
    assert sorted(c for c, _, _, _ in said) == sorted([HOST.user_id, GUEST.user_id])
    assert [(c, mid) for c, mid, _, _ in said] == sorted(asked.items()), "the settlement used the old slot"
    assert all("pays" in text for _, _, text, _ in said)
    assert all(labels(markup) == [] for _, _, _, markup in said), "a spent Board carries no buttons"
    assert len(bot.sent) == sent + 2, "each chat earns one fresh live Board"
    assert len(delivery.boards) == 2 and all(b.message_id not in asked.values()
                                             for b in delivery.boards.values())


# However many stray messages a night holds, a refresh edits the chat's existing slot and never
# leaves a second Board above it.
def test_a_night_of_plain_messages_never_stacks_a_second_board():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    slot = {chat: b.message_id for chat, b in delivery.boards.items()}

    for text in ("hi", "", "👍", "anyone about?"):
        delivery.run(r.message(HOST, text))

    assert len(delivery.boards) == 2, "two chats, two live messages — never a third thing"
    assert {c: b.message_id for c, b in delivery.boards.items()} == slot, "the same two messages, edited"
    assert len(bot.boards()) == 2, "one Board ever sent per chat"


# An unanswered callback leaves the button flashing until Telegram's timeout. Every tap is answered;
# only a refusal has words.
def test_a_plain_tap_is_answered_so_the_button_stops_flashing():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))

    delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)), callback_id="abc")

    assert bot.toasts == [("abc", None, {})]


def test_a_tap_that_telegram_calls_too_old_does_not_count_against_the_route():
    r, t = seated_table()
    delivery = mjbot.Delivery(FakeBot())
    delivery.bot.answer_callback_query = lambda *a, **k: (_ for _ in ()).throw(
        ApiTelegramException("answerCallbackQuery", {}, {"error_code": 400, "description": "query is too old"}))

    for _ in range(mjbot.BREAKER_AFTER + 1):
        delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)), callback_id="old")

    assert not delivery._held()


# Four Boards in a row made the last seat wait ~1.4s, so every edit must be in flight at once: the
# Barrier only opens when all four calls are waiting together.
class RendezvousBot(FakeBot):
    def __init__(self, parties):
        FakeBot.__init__(self)
        self.meeting = threading.Barrier(parties, timeout=2)

    def edit_message_text(self, **kwargs):
        self.meeting.wait()
        return FakeBot.edit_message_text(self, **kwargs)


def test_every_seats_board_is_edited_at_the_same_time():
    r, t = seated_four()
    bot = RendezvousBot(parties=4)
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))

    delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)))     # raises BrokenBarrierError if serial

    assert len(bot.edited) == 4


# The Board edit and the menu change are different calls; queued behind the Board, a menu change
# costs a second round trip (0.69s + 0.33s live).
class RendezvousMenuBot(FakeBot):
    """The Board edit and the menu call each wait for the other, so they must be in flight together."""

    def __init__(self):
        FakeBot.__init__(self)
        self.meeting = threading.Barrier(2, timeout=2)

    def edit_message_text(self, **kwargs):
        self.meeting.wait()
        return FakeBot.edit_message_text(self, **kwargs)

    def set_my_commands(self, commands, scope=None, language_code=None):
        self.meeting.wait()
        return FakeBot.set_my_commands(self, commands, scope=scope, language_code=language_code)


def test_a_menu_change_does_not_queue_behind_the_board_edit():
    bot = RendezvousMenuBot()
    delivery = mjbot.Delivery(bot)
    delivery.boards[HOST.user_id] = mjbot.BoardInChat(1, ("old", ()))

    delivery.run([table.Board(HOST.user_id, "new", ()),
                  table.Commands(HOST.user_id, ("/leave",))])       # BrokenBarrierError if one waits for the other

    assert len(bot.edited) == 1 and len(bot.menus) == 1


# A job that blows up on something other than the network must not let run() return while the other
# chats' writes are still going out: the next batch would overlap them.
def test_a_job_that_crashes_does_not_release_the_batch_early():
    r, t = seated_four()
    bot = SlowOnePeerBot(slow_chat=GUEST.user_id)
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))
    bot.crash_chat = HOST.user_id

    with pytest.raises(RuntimeError):
        delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)))

    assert bot.finished_slow, "run() came back while a chat's edit was still in flight"


class SlowOnePeerBot(FakeBot):
    def __init__(self, slow_chat):
        FakeBot.__init__(self)
        self.slow_chat, self.crash_chat, self.finished_slow = slow_chat, None, False

    def edit_message_text(self, text=None, chat_id=None, message_id=None, reply_markup=None):
        if chat_id == self.crash_chat:
            raise RuntimeError("a bug, not the network")
        if chat_id == self.slow_chat:
            time.sleep(0.3)
            self.finished_slow = True
        return FakeBot.edit_message_text(self, text=text, chat_id=chat_id, message_id=message_id,
                                         reply_markup=reply_markup)
