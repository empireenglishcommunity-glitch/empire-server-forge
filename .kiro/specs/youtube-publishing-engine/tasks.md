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

- [ ] **3.1 Custom thumbnail upload** (long-form; Shorts optional). [engagement/CTR]
- [ ] **3.2 Post-publish velocity check** (24h underperformance flag). [R5.3]
- [ ] **3.3 Playlist assignment / end-screen linking** (session time). [algorithm]
- [ ] **3.4 Quota guard** — pre-flight quota check; defer non-critical ops. [R6.1, R6.3]

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
