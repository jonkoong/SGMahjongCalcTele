import os

def _load_dotenv(path='.env'):
    # Minimal KEY=value loader so the token stays out of git without a new dependency.
    if not os.path.isfile(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip())

_load_dotenv()

# Telegram bot token from @BotFather. Never commit a real token.
token = os.environ.get('MJ_TOKEN', '...')
