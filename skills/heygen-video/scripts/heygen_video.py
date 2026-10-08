#!/usr/bin/env python3
import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import math
import mimetypes
import os
from pathlib import Path
import shutil
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
import uuid

API = "https://api.heygen.com"
PRICING_SOURCE = "https://help.heygen.com/en/articles/17272995-introducing-heygen-video-generate-cinematic-clips-from-a-prompt"
MODEL_SOURCE = "https://developers.heygen.com/docs/models/heygen-video"

# Saved pricing schedule (USD per output second). Edit this block when HeyGen changes pricing.
PRICING_VERIFIED_ON = date(2026, 10, 5)
PRICING_STALE_AFTER_DAYS = 30
PROMO_ENDS = date(2026, 11, 1)  # Standard rates from this UTC date; HeyGen gives no cutoff timezone.
STANDARD_RATES = {
    ("text_image", "480p"): Decimal("0.02"), ("text_image", "768p"): Decimal("0.03"),
    ("reference", "480p"): Decimal("0.04"), ("reference", "768p"): Decimal("0.06"),
}
PROMO_MULTIPLIER = Decimal("0.5")
HIGH_RES_MULTIPLIER = Decimal(3)  # Developer docs: 1080p and 2k bill at 3x the 768p rate.

MODES = ("text_to_video", "image_to_video", "reference_to_video")
MODE_ALIASES = {"t2v": "text_to_video", "i2v": "image_to_video", "ref2va": "reference_to_video"}
RESOLUTIONS = ("480p", "768p", "1080p", "2k")
HIGH_RES = ("1080p", "2k")
ASPECT_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
ENHANCEMENTS = ("turbo", "quality", "disabled")
ALLOWED_FIELDS = {
    "model", "mode", "prompt", "duration", "resolution", "aspect_ratio", "prompt_enhancement",
    "seed", "image", "reference_images", "reference_videos", "reference_audio",
    "callback_url", "callback_id",
}
REFERENCE_LIMITS = {"reference_images": 9, "reference_videos": 3, "reference_audio": 3}
MAX_REFERENCES = 12


class NoRedirect(HTTPRedirectHandler):
    """Refuse redirects so the API key is never forwarded to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f"HeyGen API answered with a redirect ({code}); refusing to resend the API key.")


API_OPENER = build_opener(NoRedirect)


def today_utc():
    return datetime.now(timezone.utc).date()


def check_media(item, label):
    if not isinstance(item, dict):
        raise ValueError(f"{label} must be a media object.")
    kind = item.get("type")
    if kind == "asset_id":
        expected = {"type", "asset_id"}
        if not isinstance(item.get("asset_id"), str) or not item["asset_id"]:
            raise ValueError(f"{label} needs a non-empty asset_id.")
    elif kind == "url":
        expected = {"type", "url"}
        if not isinstance(item.get("url"), str) or not item["url"].startswith("https://"):
            raise ValueError(f"{label} url must be a direct https:// link (HeyGen does not follow redirects).")
    elif kind == "base64":
        expected = {"type", "media_type", "data"}
        if not isinstance(item.get("media_type"), str) or not isinstance(item.get("data"), str) or not item["data"]:
            raise ValueError(f"{label} base64 needs media_type and data.")
    else:
        raise ValueError(f"{label} type must be asset_id, url, or base64.")
    extra = set(item) - expected
    if extra:
        raise ValueError(f"{label} has unsupported fields: {', '.join(sorted(extra))}.")


def validate(request):
    """Check a request against the documented heygen-video-1 schema before any estimate or submission."""
    if not isinstance(request, dict):
        raise ValueError("Request must be a JSON object.")
    unknown = set(request) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields (HeyGen rejects them): {', '.join(sorted(unknown))}. Put style in the prompt.")
    if request.get("model") != "heygen-video-1":
        raise ValueError("model must be heygen-video-1.")
    mode = MODE_ALIASES.get(request.get("mode"), request.get("mode"))
    if mode not in MODES:
        raise ValueError("Set an explicit mode: text_to_video, image_to_video, or reference_to_video.")
    resolution = request.get("resolution")
    if resolution not in RESOLUTIONS:
        raise ValueError("Set resolution explicitly to 480p, 768p, 1080p, or 2k.")
    duration = request.get("duration")
    if type(duration) is not int or not 5 <= duration <= 15:
        raise ValueError("duration must be an integer from 5 to 15 seconds.")
    if not isinstance(request.get("prompt"), str) or not 1 <= len(request["prompt"]) <= 32000:
        raise ValueError("prompt must contain 1 to 32000 characters.")
    if "prompt_enhancement" in request and request["prompt_enhancement"] not in ENHANCEMENTS:
        raise ValueError("prompt_enhancement must be turbo, quality, or disabled.")
    if "seed" in request:
        seed = request["seed"]
        if type(seed) is not int or not 0 <= seed <= 4294967295:
            raise ValueError("seed must be an integer from 0 to 4294967295.")

    aspect = request.get("aspect_ratio")
    if mode == "image_to_video":
        if aspect is not None:
            raise ValueError("Omit aspect_ratio in image_to_video; the first frame sets it. Crop the image instead.")
    elif aspect is not None:
        allowed = ASPECT_RATIOS + (("adaptive",) if mode == "reference_to_video" else ())
        if aspect not in allowed:
            raise ValueError(f"aspect_ratio must be one of: {', '.join(allowed)}.")
    if resolution in HIGH_RES and mode != "image_to_video":  # Image mode: the first frame must already be 16:9 or 9:16.
        effective = aspect or ("16:9" if mode == "text_to_video" else None)
        if effective not in ("16:9", "9:16"):
            raise ValueError("1080p and 2k require an explicit aspect_ratio of 16:9 or 9:16.")

    if mode == "image_to_video":
        if not request.get("image"):
            raise ValueError("image_to_video requires image.")
        check_media(request["image"], "image")
    elif "image" in request:
        raise ValueError("image is only allowed in image_to_video.")

    total = 0
    for field, limit in REFERENCE_LIMITS.items():
        if field not in request:
            continue
        if mode != "reference_to_video":
            raise ValueError(f"{field} is only allowed in reference_to_video.")
        items = request[field]
        if not isinstance(items, list):
            raise ValueError(f"{field} must be a list.")
        if len(items) > limit:
            raise ValueError(f"{field} allows at most {limit} items.")
        for index, item in enumerate(items, 1):
            check_media(item, f"{field}[{index}]")
        total += len(items)
    if total > MAX_REFERENCES:
        raise ValueError(f"At most {MAX_REFERENCES} references in total.")
    if mode == "reference_to_video" and not (request.get("reference_images") or request.get("reference_videos")):
        raise ValueError("reference_to_video requires at least one image or video reference; audio alone is insufficient.")

    if "callback_url" in request:
        if not isinstance(request["callback_url"], str) or not request["callback_url"].startswith("https://"):
            raise ValueError("callback_url must be an https:// URL.")
    if "callback_id" in request:
        if not isinstance(request["callback_id"], str) or len(request["callback_id"]) > 256:
            raise ValueError("callback_id must be a string of at most 256 characters.")
    return mode, resolution, duration


def emit(value):
    print(json.dumps(value, indent=2))


def api(path, payload=None, headers=None, timeout=45):
    key = os.environ.get("HEYGEN_API_KEY")
    if not key:
        raise ValueError("Set HEYGEN_API_KEY locally before calling HeyGen. Do not paste it into chat.")
    request_headers = {"x-api-key": key, **(headers or {})}
    if isinstance(payload, dict):
        payload = json.dumps(payload).encode()
        request_headers["Content-Type"] = "application/json"
    request = Request(API + path, data=payload, headers=request_headers)
    with API_OPENER.open(request, timeout=timeout) as response:
        return json.load(response)


def estimate(request, input_seconds, today=None):
    mode, resolution, duration = validate(request)
    if request.get("reference_videos"):
        if input_seconds is None or not math.isfinite(input_seconds) or input_seconds <= 0:
            raise ValueError("Provide measured total input video length with --input-video-seconds.")
    elif input_seconds not in (None, 0):
        raise ValueError("Only provide input video seconds when reference_videos is present.")
    today = today or today_utc()
    promo = today < PROMO_ENDS
    family = "reference" if mode == "reference_to_video" else "text_image"
    rate = STANDARD_RATES[(family, "768p" if resolution in HIGH_RES else resolution)]
    if resolution in HIGH_RES:
        rate *= HIGH_RES_MULTIPLIER
    if promo:
        rate *= PROMO_MULTIPLIER
    seconds = Decimal(duration) + Decimal(str(input_seconds or 0))
    notes = ["Estimate only; verify current account pricing. Promotion cutoff timezone is unspecified; dates use UTC."]
    if resolution in HIGH_RES:
        notes.append("1080p/2k rate is derived from the developer docs (3x 768p); the pricing article does not list it.")
    age = (today - PRICING_VERIFIED_ON).days
    stale = age > PRICING_STALE_AFTER_DAYS
    if stale:
        notes.append(f"Saved pricing is {age} days old. Check the source before quoting this estimate.")
    return {
        "currency": "USD", "estimated_cost": str((rate * seconds).quantize(Decimal("0.001"))),
        "rate_per_second": str(rate.quantize(Decimal("0.001"))), "billable_seconds": str(seconds),
        "pricing": "October 2026 promotion" if promo else "Published standard rate",
        "as_of": today.isoformat(), "pricing_verified_on": PRICING_VERIFIED_ON.isoformat(),
        "pricing_stale": stale, "source": PRICING_SOURCE, "note": " ".join(notes),
    }


def create(args):
    request = json.loads(args.request.read_text())
    cost = estimate(request, args.input_video_seconds)
    if args.dry_run:
        emit({"estimate": cost, "request": request})
        return
    if args.job is None:
        raise ValueError("--job is required for submission and safe resumption.")
    if not os.environ.get("HEYGEN_API_KEY"):
        raise ValueError("Set HEYGEN_API_KEY locally before submitting. Do not paste it into chat.")
    if args.job.exists():
        record = json.loads(args.job.read_text())
        if record["request"] != request:
            raise ValueError("This job file belongs to a different request. Do not reuse it for a new render.")
        if record.get("video_id"):
            emit({"video_id": record["video_id"], "resumed": True, "job": str(args.job.resolve())})
            return
        if time.time() - record["submitted_at"] >= 86400:
            raise ValueError("Unresolved submission is older than 24 hours. Reconcile with HeyGen before resubmitting.")
    else:
        record = {"request": request, "estimate": cost, "idempotency_key": str(uuid.uuid4()), "submitted_at": time.time()}
        with args.job.open("x") as handle:
            json.dump(record, handle, indent=2)
    result = api("/v3/models/videos", request, {"Idempotency-Key": record["idempotency_key"]})["data"]
    record.update(video_id=result["video_id"], status=result["status"])
    args.job.write_text(json.dumps(record, indent=2))
    emit({"video_id": record["video_id"], "status": record["status"], "estimate": record["estimate"], "job": str(args.job.resolve())})


def fetch_status(record):
    return api("/v3/models/videos/" + quote(record["video_id"], safe=""))["data"]


def status(args):
    record = json.loads(args.job.read_text())
    if not record.get("video_id"):
        raise ValueError("No video ID saved. Resume create with the original request and job file.")
    if args.output and args.output.exists():
        raise ValueError("Output already exists; inspect it or choose another output path.")
    deadline = time.monotonic() + args.timeout
    while True:
        result = fetch_status(record)
        record["result"] = result
        record["status"] = result["status"]
        args.job.write_text(json.dumps(record, indent=2))
        if not args.wait or result["status"] not in ("pending", "processing"):
            break
        if time.monotonic() + args.interval > deadline:
            result["note"] = f"Still {result['status']} after waiting; run status again to resume."
            break
        print(f"{result['status']}...", file=sys.stderr, flush=True)
        time.sleep(args.interval)
    if result["status"] in ("failed", "cancelled"):
        emit(result)
        return 1
    if result["status"] == "completed" and args.output:
        if not result.get("video_url", "").startswith("https://"):
            raise ValueError("HeyGen returned a missing or non-HTTPS download URL.")
        partial = args.output.with_name(args.output.name + ".part")
        try:
            # Download without sending the API key to the media host.
            with urlopen(result["video_url"], timeout=120) as response, partial.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            partial.replace(args.output)
        finally:
            if partial.exists():
                partial.unlink()
        result["local_path"] = str(args.output.resolve())
    emit(result)
    return 0


def upload(args):
    if not args.file.is_file():
        raise ValueError(f"Not a file: {args.file}")
    boundary = uuid.uuid4().hex
    media_type = mimetypes.guess_type(args.file.name)[0] or "application/octet-stream"
    filename = args.file.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
               f'Content-Type: {media_type}\r\n\r\n').encode()
    payload += args.file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    emit(api("/v3/assets", payload, {"Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=300))


def validate_cmd(args):
    mode, resolution, duration = validate(json.loads(args.request.read_text()))
    emit({"valid": True, "mode": mode, "resolution": resolution, "duration": duration})


def main():
    parser = argparse.ArgumentParser(description="HeyGen Video: estimate, submit, retrieve, and upload references.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("options", help="List generation settings without an API key or network call.")
    create_parser = commands.add_parser("create", help="Estimate with --dry-run, otherwise submit one paid job.")
    create_parser.add_argument("--request", type=Path, required=True)
    create_parser.add_argument("--job", type=Path)
    create_parser.add_argument("--input-video-seconds", type=float)
    create_parser.add_argument("--dry-run", action="store_true")
    status_parser = commands.add_parser("status", help="Check an existing job and optionally download its completed video.")
    status_parser.add_argument("--job", type=Path, required=True)
    status_parser.add_argument("--output", type=Path)
    status_parser.add_argument("--wait", action="store_true", help="Poll until the job finishes or --timeout passes.")
    status_parser.add_argument("--timeout", type=float, default=600, help="Seconds to wait with --wait (default 600).")
    status_parser.add_argument("--interval", type=float, default=10, help="Seconds between polls (default 10).")
    validate_parser = commands.add_parser("validate", help="Check a request file against the schema without a key or network call.")
    validate_parser.add_argument("--request", type=Path, required=True)
    upload_parser = commands.add_parser("upload", help="Upload a local reference and return its asset record.")
    upload_parser.add_argument("file", type=Path)
    args = parser.parse_args()
    if args.command == "options":
        print("""HeyGen Video options (model: heygen-video-1)

Skill prompt refinement (visible before generation):
  Say 'refine prompt' or 'enhance prompt' to improve your brief.
  Refinement alone returns a prompt without calling HeyGen.
  Add 'and generate' to show the refined prompt and cost for confirmation.

Mode:
  text_to_video       Describe a new scene; no media required.
  image_to_video      Animate one image as the literal first frame.
  reference_to_video  Guide a new scene with images/videos, plus optional audio.

Resolution: 480p (cheaper draft), 768p (more detail),
  1080p and 2k (16:9 or 9:16 only; 3x the 768p rate).
Duration: any integer from 5 to 15 seconds.
Aspect ratio: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16.
  Reference mode also accepts adaptive; image mode follows its first frame.
HeyGen prompt_enhancement (processed by HeyGen before generation):
  turbo     Fast expansion; the API default.
  quality   More thorough expansion.
  disabled  Sends your prompt unchanged.
  After the skill's refinement, it chooses disabled unless you override it.
  Choosing turbo or quality lets HeyGen rewrite the reviewed prompt again.
Seed: omit for random, or use an integer from 0 to 4294967295.
Sound: direct dialogue, ambience, effects, and music in the prompt.
  There is no separate audio toggle in the API schema.

12 documented visual styles (prompt directions, not API presets):
   1. Live-action cinema
   2. Plasticine stop-motion
   3. Hand-painted cel anime
   4. Pencil, fineliner and marker animation
   5. Mid-century screen print
   6. Anime key drawing
   7. Pencil sketch
   8. Marker rendering
   9. Watercolour wash
  10. Impasto oil
  11. Painted anime background
  12. Plasticine model
Custom styles are also allowed. Describe the style in prompt; do not add a style field.

Inputs:
  prompt: 1 to 32,000 characters, required in every mode.
  image: required for image_to_video.
  reference_images: up to 9; reference_videos: up to 3;
  reference_audio: up to 3; 12 references total, reference mode only.
  Reference mode requires at least one image or video; audio alone is insufficient.
  Media formats: uploaded asset ID, direct HTTPS URL, or inline base64.
  URL limits: image 16 MB; video/audio 32 MB (no redirects).
  Base64 limits: image 5 MB; video/audio 16 MB.

Advanced notifications:
  callback_url: HTTPS completion callback.
  callback_id: optional correlation label, up to 256 characters.

API defaults: reference_to_video, 5 seconds, 768p, turbo, random seed.
Aspect defaults: text 16:9; reference adaptive; image follows first frame.
Skill draft defaults: text mode without media, 5 seconds, 480p, 16:9.
Enhancement default for a fully directed/refined prompt: disabled.
Use validate --request request.json to check a request offline.
Use create --request request.json --dry-run for a dated price estimate.
For video references, include --input-video-seconds with their total duration.

Before any paid generation:
  Review the final prompt/settings and estimated total USD cost.
  The skill waits for your confirmation before submitting.
  Extra paid variations/rerenders need their own estimate and confirmation.

Example in chat:
  $heygen-video refine prompt and generate: a coffee cup on a cafe table,
  text to video, 10 seconds, 768p, 9:16, live-action cinema,
  prompt_enhancement disabled, no music.

No API key or network call is needed to list options.""")
        print("\nEstimated pricing (USD; saved schedule, not a live billing quote):")
        print("Mode                 Resolution  Per second  10-second output")
        for mode in ("text_to_video", "image_to_video", "reference_to_video"):
            for resolution in RESOLUTIONS:
                request = {"model": "heygen-video-1", "mode": mode,
                           "prompt": "Pricing example", "duration": 10, "resolution": resolution}
                if resolution in HIGH_RES and mode != "image_to_video":
                    request["aspect_ratio"] = "16:9"
                if mode == "image_to_video":
                    request["image"] = {"type": "asset_id", "asset_id": "estimate-only"}
                elif mode == "reference_to_video":
                    request["reference_images"] = [{"type": "asset_id", "asset_id": "estimate-only"}]
                cost = estimate(request, None)
                print(f"{mode:20} {resolution:11} ${cost['rate_per_second']:10} ${cost['estimated_cost']}")
        print(f"Pricing date: {cost['as_of']}; basis: {cost['pricing']}.")
        print("Published promotion ends after October 2026; November standard rates are double.")
        print("Reference mode also bills input video seconds; image/audio references add no seconds.")
        print("1080p/2k rates are derived from the developer docs (3x 768p), not the pricing article.")
        print(f"Rates last verified {PRICING_VERIFIED_ON.isoformat()}; verify current pricing and provider cutoff timezone.")
        if cost["pricing_stale"]:
            print("WARNING: saved pricing is over 30 days old. Check the source before quoting estimates.")
        print("Source: " + PRICING_SOURCE)
        return 0
    try:
        return {"create": create, "status": status, "upload": upload, "validate": validate_cmd}[args.command](args) or 0
    except HTTPError as error:
        message = f"HeyGen/media HTTP {error.code}: {error.read().decode(errors='replace')}"
    except (ValueError, OSError, URLError, KeyError) as error:
        message = str(error)
    key = os.environ.get("HEYGEN_API_KEY")
    print(message.replace(key, "[REDACTED]") if key else message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
