"""Import every model so Base.metadata is complete (used by Alembic)."""

from app.models.account import Address, ContactMessage, ContactReply, PasswordResetToken
from app.models.analytics import AnalyticsEvent, AnalyticsSession, ConsentDaily
from app.models.base import Base
from app.models.category import Category
from app.models.commerce import (
    AuditLog,
    Cart,
    CartRule,
    Coupon,
    CouponRedemption,
    EmailOutbox,
    OrderEvent,
    Payment,
    Sale,
    StoreSetting,
)
from app.models.engagement import Campaign, Review, ReviewVote, StockAlert, WishlistItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import NewsletterSubscriber, User

__all__ = [
    "Address", "AnalyticsEvent", "AnalyticsSession", "AuditLog", "Base", "Campaign", "Cart", "CartRule",
    "Category", "ConsentDaily", "ContactMessage", "ContactReply", "Coupon", "CouponRedemption", "EmailOutbox",
    "NewsletterSubscriber", "Order", "OrderEvent", "OrderItem", "PasswordResetToken", "Payment", "Product",
    "Review", "ReviewVote", "Sale", "StockAlert", "StoreSetting", "User", "WishlistItem",
]
