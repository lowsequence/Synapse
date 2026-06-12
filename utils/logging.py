from colorama import Fore, Style
import datetime
import os
import pytz

dhaka_tz = pytz.timezone('Asia/Dhaka')

class Logger:
    def __init__(self) -> None:
        if not os.path.exists("logs"):
            os.makedirs("logs")

        self.logging_file = f"logs/{datetime.datetime.now(dhaka_tz).strftime('%Y-%m-%d %H-%M-%S')}.log"
        self.file = open(self.logging_file, "w", encoding="utf-8")
        self.log(f"Log file created at {datetime.datetime.now(dhaka_tz)}\n", "INFO")

    def log(self, message, level="INFO"):
        timestamp = datetime.datetime.now(dhaka_tz).strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        if level == "INFO":
            log_color = Fore.BLUE
        elif level == "WARNING":
            log_color = Fore.YELLOW
        elif level == "ERROR":
            log_color = Fore.RED
        else:
            log_color = Fore.WHITE
        print(f"{log_color}{log_entry}{Style.RESET_ALL}", end="")
        self.file.write(log_entry)
        self.file.flush()

    def info(self, message):
        self.log(message, "INFO")

    def warning(self, message):
        self.log(message, "WARNING")

    def error(self, message):
        self.log(message, "ERROR")

    def close(self):
        self.file.write(f"Log file closed at {datetime.datetime.now(dhaka_tz)}\n")
        self.file.close()

logger = Logger()
