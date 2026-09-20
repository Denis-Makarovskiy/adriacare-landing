"""Fail-closed probe through authenticated Beget submission SMTP.

Lenovo never opens TCP/25 to recipient MX hosts.  It authenticates only to the
same Beget relay used for delivery, issues MAIL/RCPT/RSET, and never issues
DATA.  A positive recipient RCPT and a rejected random catch-all probe are
both required before an address can pass this gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import os
import random
import smtplib
import ssl
import string


@dataclass(frozen=True)
class VerificationResult:
    email: str
    status: str
    send_allowed: bool
    mx_host: str = ''
    smtp_code: int | None = None
    smtp_message: str = ''



def classify_rejection(code: int, reply: str) -> str:
    """Map a refused recipient to a status the pipeline can act on.

    Only a permanent 5.1.x / "user unknown" answer means the mailbox does not
    exist.  4xx answers are temporary, 5.7.x means the relay refused on policy
    grounds, and everything else stays an inconclusive rejection.
    """
    text = (reply or '').lower()
    enhanced = re.search(r'\b([45]\.\d{1,3}\.\d{1,3})\b', text)
    enhanced_code = enhanced.group(1) if enhanced else ''
    if 400 <= code < 500 or enhanced_code.startswith('4.'):
        return 'temporary_failure'
    if enhanced_code.startswith('5.7') or code in (554, 557):
        return 'policy_blocked'
    if enhanced_code.startswith('5.1') or 'user unknown' in text or 'no such user' in text \
            or 'recipient address rejected' in text or code == 550:
        return 'undeliverable'
    return 'rejected_other'

def _result(email: str, status: str, message: str = '', *, mx_host: str = '',
            smtp_code: int | None = None, send_allowed: bool = False) -> VerificationResult:
    return VerificationResult(email=email, status=status, send_allowed=send_allowed,
                              mx_host=mx_host, smtp_code=smtp_code, smtp_message=message[:300])


def _smtp_config() -> tuple[str, int, str, str]:
    host = os.environ.get('ADRIA_SMTP_HOST', 'smtp.beget.com').strip().lower()
    port = int(os.environ.get('ADRIA_SMTP_PORT', '465'))
    user = os.environ.get('ADRIA_SMTP_USER', '').strip()
    password = os.environ.get('ADRIA_SMTP_PASSWORD', '')
    if host != 'smtp.beget.com' or port != 465:
        raise RuntimeError('SMTP probe is restricted to authenticated smtp.beget.com:465')
    if not user or not password:
        raise RuntimeError('Beget SMTP credentials are missing')
    return host, port, user, password


def _decode(reply: bytes | str) -> str:
    return reply.decode('utf-8', errors='replace') if isinstance(reply, bytes) else str(reply)


def _random_recipient(email: str) -> str:
    local, domain = email.rsplit('@', 1)
    alphabet = string.ascii_lowercase + string.digits
    return f"adriacare-probe-{' '.join(random.choice(alphabet) for _ in range(20)).replace(' ', '')}@{domain}"


def verify_email(email: str, *, helo_domain: str, mail_from: str, timeout: float) -> VerificationResult:
    """Probe through Beget only; no direct recipient-MX connection is possible."""
    try:
        host, port, user, password = _smtp_config()
        client = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
    except (OSError, ValueError, RuntimeError, smtplib.SMTPException) as exc:
        return _result(email, 'smtp_relay_unreachable', f'{type(exc).__name__}: {exc}')
    try:
        client.ehlo(helo_domain)
        client.login(user, password)
        mail_code, mail_reply = client.mail(mail_from)
        if mail_code not in (250, 251):
            return _result(email, 'smtp_relay_rejected_sender', _decode(mail_reply), mx_host=host,
                           smtp_code=mail_code)
        code, reply = client.rcpt(email)
        reply_text = _decode(reply)
        client.rset()
        if code not in (250, 251, 252):
            status = classify_rejection(code, _decode(reply_text))
            return _result(email, status, reply_text, mx_host=host, smtp_code=code)
        # A relay accepting every recipient cannot prove that this mailbox
        # exists.  It remains a hard block rather than an optimistic success.
        mail_code, mail_reply = client.mail(mail_from)
        if mail_code not in (250, 251):
            return _result(email, 'smtp_relay_rejected_sender', _decode(mail_reply), mx_host=host,
                           smtp_code=mail_code)
        random_code, random_reply = client.rcpt(_random_recipient(email))
        client.rset()
        if random_code in (250, 251, 252):
            return _result(email, 'catch_all', _decode(random_reply), mx_host=host, smtp_code=code)
        return _result(email, 'deliverable', reply_text, mx_host=host, smtp_code=code, send_allowed=True)
    except (OSError, smtplib.SMTPException) as exc:
        return _result(email, 'smtp_relay_unreachable', f'{type(exc).__name__}: {exc}')
    finally:
        try:
            client.quit()
        except (OSError, smtplib.SMTPException):
            client.close()
