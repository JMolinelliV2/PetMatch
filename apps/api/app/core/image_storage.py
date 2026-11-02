from io import BytesIO
from uuid import UUID, uuid4
import warnings

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

MIME_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
FORMAT_SUFFIXES = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_IMAGE_PIXELS = 24_000_000
MAX_IMAGE_EDGE = 2048


def _client(endpoint: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _clean_image(payload: bytes, mime_type: str) -> tuple[bytes, int, int, str]:
    expected_format = MIME_FORMATS.get(mime_type)
    if expected_format is None:
        raise ValueError("Only JPEG, PNG, and WebP images are accepted")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as original:
                if original.format != expected_format:
                    raise ValueError("The file contents do not match the declared image type")
                if original.width * original.height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image dimensions are too large")
                image = ImageOps.exif_transpose(original)
                image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
                clean = image.copy()
                clean.info.clear()
                output = BytesIO()
                if expected_format == "JPEG":
                    if clean.mode not in ("RGB", "L"):
                        background = Image.new("RGB", clean.size, "white")
                        if "A" in clean.getbands():
                            background.paste(clean, mask=clean.getchannel("A"))
                        else:
                            background.paste(clean.convert("RGB"))
                        clean = background
                    clean.save(output, format="JPEG", quality=88, optimize=True, progressive=True, exif=b"")
                elif expected_format == "PNG":
                    clean.save(output, format="PNG", optimize=True)
                else:
                    clean.save(output, format="WEBP", quality=88, method=6, exif=b"")
                return output.getvalue(), clean.width, clean.height, FORMAT_SUFFIXES[expected_format]
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("The uploaded file is not a valid supported image") from exc


def _ensure_bucket(client) -> None:
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        try:
            client.create_bucket(Bucket=settings.s3_bucket)
        except ClientError as create_exc:
            if create_exc.response.get("Error", {}).get("Code") not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                raise


def store_private_image(owner_type: str, owner_id: UUID, mime_type: str, payload: bytes) -> tuple[str, int, int]:
    clean_payload, width, height, suffix = _clean_image(payload, mime_type)
    client = _client(settings.s3_endpoint)
    _ensure_bucket(client)
    key = f"{owner_type}/{owner_id}/{uuid4()}.{suffix}"
    client.put_object(Bucket=settings.s3_bucket, Key=key, Body=clean_payload, ContentType=mime_type)
    return key, width, height


def create_download_url(storage_key: str) -> str:
    client = _client(settings.s3_public_endpoint)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": storage_key},
        ExpiresIn=900,
    )


def store_profile_image(user_id: UUID, mime_type: str, payload: bytes) -> str:
    clean_payload, _, _, _ = _clean_image(payload, mime_type)
    with Image.open(BytesIO(clean_payload)) as image:
        rgba = ImageOps.fit(image.convert("RGBA"), (512, 512), method=Image.Resampling.LANCZOS)
        square = Image.new("RGB", rgba.size, "white")
        square.paste(rgba, mask=rgba.getchannel("A"))
        output = BytesIO()
        square.save(output, format="JPEG", quality=88, optimize=True, exif=b"")
    key, _, _ = store_private_image("user_avatar", user_id, "image/jpeg", output.getvalue())
    return key


def delete_private_image(storage_key: str) -> None:
    client = _client(settings.s3_endpoint)
    client.delete_object(Bucket=settings.s3_bucket, Key=storage_key)


def _load_clean_jpeg(storage_key: str, mime_type: str, max_edge: int) -> tuple[bytes, str]:
    response = _client(settings.s3_endpoint).get_object(Bucket=settings.s3_bucket, Key=storage_key)
    stream = response["Body"]
    try:
        payload = stream.read(settings.max_photo_size_bytes + 1)
    finally:
        stream.close()
    if len(payload) > settings.max_photo_size_bytes:
        raise ValueError("Image is too large for analysis")
    clean_payload, _, _, _ = _clean_image(payload, mime_type)
    with Image.open(BytesIO(clean_payload)) as image:
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        rgba = image.convert("RGBA")
        clean = Image.new("RGB", rgba.size, "white")
        clean.paste(rgba, mask=rgba.getchannel("A"))
        output = BytesIO()
        clean.save(output, format="JPEG", quality=85, optimize=True, exif=b"")
        return output.getvalue(), "image/jpeg"


def load_analysis_image(storage_key: str, mime_type: str) -> tuple[bytes, str]:
    # Uploads already have bounded dimensions, corrected EXIF and stripped metadata.
    # Keep their useful pixels for the detector; the VLM has its own preprocessing.
    response = _client(settings.s3_endpoint).get_object(Bucket=settings.s3_bucket, Key=storage_key)
    body = response["Body"]
    try:
        payload = body.read(settings.max_photo_size_bytes + 1)
    finally:
        body.close()
    if not payload or len(payload) > settings.max_photo_size_bytes:
        raise ValueError("Invalid stored image size")
    return payload, mime_type


def load_display_image(storage_key: str, mime_type: str) -> tuple[bytes, str]:
    return _load_clean_jpeg(storage_key, mime_type, MAX_IMAGE_EDGE)

