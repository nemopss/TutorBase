#!/usr/bin/env python3
"""
Generate Telegram WebApp initData for local testing without real WebApp.
Output is a URL-encoded string that can be sent to /api/v1/auth/login.

Usage:
  python scripts/generate_init_data.py --bot-token TOKEN --user-id 123 --username test_user --first-name Test --last-name User

Note:
  - query_id and other optional fields are fake placeholders.
  - Use only for local testing; do not keep bot tokens in repo.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import urllib.parse
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TelegramUserData:
    user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None

    def to_json(self) -> str:
        payload = {
            "id": self.user_id,
        }
        if self.username:
            payload["username"] = self.username
        if self.first_name:
            payload["first_name"] = self.first_name
        if self.last_name:
            payload["last_name"] = self.last_name
        if self.language_code:
            payload["language_code"] = self.language_code
        # Use compact JSON (Telegram produces no whitespace)
        return json.dumps(payload, separators=(",", ":"))


def generate_init_data(bot_token: str, user: TelegramUserData) -> str:
    data_pairs = {
        "query_id": "AAAAA_BBBB",  # fake id
        "user": user.to_json(),
        "auth_date": str(int(datetime.now().timestamp())),
    }

    # Build data-check string (sorted key=value joined by newlines)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_pairs.items()))

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    init_data_parts = [
        urllib.parse.urlencode({"hash": hash_value})
    ] + [urllib.parse.urlencode({key: value}) for key, value in data_pairs.items()]

    # Hash first, then payload entries (Telegram sends hash last, но порядок неважен)
    return "&".join(init_data_parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Telegram initData for local testing")
    parser.add_argument("--bot-token", required=True, help="Telegram bot token")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--username")
    parser.add_argument("--first-name")
    parser.add_argument("--last-name")
    parser.add_argument("--language-code")

    args = parser.parse_args()

    user = TelegramUserData(
        user_id=args.user_id,
        username=args.username,
        first_name=args.first_name,
        last_name=args.last_name,
        language_code=args.language_code,
    )

    init_data = generate_init_data(args.bot_token, user)
    print(init_data)


if __name__ == "__main__":
    main()
