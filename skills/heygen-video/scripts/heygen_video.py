#!/usr/bin/env python3
import argparse
from datetime import date, datetime
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
from urllib.request import Request, urlopen
import uuid
from zoneinfo import ZoneInfo

API = "https://api.heygen.com"
PRICING_SOURCE = "https://help.heygen.com/en/articles/17272995-introducing-heygen-video-generate-cinematic-clips-from-a-prompt"


def emit(value):
    print(json.dumps(value, indent=2))


def api(path, payload=None, headers=None):
    key = os.environ.get("HEYGEN_API_KEY")
    if not key:
        raise ValueError("Set HEYGEN_API_KEY locally before calling HeyGen. Do not paste it into chat.")
    request_headers = {"x-api-key": key, **(headers or {})}
    if isinstance(payload, dict):
        payload = json.dumps(payload).encode()
        request_headers["Content-Type"] = "application/json"
    request = Request(API + path, data=payload, headers=request_headers)
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def estimate(request, input_seconds, today=None):
    if request.get("model") != "heygen-video-1":
        raise ValueError("model must be heygen-video-1.")
    mode = request.get("mode")
    resolution = request.get("resolution")
    duration = request.get("duration")
    if mode not in ("text_to_video", "image_to_video", "reference_to_video"):
        raise ValueError("Set an explicit mode: text_to_video, image_to_video, or reference_to_video.")
    if resolution not in ("480p", "768p"):
        raise ValueError("Set resolution explicitly to 480p or 768p.")
    if type(duration) is not int or not 5 <= duration <= 15:
        raise ValueError("duration must be an integer from 5 to 15 seconds.")
    if not isinstance(request.get("prompt"), str) or not 1 <= len(request["prompt"]) <= 32000:
        raise ValueError("prompt must contain 1 to 32000 characters.")
    if mode == "image_to_video" and not request.get("image"):
        raise ValueError("image_to_video requires image.")
    if mode == "reference_to_video" and not (request.get("reference_images") or request.get("reference_videos")):
        raise ValueError("reference_to_video requires at least one image or video reference.")
    if request.get("reference_videos"):
        if mode != "reference_to_video":
            raise ValueError("reference_videos requires reference_to_video mode.")
        if input_seconds is None or not math.isfinite(input_seconds) or input_seconds <= 0:
            raise ValueError("Provide measured total input video length with --input-video-seconds.")
    elif input_seconds not in (None, 0):
        raise ValueError("Only provide input video seconds when reference_videos is present.")
    today = today or datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date()
    promo = date(2026, 9, 30) <= today < date(2026, 11, 1)
    rate = Decimal("0.010" if resolution == "480p" else "0.015")
    if mode == "reference_to_video":
        rate *= 2
    if not promo:
        rate *= 2
    seconds = Decimal(duration) + Decimal(str(input_seconds or 0))
    return {
        "currency": "USD", "estimated_cost": str(rate * seconds),
        "rate_per_second": str(rate), "billable_seconds": str(seconds),
        "pricing": "October 2026 promotion" if promo else "Published standard rate",
        "as_of": today.isoformat(), "pricing_verified_on": "2026-10-05",
        "source": PRICING_SOURCE,
        "note": "Estimate only; verify current account pricing. Promotion cutoff timezone is unspecified."
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


def status(args):
    record = json.loads(args.job.read_text())
    if not record.get("video_id"):
        raise ValueError("No video ID saved. Resume create with the original request and job file.")
    result = api("/v3/models/videos/" + quote(record["video_id"], safe=""))["data"]
    record["result"] = result
    record["status"] = result["status"]
    args.job.write_text(json.dumps(record, indent=2))
    if result["status"] in ("failed", "cancelled"):
        emit(result)
        return 1
    if result["status"] == "completed" and args.output:
        if args.output.exists():
            raise ValueError("Output already exists; inspect it or choose another output path.")
        if not result["video_url"].startswith("https://"):
            raise ValueError("HeyGen returned a non-HTTPS download URL.")
        partial = args.output.with_name(args.output.name + ".part")
        # Download without sending the API key to the media host.
        with urlopen(result["video_url"], timeout=45) as response, partial.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        partial.replace(args.output)
        result["local_path"] = str(args.output.resolve())
    emit(result)
    return 0


def upload(args):
    boundary = uuid.uuid4().hex
    media_type = mimetypes.guess_type(args.file.name)[0] or "application/octet-stream"
    filename = args.file.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
               f'Content-Type: {media_type}\r\n\r\n').encode()
    payload += args.file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    emit(api("/v3/assets", payload, {"Content-Type": f"multipart/form-data; boundary={boundary}"}))


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
    upload_parser = commands.add_parser("upload", help="Upload a local reference and return its asset record.")
    upload_parser.add_argument("file", type=Path)
    args = parser.parse_args()
    if args.command == "options":
        print("""HeyGen Video options (model: heygen-video-1)

Codex prompt refinement (visible before generation):
  Say 'refine prompt' or 'enhance prompt' to improve your brief.
  Refinement alone returns a prompt without calling HeyGen.
  Add 'and generate' to show the refined prompt and cost for confirmation.

Mode:
  text_to_video       Describe a new scene; no media required.
  image_to_video      Animate one image as the literal first frame.
  reference_to_video  Guide a new scene with images/videos, plus optional audio.

Resolution: 480p (cheaper draft), 768p (more detail).
Duration: any integer from 5 to 15 seconds.
Aspect ratio: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16.
  Reference mode also accepts adaptive; image mode follows its first frame.
HeyGen prompt_enhancement (processed by HeyGen before generation):
  turbo     Fast expansion; the API default.
  quality   More thorough expansion.
  disabled  Sends your prompt unchanged.
  After Codex refinement, the skill chooses disabled unless you override it.
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
Enhancement default for a fully directed/Codex-refined prompt: disabled.
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
            for resolution in ("480p", "768p"):
                request = {"model": "heygen-video-1", "mode": mode,
                           "prompt": "Pricing example", "duration": 10, "resolution": resolution}
                if mode == "image_to_video":
                    request["image"] = {"type": "asset_id", "asset_id": "estimate-only"}
                elif mode == "reference_to_video":
                    request["reference_images"] = [{"type": "asset_id", "asset_id": "estimate-only"}]
                cost = estimate(request, None)
                print(f"{mode:20} {resolution:11} ${cost['rate_per_second']:10} ${cost['estimated_cost']}")
        print(f"Pricing date: {cost['as_of']}; basis: {cost['pricing']}.")
        print("Published promotion ends after October 2026; November standard rates are double.")
        print("Reference mode also bills input video seconds; image/audio references add no seconds.")
        print("Rates last verified 2026-10-05; verify current pricing and provider cutoff timezone.")
        print("Source: " + PRICING_SOURCE)
        return 0
    try:
        return {"create": create, "status": status, "upload": upload}[args.command](args) or 0
    except HTTPError as error:
        message = f"HeyGen/media HTTP {error.code}: {error.read().decode(errors='replace')}"
    except (ValueError, OSError, URLError, KeyError) as error:
        message = str(error)
    key = os.environ.get("HEYGEN_API_KEY")
    print(message.replace(key, "[REDACTED]") if key else message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
