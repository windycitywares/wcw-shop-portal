"""When is a cart abandoned?"""

from datetime import timedelta

ACTIVE_WINDOW = timedelta(hours=1)  # a cart touched in the last hour is still being shopped, not abandoned
