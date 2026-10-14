"""Import every model so Base.metadata is complete (used by Alembic)."""

from app.models.account import Address, ContactMessage, PasswordResetToken
from app.models.base import Base
from app.models.category import Category
from app.models.commerce import (
    Coupon,
    CouponRedemption,
    OrderEvent,
    Refund,
    Sale,
    Setting,
    ShippingMethod,
    TaxRate,
)
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import NewsletterSubscriber, User

__all__ = [
    "Address", "Base", "Category", "ContactMessage", "Coupon", "CouponRedemption", "NewsletterSubscriber", "Order",
    "OrderEvent", "OrderItem", "PasswordResetToken", "Product", "Refund", "Sale", "Setting", "ShippingMethod",
    "TaxRate", "User",
]
