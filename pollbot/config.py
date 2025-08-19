"""Config values for pollbot."""
import logging
import os
import sys

import toml

default_config = {
"telegram": {
        "bot_name": os.getenv("TELEGRAM_BOT_NAME", "soroush_s_bot"),
        "api_key": os.getenv("TELEGRAM_API_KEY", "7814140344:AAHVSofi8vgJpxE-ABACz98mIq5d1BPU4RQ"),
        "worker_count": int(os.getenv("TELEGRAM_WORKER_COUNT", 20)),
        "admin": os.getenv("TELEGRAM_ADMIN", "soroush"),
        "allow_private_vote": os.getenv("TELEGRAM_ALLOW_PRIVATE_VOTE", "True") == "True",
        "max_user_votes_per_day": int(os.getenv("TELEGRAM_MAX_USER_VOTES_PER_DAY", 200)),
        "max_inline_shares": int(os.getenv("TELEGRAM_MAX_INLINE_SHARES", 20)),
        "max_polls_per_user": int(os.getenv("TELEGRAM_MAX_POLLS_PER_USER", 200)),
    },
    "database": {
        "sql_uri": os.getenv("DATABASE_SQL_URI", "postgresql://pollbot:pollbot@localhost:5432/pollbot"),
        "connection_count": int(os.getenv("DATABASE_CONNECTION_COUNT", 20)),
        "overflow_count": int(os.getenv("DATABASE_OVERFLOW_COUNT", 10)),
    },
    "logging": {
        "sentry_enabled": False,
        "sentry_token": "",
        "log_level": logging.INFO,
        "debug": False,
    },
    "webhook": {
        "enabled": False,
        "domain": "https://localhost",
        "token": "pollbot",
        "cert_path": "/path/to/cert.pem",
        "port": 7000,
    },
}

config_path = os.path.expanduser("~/.config/ultimate_pollbot.toml")

if not os.path.exists(config_path):
    with open(config_path, "w") as file_descriptor:
        toml.dump(default_config, file_descriptor)
    print("Please adjust the configuration file at '~/.config/ultimate_pollbot.toml'")
    sys.exit(1)
else:
    config = toml.load(config_path)

    config=default_config

    # Set default values for any missing keys in the loaded config
    for key, category in default_config.items():
        for option, value in category.items():
            if option not in config[key]:
                config[key][option] = value

