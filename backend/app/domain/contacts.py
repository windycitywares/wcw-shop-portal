"""Rules about who may receive marketing email."""

# Rows made only so a service email (cart reminder, review request) can carry a working unsubscribe link.
# They are not newsletter subscribers and never receive campaigns.
SERVICE_ONLY_SOURCES = ("cart_reminder", "order")
