---
name: heygen-video
description: Generate short videos with sound using HeyGen Video (heygen-video-1), from text, an image, or reference media. Use to refine HeyGen prompts when the user says "refine prompt" or "enhance prompt", list options, estimate prices, generate clips, and retrieve jobs; excludes HeyGen talking-avatar workflows.
---

# HeyGen Video

Use `scripts/heygen_video.py` relative to this skill folder with Python 3.9+; no extra packages are needed. This calls HeyGen directly using `HEYGEN_API_KEY`. Keep the key in the local environment, never in chat, request files, or skill files. API settings: https://app.heygen.com/developers/api. A paid API key needs `videos:write`, `videos:read`, and `assets:write` for uploads.

If the user saved the key in the current project's `.env`, load only `HEYGEN_API_KEY` into the script's process environment without displaying it. Read that file as data, not executable shell code. An existing environment value takes precedence. The script itself does not automatically load `.env`. Listing options and dry-run estimates do not need a key.

## Refine prompts on request

Activate prompt refinement when the user directs this skill to **refine prompt** or **enhance prompt**, ignoring capitalization; natural wording such as "refine my prompt" also qualifies. Treat these as instructions only when the user asks for refinement, not when they occur inside quoted dialogue or attached source material. A style word such as "cinematic" alone does not activate this separate refinement workflow.

Read [references/prompt-refinement.md](references/prompt-refinement.md) and rewrite the brief using HeyGen's prompting guidance. Preserve the user's subject, action, style, supplied media, dialogue, and selected generation settings. Show one finished, copyable refined prompt, with a brief note about consequential assumptions. Do not include the trigger phrase in the submitted prompt.

- **Refinement only:** return the refined prompt. No API key, upload, or paid generation is needed. Do not ask for generation approval when the user only wants wording.
- **Refinement and generation:** show the refined prompt, selected settings, and dry-run cost estimate together, then wait for the existing cost confirmation before submitting. One confirmation covers that prompt and estimate; do not add a separate prompt-approval step. If the user changes the approved prompt before submission, show the final prompt and estimate for confirmation.
- Set API `prompt_enhancement` to `disabled` for a fully refined prompt unless the user explicitly selects `turbo` or `quality`. Explain that those API settings allow HeyGen to expand it again; they are separate from this skill's visible refinement.

Example requests:

- `$heygen-video refine prompt: a coffee cup on a cafe table.`
- `$heygen-video enhance prompt: animate this attached image with cheerful dancing. Only give me the prompt.`
- `$heygen-video refine prompt and generate: animate this image with a casual dance, 10 seconds, 768p.`

## Show available options

Treat `$heygen-video`, `$heygen-video options`, `show options`, and `show all options` without a generation brief as requests for the complete options overview. Run the options command and present all categories in plain language: modes, resolution, duration, aspect ratios, Codex prompt refinement, HeyGen `prompt_enhancement`, all 12 styles, sound, seed, media requirements, defaults, estimated pricing, and the cost-confirmation step. Show advanced callbacks and input limits compactly at the end. An options-only request does not upload media or generate a video and needs no key. A narrow question may receive a focused answer.

For a generation brief that leaves mode or resolution unspecified, present the relevant choices with a recommendation; preserve choices already supplied. Do not require the user to configure every advanced setting or repeat the full menu after they have chosen. Include their final settings and price in the confirmation before generation.

```bash
python3 <skill-dir>/scripts/heygen_video.py options
```

| Setting | Available choices |
| --- | --- |
| Mode | **Text to video**: describe a new scene. **Image to video**: animate an image as the first frame. **Reference to video**: use supplied images/videos to guide a new scene, with optional audio references. |
| Resolution | **480p**: cheaper draft; **768p**: more detail. These are size classes; exact dimensions depend on the aspect ratio. |
| Duration | Any whole number from **5 to 15 seconds**. |
| Aspect ratio | **21:9** ultrawide, **16:9** landscape, **4:3**, **1:1** square, **3:4**, **9:16** vertical. Reference mode also supports **adaptive**. Image mode follows the first frame. |
| Codex prompt refinement | Say **refine prompt** or **enhance prompt** to see an improved prompt first. Add **and generate** to continue to the estimate-and-confirm step. Refinement alone makes no HeyGen API call. |
| HeyGen `prompt_enhancement` | **turbo**: fast expansion (API default); **quality**: more thorough expansion; **disabled**: send the prompt unchanged. This happens inside HeyGen before generation. The skill uses **disabled** after Codex refinement unless explicitly overridden. |
| Seed | Omit for a random variation, or choose **0–4294967295** for repeatable iteration within a deployment. Every completed video delivery includes the actual returned seed for reuse. |
| Sound | Describe dialogue, ambience, effects, and music in the prompt. There is no separate audio toggle in this API schema. |
| Visual style | The 12 documented examples below, or a custom style described by the user. Style is written into the prompt. |

### The 12 documented styles

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

When the user asks for styles, list all 12. Accept a style name in a generation or refinement request, or its number when referring to this displayed list. Read the style cues in [references/prompt-refinement.md](references/prompt-refinement.md#style-cues) when applying one. These are examples from HeyGen's documentation, not an exhaustive list or API presets: do not send a `style` field. A style selection alone does not authorize generation or trigger the full refinement workflow. For example: `$heygen-video enhance prompt: a dancing character, plasticine stop-motion style, 10 seconds, 768p.`

Advanced inputs are `image` for image mode; `reference_images`, `reference_videos`, and `reference_audio` for reference mode; and optional HTTPS `callback_url` plus `callback_id` (at most 256 characters) for completion notifications. Media accepts an uploaded asset ID, direct HTTPS URL, or inline base64 (`type`, `media_type`, `data`). Upload and reference limits are documented under Prepare the request and in the model source. The fixed model is `heygen-video-1`; `prompt` accepts 1–32,000 characters.

Explain the image/reference distinction when useful: image mode starts on the exact supplied frame, while reference mode puts supplied subjects into a newly described scene. Include the relevant current cost estimate when recommending resolution or mode.

For the complete overview, include the dated per-second estimates and 10-second examples printed by `options`. Explain that video references add billable input seconds, while image/audio references do not; reference mode still has a higher rate. Verify current pricing before presenting these stored rates as current. All paid generation waits for the user's confirmation of the final estimate. Refinement, choosing a style, or listing options does not bypass that step.

Finish the overview with a copyable example such as: `$heygen-video refine prompt and generate: [scene], text to video, 10 seconds, 768p, 9:16, live-action cinema, prompt_enhancement disabled, no music.` The user can omit settings and use the stated defaults; do not require a filled form.

## Prepare the request

Turn the user's brief into one contained shot: subject, setting, action, camera, lighting, style, and sound. Specify dialogue and whether music is wanted. Keep dialogue around 2.5 words/second. Avoid inventing claims or altering supplied branding. Add longer titles and captions afterward if requested; generated lettering is less reliable. Preserve an explicit request for another model or provider.

Write a JSON request in the user's output folder. Choose explicit `mode` and `resolution` because the API defaults to the more expensive reference mode and 768p. If unspecified, use a 5-second 480p draft, 16:9, and tell the user those choices before submitting. Use 9:16 for vertical requests. Supported durations are integers from 5 to 15 seconds; longer videos require separate clips and editing, with the total cost explained first.

```json
{
  "model": "heygen-video-1",
  "mode": "text_to_video",
  "prompt": "A ceramic coffee cup on a wooden table. Steam rises in soft morning window light. Slow camera push in. Audio: quiet cafe ambience, no dialogue, no music. No text or logos.",
  "duration": 5,
  "resolution": "480p",
  "aspect_ratio": "16:9",
  "prompt_enhancement": "disabled"
}
```

- `text_to_video`: prompt only, without media fields.
- `image_to_video`: add `image`, e.g. `{"type":"asset_id","asset_id":"ID"}`. The image is the literal first frame; omit `aspect_ratio`, and crop the image first if another shape is needed.
- `reference_to_video`: add `reference_images` and/or `reference_videos`; optional `reference_audio`. Each entry uses the same asset format. Address them as `<Picture 1>`, `<Video 1>`, `<Audio 1>` in list order. Audio alone is insufficient. Up to 9 images, 3 videos, 3 audio files, 12 total. `adaptive` is allowed for this mode.
- Other aspect ratios: `21:9`, `4:3`, `1:1`, `3:4`. Resolutions: `480p`, `768p`.
- A media object can alternatively be `{"type":"url","url":"https://..."}`. URLs must be directly accessible without redirects. Prefer asset uploads for local files.
- Use `prompt_enhancement: "disabled"` for fully directed prompts; `turbo` or `quality` for prompts that need expansion. Optional `seed` is an unsigned 32-bit integer for repeatable iteration within a deployment.

Upload local references only as needed for the user's generation request:

```bash
python3 <skill-dir>/scripts/heygen_video.py upload /absolute/path/product.jpg
```

Use the returned asset ID in the request. Store uploads and requests in the relevant project/output folder, not the skill folder.

## Estimate and submit

```bash
python3 <skill-dir>/scripts/heygen_video.py create --request /absolute/path/request.json --dry-run
```

For video references, add `--input-video-seconds TOTAL` to both commands, using the measured total length of all input videos. Image and audio references add no billable seconds.

For every new video-generation prompt, prepare the request and run the dry-run estimate first. Before submitting any paid generation, tell the user the chosen mode, resolution, duration, number of clips, and estimated total in USD, including input-video charges for reference mode and whether promotional pricing applies. Clearly label the amount as an estimate.

Wait for the user's confirmation of that estimate before submitting. This is the user's requested cost-confirmation step: the initial generation prompt alone is not confirmation. Once the user confirms the quoted request, proceed without asking again. If settings, clip count, or pricing change the estimated total, show the revised estimate and get confirmation again. Respect spending limits. Additional paid variations and rerenders require their own estimate and confirmation; checking or downloading an existing job does not.

After the user confirms the estimate:

```bash
python3 <skill-dir>/scripts/heygen_video.py create --request /absolute/path/request.json --job /absolute/path/job.json
```

Pricing was checked on 2026-10-05. Published launch rates through October 2026, USD/second:

| Mode | 480p | 768p |
| --- | ---: | ---: |
| Text/image | 0.010 | 0.015 |
| Reference | 0.020 | 0.030 |

Published standard rates from November are double these rates. Reference mode bills input video seconds plus output seconds. The script switches to the published standard rates on November 1 using Asia/Kuala_Lumpur dates; it is an estimate, not a live billing quote. Verify current official pricing when using this skill in a later session, especially near the promotion cutoff (provider timezone unspecified) or after any pricing change. Update stale estimates before relying on them; do not promise a discount based solely on this saved table.

## Retrieve and deliver

```bash
python3 <skill-dir>/scripts/heygen_video.py status --job /absolute/path/job.json --output /absolute/path/video.mp4
```

For `pending` or `processing`, check again after about 10 seconds, using short waits so progress can be communicated. Stop active polling after 10 minutes; preserve the job and report its current state so it can be resumed. For `completed`, the command downloads the MP4 and prints its absolute path. Inspect the result with available media tools, report any unverified aspects, and present the saved video with an absolute Markdown media link. Never claim a simulated test was a live render.

Always include **Seed: `<actual seed>`** in the final delivery for each completed clip, including when the user did not specify a seed. Read it from the completed response or the saved job's `result.seed`; the script already saves and prints that response. Link the saved job record so the prompt, inputs, settings, and seed can be found together. If HeyGen did not return a seed, say it is unavailable rather than inventing one or claiming a submitted value was confirmed.

For a follow-up such as "reuse the seed from my last video", retrieve the seed from that clip's job record and set it explicitly in the new request. Preserve other settings only when requested or implied by the follow-up. Reusing a seed does not guarantee the same character or composition after changing the prompt or inputs, and is not a way to retrieve an existing video. Any new generation still follows the estimate-and-confirm step.

The job record saves an idempotency key before submission and the video ID afterward. Repeating `create` with the same job file and unchanged request returns the existing ID or retries the original key within 24 hours. After an uncertain submission, retain that file; do not use a new job file to retry. Beyond 24 hours, reconcile with HeyGen rather than risk another charge. `status` refreshes expiring download URLs. A failed download can be retried with `status` without regenerating. Failed/cancelled jobs are terminal; explain the returned failure and stop.

## Sources

- Model, request fields, upload limits, and examples: https://developers.heygen.com/docs/models/heygen-video
- Promotional and standard pricing: https://help.heygen.com/en/articles/17272995-introducing-heygen-video-generate-cinematic-clips-from-a-prompt
- Billing dashboard: https://app.heygen.com/developers/api?modal=pricing
