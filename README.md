# HeyGen Video Skill

A Codex skill for generating short video clips with sound using HeyGen's `heygen-video-1` model. Start from a text description, animate an image, or guide a scene with reference media.

The skill can refine prompts, list options, estimate costs, submit jobs, and download completed videos with their returned seeds. It supports 5–15 second clips at 480p or 768p. It does not cover HeyGen's talking-avatar workflows.

## Install in Codex

Ask Codex to install the skill:

```text
$skill-installer install the skill from https://github.com/imknight/heygen-video-skill/tree/main/skills/heygen-video
```

For a local installation, copy the entire `skills/heygen-video` folder into `~/.agents/skills/heygen-video`. For a project-only installation, copy it into the project's `.agents/skills/heygen-video` folder instead.

Codex detects installed skills automatically. If the skill does not appear, restart Codex. See the [official skill installation guide](https://learn.chatgpt.com/docs/build-skills).

## Requirements and API key

- Codex with local skill and Python execution support.
- Python 3.9+ with IANA time-zone data for `Asia/Kuala_Lumpur`. The helper uses only Python's standard library. If your system lacks time-zone data, install it with `python3 -m pip install tzdata`.
- Your own HeyGen API key for uploads, generation, and job retrieval. Prompt refinement, options, and dry-run estimates do not require a key.

Get a key from [HeyGen's API settings](https://app.heygen.com/developers/api). A paid key needs `videos:write`, `videos:read`, and `assets:write` for uploads.

Set `HEYGEN_API_KEY` in the environment available to Codex and its Python process. For a terminal session:

```sh
export HEYGEN_API_KEY='your-api-key'
```

Keep your key local. Do not paste it into a chat or commit it to GitHub. You can also put it in the current project's `.env`: the skill instructs Codex to load only that value without displaying it. The Python helper does not load `.env` automatically, and an existing environment value takes precedence.

## Use the skill

Show available settings:

```text
$heygen-video options
```

Improve a prompt without generating a video:

```text
$heygen-video refine prompt: a coffee cup on a cafe table, soft morning light, slow camera push in, quiet cafe ambience, no music.
```

Refine a prompt and prepare a generation:

```text
$heygen-video refine prompt and generate: a coffee cup on a cafe table, text to video, 5 seconds, 480p, 16:9, live-action cinema, no music.
```

The skill presents the final prompt, settings, and estimated USD cost, then waits for your confirmation before paid generation. Each additional paid variation needs its own estimate and confirmation. Attach your media when requesting image or reference mode.

Store requests, job records, and downloaded videos in your project or output folder, outside the installed skill. If you work in this repository, use `outputs/`, which is ignored by Git. Retain job records to resume submissions and retrieve returned seeds.

## Python helper

From the repository root, list options without a key or network call:

```sh
python3 skills/heygen-video/scripts/heygen_video.py options
```

Using the request format in [SKILL.md](skills/heygen-video/SKILL.md#prepare-the-request), estimate a saved request without submitting it:

```sh
python3 skills/heygen-video/scripts/heygen_video.py create --request /absolute/path/request.json --dry-run
```

For video references, add `--input-video-seconds` with the measured total duration of all input videos. Reference mode bills input video seconds plus output seconds.

**Direct CLI submission bypasses the chat confirmation step:** running `create` without `--dry-run` submits a paid job. See [SKILL.md](skills/heygen-video/SKILL.md) for upload, submission, retrieval, and resumption instructions.

## Pricing

Estimates use a saved pricing schedule last verified on October 5, 2026, not a live billing quote. The helper switches from the published October promotion to standard rates on November 1, 2026, using Kuala Lumpur dates; the provider's cutoff timezone is unspecified. Verify [current official pricing](https://help.heygen.com/en/articles/17272995-introducing-heygen-video-generate-cinematic-clips-from-a-prompt) and your account pricing before spending.

## Package contents

```text
skills/heygen-video/
├── SKILL.md
├── agents/openai.yaml
├── scripts/heygen_video.py
└── references/prompt-refinement.md
```

This is a community skill, not an official HeyGen integration. Provider documentation remains attributed in the skill and its reference guide.

## License

[MIT](LICENSE). The license covers this skill's code and instructions; using HeyGen's API requires your own account and remains subject to HeyGen's terms and charges.
