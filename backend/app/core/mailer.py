"""Outgoing email over SMTP (standard library only).

Sending runs in a worker thread so it never blocks the event loop. Without SMTP_HOST (development),
messages are written to the log instead, so flows like "forgot password" can still be tried locally.
"""

import asyncio
import logging
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.config import Settings, get_settings
from app.core.exceptions import DomainError

log = logging.getLogger("wcw.mail")


class MailError(DomainError):
    status_code = 503

    def __init__(self, message: str, reason: str | None = None):
        super().__init__(message)
        self.reason = reason  # the mail server's own words: for the admin's test button, never shown to shoppers


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
    reply_to = mail.reply_to or settings.mail_reply_to
    if reply_to:
        msg["Reply-To"] = reply_to
    for name, value in mail.headers:
        msg[name] = value
    msg.set_content(mail.text)
    if mail.html:
        msg.add_alternative(mail.html, subtype="html")
    return msg


# ---- settings made in the admin (Settings → Email config) override the server's own ------------------------

_DEFAULT_PORT = {"ssl": 465, "starttls": 587, "none": 25}
CONFIG_SECONDS = 15.0
_config: tuple[float, Settings] | None = None


def clear_config_cache() -> None:
    global _config
    _config = None


def apply_overrides(base: Settings, stored: dict) -> Settings:
    """The server's mail settings with whatever the owner saved in the admin on top. A saved mail server replaces all
    the server's SMTP fields (so a leftover username cannot be paired with a new host); sender fields override one by one."""
    from app.core import secretbox

    update: dict = {}
    if stored.get("from_address"):
        update["mail_from"] = stored["from_address"]
    if stored.get("from_name"):
        update["mail_from_name"] = stored["from_name"]
    if stored.get("reply_to"):
        update["mail_reply_to"] = stored["reply_to"]
    if stored.get("smtp_host"):
        security = stored.get("smtp_security") or "ssl"
        update.update(
            smtp_host=stored["smtp_host"], smtp_security=security,
            smtp_port=stored.get("smtp_port") or _DEFAULT_PORT[security],
            smtp_user=stored.get("smtp_user"), smtp_password=secretbox.unseal(stored.get("smtp_password_enc")),
        )
    return base.model_copy(update=update)


async def effective_settings() -> Settings:
    """What to send with right now: the server's settings plus the admin's, read from the live data (not the Test copy)
    and remembered for a few seconds so every email doesn't cost a query."""
    global _config
    now = time.monotonic()
    if _config is not None and now - _config[0] < CONFIG_SECONDS:
        return _config[1]
    stored: dict = {}
    try:
        from app.core import appmode
        from app.core.database import SessionFactory
        from app.models.commerce import StoreSetting

        with appmode.use(appmode.LIVE):
            async with SessionFactory() as session:
                row = await session.get(StoreSetting, "email")
        stored = (row.value if row else None) or {}
    except Exception:  # database hiccup or not migrated yet: send with the server's own settings
        log.warning("Couldn't read the email settings; using the server's", exc_info=True)
    effective = apply_overrides(get_settings(), stored)
    _config = (now, effective)
    return effective


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
    s = await effective_settings()
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
        raise MailError("We couldn't send the email right now. Please try again later.", reason=str(exc) or type(exc).__name__) from exc
