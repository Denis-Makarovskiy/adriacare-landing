"""Правила допуска и остановки, перенесённые с Lenovo (пункты 4.5, 4.8, 4.12)."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_ADRIA = Path(__file__).resolve().parents[1] / "ops" / "lenovo" / "adriacare"


def _load(name: str, filename: str):
    for module_name, attributes in (
        ("db", {"connect": lambda *args, **kwargs: None}),
        ("codex_drafts", {"context_sha256": lambda *a, **k: "", "policy_sha256": lambda *a, **k: ""}),
    ):
        if module_name not in sys.modules:
            stub = types.ModuleType(module_name)
            for key, value in attributes.items():
                setattr(stub, key, value)
            sys.modules[module_name] = stub
    spec = importlib.util.spec_from_file_location(name, _ADRIA / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


smtp = _load("lenovo_smtp_verifier", "smtp_verifier_client.py")
send_due = _load("lenovo_send_due", "send_due.py")
browser = _load("lenovo_browser_research", "browser_research.py")


@pytest.mark.parametrize(
    ("code", "reply", "expected"),
    [
        (550, "5.1.1 User unknown", "undeliverable"),
        (550, "Recipient address rejected: no such user here", "undeliverable"),
        (550, "Requested action not taken", "undeliverable"),
        (450, "4.2.1 mailbox busy", "temporary_failure"),
        (421, "4.7.0 try again later", "temporary_failure"),
        (554, "5.7.1 Policy rejection", "policy_blocked"),
        (521, "server refused", "rejected_other"),
    ],
)
def test_smtp_rejection_classification(code: int, reply: str, expected: str) -> None:
    assert smtp.classify_rejection(code, reply) == expected


@pytest.mark.parametrize(
    ("bounced", "total", "expected"),
    [
        (0, 20, False),
        (0, 19, False),
        (1, 20, True),      # 5 %
        (2, 50, True),      # 4 %
        (1, 50, False),     # 2 %
        (3, 100, False),    # 3 % ровно — не превышение
        (4, 100, True),
    ],
)
def test_bounce_rate_threshold(bounced: int, total: int, expected: bool) -> None:
    assert send_due.bounce_rate_exceeded(bounced, total) is expected


@pytest.mark.parametrize(
    ("failures", "expected"),
    [
        ({"https://a.de": "browser_exit_1"}, True),
        ({"https://a.de": "browser_exit_1", "https://b.de": "browser_exit_1"}, True),
        ({"https://a.de": "browser_navigation_error"}, False),
        ({"https://a.de": "browser_exit_1", "https://b.de": "browser_timeout"}, False),
        ({}, False),
    ],
)
def test_dead_domain_rule(failures: dict[str, str], expected: bool) -> None:
    assert browser.is_dead_domain(failures) is expected
