# Social Publishing Workflow — Build Notes

> Implements `docs/SOCIAL-PUBLISHING-DESIGN.md`. This folder holds the n8n
> workflow JSON for the publishing pipeline, built incrementally per the
> design's build order (§6). **Credentials are referenced by name only — no
> secret values here** (design §5, rule 1).
>
> **Status:** Phase 1 (plumbing + YouTube + Instagram) — JSON authored, not
> yet imported/tested in n8n. TikTok draft flow is Phase 3.

## What connects to what

Upstream: `empire-video-forge`'s batch runner writes finished clips into
Google Drive routing folders:

```
Drive: /empire-video-forge/output/01-EEC-only/     → EEC YouTube, EEC Instagram, (EEC TikTok)
Drive: /empire-video-forge/output/02-EEC-and-MACAL/ → all
Drive: /empire-video-forge/output/03-MACAL-only/    → MACAL Instagram, (MACAL TikTok)
```

Alongside each clip is its `<name>_metadata.json` (from OpenShorts) containing
per-platform titles, hooks, captions and hashtags. The workflow reads that for
copy instead of re-transcribing.

## The safety-critical routing (design §2) — how the JSON enforces it

The forbidden direction (MACAL → EEC) is made **structurally impossible**, not
just handled:

1. **Credential isolation (primary guard).** The workflow has **separate
   branches per brand**. The MACAL branch's nodes reference **only** MACAL
   credentials (`IG MACAL`, `TikTok MACAL`). No EEC credential (`YT EEC`,
   `IG EEC`) is attached to any node reachable from the `03-MACAL-only` path.
   A logic bug cannot post MACAL content to EEC because the EEC token is not
   reachable from that branch.
2. **Pre-publish assertion (Code node `guard-brand-routing`).** Every job
   object carries `brand_origin` and resolved `destinations[]`. Before any
   publish node runs:
   `if (brand_origin === 'MACAL' && destinations.some(d => d.brand === 'EEC')) throw` —
   aborts the **whole** job (no partial publish).
3. **Ledger row (Google Sheets append).** Every destination attempt writes
   `brand_origin` + destination + status, so a misroute is detectable after
   the fact.

Routing is derived purely from the **Drive folder** the file was found in —
never from filename or content (design §2 mechanism).

## Node graph (Phase 1)

```
[Google Drive Trigger: watch output/ recursively]
        ↓
[Code: classify]  — derive brand_origin + destinations[] from the parent folder
        ↓
[Code: guard-brand-routing]  — the pre-publish assertion (fail-closed)
        ↓
[Read metadata.json sibling from Drive]  — titles/captions/hashtags
        ↓
[Download clip bytes from Drive]
        ↓
        ├───────────────  Switch on brand_origin  ───────────────┐
        │ (EEC branch — EEC creds only)     │ (MACAL branch — MACAL creds only)
        ↓                                   ↓
  [YouTube: videos.insert (EEC)]      (MACAL has no YouTube destination)
  [Stage→R2] → [IG EEC: REELS]        [Stage→R2] → [IG MACAL: REELS]
        ↓                                   ↓
  [Ledger append]                     [Ledger append]
        ↓                                   ↓
  [Purge R2 staged object]            [Purge R2 staged object]
```

Cross-post (`02-EEC-and-MACAL`) resolves to both brands but **staggers** MACAL
by 24–48h and uses a **distinct caption** (design §2) — implemented as a
`Wait`/scheduled re-enqueue on the MACAL branch, Phase 2.

> ⚠️ **KNOWN DEFERRED (Phase 2):** In `phase1.json`, the Switch routes by
> `brand_origin`, so a `02-EEC-and-MACAL` file (origin `EEC`) currently goes
> down the **EEC branch only** — it posts to EEC YouTube + EEC Instagram but
> does **not** yet fan out the staggered MACAL cross-post. This matches the
> design's build order (§6 defers cross-post staggering to Phase 2). It is a
> deliberate, documented gap, not a silent one. The safety direction is
> unaffected: this only *omits* an allowed MACAL cross-post; it never sends
> MACAL-origin content to EEC.

> ⚠️ **Metadata/caption reading is stubbed in Phase 1.** The nodes reference
> `$json.yt_title`, `$json.ig_caption`, etc., but Phase 1 does not yet fetch
> and parse the sibling `<name>_metadata.json` from Drive. Until that node is
> added (Phase 1.1), captions fall back to empty / the filename. Wire the
> metadata fetch before relying on auto-captions. This keeps the risky media
> path testable first (design §6: "captions typed by hand" initially).

## Per-platform mechanics baked in (design §4)

- **YouTube:** `videos.insert`, resumable; vertical + ≤3min auto-classifies as
  a Short. Own quota bucket (100 uploads/day) — non-issue.
- **Instagram:** cannot POST bytes — Meta cURLs a public URL. So: upload clip
  to **R2** (`social-staging.empireenglish.online`) → create media container
  with `media_type=REELS` (NOT `VIDEO`) → poll container status → `media_publish`
  → delete the R2 object. `graph.instagram.com` (Instagram Login), dev mode ok.
- **TikTok (Phase 3):** `MEDIA_UPLOAD` inbox/draft flow via the **sandbox** app;
  `creator_info` query before each publish; owner taps publish in-app. Never
  `video.publish` (forces private on unaudited clients).

## Credentials this workflow references (by NAME — set in n8n cred store)

| Credential name in n8n | Type | For |
|---|---|---|
| `Google Drive - empire` | Google Drive OAuth2 | Drive trigger + download |
| `YouTube - EEC` | YouTube OAuth2 | EEC YouTube upload |
| `IG - EEC` | HTTP Header Auth (IG token) | EEC Instagram |
| `IG - MACAL` | HTTP Header Auth (IG token) | MACAL Instagram |
| `R2 - social-staging` | S3 (Cloudflare R2) | stage/purge for IG |
| `Google Sheets - ledger` | Google Sheets OAuth2 | ledger |
| `TikTok - EEC` / `TikTok - MACAL` | OAuth2 (Phase 3) | TikTok drafts |

n8n non-secret config values live in server env vars (e.g. `IG_EEC_USER_ID`,
`IG_MACAL_USER_ID`, `R2_PUBLIC_BASE`, `R2_BUCKET`), never hardcoded.

## Import steps (when ready)

1. n8n → + Add workflow → ⋯ → Import from file → `social-publishing-phase1.json`.
2. Attach the named credentials to each node (they're placeholders on import).
3. Set the env vars above on the n8n server.
4. Test with ONE clip in `output/01-EEC-only/` → YouTube first, then IG.
5. Only after EEC works end-to-end, exercise the MACAL branch.

## Open items (from design §7)

- Long-form YouTube thumbnails (Shorts don't need them).
- Bidi rule on Arabic captions: hashtags in their own block, never inline.
- Per-brand posting slots (needed for the Phase 2 scheduling queue).
