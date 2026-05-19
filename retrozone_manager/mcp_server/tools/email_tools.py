"""Email MCP tools — IMAP read (inbox, search) + SMTP draft (no auto-send)."""
import imaplib
import email
from email.header import decode_header
import json
from datetime import datetime
from ..db.schema import get_conn


def _get_imap_config():
    """Get IMAP config from the main app settings."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))
    from retrozone_manager import config
    settings = config.load_settings()
    return {
        "host": settings.get("imap_host", ""),
        "port": int(settings.get("imap_port", 993)),
        "user": settings.get("imap_user", ""),
        "password": settings.get("imap_password", ""),
    }


def _decode_str(s):
    """Decode email header string."""
    if s is None:
        return ""
    decoded = decode_header(s)
    parts = []
    for part, charset in decoded:
        if isinstance(part, bytes):
            parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return "".join(parts)


def _imap_connect():
    """Connect and authenticate to IMAP server. Returns imaplib.IMAP4_SSL or raises."""
    cfg = _get_imap_config()
    if not cfg["host"] or not cfg["user"]:
        raise ValueError("IMAP not configured. Set imap_host, imap_user, imap_password in Settings.")
    mail = imaplib.IMAP4_SSL(cfg["host"], cfg["port"])
    mail.login(cfg["user"], cfg["password"])
    return mail


def check_inbox(folder: str = "INBOX", limit: int = 10, unread_only: bool = False) -> str:
    """Check email inbox. READ-ONLY — safe, no side effects.

    Returns recent emails with subject, sender, date.
    Set unread_only=True to see only unread messages.
    """
    try:
        mail = _imap_connect()
    except Exception as e:
        return f"Email not configured or connection failed: {e}\nSet IMAP settings in the Settings panel first."

    try:
        mail.select(folder, readonly=True)
        search_crit = "UNSEEN" if unread_only else "ALL"
        _, msg_ids = mail.search(None, search_crit)
        ids = msg_ids[0].split()

        if not ids:
            return f"No{' unread' if unread_only else ''} emails in {folder}."

        # Get latest N (reverse order)
        ids = ids[-limit:][::-1]
        emails = []

        for mid in ids:
            _, msg_data = mail.fetch(mid, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    subject = _decode_str(msg.get("Subject", ""))
                    from_addr = _decode_str(msg.get("From", ""))
                    date = msg.get("Date", "")
                    emails.append({
                        "uid": mid.decode(),
                        "subject": subject,
                        "from": from_addr,
                        "date": date,
                    })

        lines = [f"Inbox ({folder}) — {len(emails)} recent{' (unread only)' if unread_only else ''}:\n"]
        for i, e in enumerate(emails, 1):
            lines.append(
                f"{i}. {e['subject']}\n"
                f"   From: {e['from']} | Date: {e['date']}\n"
                f"   UID: {e['uid']}"
            )

        return "\n\n".join(lines)
    except Exception as e:
        return f"Error reading inbox: {e}"
    finally:
        mail.logout()


def get_email(uid: str, folder: str = "INBOX") -> str:
    """Get full email body by UID. READ-ONLY.

    Use this to read the full content of a specific email from check_inbox results.
    """
    try:
        mail = _imap_connect()
    except Exception as e:
        return f"Email connection failed: {e}"

    try:
        mail.select(folder, readonly=True)
        _, msg_data = mail.fetch(uid.encode(), "(RFC822)")
        for part in msg_data:
            if isinstance(part, tuple):
                msg = email.message_from_bytes(part[1])
                subject = _decode_str(msg.get("Subject", ""))
                from_addr = _decode_str(msg.get("From", ""))
                to_addr = _decode_str(msg.get("To", ""))
                date = msg.get("Date", "")

                body = ""
                if msg.is_multipart():
                    for mp in msg.walk():
                        ct = mp.get_content_type()
                        if ct == "text/plain":
                            payload = mp.get_payload(decode=True)
                            charset = mp.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="replace")
                            break
                    if not body:
                        for mp in msg.walk():
                            if mp.get_content_type() == "text/html":
                                payload = mp.get_payload(decode=True)
                                charset = mp.get_content_charset() or "utf-8"
                                body = payload.decode(charset, errors="replace")[:2000]
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        charset = msg.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")

                return (
                    f"Subject: {subject}\n"
                    f"From: {from_addr}\n"
                    f"To: {to_addr}\n"
                    f"Date: {date}\n"
                    f"\n{body[:5000]}"
                )

        return f"Email UID {uid} not found."
    except Exception as e:
        return f"Error reading email: {e}"
    finally:
        mail.logout()


def search_emails(query: str, folder: str = "INBOX") -> str:
    """Search emails by subject or sender. READ-ONLY.

    Searches using IMAP SEARCH command.
    """
    try:
        mail = _imap_connect()
    except Exception as e:
        return f"Email connection failed: {e}"

    try:
        mail.select(folder, readonly=True)
        _, msg_ids = mail.search(None, f'OR SUBJECT "{query}" FROM "{query}"')
        ids = msg_ids[0].split()

        if not ids:
            return f"No emails matching '{query}' in {folder}."

        ids = ids[-15:][::-1]
        results = []

        for mid in ids:
            _, msg_data = mail.fetch(mid, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    results.append({
                        "uid": mid.decode(),
                        "subject": _decode_str(msg.get("Subject", "")),
                        "from": _decode_str(msg.get("From", "")),
                        "date": msg.get("Date", ""),
                    })

        lines = [f"Search results for '{query}' ({len(results)}):\n"]
        for i, e in enumerate(results, 1):
            lines.append(
                f"{i}. {e['subject']}\n"
                f"   From: {e['from']} | Date: {e['date']}\n"
                f"   UID: {e['uid']}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error searching emails: {e}"
    finally:
        mail.logout()


def draft_email(to: str, subject: str, body: str) -> str:
    """Create an email draft. Does NOT send — saves to email_drafts table for approval.

    The draft will appear in the UI for review before sending.
    Returns the draft ID for tracking.
    """
    conn = get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO email_drafts (to_addr, subject, body, status) VALUES (?, ?, ?, 'draft')",
            (to, subject, body)
        )
        conn.commit()
        draft_id = cursor.lastrowid
        return (
            f"Email draft saved: #{draft_id}\n"
            f"To: {to}\n"
            f"Subject: {subject}\n"
            f"Body preview: {body[:200]}{'...' if len(body) > 200 else ''}\n"
            f"Status: draft (awaiting approval to send)"
        )
    except Exception as e:
        return f"Error creating draft: {e}"
    finally:
        conn.close()
