"""Stand-ins for Telegram, shared by the delivery tests."""
import threading


class Sent:
    def __init__(self, message_id):
        self.message_id = message_id


class FakeBot:
    def __init__(self):
        self.sent = []
        self.edited = []
        self.toasts = []
        self.menus = []                  # (chat_id, command names) per set_my_commands call
        self.next_id = 100
        self.ids = threading.Lock()      # chats are written to side by side, as the real bot does

    def set_my_commands(self, commands, scope=None, language_code=None):
        self.menus.append((getattr(scope, "chat_id", None), tuple(c.command for c in commands)))
        return True

    def send_message(self, chat_id, text, reply_markup=None):
        with self.ids:
            self.next_id += 1
            self.sent.append((chat_id, text, reply_markup))
            return Sent(self.next_id)

    def edit_message_text(self, text=None, chat_id=None, message_id=None, reply_markup=None):
        self.edited.append((chat_id, message_id, text, reply_markup))
        return True

    def answer_callback_query(self, callback_query_id, text=None, **kwargs):
        # kwargs are kept, not dropped: `show_alert` is the whole difference between a refusal a
        # player reads and one they never see, and a fake that discarded it could not tell them apart.
        self.toasts.append((callback_query_id, text, dict(kwargs)))
        return True

    def boards(self):
        """
        The Board sends and only them — a Board is the one message that counts seats.

        Five assertions used to carry the literal themselves, so the rule for telling a Board from a
        one-line reply lived in five places (F-19).
        """
        return [s for s in self.sent if "seated" in s[1]]
