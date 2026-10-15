"""Outgoing email over SMTP (standard library only).

Sending runs in a worker thread so it never blocks the event loop. Without SMTP_HOST (development),
messages are written to the log instead, so flows like "forgot password" can still be tried locally.
"""

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.config import Settings, get_settings
from app.core.exceptions import DomainError

log = logging.getLogger("wcw.mail")


class MailError(DomainError):
    status_code = 503


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None
    reply_to: str | None = None
    headers: tuple[tuple[str, str], ...] = ()  # extra headers such as List-Unsubscribe


def build_message(mail: Mail, settings: Settings) -> EmailMessage:
    """EmailMessage rejects CR/LF in headers, which blocks header injection via user input."""
    msg = EmailMessage()
    msg["From"] = formataddr((settings.mail_from_name, settings.mail_from))
    msg["To"] = mail.to
    msg["Subject"] = mail.subject
    msg["Message-ID"] = make_msgid(domain=settings.mail_from.split("@")[-1])
    if mail.reply_to:
        msg["Reply-To"] = mail.reply_to
    for name, value in mail.headers:
        msg[name] = value
    msg.set_content(mail.text)
    if mail.html:
        msg.add_alternative(mail.html, subtype="html")
    return msg


def _send_sync(msg: EmailMessage, s: Settings) -> None:
    timeout = 20
    if s.smtp_security == "ssl":
        server: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=timeout,
                                                context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=timeout)
    with server:
        if s.smtp_security == "starttls":
            server.starttls(context=ssl.create_default_context())
        if s.smtp_user and s.smtp_password:
            server.login(s.smtp_user, s.smtp_password)
        server.send_message(msg)


def _for_test_mode(mail: Mail) -> Mail | None:
    """In Test mode the data is a copy of the live shop, with real customers' addresses in it. Nothing may reach
    them: every email goes to the test inbox set in Admin → Test mode (or nowhere when none is set)."""
    from dataclasses import replace
    from html import escape

    from app.core import appmode

    state = appmode.current()
    if not state.is_test:
        return mail
    if not state.test_mail_to:
        log.warning("Test mode: email to %s (%s) not sent (no test inbox set)", mail.to, mail.subject)
        return None
    note = f"Test mode: this email was addressed to {mail.to}."
    return replace(
        mail, to=state.test_mail_to, subject=f"[TEST] {mail.subject}", text=f"{note}\n\n{mail.text}",
        html=f'<p style="background:#fff3cd;padding:8px;font-family:sans-serif">{escape(note)}</p>{mail.html}' if mail.html else None,
        headers=tuple(h for h in mail.headers if h[0].lower() != "list-unsubscribe"),
    )


async def send(mail: Mail) -> None:
    """Every email the app sends goes through here: Test-mode redirection first, then delivery."""
    redirected = _for_test_mode(mail)
    if redirected is None:
        return
    await deliver(redirected)


async def deliver(mail: Mail) -> None:
    """Hand one email to the SMTP server (tests replace this, so they see exactly what would go out)."""
    s = get_settings()
    msg = build_message(mail, s)
    if not s.smtp_host:
        if s.is_production:  # never write reset links etc. to production logs
            log.error("SMTP not configured — email to %s (%s) was not sent", mail.to, mail.subject)
            raise MailError("Email isn't available right now. Please try again later.")
        log.warning("SMTP not configured — email not sent.\nTo: %s\nSubject: %s\n\n%s", mail.to, mail.subject, mail.text)
        return
    try:
        await asyncio.to_thread(_send_sync, msg, s)
    except (OSError, smtplib.SMTPException) as exc:
        log.exception("Sending email to %s failed", mail.to)
        raise MailError("We couldn't send the email right now. Please try again later.") from exc
