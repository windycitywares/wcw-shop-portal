"""The one connection to the Etsy shop: credentials, "Allow access", token refresh, disconnect."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secretbox
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.domain import etsy_oauth as oauth
from app.models.etsy import EtsyConnection
from app.models.user import User
from app.services import audit, etsy_client
from app.services.etsy_client import EtsyError

OAUTH_VALID_FOR = timedelta(minutes=15)


class EtsyConnectionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def row(self) -> EtsyConnection:
        row = (await self.session.execute(select(EtsyConnection).where(EtsyConnection.id == 1))).scalar_one_or_none()
        if row is None:
            row = EtsyConnection(id=1)
            self.session.add(row)
            await self.session.flush()
        return row

    async def status(self) -> dict[str, Any]:
        row = await self.row()
        return {
            "client_id": row.client_id,
            "secret_set": bool(secretbox.unseal(row.client_secret_enc)),
            "connected": bool(row.access_token and row.refresh_token),
            "shop_name": row.shop_name, "etsy_shop_id": row.etsy_shop_id, "connected_at": row.connected_at,
            "listings_synced_at": row.listings_synced_at, "orders_synced_at": row.orders_synced_at,
            "last_error": row.last_error, "last_error_at": row.last_error_at,
            "redirect_uri": get_settings().etsy_redirect_uri, "scopes": row.scopes,
        }

    async def save_credentials(self, actor: User, client_id: str | None, client_secret: str | None) -> None:
        row = await self.row()
        if client_id is not None:
            client_id = client_id.strip()
            if not client_id or len(client_id) > 100 or " " in client_id:
                raise ValidationFailedError("client_id: that doesn't look like an Etsy keystring")
            row.client_id = client_id
        if client_secret:
            if len(client_secret) > 200:
                raise ValidationFailedError("client_secret: too long")
            row.client_secret_enc = secretbox.seal(client_secret.strip())
        audit.record(self.session, actor, "etsy.credentials", "etsy_connection", 1, "Etsy app credentials changed")
        await self.session.commit()

    async def start(self, actor: User) -> str:
        row = await self.row()
        if not row.client_id:
            raise ValidationFailedError("Save the Etsy keystring first")
        verifier, state = oauth.new_verifier(), oauth.new_state()
        row.oauth_state = f"{state}|{datetime.now(timezone.utc).isoformat()}|{actor.id}"
        row.oauth_verifier = secretbox.seal(verifier)
        await self.session.commit()
        return oauth.authorize_url(client_id=row.client_id, redirect_uri=get_settings().etsy_redirect_uri, state=state, verifier=verifier)

    async def finish(self, state: str, code: str) -> str:
        """The browser came back from Etsy. Returns the connected shop's name; raises EtsyError / ValidationFailedError."""
        row = await self.row()
        stored = (row.oauth_state or "").split("|")
        if len(stored) != 3 or stored[0] != state:
            raise ValidationFailedError("This connection attempt is not recognised. Start again from Settings → External shops.")
        if datetime.now(timezone.utc) - datetime.fromisoformat(stored[1]) > OAUTH_VALID_FOR:
            raise ValidationFailedError("This connection attempt expired. Start again from Settings → External shops.")
        verifier = secretbox.unseal(row.oauth_verifier)
        if not row.client_id or not verifier:
            raise ValidationFailedError("The connection attempt could not be completed. Start again.")
        row.oauth_state = row.oauth_verifier = None  # one use
        tokens = await etsy_client.exchange_code(
            client_id=row.client_id, redirect_uri=get_settings().etsy_redirect_uri, code=code, verifier=verifier)
        access = tokens["access_token"]
        user_id = oauth.user_id_from_token(access)
        if user_id is None:
            raise EtsyError("Etsy's answer did not identify the account")
        key = etsy_client.api_key(row.client_id, secretbox.unseal(row.client_secret_enc))
        shops = await etsy_client.get(f"/users/{user_id}/shops", api_key=key, access_token=access)
        shop = shops if "shop_id" in shops else (shops.get("results") or [None])[0]
        if not shop:
            raise EtsyError("That Etsy account has no shop")
        self._store_tokens(row, tokens)
        row.etsy_shop_id, row.shop_name = shop["shop_id"], shop.get("shop_name")
        row.scopes = tokens.get("scope") or " ".join(oauth.SCOPES)
        row.connected_at, row.connected_by_id = datetime.now(timezone.utc), int(stored[2])
        row.last_error = row.last_error_at = None
        audit.record(self.session, None, "etsy.connect", "etsy_connection", 1, f"Connected Etsy shop {row.shop_name}")
        await self.session.commit()
        return row.shop_name or "your shop"

    @staticmethod
    def _store_tokens(row: EtsyConnection, tokens: dict[str, Any]) -> None:
        row.access_token = secretbox.seal(tokens["access_token"])
        row.refresh_token = secretbox.seal(tokens["refresh_token"])
        row.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600)))

    async def access_token(self) -> tuple[str, str]:
        """(the x-api-key value, a valid access token), refreshing it when it is about to expire. Records the failure when it can't."""
        row = await self.row()
        if not (row.client_id and row.access_token and row.refresh_token):
            raise EtsyError("Etsy is not connected")
        if row.token_expires_at and row.token_expires_at - datetime.now(timezone.utc) < timedelta(minutes=5):
            try:
                tokens = await etsy_client.refresh(client_id=row.client_id, refresh_token=secretbox.unseal(row.refresh_token) or "")
            except EtsyError as exc:
                await self.fail(str(exc))
                raise
            self._store_tokens(row, tokens)
            await self.session.commit()
        token = secretbox.unseal(row.access_token)
        if not token:
            raise EtsyError("The stored Etsy access can't be read. Reconnect Etsy in Settings.")
        return etsy_client.api_key(row.client_id, secretbox.unseal(row.client_secret_enc)), token

    async def fail(self, message: str) -> None:
        row = await self.row()
        row.last_error, row.last_error_at = message[:500], datetime.now(timezone.utc)
        await self.session.commit()

    async def disconnect(self, actor: User) -> None:
        row = await self.row()
        row.access_token = row.refresh_token = row.token_expires_at = row.scopes = None
        row.oauth_state = row.oauth_verifier = None
        audit.record(self.session, actor, "etsy.disconnect", "etsy_connection", 1, "Disconnected Etsy")
        await self.session.commit()
