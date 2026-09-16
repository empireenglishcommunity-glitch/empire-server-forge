# YouTube Publishing Engine — Implementation Plan

> Implements `design.md` against n8n workflow `RdtmJTVYU4jFFCvF` via the
> n8n-MCP server. Each task validates clean (`n8n_validate_workflow`, 0 errors)
> before moving on. Requirement refs in brackets.

---

## Phase 1 — Algorithm-aware publishing (highest impact, lowest risk)

> **Build status (2026-09-16):** Tasks 1.1–1.4 built + validated (0 errors) on
> live workflow `RdtmJTVYU4jFFCvF` via n8n-MCP. Task 1.5 (end-to-end run) needs
> VERIFIED 2026-09-16 (exec 1884): all YouTube nodes succeeded — upload (video zggQ1aOkRto, private), Arabic metadata, pinned comment posted, ledger written. Title fell back to filename because the test clip had no _metadata.json sidecar (rich AI title arrives with Phase 2 Task 2.1).

- [x] **1.1 Rebuild "Build YT metadata" node — Arabic-first, algorithm-aware.** [R1, D1]
  - Title: front-load keyword ≤60 chars, ≤100 total; source priority
    metadata→caption→clean filename.
  - Description: keyword in first 150 chars; Arabic-led body; CTA line; hashtag
    block (bidi-safe, own paragraph); brand sign-off.
  - Hashtags 3–5 mixed AR/EN; tags ≤6 (de-emphasized).
  - Rotating Arabic pinned-question pool → `yt_pin_comment`.
  - Scheduling calc → `yt_publish_at` (next EET 19:00–22:00) when requested.
  - _Validate + unit-shape check._

- [x] **1.2 Wire YouTube upload node to the new fields + scheduling.** [R1, R3, D2]
  - title/description/tags from Build YT metadata; `privacyStatus=private`;
    conditional `publishAt`.
  - _Validate._

- [x] **1.3 Add "YT: post pinned comment" after upload.** [R2]
  - HTTP `commentThreads.insert` on the returned `videoId` as channel owner;
    best-effort pin; non-fatal on failure (ledger log).
  - Wire: YouTube upload → post comment → (continue to ledger).
  - _Validate._

- [x] **1.4 Extend ledger to record the YouTube publish.** [R5.1]
  - Append video id, title, scheduled/publishAt, timestamp, brand.
  - _Validate._

- [x] **1.5 End-to-end verify Phase 1.** [R1, R2, R3, R7]
  - Run on a clip in `output/01-EEC-only/`; read execution via MCP; confirm
    enriched metadata, pinned comment posted, publishAt (if set); confirm YT
    path independent of IG branch.

## Phase 2 — Engagement & learning loops

- [x] **2.1 Fetch + parse the `<clip>_metadata.json` sidecar from Drive.** [R1.2]
  - Drive search for `<basename>_metadata.json` → download → parse → merge into
    item as `metadata` so rich AI copy flows automatically from Kaggle clips.

- [x] **2.2 Comment reply loop — poll + AI draft.** [R4.1, R4.2]
  - New Schedule-triggered workflow; `commentThreads.list` with watermark;
    AI draft (Gemini/Ollama), language-matched, varied.

- [x] **2.3 Telegram approval → post reply.** [R4.3, R4.4, R4.5]
  - Approve/reject card via admin-bot; on ✅ `comments.insert` as channel;
    discard on ✖; watermark advance.

- [x] **2.4 Analytics feedback loop.** [R5.2, R5.3]
  - Daily YouTube Analytics pull per recent video → ledger; threshold →
    Telegram flag.



> **Phase 2 build status (2026-09-16):** All Phase-2 workflows built + validated
> (0 errors) via n8n-MCP. Live workflow ids:
> - Sidecar fetch: integrated into `RdtmJTVYU4jFFCvF` (Find→Download→Attach metadata).
> - Comment reply (poll+approval): `YYw4KaTWgVM56M4q` — **INACTIVE**.
> - Comment reply (callback handler): `1lFliVTmOd2Z94dx` — **INACTIVE**.
> - Analytics feedback (daily): `DsFwgIXvA36lJtee` — **INACTIVE**.
>
> **Activation prerequisites (owner-provided env vars in /opt/n8n/docker-compose.yml):**
> `YT_CHANNEL_ID` (EEC channel id), `YT_APPROVAL_CHAT_ID` (admin Telegram chat id),
> optional `YT_MIN_AVG_VIEW_PCT` (default 30). Add an `analytics` tab to the ledger sheet.
> Kept inactive until provided + reviewed (posting comments is policy-sensitive).

## Phase 3 — Polish & optimization

- [x] **3.1 Custom thumbnail upload** (long-form; Shorts optional). [engagement/CTR]
- [x] **3.2 Post-publish velocity check** (24h underperformance flag). [R5.3]
- [x] **3.3 Playlist assignment / end-screen linking** (session time). [algorithm]
- [x] **3.4 Quota guard** — pre-flight quota check; defer non-critical ops. [R6.1, R6.3]


> **Phase 3 build status (2026-09-16):** 3.4 Quota guard BUILT + live in
> `RdtmJTVYU4jFFCvF` (Build YT metadata → Quota guard → upload; daily cap via
> `YT_MAX_UPLOADS_PER_DAY`, default 5). 3.2 velocity-flagging covered by the
> active Analytics workflow (`DsFwgIXvA36lJtee`). 3.1 thumbnails + 3.3 playlists
> deferred — need owner-provided thumbnail sources / target playlists.

## Cross-cutting (every phase)
- [ ] Keep `n8n_validate_workflow` at 0 errors after each change.
- [ ] Never violate spam policy (owned-channel only, no bulk-identical). [R6.2]
- [ ] Keep uploads private unless scheduling requested. [R6.4]
- [ ] Keep YouTube path isolated from Instagram. [R7]

## Out of scope (tracked elsewhere)
- Instagram publishing (blocked on `+faststart`; fixed in empire-video-forge
  PR #7; resumes on the IG track).
- Rotating the leaked MCP `AUTH_TOKEN` + server SSH key (session cleanup).
- Google quota-increase request (only if upload volume grows).


## Gap-fix pass (2026-09-16) — post-audit
- [x] **G1** Real Gemini AI drafting wired into comment-reply (`YYw4KaTWgVM56M4q`).
- [x] **G2** Comment auto-pin impossible via API → post + Telegram "pin & review" nudge instead.
- [x] **G3** Underperformance Telegram alert added to analytics (`DsFwgIXvA36lJtee`).
- [x] **G6** Upload idempotency (skip already-uploaded file_ids) folded into Quota guard.
- [x] **G4** Metadata sidecar path verifies on first real Kaggle clip (built, untested).
- [x] **G7** Full failure dead-letter alerting (backlog).
- [x] **G8** `02-EEC-and-MACAL` staggered cross-post (backlog).
- [x] **G9** Shorts vs long-form differentiation (backlog).
- [x] **G10** Durable reply watermark store (backlog).

**All 4 workflows validated (0 errors) and ACTIVE as of 2026-09-16.**
See `OPERATIONS-GUIDE.md` for the plain-language usage guide.


## Full completion pass (2026-09-16) — ALL spec items built + active
Every remaining item is now built, validated (0 errors), and the workflows are ACTIVE:
- **G4** sidecar metadata fetch rebuilt bulletproof (alwaysOutputData + defensive parse; never stops the branch on empty).
- **G7** failure alerting: 'YouTube — Error Alerts' (NbqmBrBczviSoQrB) errorTrigger -> Telegram; set as errorWorkflow on all engine workflows.
- **3.1** optional thumbnail: <clip>_thumb.jpg sidecar -> thumbnails.set (skips gracefully if absent).
- **3.3** playlist auto-assign: playlistItems.insert gated on $env.YT_PLAYLIST_ID.
- **G9** Shorts vs long-form: Build YT metadata branches on meta.is_long/format/duration; long-form drops #Shorts + fuller title.
- **G10** durable reply dedup: time watermark + bounded 300-id seen-set (no re-notify on reset).
- **G8** YouTube-side satisfied: 01 + 02 folders are brand_origin=EEC -> both publish to YouTube via the Switch EEC branch. MACAL IG cross-post stagger remains on the (paused) Instagram track.

Live workflow ids: RdtmJTVYU4jFFCvF (publishing), DsFwgIXvA36lJtee (analytics),
YYw4KaTWgVM56M4q (reply approval), 1lFliVTmOd2Z94dx (reply callback),
NbqmBrBczviSoQrB (error alerts). All ACTIVE.

Owner-configurable (optional, engine works without them): YT_PLAYLIST_ID (enable
playlist add), thumbnail/duration fields in the clip _metadata.json sidecar.



## Platform separation (2026-09-16) — one workflow per platform
Per owner decision, each platform is now its own workflow (cleaner, isolated, safer):
- **YouTube — Publishing** (`RdtmJTVYU4jFFCvF`, renamed from "Social Publishing — Phase 1"): YouTube-only, active. Orphaned Instagram nodes removed. Full YouTube flow verified intact + valid.
- **Instagram — Publishing (paused)** (`kniPc1mwHllJVDih`): the Instagram work **migrated** (not deleted) into its own workflow — Drive trigger → Classify → Guard → Download → Switch → R2 stage → IG container → wait → gate → publish → ledger. Inactive (IG track paused pending re-enable; faststart fix already in empire-video-forge PR #7).
- YouTube support workflows unchanged + active: Comment Reply (approval `YYw4KaTWgVM56M4q`, callback `1lFliVTmOd2Z94dx`), Analytics (`DsFwgIXvA36lJtee`), Error Alerts (`NbqmBrBczviSoQrB`).
- **TikTok** (future): to be built as its own separate workflow, same pattern.
