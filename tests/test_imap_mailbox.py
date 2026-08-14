from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from imap_mailbox import (  # noqa: E402
    ImapConfig,
    command_check,
    decode_value,
    fetch_headers,
    load_env_file,
    password_from_keychain,
    select_read_only,
    unread_ids,
)


class FakeImap:
    def select(self, mailbox, readonly=False):
        assert mailbox == "INBOX"
        assert readonly is True
        return "OK", [b"12"]

    def uid(self, command, *args):
        if command == "search":
            return "OK", [b"41 42"]
        if command == "fetch":
            uid = args[0]
            header = (
                b"Date: Thu, 14 Aug 2026 10:00:00 +0200\r\n"
                b"From: =?UTF-8?Q?Pflegeheim_M=C3=BCnchen?= <info@example.de>\r\n"
                b"To: partners@adriacare.me\r\n"
                b"Subject: Re: Kooperation\r\n"
                b"Message-ID: <reply@example.de>\r\n"
                b"In-Reply-To: <outreach@adriacare.me>\r\n\r\n"
            )
            return "OK", [(b"UID " + uid, header), b")"]
        raise AssertionError(command)


def make_config() -> ImapConfig:
    return ImapConfig("imap.beget.com", 993, "partners@adriacare.me", "secret", "INBOX")


def test_config_requires_credentials(monkeypatch) -> None:
    monkeypatch.delenv("ADRIA_IMAP_USER", raising=False)
    monkeypatch.delenv("ADRIA_IMAP_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="ADRIA_IMAP_USER"):
        ImapConfig.from_env()


def test_env_file_loads_only_known_keys(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ADRIA_IMAP_USER", raising=False)
    monkeypatch.delenv("UNRELATED", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ADRIA_IMAP_USER=partners@adriacare.me\nUNRELATED=do-not-load\n",
        encoding="utf-8",
    )
    load_env_file(env_file)
    assert os.environ["ADRIA_IMAP_USER"] == "partners@adriacare.me"
    assert "UNRELATED" not in os.environ


def test_config_can_load_password_from_keychain(monkeypatch) -> None:
    monkeypatch.setenv("ADRIA_IMAP_USER", "partners@adriacare.me")
    monkeypatch.delenv("ADRIA_IMAP_PASSWORD", raising=False)
    monkeypatch.setattr("imap_mailbox.password_from_keychain", lambda username: "secret")
    assert ImapConfig.from_env().password == "secret"


def test_keychain_lookup_does_not_log_password(monkeypatch) -> None:
    class Result:
        stdout = "secret-value\n"

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr("imap_mailbox.subprocess.run", lambda *args, **kwargs: Result())
    assert password_from_keychain("partners@adriacare.me") == "secret-value"


def test_read_only_mailbox_summary() -> None:
    summary = command_check(FakeImap(), make_config())
    assert summary["messages"] == 12
    assert summary["unread"] == 2
    assert summary["read_only"] is True


def test_header_fetch_uses_peek_and_decodes_subject() -> None:
    messages = fetch_headers(FakeImap(), [b"42"])
    assert len(messages) == 1
    assert messages[0]["uid"] == "42"
    assert messages[0]["subject"] == "Re: Kooperation"
    assert "Pflegeheim München" in messages[0]["from"]
    assert messages[0]["in_reply_to"] == "<outreach@adriacare.me>"


def test_helpers() -> None:
    client = FakeImap()
    assert select_read_only(client, "INBOX") == 12
    assert unread_ids(client) == [b"41", b"42"]
    assert decode_value("=?UTF-8?Q?Gr=C3=BC=C3=9Fe?=") == "Grüße"
