from fastapi import APIRouter

from app.api.v1 import account, admin_carts, admin_orders, admin_promotions, admin_system, auth, categories, imports, products, shop, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(auth.newsletter_router)
api_router.include_router(account.addresses_router)
api_router.include_router(account.contact_router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(products.router)
api_router.include_router(imports.router)
# storefront: store config, cart quotes, checkout and orders
api_router.include_router(shop.router)
# admin
api_router.include_router(admin_orders.router)
api_router.include_router(admin_carts.router)
api_router.include_router(admin_promotions.router)
api_router.include_router(admin_system.router)
