"""Role-based access control: roles map to a fixed set of permissions.

Routes depend on *permissions*, never on role names, so adding a role or
changing what a role may do is a one-line change here.
"""

from enum import StrEnum

from app.core.enums import UserRole


class Permission(StrEnum):
    CATALOG_VIEW_UNPUBLISHED = "catalog:view_unpublished"
    CATALOG_CREATE = "catalog:create"
    CATALOG_EDIT_OWN = "catalog:edit_own"
    CATALOG_EDIT_ANY = "catalog:edit_any"
    CATALOG_PUBLISH = "catalog:publish"
    CATALOG_DELETE = "catalog:delete"
    CATALOG_IMPORT = "catalog:import"
    CATEGORY_MANAGE = "category:manage"
    ORDERS_MANAGE = "orders:manage"
    FINANCE_VIEW = "finance:view"
    USERS_MANAGE = "users:manage"
    SETTINGS_MANAGE = "settings:manage"
    PROMOTIONS_MANAGE = "promotions:manage"  # sales, coupons, automatic offers, email campaigns
    REPORTS_VIEW = "reports:view"
    CUSTOMERS_VIEW = "customers:view"
    REVIEWS_MODERATE = "reviews:moderate"
    AUDIT_VIEW = "audit:view"


_AUTHOR = {
    Permission.CATALOG_VIEW_UNPUBLISHED,
    Permission.CATALOG_CREATE,
    Permission.CATALOG_EDIT_OWN,
    Permission.CATALOG_IMPORT,  # imports land as drafts for authors
}

_PUBLISHER = _AUTHOR | {
    Permission.CATALOG_EDIT_ANY,
    Permission.CATALOG_PUBLISH,
    Permission.CATALOG_DELETE,
    Permission.CATEGORY_MANAGE,
    Permission.REVIEWS_MODERATE,
}

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.ADMIN: frozenset(Permission),
    UserRole.PUBLISHER: frozenset(_PUBLISHER),
    UserRole.AUTHOR: frozenset(_AUTHOR),
    UserRole.CUSTOMER: frozenset(),
}

STAFF_ROLES = frozenset({UserRole.ADMIN, UserRole.PUBLISHER, UserRole.AUTHOR})


def has_permission(role: UserRole | str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(UserRole(role), frozenset())


def permissions_for(role: UserRole | str) -> list[str]:
    return sorted(p.value for p in ROLE_PERMISSIONS.get(UserRole(role), frozenset()))
