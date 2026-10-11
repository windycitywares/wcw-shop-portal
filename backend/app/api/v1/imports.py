from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.api.deps import SessionDep, require
from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.core.permissions import Permission
from app.importers import list_importers
from app.models.user import User
from app.schemas.imports import ImporterInfo, ImportPreview, ImportSummary
from app.services.exporting import XLSX_MIME, ExportService
from app.services.importing import ImportOptions, ImportService

router = APIRouter(prefix="/imports", tags=["imports"])
Importer = Annotated[User, Depends(require(Permission.CATALOG_IMPORT))]


async def _read(upload: UploadFile) -> bytes:
    limit = get_settings().max_import_bytes
    content = await upload.read(limit + 1)
    if len(content) > limit:
        raise ValidationFailedError(f"File is larger than {limit // (1024 * 1024)} MB")
    if not content:
        raise ValidationFailedError("The file is empty")
    return content


@router.get("/sources", response_model=list[ImporterInfo])
async def import_sources(_: Importer):
    """Which marketplaces / formats can be imported."""
    return [
        ImporterInfo(
            key=i.key, label=i.label, description=i.description, accepted_extensions=list(i.accepted_extensions)
        )
        for i in list_importers()
    ]


@router.get("/template.xlsx")
async def import_template(_: Importer):
    return Response(
        ExportService.template_xlsx(),
        media_type=XLSX_MIME,
        headers={"Content-Disposition": 'attachment; filename="wcw-import-template.xlsx"'},
    )


@router.post("/preview", response_model=ImportPreview)
async def preview_import(
    session: SessionDep,
    _: Importer,
    source: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    """Parse the file and show what would be imported — nothing is saved."""
    content = await _read(file)
    return ImportService(session).preview(source, content, file.filename or "upload")


@router.post("", response_model=ImportSummary)
async def run_import(
    session: SessionDep,
    user: Importer,
    source: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    category_id: Annotated[int | None, Form()] = None,
    publish: Annotated[bool, Form()] = False,
    update_existing: Annotated[bool, Form()] = True,
):
    content = await _read(file)
    options = ImportOptions(category_id=category_id, publish=publish, update_existing=update_existing)
    return await ImportService(session).run(source, content, file.filename or "upload", user, options)
