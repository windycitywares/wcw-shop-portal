"""WSGI entry point for cPanel "Setup Python App" (CloudLinux + LiteSpeed/Passenger).

cPanel generates its own passenger_wsgi.py that loads this file; configure the app with
Startup file = wsgi.py and Entry point = application. a2wsgi adapts the async FastAPI app.

LiteSpeed's request-body stream blocks when read past its end (e.g. on a GET with no body)
instead of returning b"". Starlette reads the body to detect client disconnects, so without
the guard below requests hang until LiteSpeed kills the worker. We hand the app a stream that
never reads past CONTENT_LENGTH.
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app  # noqa: E402


class BoundedInput:
    """File-like wrapper that returns b"" once CONTENT_LENGTH bytes have been read."""

    def __init__(self, stream, length: int):
        self._stream = stream
        self._remaining = length

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        size = self._remaining if size is None or size < 0 else min(size, self._remaining)
        data = self._stream.read(size)
        self._remaining -= len(data)
        if not data:
            self._remaining = 0
        return data

    def readline(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        size = self._remaining if size is None or size < 0 else min(size, self._remaining)
        data = self._stream.readline(size)
        self._remaining -= len(data)
        return data

    def __iter__(self):
        while line := self.readline():
            yield line


_asgi = ASGIMiddleware(app)


def application(environ, start_response):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length > 0:
        environ["wsgi.input"] = BoundedInput(environ["wsgi.input"], length)
    else:
        environ["wsgi.input"] = io.BytesIO(b"")
    return _asgi(environ, start_response)
