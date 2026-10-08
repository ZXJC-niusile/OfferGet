"""One local-only photo contract shared by every resume renderer.

No-photo is an authoritative exclusion, including profile paths. Placeholder is
an explicit layout-preview choice. Real photos must decode as safe raster files.
"""
from __future__ import annotations

import base64
import io
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Union

PHOTO_MODES = ("photo", "no-photo", "placeholder")
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTO_PIXELS = 25_000_000
_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif"}
_SUFFIXES = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP", ".gif": "GIF"}


@dataclass(frozen=True)
class PhotoSelection:
    mode: str
    path: Optional[str] = None
    data_uri: Optional[str] = None


def image_to_base64_data_uri(image_path: Optional[Union[str, Path]]) -> Optional[str]:
    """Validate actual raster bytes before embedding; never guess a MIME type."""
    if not image_path:
        return None
    path = Path(image_path).expanduser().resolve()
    if path.suffix.lower() not in _SUFFIXES:
        raise ValueError("Photo must be a PNG, JPEG, WebP or GIF raster image; SVG and other files are not supported")
    try:
        if not path.is_file():
            raise ValueError(f"Photo file not found: {path}")
        if path.stat().st_size > MAX_PHOTO_BYTES:
            raise ValueError("Photo file exceeds the 10 MiB limit")
        with path.open("rb") as source:
            data = source.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise ValueError("Photo file exceeds the 10 MiB limit")
    except OSError as exc:
        raise ValueError(f"Cannot read photo file: {path}") from exc
    image_format, _, _ = validate_raster_bytes(data, expected_format=_SUFFIXES[path.suffix.lower()])
    return f"data:{_FORMATS[image_format]};base64,{base64.b64encode(data).decode('ascii')}"


def validate_raster_bytes(data: bytes, expected_format: Optional[str] = None):
    """Verify bounded still-image bytes, including direct data-URI API inputs."""
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("Photo file exceeds the 10 MiB limit")
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Photo validation requires Pillow; install the render optional dependencies") from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                image_format = image.format
                if image_format not in _FORMATS or (expected_format and expected_format != image_format):
                    raise ValueError("Photo filename extension or MIME type does not match a supported raster image")
                if image.width * image.height > MAX_PHOTO_PIXELS:
                    raise ValueError("Photo exceeds the 25 megapixel limit")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Photo must be a single-frame still image")
                dimensions = image.size
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError(f"Invalid photo image: {exc}") from exc
    return image_format, *dimensions


def photo_data_uri_to_png(data_uri: str):
    """Return verified Word-compatible PNG bytes, preserving pixels/aspect ratio.

    EXIF orientation is normalized, with no resize or crop. This also makes
    supported WebP/GIF inputs portable to Word without external relationships.
    """
    import binascii
    if not isinstance(data_uri, str) or len(data_uri) > MAX_PHOTO_BYTES * 4 // 3 + 100:
        raise ValueError("Invalid or oversized photo data URI")
    header, separator, payload = data_uri.partition(",")
    expected = {f"data:{mime};base64": fmt for fmt, mime in _FORMATS.items()}.get(header)
    if not separator or expected is None:
        raise ValueError("Photo must use a supported raster data URI")
    try:
        data = base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid photo base64 data") from exc
    validate_raster_bytes(data, expected_format=expected)
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(data)) as image:
        oriented = ImageOps.exif_transpose(image)
        pixels = oriented.convert("RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB")
        output = io.BytesIO()
        pixels.save(output, format="PNG")
        return output.getvalue(), pixels.width, pixels.height


def resolve_photo(candidate: Mapping[str, Any], *, photo_path=None,
                  reserve_photo: bool = True, photo_mode: Optional[str] = None) -> PhotoSelection:
    """Resolve selection without mutating or reading disabled photo sources.

    Explicit boolean false wins over all source metadata. An omitted mode keeps
    the old programmatic placeholder default; the CLI supplies no-photo by default.
    """
    mode = photo_mode if photo_mode is not None else candidate.get("photo_mode")
    if mode is not None and mode not in PHOTO_MODES:
        raise ValueError(f"Unknown photo mode {mode!r}; choose {', '.join(PHOTO_MODES)}")
    if not reserve_photo or mode == "no-photo":
        return PhotoSelection("no-photo")
    if mode == "placeholder":
        return PhotoSelection("placeholder")
    path = photo_path or candidate.get("photo_path") or candidate.get("photo")
    if path:
        data = image_to_base64_data_uri(path)
        return PhotoSelection("photo", str(Path(path).expanduser().resolve()), data)
    if mode == "photo":
        raise ValueError("Photo mode requires an actual image: use --photo-path or candidate.photo_path; use --photo-mode placeholder only for a layout preview")
    return PhotoSelection("no-photo" if candidate.get("reserve_photo") is False else "placeholder")
