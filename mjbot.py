"""The only file that talks to Telegram. Rules live in table.py, money in score.py."""
import logging
import os
import threading
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, wait
from functools import partial

import requests
import telebot
from telebot import apihelper, types

import config
from table import COMMAND_HELP, Board, Commands, Line, Retired, Room, Toast, User

# Retries are ours, not telebot's: it resends after a read timeout, the Bot API has no idempotency
# key, and a timed-out sendMessage has usually landed, so a resend showed one player the same win
# twice. Connect failures still need retrying because the route here drops the first connect.
apihelper.MAX_RETRIES = int(os.environ.get('MJ_MAX_RETRIES', 4))
apihelper.RETRY_TIMEOUT = 2

# telebot's defaults (connect 15s, read 30s) would block the single worker for half a minute per stall.
apihelper.CONNECT_TIMEOUT = int(os.environ.get('MJ_CONNECT_TIMEOUT', 10))
apihelper.READ_TIMEOUT = int(os.environ.get('MJ_READ_TIMEOUT', 10))


def _request(method, url, params=None, files=None, timeout=None, proxies=None):
    """
    Send one API call, retrying only what provably never reached Telegram.

    A connect failure sends nothing, so resending is safe. After a read timeout Telegram may have
    acted, so only getUpdates is repeated; a failed Board edit is retried by the next refresh. A
    held getUpdates is not a stall, so its read window must outlast the poll hold.
    """
    connect, read = timeout
    reading = method == "get"             # only a read is safe to repeat
    if reading:
        read = max(read, int(os.environ.get('MJ_POLL_TIMEOUT', 5)) + 10)
    tries = apihelper.MAX_RETRIES if reading else 2
    session = apihelper._get_req_session()   # private telebot API: re-check on upgrade (requirements.txt)
    failure = None
    for attempt in range(1, tries + 1):
        try:
            return session.request(method, url, params=params, files=files,
                                   timeout=(connect, read), proxies=proxies)
        except requests.exceptions.ConnectTimeout as e:
            failure = e                       # nothing was sent
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if not reading:
                raise
            failure = e
        if attempt < tries and isinstance(failure, requests.exceptions.ConnectTimeout):
            time.sleep(apihelper.RETRY_TIMEOUT)
    raise failure


# MJ_TIMING=1 prints one line per API call (seconds, plus the idle gap since the previous call on
# that thread, which shows a cold connection) and one per handled update.
TIMING = os.environ.get('MJ_TIMING') == '1'
_last_end = {}


def _timed(send):
    def timed(method, url, *args, **kwargs):
        name = url.rsplit('/', 1)[-1]               # method only; the rest of the path holds the token
        who = threading.current_thread().name
        start = time.monotonic()
        idle = start - _last_end.get(who, start)
        outcome = 'ok'
        try:
            return send(method, url, *args, **kwargs)
        except Exception as e:
            outcome = type(e).__name__
            raise
        finally:
            _last_end[who] = time.monotonic()
            print('[timing] %-20s %6.2fs idle-before=%6.1fs %s [%s]'
                  % (name, _last_end[who] - start, idle, outcome, who))
    return timed


apihelper.CUSTOM_REQUEST_SENDER = _timed(_request) if TIMING else _request

# MJ_DEBUG=1 turns on telebot's update diagnostics ('Received N new updates'). It already has a
# stderr handler, so only the level changes.
if os.environ.get('MJ_DEBUG') == '1':
    telebot.logger.setLevel(logging.DEBUG)

# One worker: taps are handled one at a time, so two players cannot interleave a win.
bot = telebot.TeleBot(config.token, num_threads=1)

ROOM = Room()

# Anything a player might send: a photo or sticker still counts as showing up.
MESSAGES = ['text', 'audio', 'voice', 'video', 'video_note', 'animation', 'document',
            'photo', 'sticker', 'location', 'contact', 'venue', 'poll']


def _brief(error):
    """One line about a failed call, token redacted: a `requests` exception quotes the path `bot<TOKEN>/<method>`."""
    return str(error).replace(config.token, '<token>')


def keyboard(rows):
    if not rows:
        return None
    buttons = types.InlineKeyboardMarkup()
    for row in rows:
        buttons.row(*[types.InlineKeyboardButton(label, callback_data=tok)
                      for label, tok in row])
    return buttons


BoardInChat = namedtuple('BoardInChat', 'message_id stamp')


# With one worker, one stalled call freezes every player. After this many failures in a row,
# attempts pause so players don't each queue behind another dead 10s attempt; the beat then
# resumes what is owed.
BREAKER_AFTER = int(os.environ.get('MJ_BREAKER_AFTER', 2))
BREAKER_COOLDOWN = float(os.environ.get('MJ_BREAKER_COOLDOWN', 15))
# A parked write Telegram will never take (a deleted message, a chat that blocked the bot) would
# block everything behind it, so it is dropped after this many beats.
PARK_TRIES = 3
# The Boards of one win go out in parallel (a call costs ~0.35s, so four in series made the last
# seat wait ~1.4s); the rules stay on the one worker. Slots: the tap's answer, one per seat, one
# per menu change.
FAN_OUT = 9


class Delivery:
    """
    One Board message per chat, edited in place; everything else is a fresh message.

    Writes are never resent, so a Board that times out is gone. `intended` remembers what each
    chat was last owed and `reconcile` pushes anything that never landed, so no DM is left on a
    dead keyboard.
    """

    def __init__(self, bot, clock=time.monotonic):
        self.bot = bot
        self.boards = {}
        self.intended = {}
        self.owed = []                       # [write, tries left] for writes the route never got to
        self.menus = {}                      # last command list each chat was given
        self.lock = threading.Lock()         # one batch (or one beat) at a time
        self.books = threading.Lock()        # the parked queue, while a batch fans out
        self.pool = ThreadPoolExecutor(max_workers=FAN_OUT, thread_name_prefix='deliver')
        self.clock = clock
        self.failures = 0
        self.retry_after = 0.0

    def run(self, effects, callback_id=None):
        """
        Deliver one batch of effects.

        The tap is answered first, on its own line: an unanswered callback leaves the button
        flashing until Telegram's timeout. A refusal's Toast is that answer; any other tap is
        answered silently. Each chat's effects then go out in order, different chats in parallel.

        A Board is remembered so the beat can retry it. A write never attempted because the route
        was down is parked, since sending it later cannot duplicate it. A late toast is worthless,
        so it is dropped.
        """
        toast = next((e for e in effects if isinstance(e, Toast)), None)
        chats = {}
        for effect in effects:
            if isinstance(effect, Toast):
                continue
            # A menu change is its own call, so it needn't wait behind the Board edit.
            lane = ('menu', effect.chat_id) if isinstance(effect, Commands) else effect.chat_id
            chats.setdefault(lane, []).append(effect)
        jobs = [lambda c=c: self._chat(c) for c in chats.values()]
        if callback_id:
            jobs.insert(0, lambda: [self._try(lambda: self._answer(callback_id, toast), 'Answer')])
        with self.lock:
            if len(jobs) == 1:
                outcomes = jobs[0]()
            else:
                done = [self.pool.submit(job) for job in jobs]
                wait(done)                  # even if one crashed: the next batch must not overlap
                outcomes = [o for f in done for o in f.result()]
            self._streak(outcomes)

    def _chat(self, effects):
        outcomes = []
        for effect in effects:
            retry = None
            if isinstance(effect, Retired):
                # the slot goes back even if the write has to wait
                write, retriable = self._spend(effect)
                retry = write if retriable else None
            else:
                if isinstance(effect, Board):
                    self.intended[effect.chat_id] = effect      # stays dirty until it lands
                write = partial(self._deliver, effect)
            if self._held():
                if isinstance(effect, (Line, Retired, Commands)):
                    with self.books:
                        self.owed.append([write, PARK_TRIES])   # never attempted, so it cannot duplicate
                continue
            outcomes.append(self._try(write, 'Delivery', retry))
        return outcomes

    def _answer(self, callback_id, toast):
        # show_alert keeps a refusal on screen until dismissed (Telegram's default is a quiet
        # notification that clears itself, so refusals went unread) and shows it only to the tapper.
        try:
            if toast:
                self.bot.answer_callback_query(callback_id, toast.text, show_alert=True)
            else:
                self.bot.answer_callback_query(callback_id)
        except apihelper.ApiTelegramException as e:
            # Telegram answered, so the route is fine: this tap is just too old.
            print('Answer refused (%s)' % _brief(e))

    def reconcile(self):
        """
        Push whatever never landed: parked writes first, in order, then any Board still dirty.
        `_board` skips one that is already current.
        """
        with self.lock:
            if self._held():
                return
            while self.owed:
                outcome = self._try(self.owed[0][0], 'Flush')
                self._streak([outcome])
                if outcome == 'failed':
                    self.owed[0][1] -= 1
                    if not self.owed[0][1]:
                        print('Flush given up on — that write never landed')
                        self.owed.pop(0)
                    break                               # still down — the queue keeps its order
                self.owed.pop(0)
            for board in list(self.intended.values()):
                self._streak([self._try(lambda b=board: self._board(b), 'Reconcile')])

    def _held(self):
        return self.clock() < self.retry_after

    def _try(self, deliver, note, retry=None):
        """
        Run one write without letting a kicked chat, a too-old tap or a dead route take the polling
        thread down. The Board stamp stays unrecorded, so the next reconcile edits it again.
        Returns 'failed', 'sent', or None when nothing went out; `_streak` turns those into the
        breaker.

        A failed `Retired` is parked, because its text (the settlement) is said once and exists
        nowhere else: `clear_round` has already zeroed the balances. Retrying an edit is safe where
        a send is not, since an edit names the message it writes.
        """
        if self._held():
            return None
        try:
            sent = deliver()
        except (apihelper.ApiTelegramException, requests.exceptions.RequestException) as e:
            print('%s dropped (%s: %s)' % (note, type(e).__name__, _brief(e)))
            if retry is not None:
                with self.books:
                    self.owed.append([retry, PARK_TRIES])   # the beat flushes it in order, with the rest
            return 'failed'
        return None if sent is False else 'sent'    # a write skipped as already current proves nothing

    def _streak(self, outcomes):
        """
        Enough failures in a row hold writes instead of stalling every player. A batch counts as one
        event: four Boards killed by one blip was one stall, and counting each would hold the table
        for 15s over a hiccup.
        """
        if 'failed' in outcomes:
            self.failures += 1
            if self.failures >= BREAKER_AFTER:
                self.retry_after = self.clock() + BREAKER_COOLDOWN
                print('Route looks down — holding writes for %.0fs' % BREAKER_COOLDOWN)
        elif 'sent' in outcomes:
            self.failures = 0

    def _deliver(self, effect):
        if isinstance(effect, Board):
            return self._board(effect)
        if isinstance(effect, Commands):
            return self._menu(effect)
        if isinstance(effect, Line):
            self.bot.send_message(effect.chat_id, effect.text)

    def _menu(self, effect):
        """
        Telegram's slash menu, scoped to one player. Cached because tapping through the three
        stages of a win would push the identical list three times and setMyCommands has no 'only if
        changed'. A failed call leaves the cache alone, so the next message retries.
        """
        if self.menus.get(effect.chat_id) == effect.names:
            return False
        self.bot.set_my_commands(
            [types.BotCommand(command=command, description=COMMAND_HELP[command])
             for command in effect.names],
            scope=types.BotCommandScopeChat(effect.chat_id))
        self.menus[effect.chat_id] = effect.names

    def _spend(self, effect):
        """
        Hand the chat's message slot back and return the write that marks it spent. The handback is
        bookkeeping, so it happens even while the route is down; that makes the next Board a fresh
        message instead of an overwrite of an old notice.
        """
        held = self.boards.pop(effect.chat_id, None)
        self.intended.pop(effect.chat_id, None)
        message_id = held.message_id if held else None
        return (lambda: self._retire(effect.chat_id, message_id, effect.text),
                message_id is not None)          # an edit names its message; a send does not

    def _retire(self, chat_id, message_id, text):
        """
        An edit without reply_markup keeps the old keyboard, so clearing a spent Board needs an
        explicitly empty one.
        """
        if message_id is None:
            self.bot.send_message(chat_id, text)
            return
        try:
            self.bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id,
                                       reply_markup=types.InlineKeyboardMarkup())
        except apihelper.ApiTelegramException as e:
            # 'not modified' means the notice is already on screen, which is what the retry wanted.
            if 'not modified' not in str(e):
                raise

    def _board(self, effect):
        held = self.boards.get(effect.chat_id)
        stamp = (effect.text, effect.rows)
        if held and held.stamp == stamp:
            return False  # Telegram rejects an edit that would change nothing.
        markup = keyboard(effect.rows)
        if held:
            self.bot.edit_message_text(text=effect.text, chat_id=effect.chat_id,
                                       message_id=held.message_id, reply_markup=markup)
            self.boards[effect.chat_id] = BoardInChat(held.message_id, stamp)
        else:
            sent = self.bot.send_message(effect.chat_id, effect.text, reply_markup=markup)
            self.boards[effect.chat_id] = BoardInChat(sent.message_id, stamp)


DELIVERY = Delivery(bot)


def player(chat_user):
    """Identity is the account; the name is only ever for display."""
    name = '@' + chat_user.username if chat_user.username else chat_user.first_name
    return User(chat_user.id, name)


def _handle(label, decide, callback_id=None):
    start = time.monotonic()
    effects = decide()
    decided = time.monotonic()
    DELIVERY.run(effects, callback_id=callback_id)
    if TIMING:
        print('[timing] %s rules=%.3fs deliver=%.2fs effects=%d'
              % (label, decided - start, time.monotonic() - decided, len(effects)))


@bot.message_handler(content_types=MESSAGES)
def on_message(message):
    _handle('MESSAGE', lambda: ROOM.message(player(message.from_user), message.text or ''))


@bot.callback_query_handler(func=lambda call: True)
def on_tap(call):
    _handle('TAP', lambda: ROOM.tap(player(call.from_user), call.data), callback_id=call.id)


def start_reconciler(delivery, interval=None):
    """Players should not have to tap again to see a Board they are owed."""
    period = interval or float(os.environ.get('MJ_RECONCILE_SECONDS', 5))

    def beat():
        while True:
            time.sleep(period)
            delivery.reconcile()

    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    return thread


def polling_kwargs(first=True):
    """
    MJ_POLL_TIMEOUT is the getUpdates hold (the API 'timeout' param); keep it low, some networks
    drop long-held connections.

    skip_pending applies to the first poll only: a cold start has an empty Room, so queued updates
    name Tables this process never had. It skips rather than purges: telebot confirms every queued
    update but the newest, which is still delivered and refused. It also costs a probe getUpdates
    held for telebot's own 20s regardless of MJ_POLL_TIMEOUT, so a cold start can stall that long.
    A restarted poll drops the flag: the Tables are still live and the queued taps name them.
    """
    # interval=0: telebot otherwise sleeps between polls even after a reply, delaying a tap that
    # lands in the sleep.
    return {'non_stop': True, 'interval': 0, 'skip_pending': first,
            'long_polling_timeout': int(os.environ.get('MJ_POLL_TIMEOUT', 5))}


if __name__ == "__main__":
    start_reconciler(DELIVERY)
    poll = polling_kwargs()
    print('Bot online (polling, hold=%ss). Press Ctrl+C to stop.'
          % poll['long_polling_timeout'])
    while True:
        try:
            bot.polling(**poll)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            # Transient drop (ReadTimeout/ConnectionError): restart, don't die.
            print('Polling dropped (%s: %s) - restarting in 3s' % (type(e).__name__, _brief(e)))
            time.sleep(3)
            # The Tables survived, so queued updates are tonight's, not stale.
            poll = polling_kwargs(first=False)
