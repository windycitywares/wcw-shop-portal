"""Email campaigns to people who agreed to hear from us.

Safety rules that are built in rather than left to the person sending:
- only addresses on the marketing list receive a campaign (never people who only get order or reminder emails),
- everyone who unsubscribed is left out, and every email carries an unsubscribe link,
- a campaign can be sent once; two people clicking "Send" at the same moment cannot double-send it,
- one send is capped (MAX_RECIPIENTS), so a slip can't email the whole list by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.domain import emailtext
from app.models.commerce import Coupon
from app.models.engagement import Campaign
from app.models.user import User
from app.schemas.campaigns import SEGMENT_LABELS, AudienceOut, CampaignIn, CampaignListOut, CampaignOut, SegmentChoice
from app.services import audit, emails
from app.services.auth import SERVICE_ONLY_SOURCES
from app.services.customers import CustomerService
from app.services.promotions import issue_coupon

MAX_RECIPIENTS = 3000
INLINE_SEND = 20  # the rest is delivered by the scheduled job

SUBSCRIBERS_SQL = text("""
SELECT email, locale, unsubscribe_token FROM newsletter_subscribers
WHERE unsubscribed_at IS NULL AND source <> ALL(CAST(:service_only AS text[]))
ORDER BY id
""")

STATS_SQL = text("""
SELECT count(*)::int AS issued, COALESCE(sum(c.used_count), 0)::int AS redeemed,
       COALESCE((SELECT sum(o.grand_total - o.refunded_total) FROM orders o
                 WHERE o.coupon_code IN (SELECT code FROM coupons WHERE campaign = :tag)
                   AND o.paid_at IS NOT NULL AND o.status NOT IN ('cancelled', 'refunded')), 0) AS revenue
FROM coupons c WHERE c.campaign = :tag
""")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def tag(campaign_id: int) -> str:
    return f"campaign-{campaign_id}"


@dataclass(frozen=True)
class Recipient:
    email: str
    locale: str
    token: str


class CampaignService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- audience -----------------------------------------------------------------------
    async def audience(self, segment: str) -> list[Recipient]:
        rows = (await self.session.execute(SUBSCRIBERS_SQL, {"service_only": list(SERVICE_ONLY_SOURCES)})).mappings().all()
        people = [Recipient(r["email"], emailtext.loc(r["locale"]), r["unsubscribe_token"]) for r in rows]
        if segment == "subscribers":
            return people
        customers = {c.email: c.segment for c in await CustomerService(self.session).everyone()}
        if segment == "prospects":
            return [p for p in people if p.email not in customers]
        if segment == "customers":
            return [p for p in people if p.email in customers]
        return [p for p in people if customers.get(p.email) == segment]

    async def audience_size(self, segment: str) -> AudienceOut:
        if segment not in SEGMENT_LABELS:
            raise ValidationFailedError("Unknown audience")
        return AudienceOut(segment=segment, label=SEGMENT_LABELS[segment], count=len(await self.audience(segment)))

    # ---- CRUD -----------------------------------------------------------------------------
    async def _get(self, campaign_id: int) -> Campaign:
        campaign = await self.session.get(Campaign, campaign_id)
        if campaign is None:
            raise NotFoundError("Campaign not found")
        return campaign

    async def out(self, campaign: Campaign) -> CampaignOut:
        out = CampaignOut.model_validate(campaign)
        if campaign.status == "sent" and campaign.coupon_kind:
            row = (await self.session.execute(STATS_SQL, {"tag": tag(campaign.id)})).mappings().one()
            out.coupons_issued, out.coupons_redeemed, out.revenue = row["issued"], row["redeemed"], Decimal(row["revenue"])
        return out

    async def list(self) -> CampaignListOut:
        rows = (await self.session.execute(select(Campaign).order_by(Campaign.id.desc()).limit(200))).scalars().all()
        return CampaignListOut(
            items=[await self.out(c) for c in rows], segments=[SegmentChoice(key=k, label=v) for k, v in SEGMENT_LABELS.items()]
        )

    def _apply(self, campaign: Campaign, data: CampaignIn) -> None:
        campaign.name, campaign.subject, campaign.body = data.name, data.subject, data.body
        campaign.translations = {k: v.model_dump() for k, v in data.translations.items()}
        campaign.segment = data.segment
        campaign.coupon_kind, campaign.coupon_value = data.coupon_kind, data.coupon_value
        campaign.coupon_expires_days, campaign.coupon_min_subtotal = data.coupon_expires_days, data.coupon_min_subtotal

    async def create(self, data: CampaignIn, user: User) -> CampaignOut:
        campaign = Campaign(created_by_id=user.id, status="draft", recipients=0)
        self._apply(campaign, data)
        self.session.add(campaign)
        await self.session.flush()
        audit.record(self.session, user, "campaign.create", "campaign", campaign.id, f"Created campaign “{campaign.name}”")
        await self.session.commit()
        await self.session.refresh(campaign)
        return await self.out(campaign)

    async def update(self, campaign_id: int, data: CampaignIn, user: User) -> CampaignOut:
        campaign = await self._get(campaign_id)
        if campaign.status != "draft":
            raise ConflictError("A campaign that was sent can't be edited. Duplicate it instead.")
        self._apply(campaign, data)
        audit.record(self.session, user, "campaign.update", "campaign", campaign.id, f"Changed campaign “{campaign.name}”")
        await self.session.commit()
        await self.session.refresh(campaign)
        return await self.out(campaign)

    async def delete(self, campaign_id: int, user: User) -> None:
        campaign = await self._get(campaign_id)
        if campaign.status != "draft":
            raise ConflictError("A campaign that was sent is kept for your records.")
        audit.record(self.session, user, "campaign.delete", "campaign", campaign.id, f"Deleted campaign “{campaign.name}”")
        await self.session.delete(campaign)
        await self.session.commit()

    # ---- sending ----------------------------------------------------------------------------
    def _text_for(self, campaign: Campaign, locale: str) -> tuple[str, str]:
        t = (campaign.translations or {}).get(locale) or {}
        return (t.get("subject") or campaign.subject, t.get("body") or campaign.body)

    def _context(self, campaign: Campaign, recipient: Recipient, code: str | None, expires: datetime | None) -> dict:
        subject, body = self._text_for(campaign, recipient.locale)
        link = emails.site_link("/shop", recipient.locale)
        ctx = {
            "name": None, "subject": subject, "body": body,
            "shop_url": f"{link}?utm_source=email&utm_medium=email&utm_campaign={tag(campaign.id)}",
            "unsubscribe_url": emails.unsubscribe_url(recipient.token, recipient.locale),
        }
        if code:
            ctx.update(code=code, expires=emailtext.long_date(expires, recipient.locale) if expires else None)
        return ctx

    async def send_test(self, campaign_id: int, user: User) -> None:
        campaign = await self._get(campaign_id)
        recipient = Recipient(user.email.lower(), "en", "sample-token-not-a-real-link")
        code = "SAMPLE-CODE" if campaign.coupon_kind else None
        ctx = self._context(campaign, recipient, code, None)
        ctx["subject"] = f"[Test] {ctx['subject']}"
        row = emails.enqueue(self.session, "campaign", recipient.email, ctx, locale="en", related_type="campaign", related_id=campaign.id)
        await self.session.commit()
        await emails.deliver(self.session, [row])

    async def send(self, campaign_id: int, user: User) -> CampaignOut:
        # The row lock makes a second click (or a second tab) wait here and then find the campaign already sent.
        campaign = (await self.session.execute(select(Campaign).where(Campaign.id == campaign_id).with_for_update())).scalar_one_or_none()
        if campaign is None:
            raise NotFoundError("Campaign not found")
        if campaign.status != "draft":
            await self.session.rollback()
            raise ConflictError("This campaign has already been sent.")
        people = await self.audience(campaign.segment)
        if not people:
            await self.session.rollback()
            raise ValidationFailedError("Nobody is in that audience yet, so there is nothing to send.")
        if len(people) > MAX_RECIPIENTS:
            await self.session.rollback()
            raise ValidationFailedError(f"That audience has {len(people)} people. Choose a smaller segment (the limit is {MAX_RECIPIENTS} per campaign).")
        queued = []
        for person in people:
            code = expires = None
            if campaign.coupon_kind:
                coupon: Coupon = await issue_coupon(
                    self.session, email=person.email, kind=campaign.coupon_kind, value=campaign.coupon_value or Decimal("0"),
                    expires_days=campaign.coupon_expires_days, source="campaign", prefix="THANKS", campaign=tag(campaign.id),
                    min_subtotal=campaign.coupon_min_subtotal or Decimal("0"), name=campaign.name,
                )
                code, expires = coupon.code, coupon.expires_at
            queued.append(emails.enqueue(
                self.session, "campaign", person.email, self._context(campaign, person, code, expires), locale=person.locale,
                related_type="campaign", related_id=campaign.id,
            ))
        campaign.status, campaign.recipients, campaign.sent_at = "sent", len(people), utcnow()
        audit.record(self.session, user, "campaign.send", "campaign", campaign.id, f"Sent campaign “{campaign.name}” to {len(people)} people")
        await self.session.commit()
        await emails.deliver(self.session, queued[:INLINE_SEND])
        await self.session.refresh(campaign)
        return await self.out(campaign)

