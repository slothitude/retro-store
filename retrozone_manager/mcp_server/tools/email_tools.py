"""Email MCP tools — IMAP read (inbox, search) + SMTP draft/send."""
import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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


def send_draft(draft_id: int) -> str:
    """Send a saved email draft via SMTP.

    Loads draft from email_drafts table, sends via SMTP using settings,
    and updates draft status to 'sent'.
    Returns success/error message.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    from retrozone_manager import config

    settings = config.load_settings()
    smtp_host = settings.get("smtp_host", "")
    smtp_port = int(settings.get("smtp_port", 587))
    smtp_user = settings.get("smtp_user", "")
    smtp_pass = settings.get("smtp_password", "")

    if not smtp_host:
        return "Error: SMTP not configured. Set smtp_host, smtp_user, smtp_password in Settings."

    conn = get_conn()
    try:
        draft = conn.execute("SELECT * FROM email_drafts WHERE id = ?", (draft_id,)).fetchone()
        if not draft:
            return f"Error: Draft #{draft_id} not found."
        if draft["status"] != "draft":
            return f"Error: Draft #{draft_id} is '{draft['status']}', not 'draft'."

        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = draft["to_addr"]
        msg["Subject"] = draft["subject"]
        msg.attach(MIMEText(draft["body"], "plain"))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()

        try:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()

            conn.execute(
                "UPDATE email_drafts SET status = 'sent', sent_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), draft_id)
            )
            conn.commit()
            return f"Email sent to {draft['to_addr']} — Subject: {draft['subject']}"
        except Exception as e:
            return f"Error sending email: {e}"
    except Exception as e:
        return f"Error: {e}"
    finally:
        conn.close()
