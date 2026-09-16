# YouTube Publishing Engine — Requirements

> **Status:** Draft for build. Extends the existing "Social Publishing — Phase 1"
> n8n workflow (id `RdtmJTVYU4jFFCvF`) on the Hetzner n8n instance.
> **Scope:** the **YouTube** posting path only. Instagram is a separate, paused
> track (blocked on the MP4 `+faststart` fix, now shipped in
> `empire-video-forge` PR #7; IG resumes later).
> **Owner brand:** Empire English Community (EEC) — Arabic-first, MENA audience
> learning English.

---

## Background & problem

The current workflow uploads a clip to YouTube but with **no real metadata** —
title falls back to the raw filename, description/tags are empty. That is not
publishable and gets no reach. The owner wants a **professional,
algorithm-aware** engine: clips go up correctly optimized for the 2026 YouTube
algorithm, with engagement mechanics (pinned comment, scheduling, replies) so
videos actually gain views — while staying **inside YouTube's spam policy**
(no behavior that risks strikes/termination).

Uploads stay **private** so the owner reviews before publishing (their explicit
preference), except where scheduled publishing is used.

## Grounding (verified, cited — no guesswork)

The design is built on current, authoritative sources, not folklore:

- **Shorts ranking is behavioral, not metadata-keyword-driven.** YouTube's own
  help doc lists the Shorts signals as % of viewers who chose to view (vs swiped
  away), average view duration, average % viewed, and satisfaction (likes,
  post-watch surveys). [Google Support](https://support.google.com/youtube/answer/11914225)
- **Metadata's job on Shorts is classification + discovery** (who to show it to /
  search), not rank. [gyre.pro 2026](https://gyre.pro/blog/the-youtube-algorithm-how-it-works-in-2026)
- **Titles:** front-load the keyword within ~60 chars; **descriptions:** primary
  keyword in first ~150 chars. [w3era](https://www.w3era.com/blog/seo/youtube-seo-complete-guide/)
- **Tags are near-useless** (YouTube docs: mainly for misspellings) — do not
  over-invest. [webtonic](https://www.webtonic.io/blog/youtube-seo)
- **First 48 hours decide reach** — early engagement velocity is critical.
  [pixflow](https://pixflow.net/blog/youtube-seo-for-video-editors/)
- **Comment automation policy:** replying/moderating on **your own** channel via
  the official API is allowed; **auto-commenting on others' videos, or bulk /
  identical automated comments, is spam** → strikes/termination.
  [commentshark](https://www.commentshark.com/blog/youtube-comment-bot-tos-safe),
  [YouTube spam policy](https://support.google.com/youtube/answer/2801973)
- **Quota:** default 10,000 units/day; a video upload ≈ 1,600 units;
  `commentThreads.insert` = 50 units; list calls = 1 unit.
  [Google quota](https://developers.google.com/youtube/v3/determine_quota_cost)

*Sources rephrased/summarized for licensing compliance.*

## Locked decisions

- **D1 — Language:** metadata is **Arabic-primary, bilingual**. Title/description
  lead in Arabic (matches audience → correct classification), include key English
  learning terms (the content teaches English), hashtags mixed AR/EN. RTL text
  passes the ecosystem bidi rule before use.
- **D2 — Privacy:** default upload `private` (owner review). Scheduled publishing
  (`publishAt`) is opt-in per clip via metadata, targeting peak MENA hours.
- **D3 — Peak window:** default schedule target **Egypt time (EET), 19:00–22:00**.
- **D4 — Pinned comment:** an **Arabic engagement question** pinned on the video
  to seed comments (heaviest safe Shorts signal). One unique comment per own
  video — compliant.
- **D5 — Reply automation is human-in-the-loop:** AI drafts a varied, contextual
  reply → routed to the existing **admin Telegram bot** for one-tap approval →
  posted. No blind auto-reply, no identical text, no commenting on others' videos.
- **D6 — Tags de-emphasized:** a few relevant tags only; effort goes to title,
  description, hashtags, and engagement.

---

## Requirements

### R1 — Algorithm-aware metadata generation
**User story:** As the EEC channel owner, I want every uploaded clip to have a
professionally optimized Arabic-first title, description, and hashtags, so the
algorithm classifies and surfaces it to the right audience.

**Acceptance criteria (EARS):**
1. WHEN a clip is processed for YouTube, THE SYSTEM SHALL set a title that
   front-loads the primary topic keyword within the first 60 characters.
2. WHEN metadata (`<clip>_metadata.json`) is present alongside the clip, THE
   SYSTEM SHALL use its AI title/caption/hashtags as the source.
3. IF metadata is absent, THEN THE SYSTEM SHALL derive a clean human-readable
   title (stripping pipeline prefixes/underscores) — never the raw filename.
4. THE SYSTEM SHALL build a description that places the primary keyword within
   the first 150 characters and is at least 150 words where source text allows.
5. THE SYSTEM SHALL render title/description Arabic-primary with key English
   learning terms included, and SHALL keep hashtags in their own block (bidi-safe).
6. THE SYSTEM SHALL include 3–5 relevant hashtags (mixed AR/EN) and a small set
   of tags only (tags de-emphasized per policy).
7. THE SYSTEM SHALL append a brand sign-off and a CTA/engagement prompt to the
   description.

### R2 — Pinned engagement comment
**User story:** As the owner, I want an engagement question auto-posted and
pinned on each of my videos, so the comment section is seeded and the Shorts
engagement signal is boosted — compliantly.

**Acceptance criteria:**
1. WHEN a video finishes uploading AND has a video id, THE SYSTEM SHALL post one
   top-level comment on **that owned video** as the channel.
2. THE SYSTEM SHALL pin that comment.
3. THE comment SHALL be an Arabic engagement question in brand voice, and SHALL
   vary across videos (no identical repeated text) to stay policy-compliant.
4. IF the comment post fails (quota/permission), THEN THE SYSTEM SHALL log the
   failure to the ledger and continue (non-fatal).

### R3 — Peak-time scheduling
**User story:** As the owner, I want the option to schedule a clip to go public
at peak MENA hours, so it gets the early-velocity boost the algorithm rewards.

**Acceptance criteria:**
1. WHEN a clip's metadata requests scheduling, THE SYSTEM SHALL set `publishAt`
   to the next occurrence of the configured peak window (default EET 19:00–22:00).
2. WHEN scheduling is used, THE SYSTEM SHALL set privacy to `private` with a
   `publishAt` timestamp (YouTube auto-publishes at that time).
3. IF scheduling is not requested, THEN THE SYSTEM SHALL leave the video `private`
   for manual review (default).

### R4 — AI reply-to-comments with human approval (Phase 2)
**User story:** As the owner, I want new viewer comments on my videos to get a
contextual, on-brand reply that I approve with one tap, so I drive engagement
without spam risk or being glued to the app.

**Acceptance criteria:**
1. THE SYSTEM SHALL poll new top-level comments on the channel's recent videos
   using low-quota list calls.
2. WHEN a new comment is found, THE SYSTEM SHALL generate a contextual, varied
   reply in brand voice (Arabic/English matching the comment).
3. THE SYSTEM SHALL send the draft reply to the admin Telegram bot for approval.
4. WHEN the owner approves, THE SYSTEM SHALL post the reply to that comment as
   the channel; IF rejected, THE SYSTEM SHALL discard it.
5. THE SYSTEM SHALL never post identical replies in bulk and SHALL never comment
   on videos the channel does not own.

### R5 — Analytics feedback loop (Phase 2)
**User story:** As the owner, I want per-video performance (views, avg % viewed,
swipe-away) recorded, so we learn what works and improve.

**Acceptance criteria:**
1. THE SYSTEM SHALL record each publish (video id, title, schedule, timestamp)
   to the ledger.
2. WHERE the YouTube Analytics API is available, THE SYSTEM SHALL periodically
   fetch retention/velocity metrics per video and append them to the ledger.
3. WHERE a video underperforms a threshold within 24–48h, THE SYSTEM SHALL flag
   it (Telegram notice) for the owner.

### R6 — Quota & policy safety (cross-cutting)
**Acceptance criteria:**
1. THE SYSTEM SHALL stay within the 10,000-unit/day quota; comment/analytics
   polling SHALL use list calls (1 unit) and batch where possible.
2. THE SYSTEM SHALL never perform actions that violate YouTube's spam policy
   (no auto-comment on non-owned videos, no bulk identical comments).
3. WHERE quota is at risk, THE SYSTEM SHALL prioritize uploads over comment ops
   and defer non-critical polling.
4. THE SYSTEM SHALL keep uploads `private` unless scheduling is explicitly
   requested, preserving owner review.

### R7 — Isolation from Instagram
**Acceptance criteria:**
1. THE YouTube path SHALL run independently of the Instagram branch so IG errors
   never block or fail a YouTube publish.
