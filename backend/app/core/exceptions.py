"""Domain errors raised by services, translated to HTTP responses in one place."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class PermissionDeniedError(DomainError):
    status_code = 403


class AuthenticationError(DomainError):
    status_code = 401


class ValidationFailedError(DomainError):
    status_code = 422


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code, headers=headers)
