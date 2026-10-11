"""Domain enums. Kept free of SQLAlchemy imports so importers/tests can use them."""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    PUBLISHER = "publisher"
    AUTHOR = "author"
    CUSTOMER = "customer"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class StockStatus(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    BACKORDER = "backorder"
    PREORDER = "preorder"


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class FulfillmentStatus(StrEnum):
    UNFULFILLED = "unfulfilled"
    PARTIAL = "partial"
    FULFILLED = "fulfilled"
    RETURNED = "returned"
