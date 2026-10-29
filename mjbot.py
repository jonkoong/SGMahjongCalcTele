"""The only file that talks to Telegram. Rules live in table.py, money in score.py."""
from libraries import *
import os
import threading
import time
import logging
from collections import namedtuple

import telebot.apihelper as apihelper
import requests

from table import COMMAND_HELP, Board, Commands, Line, Retired, Room, Toast, User

# The route to api.telegram.org here drops the first connect and takes ~3s to warm up, so retries
# are needed. But telebot's own engine resends a request after a read timeout, and the Bot API has
# no idempotency key: a sendMessage that times out has usually already been delivered, and the
# resend showed one player the same win twice (live, 2026-10-29 20:47). Retries are ours now.
apihelper.MAX_RETRIES = int(os.environ.get('MJ_MAX_RETRIES', 4))
apihelper.RETRY_TIMEOUT = 2

# The defaults (connect 15s, read 30s) mean one stalled call blocks the single worker for half a
# minute before anything is retried at all. Players are waiting on that tap.
apihelper.CONNECT_TIMEOUT = int(os.environ.get('MJ_CONNECT_TIMEOUT', 10))
apihelper.READ_TIMEOUT = int(os.environ.get('MJ_READ_TIMEOUT', 10))


def _request(method, url, params=None, files=None, timeout=None, proxies=None):
    """
    Send one API call, retrying only what provably never reached Telegram.

    A connect failure happens before any bytes are sent, so trying again is safe. A read timeout
    means Telegram may already have acted on it, and only getUpdates is harmless to repeat - a
    Board edit that fails is re-tried by the next refresh anyway, because its stamp stays
    unrecorded. A held getUpdates is not a stalled call either, so its read window must outlast
    the poll hold.
    """
    connect, read = timeout
    reading = method == "get"             # a read repeats harmlessly; a write may not have landed
    if reading:
        read = max(read, int(os.environ.get('MJ_POLL_TIMEOUT', 5)) + 10)
    tries = apihelper.MAX_RETRIES if reading else 2
    session = apihelper._get_req_session()
    failure = None
    for attempt in range(1, tries + 1):
        try:
            return session.request(method, url, params=params, files=files,
                                   timeout=(connect, read), proxies=proxies)
        except requests.exceptions.ConnectTimeout as e:
            failure = e                       # nothing was sent - safe to resend
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if not reading:
                raise
            failure = e                       # a read is just a read - hold again
        if attempt < tries and isinstance(failure, requests.exceptions.ConnectTimeout):
            time.sleep(apihelper.RETRY_TIMEOUT)
    raise failure


apihelper.CUSTOM_REQUEST_SENDER = _request

# MJ_DEBUG=1 turns on telebot's own update diagnostics ('Received N new updates').
# Telebot installs its own stderr handler, so only the level needs changing.
# Off by default so normal runs stay as quiet as they always were.
if os.environ.get('MJ_DEBUG') == '1':
    telebot.logger.setLevel(logging.DEBUG)

server = Flask(__name__)

# One worker: taps are handled one at a time, so two players cannot interleave a win.
bot = telebot.TeleBot(config.token, num_threads=1)

ROOM = Room()

# Anything a player might send. A photo or sticker still counts as "they showed up".
MESSAGES = ['text', 'audio', 'voice', 'video', 'video_note', 'animation', 'document',
            'photo', 'sticker', 'location', 'contact', 'venue', 'poll']


def _brief(error):
    """
    One line about a failed call, with the token out of it.

    A `requests` exception quotes the request path, and every telebot path is
    `bot<TOKEN>/<method>` — so logging the exception verbatim writes a live token into the log, on the
    dead-route path this file exists to survive. F-02.
    """
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


# One stalled call freezes every player, because there is one worker (NFR4) and a tap is several
# serial calls. So after this many failures in a row, attempts stop for a while rather than making
# each player queue behind another dead 10 s attempt. The beat resumes what is still owed.
BREAKER_AFTER = int(os.environ.get('MJ_BREAKER_AFTER', 2))
BREAKER_COOLDOWN = float(os.environ.get('MJ_BREAKER_COOLDOWN', 15))
# A parked write that Telegram will never take — a message the player deleted, a chat that blocked
# the bot — must not sit at the head of the queue forever, because everything earned after it is
# behind it. Three beats, then it is said and gone.
PARK_TRIES = 3


class Delivery:
    """
    One Board message per chat, edited in place. Everything else is a fresh message.

    Writes are never resent (AD16), so a Board that times out is simply gone. `intended` remembers
    what each chat was last owed, and `reconcile` pushes anything that never landed — that is what
    stops one DM sitting on a dead keyboard while the rest of the table moves on.
    """

    def __init__(self, bot, clock=time.monotonic):
        self.bot = bot
        self.boards = {}
        self.intended = {}
        self.owed = []                       # [write, tries left] for writes the route never got to
        self.menus = {}                      # last command list each chat was given
        self.lock = threading.Lock()
        self.clock = clock
        self.failures = 0
        self.retry_after = 0.0

    def run(self, effects, callback_id=None):
        """
        Deliver one batch of effects.

        A Board is remembered so the beat can retry it. A write that was never even attempted while
        the route was down is parked, because sending it later cannot duplicate it — unlike one
        that timed out (AD16). A toast that turns up a minute late is worthless, so it is lost.
        """
        with self.lock:
            for effect in effects:
                retry = None
                if isinstance(effect, Retired):
                    # the slot goes back even if the write has to wait
                    write, retriable = self._spend(effect)
                    retry = write if retriable else None
                else:
                    if isinstance(effect, Board):
                        self.intended[effect.chat_id] = effect      # stays dirty until it lands
                    write = lambda e=effect: self._deliver(e, callback_id)
                if self._held():
                    if isinstance(effect, (Line, Retired, Commands)):
                        self.owed.append([write, PARK_TRIES])   # never attempted, so it cannot duplicate
                    continue
                self._try(write, 'Delivery', retry)

    def reconcile(self):
        """
        Push whatever never landed: parked writes first, in the order they were earned, then any
        Board still dirty. `_board` skips one that is already current.
        """
        with self.lock:
            if self._held():
                return
            while self.owed:
                before = self.failures
                self._try(self.owed[0][0], 'Flush')
                if self.failures > before:
                    self.owed[0][1] -= 1
                    if not self.owed[0][1]:
                        print('Flush given up on — that write never landed')
                        self.owed.pop(0)
                    break                               # still down — the queue keeps its order
                self.owed.pop(0)
            for chat_id, board in list(self.intended.items()):
                self._try(lambda b=board: self._board(b), 'Reconcile')

    def _held(self):
        return self.clock() < self.retry_after

    def _try(self, deliver, note, retry=None):
        """
        A kicked chat, a too-old tap or a dead route must not take the polling thread down with it.
        The Board stamp is left unrecorded, so the next reconcile edits it again. Enough failures
        in a row and writes are held rather than stalling every player behind them.

        A failed `Retired` is parked like a write the route never got to (AD19), because its text —
        the settlement — is said once and exists nowhere else: `clear_round` has already zeroed the
        balances it came from. An edit is safe to attempt twice where a send is not, because an edit
        names the message it writes; AD16's at-most-once rule is about duplication, not about edits.
        """
        if self._held():
            return
        try:
            deliver()
        except (apihelper.ApiTelegramException, requests.exceptions.RequestException) as e:
            print('%s dropped (%s: %s)' % (note, type(e).__name__, _brief(e)))
            if retry is not None:
                self.owed.append([retry, PARK_TRIES])   # the beat flushes it in order, with the rest
            self.failures += 1
            if self.failures >= BREAKER_AFTER:
                self.retry_after = self.clock() + BREAKER_COOLDOWN
                print('Route looks down — holding writes for %.0fs' % BREAKER_COOLDOWN)
        else:
            self.failures = 0

    def _deliver(self, effect, callback_id):
        if isinstance(effect, Board):
            self._board(effect)
        elif isinstance(effect, Commands):
            self._menu(effect)
        elif isinstance(effect, Line):
            self.bot.send_message(effect.chat_id, effect.text)
        elif isinstance(effect, Toast) and callback_id:
            self.bot.answer_callback_query(callback_id, effect.text)

    def _menu(self, effect):
        """
        Telegram's slash menu, scoped to this one player. Cached deliberately: a player tapping
        through the three stages of a win would otherwise push the identical list three times, and
        setMyCommands has no 'only if it changed' of its own. A failed call leaves the cache alone,
        so the player's next message tries it again.
        """
        if self.menus.get(effect.chat_id) == effect.names:
            return
        self.bot.set_my_commands(
            [types.BotCommand(command=command, description=COMMAND_HELP[command])
             for command in effect.names],
            scope=types.BotCommandScopeChat(effect.chat_id))
        self.menus[effect.chat_id] = effect.names

    def _spend(self, effect):
        """
        Hand the chat's message slot back and return the write that marks it spent. Handing it back
        is bookkeeping rather than a write, so it happens even while the route is down: that is
        what makes the next Board a fresh message instead of an overwrite of an old notice.
        """
        held = self.boards.pop(effect.chat_id, None)
        self.intended.pop(effect.chat_id, None)
        message_id = held.message_id if held else None
        return (lambda: self._retire(effect.chat_id, message_id, effect.text),
                message_id is not None)          # an edit names its message; a send does not

    def _retire(self, chat_id, message_id, text):
        """
        An edit with no reply_markup keeps the keyboard it already has, so clearing a spent Board
        means sending an explicitly empty one.
        """
        if message_id is None:
            self.bot.send_message(chat_id, text)
            return
        try:
            self.bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id,
                                       reply_markup=types.InlineKeyboardMarkup())
        except apihelper.ApiTelegramException as e:
            # An edit that changes nothing is not a failure — that is the notice already being on
            # screen, which is what the retry was asking. AD9 says the same for a Board.
            if 'not modified' not in str(e):
                raise

    def _board(self, effect):
        held = self.boards.get(effect.chat_id)
        stamp = (effect.text, effect.rows)
        if held and held.stamp == stamp:
            return  # Telegram rejects an edit that would change nothing.
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


@bot.message_handler(content_types=MESSAGES)
def on_message(message):
    DELIVERY.run(ROOM.message(player(message.from_user), message.text or ''))


@bot.callback_query_handler(func=lambda call: True)
def on_tap(call):
    DELIVERY.run(ROOM.tap(player(call.from_user), call.data), callback_id=call.id)


#--------------Webhook

@server.route('/' + config.token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200


@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=config.webhook_url + config.token)
    return "!", 200


def start_reconciler(delivery, interval=None):
    """Players should not have to tap again to see a Board they are owed."""
    wait = interval or float(os.environ.get('MJ_RECONCILE_SECONDS', 5))

    def beat():
        while True:
            time.sleep(wait)
            delivery.reconcile()

    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    return thread


def polling_kwargs(first=True):
    """
    MJ_POLL_TIMEOUT is the getUpdates hold time, sent as the API 'timeout' param. Keep it low:
    some networks drop long-held connections. skip_pending is on for the first poll because a cold
    start dissolves every Table, so anything queued beforehand refers to a Table that no longer
    exists. A poll restarted inside this process does not dissolve anything (F-04): the Tables are
    still live and the queued taps name them, so a restart polls without it.
    """
    return dict(non_stop=True, interval=1, skip_pending=first,
                long_polling_timeout=int(os.environ.get('MJ_POLL_TIMEOUT', 5)))


if __name__ == "__main__":
    if os.environ.get('MJ_MODE', 'polling') == 'webhook':
        server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
    else:
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
                # The Tables survived this restart, so the queued updates are tonight's, not stale.
                poll = polling_kwargs(first=False)
