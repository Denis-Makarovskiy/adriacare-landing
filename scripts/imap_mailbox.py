#!/usr/bin/env python3
"""Read an outreach mailbox over IMAP without modifying message state."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email import message_from_bytes, policy
from email.header import decode_header, make_header
import imaplib
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
from typing import Callable, Sequence


DEFAULT_HOST = "imap.beget.com"
DEFAULT_PORT = 993
HEADER_FIELDS = "DATE FROM TO SUBJECT MESSAGE-ID IN-REPLY-TO REFERENCES"
ENV_KEYS = {
    "ADRIA_IMAP_HOST",
    "ADRIA_IMAP_PORT",
    "ADRIA_IMAP_USER",
    "ADRIA_IMAP_PASSWORD",
    "ADRIA_IMAP_MAILBOX",
    "ADRIA_IMAP_KEYCHAIN_SERVICE",
}


def load_env_file(path: Path = Path(".env")) -> None:
    """Load known IMAP settings without interpreting shell syntax."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int
    username: str
    password: str
    mailbox: str

    @classmethod
    def from_env(cls) -> "ImapConfig":
        username = os.environ.get("ADRIA_IMAP_USER", "").strip()
        if not username:
            raise ValueError("ADRIA_IMAP_USER is required")
        password = os.environ.get("ADRIA_IMAP_PASSWORD", "") or password_from_keychain(username)
        if not password:
            raise ValueError(
                "No IMAP password found in ADRIA_IMAP_PASSWORD or macOS Keychain"
            )
        return cls(
            host=os.environ.get("ADRIA_IMAP_HOST", DEFAULT_HOST).strip(),
            port=int(os.environ.get("ADRIA_IMAP_PORT", str(DEFAULT_PORT))),
            username=username,
            password=password,
            mailbox=os.environ.get("ADRIA_IMAP_MAILBOX", "INBOX").strip() or "INBOX",
        )


def password_from_keychain(username: str) -> str:
    if sys.platform != "darwin":
        return ""
    service = os.environ.get("ADRIA_IMAP_KEYCHAIN_SERVICE", "adriacare-imap")
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                username,
                "-s",
                service,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    return result.stdout.rstrip("\r\n")


def decode_value(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeError):
        return value


def connect(
    config: ImapConfig,
    *,
    timeout: float,
    client_factory: Callable[..., imaplib.IMAP4_SSL] = imaplib.IMAP4_SSL,
) -> imaplib.IMAP4_SSL:
    tls_context = ssl.create_default_context()
    client = client_factory(
        config.host,
        config.port,
        ssl_context=tls_context,
        timeout=timeout,
    )
    status, _ = client.login(config.username, config.password)
    if status != "OK":
        client.logout()
        raise RuntimeError("IMAP authentication failed")
    return client


def select_read_only(client: imaplib.IMAP4_SSL, mailbox: str) -> int:
    status, data = client.select(mailbox, readonly=True)
    if status != "OK":
        raise RuntimeError(f"Unable to open mailbox: {mailbox}")
    try:
        return int(data[0])
    except (TypeError, ValueError, IndexError):
        return 0


def unread_ids(client: imaplib.IMAP4_SSL) -> list[bytes]:
    status, data = client.uid("search", None, "UNSEEN")
    if status != "OK" or not data:
        raise RuntimeError("Unable to search unread messages")
    return data[0].split()


def fetch_headers(client: imaplib.IMAP4_SSL, uids: Sequence[bytes]) -> list[dict[str, object]]:
    messages = []
    for uid in uids:
        status, data = client.uid(
            "fetch",
            uid,
            f"(BODY.PEEK[HEADER.FIELDS ({HEADER_FIELDS})] RFC822.SIZE INTERNALDATE)",
        )
        if status != "OK" or not data:
            continue
        raw_header = next(
            (part[1] for part in data if isinstance(part, tuple) and isinstance(part[1], bytes)),
            b"",
        )
        if not raw_header:
            continue
        message = message_from_bytes(raw_header, policy=policy.default)
        messages.append(
            {
                "uid": uid.decode("ascii", errors="replace"),
                "date": decode_value(message.get("Date")),
                "from": decode_value(message.get("From")),
                "to": decode_value(message.get("To")),
                "subject": decode_value(message.get("Subject")),
                "message_id": decode_value(message.get("Message-ID")),
                "in_reply_to": decode_value(message.get("In-Reply-To")),
                "references": decode_value(message.get("References")),
            }
        )
    return messages


def command_check(client: imaplib.IMAP4_SSL, config: ImapConfig) -> dict[str, object]:
    total = select_read_only(client, config.mailbox)
    unread = len(unread_ids(client))
    return {
        "connected": True,
        "host": config.host,
        "port": config.port,
        "mailbox": config.mailbox,
        "messages": total,
        "unread": unread,
        "read_only": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "unread"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.limit <= 100:
        raise ValueError("--limit must be between 1 and 100")
    load_env_file()
    config = ImapConfig.from_env()
    client = connect(config, timeout=args.timeout)
    try:
        if args.command == "check":
            print(json.dumps(command_check(client, config), ensure_ascii=False, indent=2))
            return 0

        select_read_only(client, config.mailbox)
        ids = unread_ids(client)[-args.limit :]
        print(json.dumps(fetch_headers(client, ids), ensure_ascii=False, indent=2))
        return 0
    finally:
        try:
            client.close()
        except imaplib.IMAP4.error:
            pass
        client.logout()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, imaplib.IMAP4.error, OSError) as exc:
        print(f"IMAP error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
