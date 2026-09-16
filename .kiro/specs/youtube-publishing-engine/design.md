# YouTube Publishing Engine — Design

> Implements `requirements.md`. Extends n8n workflow `RdtmJTVYU4jFFCvF`
> ("Social Publishing — Phase 1") on the Hetzner instance
> (`bot.empireenglish.online`), built/edited via the n8n-MCP server.

---

## 1. Architecture overview

The engine is the **YouTube branch** of the existing Drive-triggered publishing
workflow, plus two out-of-band loops (comment reply, analytics) that run on
their own schedules.

```
                          ┌─ (existing) Drive Trigger → Classify → Guard → Download → Switch(brand)
                          │
Switch [EEC branch #0] ───┼──► Build YT metadata ──► YouTube: upload (private[/publishAt])
                          │            (R1)                    │ (R3)
                          │                                    ├──► YT: post pinned comment (R2)
                          │                                    └──► Ledger: append publish row (R5.1)
                          └──► R2 stage (IG)  ... (paused IG branch, untouched)

Out-of-band (own schedule triggers):
  [Schedule ~ every 30 min] → YT: list new comments (R4.1, 1u) → AI draft reply (R4.2)
        → Telegram approve (R4.3) → on ✅ → YT: reply as channel (R4.4)
  [Schedule ~ daily]        → YT Analytics: fetch per-video metrics (R5.2)
        → Ledger append; threshold check → Telegram flag (R5.3)
```

### Why this shape
- **Shorts ranking is behavioral**, so the engine's leverage is: (a) correct
  **classification** via Arabic-first metadata (R1), (b) **seeding engagement**
  via a pinned question (R2), (c) hitting the **first-48h velocity window** via
  scheduling (R3), and (d) sustaining engagement via **approved replies** (R4).
  Metadata is necessary but not sufficient — the content's hook does the heavy
  lifting; the engine maximizes everything around it that is automatable safely.

---

## 2. Component design

### 2.1 Build YT metadata (Code node) — R1
Input: item carrying `file_id`, `file_name`, `brand_origin`, and (when present)
a parsed `metadata` object from the clip's `<clip>_metadata.json`
(OpenShorts fields: `title`/`video_title_for_youtube_short`, `caption`,
`hashtags`, `hook`).

Output fields consumed by the YouTube node:
- `yt_title` — Arabic-primary, keyword front-loaded ≤60 chars, ≤100 total.
  Source priority: `metadata.video_title_for_youtube_short` → `metadata.title`
  → `metadata.caption` (first line) → cleaned filename fallback.
- `yt_description` — structure:
  1. Line 1 (≤150 chars): Arabic hook/keyword + core English term.
  2. Body: caption / expanded blurb (≥150 words where source allows), Arabic-led.
  3. CTA line: Arabic engagement prompt.
  4. Hashtag block (own paragraph, bidi-safe): 3–5 mixed AR/EN tags.
  5. Brand sign-off: `— Empire English Community`.
- `yt_tags` — ≤6 relevant tags (de-emphasized; mainly topical + brand).
- `yt_publish_at` — ISO timestamp if scheduling requested (see 2.3), else empty.
- `yt_pin_comment` — the Arabic engagement question for R2 (varied per video).

**Bidi safety:** any RTL string that mixes Latin tokens/hashtags is assembled so
hashtags live in their own block and never inline-mixed mid-sentence (ecosystem
bidi rule). A lightweight check runs in the Code node.

### 2.2 YouTube: upload — R3 / R1 sink
n8n `youTube` node, `resource=video, operation=upload`, `binaryProperty=clip`.
- `title = {{ $json.yt_title }}`
- `options.description = {{ $json.yt_description }}`
- `options.tags = {{ ($json.yt_tags||[]).join(',') }}`
- `options.categoryId = 27` (Education), `regionCode = US` (kept; classification
  is language-driven, not regionCode-driven)
- `options.privacyStatus = private`
- `options.publishAt = {{ $json.yt_publish_at }}` **only when set** (YouTube
  requires privacy `private` + a future `publishAt`; it auto-goes-public then).

### 2.3 Scheduling helper — R3
Computed inside Build YT metadata: if `metadata.schedule === true` (or a global
default toggle), compute the next EET 19:00–22:00 slot as an ISO8601 UTC string
(EET = UTC+2; target 19:00 EET = 17:00 UTC). If the next slot today has passed,
use tomorrow. Emitted as `yt_publish_at`. Absent → video stays private.

### 2.4 Pinned engagement comment — R2
After a successful upload (node outputs the new `videoId`):
- **Post:** HTTP `POST https://www.googleapis.com/youtube/v3/commentThreads?part=snippet`
  with body `{snippet:{videoId, topLevelComment:{snippet:{textOriginal: <question>}}}}`,
  authorized by the same `YouTube - EEC` OAuth (channel-owner). Quota 50u.
- **Pin:** pinning is a channel-owner action; via API use
  `comments.setModerationStatus` is **not** pin — pinning is done through the
  `commentThreads`/`comments` owner action. If the API cannot pin reliably, the
  comment is still posted (seeds section); pin is best-effort and logged.
- Question text: pulled from `yt_pin_comment`, chosen from a **rotating pool** of
  Arabic brand questions so no two videos get identical text (R2.3 / policy).
- Failure is non-fatal (R2.4): logged to ledger, workflow continues.

### 2.5 Comment reply loop (Phase 2) — R4
Separate workflow, **Schedule trigger** (~30 min):
1. `commentThreads.list?part=snippet&allThreadsRelatedToChannelId=<id>&order=time`
   (1u) → filter to new since last run (watermark stored in a Data table / sheet).
2. For each new top-level comment: AI drafts a **contextual, varied** reply
   (Gemini free tier / local Ollama), language-matched to the comment.
3. Send to **admin Telegram bot** (existing in `empire-server-forge/admin-bot`)
   as an approve/reject card carrying the comment id + draft.
4. On ✅ callback → `comments.insert` (reply, 50u) as channel. On ✖ → discard.
5. Never bulk-identical, never non-owned videos (R4.5). Watermark prevents
   re-processing.

### 2.6 Analytics loop (Phase 2) — R5
Separate workflow, **Schedule trigger** (daily):
- YouTube Analytics API per recent video: views, averageViewPercentage,
  averageViewDuration, shares. Append to ledger. Threshold check (e.g. avg %
  viewed < X within 24–48h) → Telegram flag.

---

## 3. Data flow & the metadata sidecar

The OpenShorts pipeline emits `<clip>_metadata.json` next to each clip with
`title`, `caption`, `hashtags`, `hook`. **Current gap:** the workflow does not
fetch the sidecar yet. Phase 1 builds Build-YT-metadata to *consume* it when
present, with a clean fallback when absent (manual uploads). A later task adds an
explicit Drive fetch+parse of the sidecar so rich AI copy flows automatically
once clips arrive from Kaggle.

---

## 4. API, quota & compliance constraints

| Operation | Quota | Notes |
|---|---|---|
| video upload | ~1600u | dominant cost; ~6 uploads/day within default 10k |
| commentThreads.insert (pin comment) | 50u | one per upload |
| commentThreads.list (reply poll) | 1u | cheap; batch/paginate |
| comments.insert (reply) | 50u | only on approval |
| Analytics query | ~1u+ | daily batch |

- Stay under 10,000u/day (R6.1). If volume grows, file a Google quota-increase
  request (free form) — flagged as a future op, not needed at current volume.
- **Compliance boundaries (hard):** replies/moderation on **owned** channel only;
  never comment on non-owned videos; never bulk-identical text (R6.2). Human
  approval in R4 keeps replies organic.
- Uploads remain `private` unless scheduled (R6.4 / D2).

## 5. Security
- All secrets stay in n8n's encrypted credential store; env vars hold only
  non-secret ids (`IG_*_USER_ID`, `R2_*`, `LEDGER_SHEET_ID`, channel id).
- Reuses existing creds: `YouTube - EEC` (OAuth, channel-owner scope),
  `Google Sheets account` (ledger), Telegram admin-bot creds.
- The MCP `AUTH_TOKEN` used to build this and the leaked SSH key tail are to be
  **rotated** (tracked in the session cleanup list) — operational, not part of
  the running engine.

## 6. Error handling
- Metadata build: pure/defensive; always returns a valid item (fallback title).
- Upload failure: surfaces the real API error (already improved during the
  publishing test); ledger records the attempt.
- Pinned comment / analytics: **non-fatal** — log + continue (R2.4).
- YouTube path is **isolated** from the Instagram branch (R7): a Switch fan-out,
  separate node chains, so IG's paused/broken state cannot fail a YT publish.

## 7. Testing strategy
- Per node: `n8n_validate_workflow` clean (0 errors) after each change.
- End-to-end: manual `Execute Workflow` on a clip in `output/01-EEC-only/`;
  verify via MCP execution read that YouTube received enriched title/description/
  tags, the pinned comment posted, and `publishAt` (when requested) is set.
- Confirm on YouTube Studio: private video shows real metadata + pinned comment.
