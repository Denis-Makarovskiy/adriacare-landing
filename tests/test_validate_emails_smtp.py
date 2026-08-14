from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import dns.exception

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_emails_smtp import (  # noqa: E402
    ValidationResult,
    classify_rcpt,
    filtered_rows,
    syntax_is_valid,
    validate_email,
)


def test_cli_daily_limit_defaults_to_ten(monkeypatch) -> None:
    from validate_emails_smtp import parse_args

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_emails_smtp.py",
            "--input",
            "input.xlsx",
            "--output",
            "output.csv",
            "--helo-domain",
            "adriacare.me",
            "--mail-from",
            "partners@adriacare.me",
        ],
    )
    assert parse_args().limit == 10


def test_syntax_validation() -> None:
    assert syntax_is_valid("info@example.org")
    assert not syntax_is_valid("missing-at.example.org")
    assert not syntax_is_valid("two@@example.org")


def test_rcpt_classification() -> None:
    assert classify_rcpt(250) == "accepted"
    assert classify_rcpt(450) == "temporary_or_policy_block"
    assert classify_rcpt(550) == "rejected"


def test_filter_deduplicates_and_selects_original_rows() -> None:
    rows = [
        {"Country": "Germany", "Facility type": "nursing_home", "Email": "INFO@A.DE", "Email_Source": ""},
        {"Country": "Germany", "Facility type": "nursing_home", "Email": "info@a.de", "Email_Source": ""},
        {"Country": "Germany", "Facility type": "assisted_living", "Email": "x@b.de", "Email_Source": ""},
        {"Country": "Austria", "Facility type": "nursing_home", "Email": "info@c.at", "Email_Source": "inferred:domain_pattern"},
    ]
    selected = filtered_rows(
        rows,
        email_column="Email",
        countries={"Germany", "Austria"},
        facility_type="nursing_home",
        source="original",
    )
    assert len(selected) == 1
    assert selected[0]["Email"] == "INFO@A.DE"


def test_invalid_syntax_never_reaches_dns() -> None:
    with patch("validate_emails_smtp.resolve_mail_hosts") as resolver:
        result = validate_email(
            "bad-address",
            helo_domain="adriacare.me",
            mail_from="partners@adriacare.me",
            timeout=1,
            catch_all_check=True,
            max_mx_hosts=1,
        )
    assert result.status == "invalid_syntax"
    assert not result.send_allowed
    resolver.assert_not_called()


def test_no_mx_is_not_sendable() -> None:
    with patch("validate_emails_smtp.resolve_mail_hosts", return_value=[]):
        result = validate_email(
            "info@example.org",
            helo_domain="adriacare.me",
            mail_from="partners@adriacare.me",
            timeout=1,
            catch_all_check=True,
            max_mx_hosts=1,
        )
    assert result.status == "no_mx"
    assert not result.send_allowed


def test_dns_failure_is_not_misclassified_as_no_mx() -> None:
    with patch(
        "validate_emails_smtp.resolve_mail_hosts",
        side_effect=dns.exception.Timeout(timeout=1),
    ):
        result = validate_email(
            "info@example.org",
            helo_domain="adriacare.me",
            mail_from="partners@adriacare.me",
            timeout=1,
            catch_all_check=True,
            max_mx_hosts=1,
        )
    assert result.status == "dns_error"
    assert not result.send_allowed


def test_deliverable_probe_is_preserved() -> None:
    probe_result = ValidationResult(
        email="info@example.org",
        status="deliverable",
        send_allowed=True,
        mx_host="mx.example.org",
        smtp_code=250,
        catch_all=False,
    )
    with (
        patch("validate_emails_smtp.resolve_mail_hosts", return_value=["mx.example.org"]),
        patch("validate_emails_smtp.smtp_probe", return_value=probe_result),
    ):
        result = validate_email(
            "info@example.org",
            helo_domain="adriacare.me",
            mail_from="partners@adriacare.me",
            timeout=1,
            catch_all_check=True,
            max_mx_hosts=1,
        )
    assert result.status == "deliverable"
    assert result.send_allowed
    assert result.checked_at_utc
