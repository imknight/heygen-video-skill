# HeyGen prompt refinement

Based on HeyGen's official [How to prompt it](https://developers.heygen.com/docs/models/heygen-video#how-to-prompt-it) and [Prompt enhancement](https://developers.heygen.com/docs/models/heygen-video#prompt-enhancement) sections, checked 2026-10-05.

## Rewrite the brief

Write concrete direction, usually a few hundred to a few thousand characters when the shot needs it. Avoid padding and contradictory constraints. A compact paragraph is enough for a simple shot; use sections only when multiple subjects or references need clarity.

1. **Scene and action:** identify the subject, setting, and visible action. Describe a feasible beginning, movement, and ending within the chosen duration. Prefer a contained shot, but preserve requested dancing, camera movement, or other action instead of replacing it with stillness.
2. **Camera:** specify framing, camera motion, and focus. For a photographic look, select a suitable camera/lens/aperture when helpful instead of relying on vague quality adjectives. For image mode, preserve the supplied first frame and its perspective.
3. **Surface and light:** describe material texture, light direction, and colour. When natural realism is intended, rule out unwanted smoothing or beauty treatment. Do not impose realism or a particular colour grade on a stylized brief.
4. **Motion and contact:** say what holds, touches, or supports what. Keep props consistent and movements physically legible. Avoid adding intricate hand work or extra actions that compete with the main action.
5. **Text and branding:** preserve supplied branding and exact requested wording. Exclude newly invented marks where appropriate; do not erase existing logos by adding a blanket prohibition. Keep generated lettering short. Suggest adding longer copy afterward, without promising extra editing that was not requested.
6. **Sound:** explicitly direct ambience, effects, dialogue, and music. Preserve supplied dialogue verbatim; flag when it cannot fit at roughly 2.5 words per second rather than silently rewriting it. If music or speech is unspecified, choose scene ambience with no dialogue or music and disclose that assumption.
7. **Style:** for illustration or animation, describe the production medium, surface marks, palette, and motion cadence. Do not automatically insert live-action camera language into a flat graphic treatment.

## Adapt to the input mode

- **Text:** describe the subject and scene sufficiently to create them from scratch.
- **Image:** inspect the supplied image, open on that exact frame, and describe what changes over time. Preserve its identity, outfit, objects, setting, and framing unless the user requests a change. Do not promise a new aspect ratio without cropping the input.
- **Reference:** inspect the supplied references and explain what each contributes using `<Picture 1>`, `<Video 1>`, and `<Audio 1>`. Match actual list order and never invent labels for media that was not supplied. Distinguish appearance preservation from requested motion or setting changes.

## Style cues

The names below come from the **Twelve styles** gallery in HeyGen's [model documentation](https://developers.heygen.com/docs/models/heygen-video). The cues are writing guidance for expanding a selected style, not additional API settings or guaranteed results. Name the medium and its visible characteristics; use only cues that fit the brief.

| Style | Useful direction to add to the prompt |
| --- | --- |
| Live-action cinema | Photographic materials, motivated lighting, an appropriate lens and depth of field, natural motion. |
| Plasticine stop-motion | Sculpted clay figures, small fingerprints and tool marks, miniature sets, deliberate frame-by-frame movement. |
| Hand-painted cel anime | Painted colour areas with inked contours, cel shadows, hand-drawn animation and painted scenery. |
| Pencil, fineliner and marker animation | Pencil construction lines, ink contours, translucent marker shading, visible paper, drawn motion. |
| Mid-century screen print | Flat graphic forms, restrained inks, halftone texture, slight print misalignment, limited animation. |
| Anime key drawing | Expressive key poses, confident construction lines, selective shading, a visible drawing surface. |
| Pencil sketch | Graphite strokes, hatching, smudges and paper grain maintained through the movement. |
| Marker rendering | Broad marker strokes, layered translucent tones, crisp contours and deliberate highlights. |
| Watercolour wash | Transparent pigment, soft colour bleeding, paper texture, gently varying painted edges. |
| Impasto oil | Thick paint ridges, visible brush or palette-knife work, canvas texture and animated painted forms. |
| Painted anime background | Detailed painted scenery, atmospheric depth and deliberate light; preserve any separately specified character style. |
| Plasticine model | A sculpted clay object or character with tangible volume and surface marks; specify motion separately. |

Preserve the distinction between plasticine material and stop-motion cadence, and between a background treatment and a character treatment. Custom styles remain allowed. Do not add colour restrictions or camera gear that conflict with the requested medium.

For image-to-video, the literal first frame retains the supplied image's look. If the user requests restyling, explicitly describe a transition from that frame. A clip stylized from its first frame needs an appropriately styled input image or a reference-mode approach; explain this instead of promising an immediate restyle or silently switching modes. Any input editing or mode change must stay within the user's request and the quoted cost-confirmation flow.

When useful, organize longer prompts as subject definitions, scene summary, elements to preserve, shot action, soundscape, and music direction. These are plain text within `prompt`, not extra API fields.

Keep mode, duration, resolution, aspect ratio, seed, and enhancement settings outside the prose prompt in the request settings. Preserve a supplied seed when iterating on an existing shot; explain that reproducibility is deployment-dependent. Never invent a seed from an earlier render that was not inspected.

Show the finished prompt and meaningful assumptions. Refinement does not itself call the video API or incur a HeyGen generation charge. If generation is also requested, follow the main skill's estimate-and-confirm workflow.
