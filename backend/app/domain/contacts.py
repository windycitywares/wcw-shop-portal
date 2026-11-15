"""Rules about who may receive marketing email."""

# Rows made only so a service email (cart reminder, review request) can carry a working unsubscribe link.
# They are not newsletter subscribers and never receive campaigns. "erased" rows are what is left of someone whose
# newsletter record was erased: no personal data, just the fingerprint that tells us not to add them back by hand.
SERVICE_ONLY_SOURCES = ("cart_reminder", "order", "erased")
