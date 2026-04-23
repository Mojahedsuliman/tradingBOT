"""
WSGI entry point for gunicorn.
- Imports health_app from app.py (which registers all bot handlers and starts background threads)
- Starts bot.infinity_polling() in a background thread
- Exposes health_app as the WSGI application for gunicorn
"""
import threading
import sys

# Import the Flask health app and the bot from app (without running polling)
# app.py currently calls bot.infinity_polling() at module level — we patch it out
import app as _app_module

# Start the Telegram bot polling in a background daemon thread
def _start_bot():
    try:
        print("🤖 Starting Telegram bot polling in background thread...")
        _app_module.bot.infinity_polling()
    except Exception as e:
        print(f"Bot polling error: {e}", file=sys.stderr)

_bot_thread = threading.Thread(target=_start_bot, daemon=True)
_bot_thread.start()

# Expose the Flask health_app as the WSGI application
application = _app_module.health_app
app = application
