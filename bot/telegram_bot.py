"""
Telegram bot for sending trading signals to multiple users/channels.
Supports:
  - Multiple individual users (via chat IDs)
  - Telegram channels (via @channel_username)
  - Auto-subscription via /start command
"""
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_RECIPIENTS

# Subscriber file (for auto-registration via /start)
SUBSCRIBERS_FILE = Path(__file__).resolve().parent.parent / "data" / "subscribers.json"


def _load_subscribers():
    """Load subscriber list from file."""
    if SUBSCRIBERS_FILE.exists():
        try:
            with open(SUBSCRIBERS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_subscribers(subscribers):
    """Save subscriber list to file."""
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subscribers, f, indent=2)


def add_subscriber(chat_id, name=""):
    """Add a new subscriber."""
    subscribers = _load_subscribers()
    chat_id_str = str(chat_id)

    # Check if already exists
    for sub in subscribers:
        if str(sub["chat_id"]) == chat_id_str:
            return False  # Already subscribed

    subscribers.append({
        "chat_id": chat_id_str,
        "name": name,
        "active": True,
    })
    _save_subscribers(subscribers)
    return True


def remove_subscriber(chat_id):
    """Remove a subscriber (mark as inactive)."""
    subscribers = _load_subscribers()
    chat_id_str = str(chat_id)
    for sub in subscribers:
        if str(sub["chat_id"]) == chat_id_str:
            sub["active"] = False
            _save_subscribers(subscribers)
            return True
    return False


def get_all_recipients():
    """
    Get all unique recipient IDs to send messages to.
    Combines: .env RECIPIENTS + subscribers.json (active only)
    """
    recipients = set()

    # From .env / GitHub secrets
    for r in TELEGRAM_RECIPIENTS:
        recipients.add(r)

    # From subscribers file (local runs)
    for sub in _load_subscribers():
        if sub.get("active", True):
            recipients.add(str(sub["chat_id"]))

    return list(recipients)


async def send_message(text, parse_mode=None):
    """Send a message to ALL recipients (users + channels)."""
    recipients = get_all_recipients()

    if not TELEGRAM_BOT_TOKEN or not recipients:
        print("[TELEGRAM] Bot token or recipients not configured. Printing to console:")
        print(text)
        return False

    try:
        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        success_count = 0
        fail_count = 0

        for chat_id in recipients:
            try:
                if len(text) > 4000:
                    chunks = _split_message(text, 4000)
                    for chunk in chunks:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                            parse_mode=parse_mode,
                        )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=parse_mode,
                    )
                success_count += 1
            except Exception as e:
                fail_count += 1
                print(f"[TELEGRAM] Failed to send to {chat_id}: {e}")

        print(f"[TELEGRAM] Sent to {success_count}/{success_count + fail_count} recipients")
        return success_count > 0
    except Exception as e:
        print(f"[TELEGRAM] Failed: {e}")
        print("[TELEGRAM] Message content:")
        print(text)
        return False


def send_message_sync(text, parse_mode=None):
    """Synchronous wrapper for send_message."""
    return asyncio.run(send_message(text, parse_mode))


def send_signal_alert(signal):
    """Send a formatted signal alert."""
    from bot.formatter import format_signal
    text = format_signal(signal)
    return send_message_sync(text)


def send_daily_digest(digest_text):
    """Send the daily market digest."""
    return send_message_sync(digest_text)


def send_multiple_signals(signals):
    """Send multiple signal alerts."""
    from bot.formatter import format_multiple_signals
    text = format_multiple_signals(signals)
    return send_message_sync(text)


def check_new_subscribers():
    """
    Check for new /start messages and auto-register subscribers.
    Call this before sending signals to pick up new users.
    """
    if not TELEGRAM_BOT_TOKEN:
        return 0

    import requests

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            return 0

        new_count = 0
        max_update_id = 0

        for update in data.get("result", []):
            max_update_id = max(max_update_id, update.get("update_id", 0))
            msg = update.get("message", {})
            text = msg.get("text", "")
            chat = msg.get("chat", {})
            chat_id = chat.get("id")
            first_name = chat.get("first_name", "")
            last_name = chat.get("last_name", "")
            name = f"{first_name} {last_name}".strip()

            if text == "/start" and chat_id:
                added = add_subscriber(chat_id, name)
                if added:
                    new_count += 1
                    print(f"[TELEGRAM] New subscriber: {name} ({chat_id})")
                    # Send welcome message to the new user
                    try:
                        import asyncio
                        from telegram import Bot
                        bot = Bot(token=TELEGRAM_BOT_TOKEN)
                        asyncio.run(bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"Welcome {first_name}!\n\n"
                                "You are now subscribed to MT5 Trading Signals.\n\n"
                                "You will receive:\n"
                                "- Hourly futures signals (Gold, Silver, Stocks)\n"
                                "- Daily market digest\n\n"
                                "Send /stop to unsubscribe."
                            )
                        ))
                    except Exception:
                        pass

            elif text == "/stop" and chat_id:
                removed = remove_subscriber(chat_id)
                if removed:
                    print(f"[TELEGRAM] Unsubscribed: {name} ({chat_id})")

        # Mark updates as read
        if max_update_id > 0:
            requests.get(f"{url}?offset={max_update_id + 1}", timeout=5)

        return new_count
    except Exception as e:
        print(f"[TELEGRAM] Error checking subscribers: {e}")
        return 0


def list_subscribers():
    """List all active subscribers."""
    recipients = get_all_recipients()
    subscribers = _load_subscribers()

    print(f"\nActive Recipients: {len(recipients)}")
    print("-" * 40)
    for r in recipients:
        # Check if it's a channel
        if r.startswith("@"):
            print(f"  Channel: {r}")
        else:
            # Find name from subscribers
            name = ""
            for sub in subscribers:
                if str(sub["chat_id"]) == r:
                    name = sub.get("name", "")
                    break
            print(f"  User: {r} {f'({name})' if name else ''}")


def _split_message(text, max_length):
    """Split a long message into chunks."""
    lines = text.split("\n")
    chunks = []
    current = []
    current_len = 0

    for line in lines:
        if current_len + len(line) + 1 > max_length and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line) + 1

    if current:
        chunks.append("\n".join(current))

    return chunks


if __name__ == "__main__":
    print("Testing Telegram bot...")
    print("\nChecking for new subscribers...")
    new = check_new_subscribers()
    print(f"New subscribers: {new}")

    list_subscribers()

    test_msg = (
        "TEST MESSAGE\n"
        "=================\n"
        "Trading Signal Bot is working!\n"
        "=================\n"
        "This is a test from MetaTrader5 Strategy system."
    )
    send_message_sync(test_msg)
