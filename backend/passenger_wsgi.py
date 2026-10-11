"""Entry point for cPanel "Setup Python App" (Phusion Passenger, WSGI).

Passenger speaks WSGI; a2wsgi adapts the async FastAPI app to it.
In cPanel set: Application startup file = passenger_wsgi.py, Entry point = application.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402

application = ASGIMiddleware(app)
