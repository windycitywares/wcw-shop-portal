"""WSGI entry point for cPanel "Setup Python App" (CloudLinux + LiteSpeed/Passenger).

cPanel generates its own passenger_wsgi.py that loads this file; configure the app with
Startup file = wsgi.py and Entry point = application. a2wsgi adapts the async FastAPI app.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402

application = ASGIMiddleware(app)
