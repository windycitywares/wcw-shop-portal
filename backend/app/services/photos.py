"""Product photo uploads: check the file really is an image, tidy it up, and save it under a name taken from the product.

Files go to MEDIA_ROOT/products/<product-slug>/<product-name>-<n>.<ext> and are served from MEDIA_URL (the media
subdomain in production). Every upload is re-encoded with Pillow, which:
- rejects anything that isn't a JPEG, PNG or WebP (whatever the file name or browser says),
- turns phone photos the right way up and strips EXIF metadata (camera GPS location included),
- scales very large photos down so pages stay fast.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.utils.text import slugify

MAX_SIDE = 2400  # longest edge after resizing, in pixels
MAX_PIXELS = 50_000_000  # refuse "decompression bombs" before decoding
MAX_PHOTOS = 20
MAX_NAME = 80
ALLOWED = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "MPO": "jpg"}  # MPO = some phones' JPEG variant


@dataclass
class Processed:
    data: bytes
    ext: str
    width: int
    height: int


def base_name(title: str) -> str:
    """'Walnut Cremation Urn — Large' -> 'walnut-cremation-urn-large' (kept short for file systems and URLs)."""
    return slugify(title, max_length=MAX_NAME)


_NUMBERED = re.compile(r"^(?P<base>.+)-(?P<n>\d+)\.[a-z0-9]+$")


def next_names(base: str, existing: set[str], ext: str, count: int) -> list[str]:
    """The next `count` free names: base-1.jpg, base-2.jpg… after the highest number already used for this base."""
    used = [int(m["n"]) for name in existing if (m := _NUMBERED.match(name)) and m["base"] == base]
    start = max(used, default=0) + 1
    names, n = [], start
    while len(names) < count:
        candidate = f"{base}-{n}.{ext}"
        if candidate not in existing:
            names.append(candidate)
        n += 1
    return names


def process(raw: bytes) -> Processed:
    """Validate and re-encode one upload. Raises ValidationFailedError with a message for the person uploading."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            kind = probe.format
            if kind not in ALLOWED:
                raise ValidationFailedError("Upload a JPEG, PNG or WebP photo")
            if probe.width * probe.height > MAX_PIXELS:
                raise ValidationFailedError("That photo is too large (over 50 megapixels)")
            probe.verify()  # catches truncated or corrupt files
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
            img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            if kind == "PNG" and has_alpha:
                img.save(out, "PNG", optimize=True)
                ext = "png"
            elif kind == "WEBP":
                img.save(out, "WEBP", quality=85, method=4)
                ext = "webp"
            else:
                img.convert("RGB").save(out, "JPEG", quality=85, optimize=True, progressive=True)
                ext = "jpg"
            return Processed(out.getvalue(), ext, img.width, img.height)
    except ValidationFailedError:
        raise
    except Image.DecompressionBombError as exc:
        raise ValidationFailedError("That photo is too large (over 50 megapixels)") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationFailedError("That file isn't a photo we can read. Upload a JPEG, PNG or WebP.") from exc


def product_dir(slug: str) -> Path:
    return Path(get_settings().media_root) / "products" / slugify(slug)


def public_url(path: Path) -> str:
    settings = get_settings()
    relative = path.resolve().relative_to(Path(settings.media_root).resolve()).as_posix()
    return f"{settings.media_url.rstrip('/')}/{relative}"


def save(slug: str, title: str, files: list[Processed]) -> list[str]:
    """Write the processed photos and return their public URLs, in order."""
    folder = product_dir(slug)
    folder.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in folder.iterdir() if p.is_file()}
    urls = []
    for item in files:
        name = next_names(base_name(title), existing, item.ext, 1)[0]
        existing.add(name)
        target = folder / name
        with open(target, "xb") as fh:  # "x": never overwrite an existing photo
            fh.write(item.data)
        urls.append(public_url(target))
    return urls


def local_path(url: str) -> Path | None:
    """The file behind one of our own photo URLs, or None for any other URL (Etsy, Amazon, typed-in links)."""
    settings = get_settings()
    prefix = settings.media_url.rstrip("/") + "/products/"
    if not url.startswith(prefix):
        return None
    root = (Path(settings.media_root) / "products").resolve()
    candidate = (root / url[len(prefix):]).resolve()
    if root not in candidate.parents or not candidate.is_file():  # no ../ tricks
        return None
    return candidate


def remove_file(url: str) -> bool:
    path = local_path(url)
    if path is None:
        return False
    path.unlink(missing_ok=True)
    return True


def ensure_room(current: int, adding: int) -> None:
    if current + adding > MAX_PHOTOS:
        raise ValidationFailedError(f"A product can have up to {MAX_PHOTOS} photos")


def require_files(count: int) -> None:
    if count == 0:
        raise NotFoundError("Choose at least one photo")
