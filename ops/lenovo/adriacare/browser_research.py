#!/usr/bin/env python3
"""Browser-only crawler of official sites, with resumable full-site traversal.

This worker never invokes Codex or any other model. It records only published
contact evidence from rendered official pages. It never runs SMTP, sends mail,
approves a draft, or creates a queue row.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import threading
from typing import Any
from urllib.parse import unquote, urlparse


ROOT = Path('/opt/agents/adriacare/app')
PYTHON = '/opt/agents/adriacare-venv/bin/python'
SELECTOR = Path('/opt/agents/adriacare-research-candidates.py')
SNAPSHOT = Path('/opt/agents/adriacare-browser-snapshot.py')
RECORDER = ROOT / 'scripts' / 'record_browser_contact_research.py'
RUNTIME = ROOT / r'C:\AdriaCare'
REPORT = RUNTIME / 'reports' / 'browser-research-latest.json'
STATE = Path('/var/lib/agents/adriacare/browser-crawl-state.json')

EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b")
PROFILE_TERMS = (
    'kurzzeitpflege', 'verhinderungspflege', 'übergangspflege',
    'stationäre pflege', 'vollstationär', 'pflegeheim', 'pflegegrad',
    'pflegebedürftig', 'pflegewohnen', 'pflegewohnbereich',
    'altenhilfezentrum', 'altenpflege', 'seniorenzentrum', 'seniorenheim',
    'tagespflege', 'wohngemeinschaft für menschen mit demenz',
)
ROLE_RANK = (
    'kontakt', 'info', 'einrichtungsleitung', 'heimleitung', 'leitung',
    'verwaltung', 'geschaeftsfuehrung', 'geschäftsführung',
)


def run(command: list[str], *, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def last_json(output: str) -> dict[str, Any]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def same_site(first: str, candidate: str) -> bool:
    root = (urlparse(first).hostname or '').lower().removeprefix('www.')
    host = (urlparse(candidate).hostname or '').lower().removeprefix('www.')
    return bool(root and host and (host == root or host.endswith('.' + root)))


def canonical(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment='').geturl()


def snapshot(url: str) -> dict[str, Any]:
    try:
        result = run([PYTHON, str(SNAPSHOT), url], timeout=70)
    except subprocess.TimeoutExpired:
        return {'url': url, 'error': 'snapshot_timeout'}
    data = last_json(result.stdout)
    if result.returncode or data.get('error'):
        return {'url': url, 'error': data.get('error') or f'browser_exit_{result.returncode}'}
    return data


def page_text(page: dict[str, Any]) -> str:
    return ' '.join([str(page.get('text_start') or ''),
                     *[str(x) for x in page.get('relevant_text') or []]])


def page_emails(page: dict[str, Any]) -> set[str]:
    result = set(EMAIL_RE.findall(page_text(page)))
    for href in page.get('mail_links') or []:
        if href.lower().startswith('mailto:'):
            result.update(EMAIL_RE.findall(unquote(href[7:].split('?', 1)[0])))
    return {email.lower() for email in result}


def choose_email(found: dict[str, str], existing: str) -> str | None:
    existing = existing.strip().lower()
    if existing and existing in found:
        return existing
    if len(found) == 1:
        return next(iter(found))
    ordered = sorted(found)
    for role in ROLE_RANK:
        matches = [email for email in ordered if email.split('@', 1)[0] == role]
        if len(matches) == 1:
            return matches[0]
    return None


def profile_basis(hits: set[str]) -> tuple[bool, str]:
    if not hits:
        return False, 'Browser did not establish an elderly-care or nursing profile on the official pages.'
    return True, 'Official rendered page contains care-profile terms: ' + ', '.join(sorted(hits)[:3]) + '.'


def read_state() -> dict[str, Any]:
    try:
        result = json.loads(STATE.read_text(encoding='utf-8'))
        return result if isinstance(result, dict) else {'leads': {}}
    except (OSError, ValueError):
        return {'leads': {}}


def write_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(STATE)


def new_crawl(start: str) -> dict[str, Any]:
    return {'website': canonical(start), 'pending': [canonical(start)], 'seen': [],
            'emails': {}, 'profile_terms': [], 'failures': {},
            'started_at': datetime.now(timezone.utc).isoformat(), 'state': 'active'}


def record(lead: dict[str, Any], decision: str, status: str, basis: str, evidence: str,
           email: str | None, detail: str, dry_run: bool) -> tuple[bool, str]:
    command = [PYTHON, str(RECORDER), '--lead-id', str(lead['id']), '--decision', decision,
               '--profile-status', status, '--profile-basis', basis, '--evidence-url', evidence,
               '--detail', detail[:900]]
    if email:
        command.extend(['--email', email])
    if dry_run:
        return True, 'dry_run'
    result = run(command, timeout=20)
    return result.returncode == 0, (result.stderr or result.stdout)[-500:]


def advance_crawl(lead: dict[str, Any], crawl: dict[str, Any], *, pages_per_run: int,
                  total_page_limit: int, checkpoint) -> tuple[dict[str, Any], bool]:
    """Open every discovered first-party page; return (crawl, reached_limit)."""
    opened = 0
    seen = set(crawl.get('seen') or [])
    pending = list(crawl.get('pending') or [])
    failures = dict(crawl.get('failures') or {})
    emails = OrderedDict((str(email).lower(), str(url)) for email, url in
                         dict(crawl.get('emails') or {}).items())
    terms = set(str(term) for term in crawl.get('profile_terms') or [])
    def save_progress() -> None:
        crawl.update({'pending': pending, 'seen': sorted(seen), 'emails': dict(emails),
                      'profile_terms': sorted(terms), 'failures': failures,
                      'last_updated_at': datetime.now(timezone.utc).isoformat()})
        checkpoint(crawl)

    while pending and opened < pages_per_run and len(seen) < total_page_limit:
        url = canonical(str(pending.pop(0)))
        if url in seen:
            continue
        seen.add(url)
        page = snapshot(url)
        opened += 1
        if page.get('error'):
            failures[url] = str(page['error'])
            save_progress()
            continue
        text = page_text(page).lower()
        terms.update(term for term in PROFILE_TERMS if term in text)
        source = str(page.get('url') or url)
        for email in sorted(page_emails(page)):
            emails.setdefault(email, source)
        for link in page.get('site_links') or []:
            link = canonical(str(link))
            if same_site(str(lead['website']), link) and link not in seen and link not in pending:
                pending.append(link)
        save_progress()
    save_progress()
    return crawl, bool(pending and len(seen) >= total_page_limit)



def is_dead_domain(failures: dict[str, str]) -> bool:
    """True when Chrome never started: the host does not resolve or is not IDNA safe."""
    return bool(failures) and all(kind == 'browser_exit_1' for kind in failures.values())

def finalise(lead: dict[str, Any], crawl: dict[str, Any], *, dry_run: bool,
             page_budget_reached: bool = False) -> dict[str, Any]:
    found = OrderedDict((str(email), str(url)) for email, url in dict(crawl.get('emails') or {}).items())
    suitable, basis = profile_basis(set(crawl.get('profile_terms') or []))
    selected = choose_email(found, str(lead.get('email') or '')) if suitable else None
    evidence = found.get(selected) or str(lead['website'])
    failures = dict(crawl.get('failures') or {})
    kinds = ', '.join(f'{kind}: {count}' for kind, count in sorted(
        ((kind, list(failures.values()).count(kind)) for kind in set(failures.values())),
        key=lambda item: item[0]))
    if selected:
        # Owner decision (2026-09-18): an address published on a successfully
        # opened official page is accepted even when other pages of the same
        # site could not be opened.  A failed page no longer invalidates the
        # whole site.
        decision, status = 'official_email_found', 'suitable'
        scope = ('the priority research budget' if page_budget_reached else 'the full discovered official site graph')
        detail = (f"Chrome traversed {scope}: {len(crawl.get('seen') or [])} page(s). "
                  f"Published address selected from {evidence}.")
        if failures:
            detail += (f" {len(failures)} page(s) could not be opened ({kinds}); "
                       'the address is accepted from a successfully opened official page.')
    elif failures and is_dead_domain(failures):
        # ``browser_exit_1`` means Chrome never started: the helper refused the
        # target, typically because the host does not resolve or is not IDNA
        # safe.  That is a final result, not a temporary network failure, and
        # retrying such a domain forever only wastes the research queue.
        decision, status = 'no_published_email', 'rejected'
        detail = (f"Domain is not reachable ({kinds}); Chrome never started, so the site is "
                  'classified as address-less and removed from the research queue.')
    elif failures:
        decision, status = 'network_error', 'unclear'
        detail = (f"Browser could not open {len(failures)} of {len(crawl.get('seen') or [])} discovered official pages "
                  f"({kinds}); no contact conclusion is recorded and the site must be retried.")
    elif page_budget_reached and not selected:
        # A bounded crawl is not proof that a site has no address.  Keep this
        # lead eligible for its normal retry policy instead of silently letting
        # a large sitemap monopolise the entire research queue.
        decision, status = 'network_error', 'unclear'
        detail = (f"Browser reached the {len(crawl.get('seen') or [])}-page research budget without a safe "
                  'published contact; the site must be retried rather than classified as address-less.')
    elif suitable:
        decision, status = 'no_published_email', 'suitable'
        detail = (f"Chrome traversed the full discovered official site graph: {len(crawl.get('seen') or [])} page(s). "
                  f"No single safe general contact selected from {len(found)} published address(es).")
    else:
        decision, status = 'no_published_email', 'unclear'
        detail = (f"Chrome traversed the full discovered official site graph: {len(crawl.get('seen') or [])} page(s). "
                  'Profile remains unclear.')
    # The recorder deliberately refuses an email attached to an inconclusive
    # result.  In particular, a partial network failure must never turn an
    # unverified address into a usable contact.
    recordable_email = selected if decision == 'official_email_found' else None
    ok, note = record(lead, decision, status, basis, evidence, recordable_email, detail, dry_run)
    return {'id': lead['id'], 'name': lead['name'], 'state': 'complete', 'decision': decision,
            'profile_status': status, 'email': selected, 'pages': len(crawl.get('seen') or []),
            'failed_pages': len(failures), 'published_email_count': len(found),
            'recorded': ok, 'detail': note}


def review(lead: dict[str, Any], all_state: dict[str, Any], *, dry_run: bool,
           pages_per_run: int, total_page_limit: int, state_lock: threading.Lock) -> dict[str, Any]:
    leads = all_state.setdefault('leads', {})
    key = str(lead['id'])
    crawl = leads.get(key)
    if not isinstance(crawl, dict) or crawl.get('website') != canonical(str(lead['website'])):
        crawl = new_crawl(str(lead['website']))
    if crawl.get('state') == 'blocked':
        return {'id': lead['id'], 'name': lead['name'], 'state': 'blocked',
                'reason': 'crawl_page_limit_exceeded', 'pages': len(crawl.get('seen') or [])}
    leads[key] = crawl

    def checkpoint(updated: dict[str, Any]) -> None:
        # Each lead owns its crawl object, but all checkpoints share one
        # durable JSON file.  Serialising the write prevents concurrent
        # workers from dropping each other's progress.
        with state_lock:
            leads[key] = updated
            if not dry_run:
                write_state(all_state)
                write_report({'checked_at': datetime.now(timezone.utc).isoformat(), 'worker': 'browser_only',
                              'model_calls': 0, 'smtp_calls': 0, 'selected': 1,
                              'outcomes': [{'id': lead['id'], 'name': lead['name'], 'state': 'in_progress',
                                            'pages': len(updated.get('seen') or []),
                                            'remaining_urls': len(updated.get('pending') or [])}],
                              'in_progress': 1, 'recorded': 0, 'official_email_found': 0,
                              'blocked_crawls': 0})

    crawl, reached_limit = advance_crawl(lead, crawl, pages_per_run=pages_per_run,
                                         total_page_limit=total_page_limit, checkpoint=checkpoint)
    if reached_limit:
        result = finalise(lead, crawl, dry_run=dry_run, page_budget_reached=True)
        leads.pop(key, None)
        return result
    if crawl.get('pending'):
        leads[key] = crawl
        return {'id': lead['id'], 'name': lead['name'], 'state': 'in_progress',
                'pages': len(crawl.get('seen') or []), 'remaining_urls': len(crawl['pending']),
                'recorded': False}
    result = finalise(lead, crawl, dry_run=dry_run)
    leads.pop(key, None)
    return result


def write_report(report: dict[str, Any]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(REPORT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--workers', type=int, default=4,
                        help='simultaneous Chrome processes within the selected batch')
    parser.add_argument('--pages-per-run', type=int, default=10)
    parser.add_argument('--total-page-limit', type=int, default=500)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 10:
        raise SystemExit('batch size must be 1..10')
    if not 1 <= args.workers <= args.batch_size:
        raise SystemExit('workers must be between 1 and batch-size')
    if not 1 <= args.pages_per_run <= 100:
        raise SystemExit('pages per run must be 1..100')
    if not args.pages_per_run <= args.total_page_limit <= 1_000:
        raise SystemExit('total page limit must be between pages-per-run and 1000')
    selection = run([PYTHON, str(SELECTOR), '--limit', '50'], timeout=30)
    data = last_json(selection.stdout)
    if selection.returncode or not isinstance(data.get('items'), list):
        raise SystemExit('candidate selector failed')
    all_state = read_state()
    blocked = {key for key, value in all_state.get('leads', {}).items()
               if isinstance(value, dict) and value.get('state') == 'blocked'}
    rows = [row for row in data['items'] if str(row['id']) not in blocked][:args.batch_size]
    state_lock = threading.Lock()
    def inspect(row: dict[str, Any]) -> dict[str, Any]:
        return review(row, all_state, dry_run=args.dry_run, pages_per_run=args.pages_per_run,
                      total_page_limit=args.total_page_limit, state_lock=state_lock)
    if rows:
        with ThreadPoolExecutor(max_workers=min(len(rows), args.workers)) as pool:
            outcomes = list(pool.map(inspect, rows))
    else:
        outcomes = []
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'worker': 'browser_only',
              'model_calls': 0, 'smtp_calls': 0, 'dry_run': args.dry_run,
              'selected': len(rows), 'parallel_workers': min(len(rows), args.workers), 'outcomes': outcomes,
              'recorded': sum(bool(row.get('recorded')) for row in outcomes),
              'official_email_found': sum(row.get('decision') == 'official_email_found' for row in outcomes),
              'in_progress': sum(row.get('state') == 'in_progress' for row in outcomes),
              'blocked_crawls': sum(row.get('state') == 'blocked' for row in outcomes),
              'blocked_total': len(blocked)}
    if not args.dry_run:
        write_state(all_state)
        write_report(report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
