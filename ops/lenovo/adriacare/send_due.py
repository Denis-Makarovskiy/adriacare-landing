#!/usr/bin/env python3
"""Send at most one due campaign email through authenticated Beget SMTP."""

from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
import hashlib
import json
import logging
import os
from pathlib import Path
import smtplib
import db as sqlite3
import ssl
import sys
from zoneinfo import ZoneInfo

from codex_drafts import context_sha256, policy_sha256


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get("ADRIA_RUNTIME_DIR", "/var/lib/agents/adriacare"))
ENV_KEYS = {"ADRIA_SMTP_HOST", "ADRIA_SMTP_PORT", "ADRIA_SMTP_USER", "ADRIA_SMTP_PASSWORD"}


def load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in ENV_KEYS:
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def smtp_config() -> tuple[str, int, str, str]:
    values = (
        os.environ.get("ADRIA_SMTP_HOST", "smtp.beget.com"),
        int(os.environ.get("ADRIA_SMTP_PORT", "465")),
        os.environ.get("ADRIA_SMTP_USER", ""),
        os.environ.get("ADRIA_SMTP_PASSWORD", ""),
    )
    if not values[2] or not values[3]:
        raise RuntimeError("SMTP credentials are missing")
    return values


def connect_smtp(timeout: float = 60.0) -> smtplib.SMTP_SSL:
    host, port, username, password = smtp_config()
    client = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
    client.login(username, password)
    return client



def bounce_rate_exceeded(bounced: int, total_sent: int, *, minimum: int = 20,
                         percent: int = 3) -> bool:
    """True when hard bounces exceed ``percent`` of the last ``total_sent`` sends."""
    if total_sent < minimum:
        return False
    return bounced * 100 > total_sent * percent

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Authenticate and NOOP without sending")
    parser.add_argument("--dry-run", action="store_true", help="Show one due row without changing state or sending")
    parser.add_argument("--now", help="Testing override ISO datetime")
    args = parser.parse_args()

    (RUNTIME / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=RUNTIME / "logs" / "sender.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # systemd supplies production credentials through its protected
    # EnvironmentFile. A local .env is optional for developer use only.
    local_env = ROOT / ".env"
    if local_env.exists():
        load_env(local_env)
    if args.check:
        client = connect_smtp()
        try:
            code, _ = client.noop()
            print(json.dumps({"authenticated": True, "noop_code": code, "sent": 0}))
        finally:
            client.quit()
        return 0

    config = json.loads((ROOT / "config" / "outreach_pilot.json").read_text(encoding="utf-8"))
    drip = config["drip"]
    daily_send_cap = int(config["daily_send_cap"])
    if not 1 <= daily_send_cap <= 30:
        raise RuntimeError("campaign daily_send_cap must be 1..30")
    zone = ZoneInfo(drip["timezone"])
    now = datetime.fromisoformat(args.now).astimezone(zone) if args.now else datetime.now(zone)
    if not drip.get("automation_enabled") or now.date() < datetime.fromisoformat(drip["start_date"]).date():
        return 0
    if now.weekday() >= 5:
        return 0
    start_h, start_m = map(int, drip["window_start"].split(":"))
    end_h, end_m = map(int, drip["window_end"].split(":"))
    if not time(start_h, start_m) <= now.time().replace(tzinfo=None) < time(end_h, end_m):
        return 0

    db_path = ROOT / "outreach-state" / "outreach.sqlite3"
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    row = None
    message_id = ""
    try:
        connection.execute("BEGIN IMMEDIATE")
        today = now.date().isoformat()
        day_status = connection.execute(
            "SELECT target_count,eligible_unique_count,active_unique_count,preflight_ok FROM campaign_day_status WHERE campaign_id=? AND business_date=?",
            (drip["campaign_id"], today),
        ).fetchone()
        if not day_status:
            raise RuntimeError(f"campaign_day_status missing for {today}")
        target_count = int(day_status["target_count"])
        eligible_count = int(day_status["eligible_unique_count"])
        active_count = int(day_status["active_unique_count"])
        if not day_status["preflight_ok"] or eligible_count < target_count:
            # The current operating playbook prohibits partial daily batches.
            connection.rollback()
            return 0
        # Bounce guard (owner decision 2026-09-19): a hard-bounce rate above
        # three percent across the most recent fifty sends stops all sending
        # until a human looks at the list.  This protects domain reputation and
        # is not an unsubscribe mechanism.
        recent = connection.execute(
            """
            WITH last_sent AS (
                SELECT lead_id FROM events WHERE event_type='sent'
                ORDER BY occurred_at::timestamptz DESC LIMIT 50
            )
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM events b WHERE b.lead_id=last_sent.lead_id
                         AND b.event_type IN ('bounced','hard_bounce'))) AS bounced
            FROM last_sent
            """
        ).fetchone()
        total_sent = int(recent["total"] or 0)
        bounced = int(recent["bounced"] or 0)
        if bounce_rate_exceeded(bounced, total_sent):
            connection.rollback()
            print(f"bounce guard: {bounced} of last {total_sent} sends bounced; sending stopped")
            return 0
        if target_count <= 0 or active_count >= min(target_count, daily_send_cap):
            connection.rollback()
            return 0
        connection.execute(
            """
            UPDATE campaign_queue
            SET state='missed',last_error='send_window_missed',updated_at=?
            WHERE campaign_id=? AND state='scheduled' AND substr(scheduled_at,1,10)<?
            """,
            (now.astimezone(timezone.utc).isoformat(), drip["campaign_id"], today),
        )
        row = connection.execute(
            """
            SELECT q.id queue_id,q.campaign_id,q.lead_id,q.scheduled_at,q.state,q.batch_id,
                   l.name,l.email,l.email_domain,l.operator,l.variant,l.personalization_fact,l.manual_approved,
                   l.do_not_contact,l.status,l.smtp_status,l.cohort,l.evidence_url,l.outreach_language,l.language_approved,
                   d.id AS draft_id,d.subject AS draft_subject,d.body AS draft_body,
                   d.context_sha256 AS draft_context_sha256,d.policy_sha256 AS draft_policy_sha256
            FROM campaign_queue q
            JOIN leads l ON l.id=q.lead_id
            JOIN daily_batches b ON b.id=q.batch_id AND b.state IN ('ready','sending')
            LEFT JOIN LATERAL (
                SELECT id,subject,body,context_sha256,policy_sha256
                FROM codex_draft_reviews
                WHERE lead_id=l.id AND status='approved'
                ORDER BY approved_at DESC,id DESC LIMIT 1
            ) d ON true
            WHERE q.campaign_id=? AND q.state='scheduled'
              AND substr(q.scheduled_at,1,10)=? AND q.scheduled_at<=?
              AND NOT EXISTS (
                  SELECT 1
                  FROM campaign_queue sent_q
                  JOIN leads sent_l ON sent_l.id=sent_q.lead_id
                  WHERE sent_q.campaign_id=q.campaign_id
                    AND substr(sent_q.scheduled_at,1,10)=substr(q.scheduled_at,1,10)
                    AND sent_q.state IN ('sent','sending','delivery_unknown')
                    AND lower(COALESCE(NULLIF(sent_l.account_key,''),NULLIF(sent_l.email_domain,''),sent_l.email))
                        = lower(COALESCE(NULLIF(l.account_key,''),NULLIF(l.email_domain,''),l.email))
              )
            ORDER BY q.scheduled_at,q.id LIMIT 1
            """,
            (drip["campaign_id"], today, now.isoformat()),
        ).fetchone()
        if row is None:
            connection.rollback()
            return 0
        if (
            not row["manual_approved"]
            or row["do_not_contact"]
            or row["status"] != "draft_ready"
            or row["smtp_status"] != "deliverable"
            or not row["language_approved"]
            or not row["cohort"]
            or not row["personalization_fact"].strip()
            or not row["evidence_url"].strip()
            or not row["draft_id"]
            or row["draft_context_sha256"] != context_sha256(row)
            or row["draft_policy_sha256"] != policy_sha256(ROOT)
        ):
            connection.execute(
                "UPDATE campaign_queue SET state='blocked',last_error='eligibility_changed',updated_at=? WHERE id=?",
                (now.astimezone(timezone.utc).isoformat(), row["queue_id"]),
            )
            connection.commit()
            return 0
        suppressed = connection.execute(
            "SELECT 1 FROM suppression WHERE lower(email)=lower(?) OR (trim(domain)<>'' AND lower(domain)=lower(?)) OR (trim(operator)<>'' AND lower(operator)=lower(?)) LIMIT 1",
            (row["email"], row["email_domain"], row["operator"]),
        ).fetchone()
        if suppressed:
            connection.execute(
                "UPDATE campaign_queue SET state='blocked',last_error='suppressed',updated_at=? WHERE id=?",
                (now.astimezone(timezone.utc).isoformat(), row["queue_id"]),
            )
            connection.commit()
            return 0
        if args.dry_run:
            connection.rollback()
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "sent": 0,
                        "queue_id": row["queue_id"],
                        "lead_id": row["lead_id"],
                        "scheduled_at": row["scheduled_at"],
                        "variant": row["variant"],
                    }
                )
            )
            return 0
        message_id = make_msgid(domain="adriacare.me")
        claimed = connection.execute(
            """
            UPDATE campaign_queue SET state='sending',attempt_count=attempt_count+1,
                message_id=?,updated_at=? WHERE id=? AND state='scheduled'
            """,
            (message_id, now.astimezone(timezone.utc).isoformat(), row["queue_id"]),
        )
        if claimed.rowcount != 1:
            # Another sender won the claim.  Never continue to SMTP without
            # owning the queue row.
            connection.rollback()
            return 0
        connection.execute(
            "UPDATE daily_batches SET state='sending' WHERE id=? AND state='ready'",
            (row["batch_id"],),
        )
        connection.commit()

        # There is deliberately no static-template fallback.  A message can
        # leave SMTP only as the exact reviewed Codex draft whose source facts
        # and approved campaign policy still match the queue row.
        subject, body = row["draft_subject"], row["draft_body"]
        message = EmailMessage()
        message["From"] = formataddr((config["sender"]["name"], config["sender"]["email"]))
        message["To"] = row["email"]
        message["Subject"] = subject
        message["Date"] = format_datetime(now)
        message["Message-ID"] = message_id
        message.set_content(body)
        occurred_at = now.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        metadata = json.dumps(
            {
                "campaign_id": row["campaign_id"],
                "campaign_queue_id": row["queue_id"],
                "scheduled_at": row["scheduled_at"],
                "variant": row["variant"],
                "codex_draft_review_id": row["draft_id"],
                "local_send_date": now.date().isoformat(),
                "transport": "smtp.beget.com:465",
            },
            ensure_ascii=False,
        )
        with connection:
            connection.execute(
                "INSERT INTO events(lead_id,event_type,occurred_at,message_id,in_reply_to,subject,body_sha256,metadata_json) VALUES(?, 'send_attempt', ?, ?, '', ?, ?, ?)",
                (row["lead_id"], occurred_at, message_id, subject, hashlib.sha256(body.encode()).hexdigest(), metadata),
            )
        smtp_attempt_started = False
        client = connect_smtp()
        try:
            # Once SMTP DATA may have been accepted, a transport exception is
            # ambiguous.  It must never return to an automatically retryable
            # state, even if the exception looks transient.
            smtp_attempt_started = True
            client.send_message(message)
        except Exception:
            # Preserve the DATA-stage exception.  A second disconnect raised
            # by QUIT must not hide the actual point of failure in the log.
            try:
                client.quit()
            except Exception:
                pass
            raise
        else:
            # A successful send_message() already includes the server's final
            # acceptance reply.  Failure of the optional QUIT handshake does
            # not make that accepted message ambiguous.
            try:
                client.quit()
            except Exception:
                pass
        with connection:
            connection.execute(
                "UPDATE campaign_queue SET state='sent',last_error='',updated_at=? WHERE id=?",
                (occurred_at, row["queue_id"]),
            )
            connection.execute(
                "UPDATE leads SET status='sent',updated_at=? WHERE id=?",
                (occurred_at, row["lead_id"]),
            )
            connection.execute(
                "INSERT INTO events(lead_id,event_type,occurred_at,message_id,in_reply_to,subject,body_sha256,metadata_json) VALUES(?, 'sent', ?, ?, '', ?, ?, ?)",
                (row["lead_id"], occurred_at, message_id, subject, hashlib.sha256(body.encode()).hexdigest(), metadata),
            )
            connection.execute(
                """UPDATE daily_batches b SET state='completed'
                   WHERE b.id=? AND b.state='sending'
                     AND (SELECT COUNT(*) FROM campaign_queue q WHERE q.batch_id=b.id AND q.state IN ('sent','delivery_unknown')) >= b.target_count""",
                (row["batch_id"],),
            )
        logging.info("sent queue_id=%s lead_id=%s", row["queue_id"], row["lead_id"])
        print(json.dumps({"sent": 1, "queue_id": row["queue_id"], "lead_id": row["lead_id"]}))
        return 0
    except Exception as exc:
        if row is not None:
            occurred_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            try:
                with connection:
                    outcome = "delivery_unknown" if "smtp_attempt_started" in locals() and smtp_attempt_started else "failed"
                    error_text = f"{outcome}: {type(exc).__name__}: {exc}"[:1000]
                    connection.execute(
                        "UPDATE campaign_queue SET state=?,last_error=?,updated_at=? WHERE id=? AND state='sending'",
                        (outcome, error_text, occurred_at, row["queue_id"]),
                    )
                    connection.execute(
                        "INSERT INTO events(lead_id,event_type,occurred_at,message_id,in_reply_to,subject,body_sha256,metadata_json) VALUES(?, ?, ?, ?, '', '', '', ?)",
                        (row["lead_id"], outcome, occurred_at, message_id, json.dumps({"error_type": type(exc).__name__, "campaign_queue_id": row["queue_id"], "automatic_retry": False})),
                    )
                    if outcome == "delivery_unknown":
                        connection.execute(
                            """UPDATE daily_batches b SET state='completed'
                               WHERE b.id=? AND b.state='sending'
                                 AND (SELECT COUNT(*) FROM campaign_queue q WHERE q.batch_id=b.id AND q.state IN ('sent','delivery_unknown')) >= b.target_count""",
                            (row["batch_id"],),
                        )
            except Exception:
                pass
        logging.exception("send failed")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"sender error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
