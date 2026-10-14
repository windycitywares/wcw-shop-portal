from fastapi import APIRouter

from app.api.v1 import account, auth, categories, imports, inbox, orders, products, promotions, shop, store, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(auth.newsletter_router)
api_router.include_router(account.addresses_router)
api_router.include_router(account.contact_router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(products.router)
api_router.include_router(imports.router)
api_router.include_router(shop.router)
api_router.include_router(orders.router)
api_router.include_router(orders.my_orders_router)
api_router.include_router(promotions.router)
api_router.include_router(store.router)
api_router.include_router(inbox.router)
