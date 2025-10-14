import threading
import time
import os
from keep_alive import keep_alive

def run_flask():
    keep_alive()

# Start Flask in a separate thread
threading.Thread(target=run_flask).start()

# Wait a few seconds to ensure web server starts
time.sleep(5)

# Start your bot
os.system("python3 bot.py")
