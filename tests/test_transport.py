"""The transport must survive a bad network and a restart (S1.18–S1.20)."""

import pytest
from telebot.apihelper import ApiTelegramException

import mjbot
import table
from tests.support import GUEST, HOST, seated_table

from tests.fakes import FakeBot



def refused(method, description):
    """The way telebot itself raises when Telegram says no."""
    return ApiTelegramException(method, {}, {"error_code": 400, "description": description})


class ExplodingBot(FakeBot):
    """Telegram refuses the first call it gets, the way it does to a stale tap."""

    def __init__(self):
        FakeBot.__init__(self)
        self.blown = 0

    def answer_callback_query(self, callback_query_id, text=None, **kwargs):
        self.blown += 1
        raise refused("answerCallbackQuery", "query is too old")

    def edit_message_text(self, text=None, chat_id=None, message_id=None, reply_markup=None):
        self.blown += 1
        raise refused("editMessageText", "message is not modified")

    def send_message(self, chat_id, text, reply_markup=None):
        self.blown += 1
        raise refused("sendMessage", "Bad Request: chat not found")


# S1.18 — a dead callback id must not take the poller down with it.
def test_a_refusal_that_telegram_wont_accept_is_ignored():
    r, t = seated_table()
    bot = ExplodingBot()
    delivery = mjbot.Delivery(bot)
    effects = r.tap(GUEST, table.token("s", t.code, t.version, 0))
    delivery.run(effects, callback_id="stale-id")        # must not raise
    assert bot.blown == 1


# S1.18 — one unreachable DM must not stop the other three getting the Board.
def test_one_unreachable_chat_does_not_stop_the_rest_of_the_fanout():
    r, t = seated_table()

    class OneBadChat(FakeBot):
        def edit_message_text(self, text=None, chat_id=None, message_id=None, reply_markup=None):
            if chat_id == HOST.user_id:
                raise refused("editMessageText", "Bad Request: bot was kicked")
            return FakeBot.edit_message_text(self, text=text, chat_id=chat_id,
                                             message_id=message_id,
                                             reply_markup=reply_markup)

    bot = OneBadChat()
    delivery = mjbot.Delivery(bot)
    delivery.run(r.message(HOST, "/board"))                    # both Boards go out fresh
    r.tap(HOST, table.token("w", t.code, t.version, 0))         # now both need an edit
    effects = r.tap(HOST, table.token("a", t.code, t.version, "t2"))
    delivery.run(effects)                                      # must not raise
    assert [chat for chat, _, _, _ in bot.edited] == [GUEST.user_id]
    assert delivery.boards[HOST.user_id].message_id == 101     # untouched, retried next refresh


# S1.19 — a stalled request must give up in seconds, not half a minute.
def test_a_stalled_api_call_gives_up_within_ten_seconds():
    from telebot import apihelper
    assert apihelper.READ_TIMEOUT <= 10
    assert apihelper.CONNECT_TIMEOUT <= 10


# S1.20 — taps queued before a restart describe a Table that no longer exists.
def test_updates_queued_before_a_restart_are_skipped():
    options = mjbot.polling_kwargs()
    assert options["skip_pending"] is True
    assert options["non_stop"] is True


# --- S1.21–S1.24: resend only what provably never arrived -------------------------------------
import requests
from telebot import apihelper

SEND = "https://api.telegram.org/botX/sendMessage"
GETU = "https://api.telegram.org/botX/getUpdates"


class NetSession:
    """Records every attempt and fails the way the route to Telegram fails here."""

    def __init__(self, fails):
        self.fails = list(fails)
        self.attempts = []

    def request(self, method, url, params=None, files=None, timeout=None, proxies=None):
        self.attempts.append((method, url, timeout))
        failure = self.fails.pop(0) if self.fails else None
        if failure:
            raise failure
        return "response"


def net(monkeypatch, fails):
    session = NetSession(fails)
    monkeypatch.setattr(apihelper, "_get_req_session", lambda reset=False: session)
    return session


# S1.21 — Telegram may already have delivered it; a resend prints the win twice. Giving up must
# still say so, because a dropped line is a missing record.
def test_a_send_that_times_out_is_not_resent(monkeypatch):
    session = net(monkeypatch, [requests.exceptions.ReadTimeout()] * 5)
    with pytest.raises(requests.exceptions.ReadTimeout):
        mjbot._request("post", SEND, params={}, files=None, timeout=(10, 10), proxies=None)
    assert len(session.attempts) == 1


# S1.21 — a connect failure never reached Telegram, so trying again is safe.
def test_a_send_that_never_connected_is_resent(monkeypatch):
    session = net(monkeypatch, [requests.exceptions.ConnectTimeout()])
    mjbot._request("post", SEND, params={}, files=None, timeout=(10, 10), proxies=None)
    assert len(session.attempts) == 2


# S1.22 — a held getUpdates is not a stalled call; the read must outlast the hold.
def test_long_polling_reads_longer_than_it_holds(monkeypatch):
    session = net(monkeypatch, [])
    mjbot._request("get", GETU, params={}, files=None, timeout=(10, 10), proxies=None)
    assert session.attempts[0][2][1] >= mjbot.polling_kwargs()["long_polling_timeout"] + 10


# S1.23 — polling is harmless to repeat, so it gets the patient retry budget.
def test_a_timed_out_poll_is_retried(monkeypatch):
    session = net(monkeypatch, [requests.exceptions.ReadTimeout()])
    mjbot._request("get", GETU, params={}, files=None, timeout=(10, 15), proxies=None)
    assert len(session.attempts) >= 2


# S1.24 — a dead route to one DM must not strand the others or kill the poller.
def test_a_network_error_on_one_chat_does_not_stop_the_others(monkeypatch):
    r, t = seated_table()

    class Dying(FakeBot):
        def send_message(self, chat_id, text, reply_markup=None):
            if chat_id == HOST.user_id:
                raise requests.exceptions.ReadTimeout()
            return FakeBot.send_message(self, chat_id, text, reply_markup=reply_markup)

    bot = Dying()
    mjbot.Delivery(bot).run(r.message(HOST, "/board"))         # must not raise
    assert [chat for chat, _, _ in bot.sent] == [GUEST.user_id]


# --- S2.14: a Board that did not land must not stay wrong -------------------------------
import time

import requests


class FlakyEdits(FakeBot):
    """The first edit dies on the route, the rest arrive."""

    def __init__(self):
        FakeBot.__init__(self)
        self.tried = 0

    def edit_message_text(self, text=None, chat_id=None, message_id=None, reply_markup=None):
        self.tried += 1
        if self.tried == 1:
            raise requests.exceptions.ReadTimeout()
        return FakeBot.edit_message_text(self, text=text, chat_id=chat_id,
                                         message_id=message_id, reply_markup=reply_markup)


def both_boards_out(r, delivery):
    delivery.run(r.message(HOST, "/board"))


def edited_chats(bot):
    return [chat for chat, _, _, _ in bot.edited]


# S2.14 — one DM must not sit on a dead keyboard because a packet went missing.
def test_a_board_that_never_landed_is_pushed_again_on_the_next_beat():
    r, t = seated_table()
    bot = FlakyEdits()
    delivery = mjbot.Delivery(bot)
    both_boards_out(r, delivery)

    delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)))   # HOST's edit times out
    assert edited_chats(bot) == [GUEST.user_id]

    delivery.reconcile()

    assert edited_chats(bot) == [GUEST.user_id, HOST.user_id]


# S2.14 — reconciling a Board that is already current is a wasted call Telegram refuses.
def test_reconcile_leaves_a_board_that_is_already_right_alone():
    r, t = seated_table()
    bot = FakeBot()
    delivery = mjbot.Delivery(bot)
    both_boards_out(r, delivery)

    delivery.reconcile()
    delivery.reconcile()

    assert bot.edited == []


# S2.14 — nobody has to tap for the beat to do its job.
def test_the_beat_fixes_a_dropped_board_with_no_further_taps():
    r, t = seated_table()
    bot = FlakyEdits()
    delivery = mjbot.Delivery(bot)
    both_boards_out(r, delivery)
    delivery.run(r.tap(HOST, table.token("w", t.code, t.version, 0)))
    assert edited_chats(bot) == [GUEST.user_id]

    mjbot.start_reconciler(delivery, interval=0.02)

    for _ in range(200):
        if HOST.user_id in edited_chats(bot):
            break
        time.sleep(0.01)
    assert HOST.user_id in edited_chats(bot)


# --- S2.16–S2.19: a dead route must not make every player wait on it ---------------------
class FrozenClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class RouteDown(FakeBot):
    """Edits die while the route is down; `up` flips it back."""

    def __init__(self, up=True, script=None):
        FakeBot.__init__(self)
        self.up = up
        self.script = script
        self.attempted = 0

    def edit_message_text(self, text=None, chat_id=None, message_id=None, reply_markup=None):
        self.attempted += 1
        dying = (not self.script.pop(0)) if self.script else not self.up
        if dying:
            raise requests.exceptions.ReadTimeout()
        return FakeBot.edit_message_text(self, text=text, chat_id=chat_id,
                                         message_id=message_id, reply_markup=reply_markup)


def board_needs_an_edit(r, delivery):
    """Fresh Boards first, then a tap that can only be delivered by editing them."""
    delivery.run(r.message(HOST, "/board"))
    delivery.run(r.tap(HOST, table.token("w", r.table_of(HOST).code,
                                         r.table_of(HOST).version, 0)))


# S2.16 — one stalled call freezing the table is what made it look crashed at 21:26.
def test_two_lost_boards_hold_the_route_instead_of_stalling_every_tap():
    r, t = seated_table()
    clock, bot = FrozenClock(), RouteDown(up=False)
    delivery = mjbot.Delivery(bot, clock=clock)

    board_needs_an_edit(r, delivery)

    assert bot.attempted == mjbot.BREAKER_AFTER                 # it tried, twice, then stopped
    delivery.reconcile()
    assert bot.attempted == mjbot.BREAKER_AFTER                 # held: not even an attempt


# S2.17 — holding is temporary; when the route is back the dirty Boards go out.
def test_the_beat_delivers_what_the_outage_swallowed():
    r, t = seated_table()
    clock, bot = FrozenClock(), RouteDown(up=False)
    delivery = mjbot.Delivery(bot, clock=clock)
    board_needs_an_edit(r, delivery)

    clock.advance(mjbot.BREAKER_COOLDOWN + 1)
    bot.up = True
    delivery.reconcile()

    assert [chat for chat, _, _, _ in bot.edited] == [HOST.user_id, GUEST.user_id]


# S2.18 — a line that was never sent is safe to send late; one that timed out is not.
# Rewritten 2026-10-29: FR14 moved entry lines onto the Board, so the parked queue is exercised
# by a refusal instead. The rule it guards is unchanged: never-sent may be retried,
# one that timed out may not.
def test_a_line_written_during_an_outage_arrives_afterwards():
    r, t = seated_table()
    clock, bot = FrozenClock(), RouteDown(up=False)
    delivery = mjbot.Delivery(bot, clock=clock)
    board_needs_an_edit(r, delivery)                            # the breaker is open now
    sent_before = len(bot.sent)

    delivery.run(r.message(GUEST, "/close"))                    # a refusal line, nothing else
    assert len(bot.sent) == sent_before                          # nothing was even attempted

    clock.advance(mjbot.BREAKER_COOLDOWN + 1)
    bot.up = True
    delivery.reconcile()

    assert [text for _, text, _ in bot.sent[sent_before:]] == \
        ["Only the host, Al, can close table %s." % t.code]


# S2.19 — two isolated hiccups are not an outage; only failures in a row count.
def test_a_delivery_that_gets_through_clears_the_streak():
    r, t = seated_table()
    clock, bot = FrozenClock(), RouteDown(script=[False, True])
    delivery = mjbot.Delivery(bot, clock=clock)

    board_needs_an_edit(r, delivery)                            # dies once, then lands
    bot.script = [False, True]
    delivery.run(r.tap(HOST, table.token("a", t.code, t.version, "t2")))

    assert bot.attempted == 4                                   # 2 + 2: nothing was held back


# F-01 — `/end` zeroes the balances its own settlement was computed from, so a settlement write that
# dies is the only copy of the night's money leaving existence: `/history` reads a zeroed Board and
# `/end` again says the night is empty. AD19 parks a write the route never got to; an edit that died
# mid-call is just as safe to attempt again, because it names the message it writes — AD16's
# at-most-once rule is about duplicating a send, and no send can duplicate an edit.
def test_a_settlement_whose_edit_died_is_said_on_the_beat():
    r, t = seated_table()
    clock, bot = FrozenClock(), RouteDown(up=True)
    delivery = mjbot.Delivery(bot, clock=clock)
    delivery.run(r.message(HOST, "/board"))
    for kind, meaning in (("w", 0), ("a", "t3"), ("p", 1)):     # Al wins 3 Tai off Bo
        delivery.run(r.tap(HOST, table.token(kind, t.code, t.version, meaning)))
    settled = lambda: sorted(c for c, _, text, _ in bot.edited if "settled" in text)

    bot.script = [False]                                        # the next edit dies mid-call
    delivery.run(r.tap(HOST, table.token("k", t.code, t.version, "end")))
    bot.script = None

    assert settled() == [GUEST.user_id], "Al's settlement is the one that died"
    assert len(delivery.owed) == 1, "parked for the beat, not discarded"

    delivery.reconcile()

    assert settled() == sorted([HOST.user_id, GUEST.user_id]), "the beat said it after all"
    assert delivery.owed == []


# S3.12 — a Table closed while the route is down must not go on showing its score afterwards: the
# notice replaces what the chat was owed, so the beat has nothing stale left to push.
def test_a_table_closed_during_an_outage_stops_showing_up_once_the_route_returns():
    r, t = seated_table()
    clock, bot = FrozenClock(), RouteDown(up=False)
    delivery = mjbot.Delivery(bot, clock=clock)
    board_needs_an_edit(r, delivery)                            # the breaker is open now

    delivery.run(r.message(HOST, "/close"))
    delivery.reconcile()                                        # still down: nothing attempted
    assert bot.edited == []

    clock.advance(mjbot.BREAKER_COOLDOWN + 1)
    bot.up = True
    delivery.reconcile()

    texts = [text for _, _, text, _ in bot.edited]
    assert len(texts) == 2 and all("closed" in text for text in texts)


# F-01 — the retry is bounded. A parked write Telegram will never take (a message the player deleted,
# a chat that blocked the bot) would otherwise sit at the head of the queue forever, with everything
# the players earn after it stranded behind it.
def test_a_parked_write_telegram_wont_take_is_given_up_on():
    r, t = seated_table()
    clock, bot = FrozenClock(), RouteDown(up=True)
    delivery = mjbot.Delivery(bot, clock=clock)
    delivery.run(r.message(HOST, "/board"))
    for kind, meaning in (("w", 0), ("a", "t3"), ("p", 1)):
        delivery.run(r.tap(HOST, table.token(kind, t.code, t.version, meaning)))
    bot.up = False                                              # the route dies on edits
    delivery.run(r.tap(HOST, table.token("k", t.code, t.version, "end")))
    assert delivery.owed, "both settlements are parked, having never landed"

    for _ in range(2):                                          # a bad minute is not a give-up
        clock.advance(mjbot.BREAKER_COOLDOWN + 1)
        delivery.reconcile()
    assert delivery.owed, "still trying"

    for _ in range(10):                                         # a message that is gone is gone
        clock.advance(mjbot.BREAKER_COOLDOWN + 1)
        delivery.reconcile()

    assert delivery.owed == [], "the queue moves on rather than hold tonight's writes behind it"


class TokenQuotingBot(FakeBot):
    """The way `requests` reports a dead connection: the URL, token and all."""

    def send_message(self, chat_id, text, reply_markup=None):
        raise requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded "
            "with url: /bot%s/sendMessage" % mjbot.config.token)


def test_a_dropped_write_logs_the_failure_without_the_token(capsys, monkeypatch):
    monkeypatch.setattr(mjbot.config, "token", "123456:AA-a-live-token")
    delivery = mjbot.Delivery(TokenQuotingBot())

    delivery.run([table.Line(1, "One")])

    logged = capsys.readouterr().out
    assert "dropped" in logged                            # the line is still there to read
    assert "AA-a-live-token" not in logged
    assert "<token>" in logged
