# Social Publishing Pipeline — Design

> **Status: DESIGN ONLY — nothing is built or deployed.**
> No workflow exists in n8n, no credentials have been created, no table
> exists in any database. Do not read this file as a description of a
> running system. When it ships, `empire-chronicle/SYSTEM-MAP.md` must be
> updated in the same PR that deploys it.

**Purpose.** The owner films and edits content himself. Everything after
export — uploading to six destinations across two brands, writing
per-platform copy, scheduling, and tracking what went where — is manual and
costs 30–60 minutes a day. This pipeline removes that.

> **Upstream:** the *editing* half — turning long-form footage into finished
> 9:16 clips in a routing folder — is addressed separately in
> [`AUTO-EDIT-STAGE-DESIGN.md`](./AUTO-EDIT-STAGE-DESIGN.md). That stage
> feeds this one; the hand-off is "a file appears in a routing folder" and
> nothing below changes.

---

## 1. Destinations

Two brands. Six destinations.

| Brand | Destination | Automation ceiling |
|---|---|---|
| Empire English Community | YouTube (Shorts + long-form) | full |
| Empire English Community | Facebook Page | full |
| Empire English Community | Instagram | full |
| Empire English Community | TikTok | draft + 1 manual tap |
| MACAL (Makkal Empire) | Instagram | full |
| MACAL (Makkal Empire) | TikTok | draft + 1 manual tap |

**Four of six are fully hands-off. Two need one tap each.** The Facebook
*personal profile* is deliberately out of scope — Meta removed
`publish_actions` in April 2018 and there is no API to post to a personal
profile. That is not a gap to be worked around later; it does not exist.

### Why TikTok cannot be fully automated

An unaudited TikTok API client is forced to `SELF_ONLY` (private)
visibility, with no parameter that overrides it, and additionally caps at
5 users per 24h with accounts required to be private at post time. The
error is `unaudited_client_can_only_post_to_private_accounts`. Passing
TikTok's audit requires presenting a compliant third-party *product* UX;
mature open-source tools have failed to obtain it. So we use the
**inbox/draft** flow (`MEDIA_UPLOAD`): the pipeline pushes video + caption
into the TikTok inbox, the owner taps publish in the app and visibility is
chosen natively. This works with normal public accounts.

The only route to true TikTok auto-publish is borrowing a third party's
already-audited app, which means a paid subscription. Rejected: two taps a
day is cheaper than breaking the zero-paid-dependency constraint.

---

## 2. The routing rule is safety-critical

The owner's rule, exactly:

- **EEC content MAY go to both brands.** Teaching content is evidence for
  the founder brand.
- **MACAL content MUST NEVER reach EEC.** Personal-brand material on a
  student channel is off-message.

The rule is **asymmetric**, so the failure modes are not equal. A missed
cross-post is a lost impression. A MACAL video on an EEC student channel is
brand damage that deleting does not undo — the students already saw it.

**Therefore the forbidden direction is made structurally impossible, not
merely handled correctly.** Same principle as flags failing closed.

### Mechanism

Routing is decided by **which Drive folder the file is exported to**. No UI,
no toggle, no filename parsing — the owner is already choosing a folder in
the export dialog, so the routing decision costs zero extra steps and is
auditable after the fact.

```
01-EEC-only/        → EEC YouTube, EEC FB Page, EEC Instagram, EEC TikTok
02-EEC-and-MACAL/   → all six
03-MACAL-only/      → MACAL Instagram, MACAL TikTok
```

Three guards, in order of strength:

1. **Credential isolation (primary).** The MACAL branch of the workflow has
   *no EEC credential attached to any node*. There is no code path from
   folder `03` to an EEC token. A logic bug cannot produce the forbidden
   outcome, because the credential is not reachable.
2. **Pre-publish assertion.** Every job carries `brand_origin` and a
   resolved `destinations[]`. Before any network call:
   `assert not (brand_origin == 'MACAL' and any(d.brand == 'EEC'))`.
   On failure the **entire job aborts** — no partial publish. A job that
   half-published is harder to reason about than one that did nothing.
3. **Ledger record.** `brand_origin` and every destination are written to
   the ledger, so a misroute is *detectable* afterwards rather than
   invisible.

Guard 1 alone is sufficient. Guards 2 and 3 exist because "sufficient" has
been wrong before in this codebase.

### Cross-posting the same file to two brands

For `02-EEC-and-MACAL/`, posting an identical file with an identical caption
to two Instagram accounts (and two TikToks) can trip duplicate detection and
suppress reach on both. So a cross-posted asset must be **staggered** (MACAL
receives it 24–48h later, via the scheduling queue) and carry a **distinct
caption** per brand. Same video, different framing — the audiences and the
reason-to-watch genuinely differ.

---

## 3. Pipeline

```
Owner edits + exports to a Drive folder   ← the only manual step
              ↓
      n8n Drive trigger (folder = routing decision)
              ↓
      stage file → R2 (temporary public URL; Instagram requires it)
              ↓
      derive metadata (transcript → caption/hashtags/title)
              ↓
      Telegram approval: thumbnail + captions + [Approve] [Edit] [Drop]
              ↓
      queue → per-brand time slots (batch approve once, drip all week)
              ↓
      fan out to resolved destinations · stagger cross-posts
              ↓
      ledger row per destination · purge staged file
```

**Why R2 staging.** Instagram does not accept uploaded bytes — Meta cURLs
the media, so it must sit at a publicly reachable HTTPS URL at publish time.
R2 is already in use for 9,360 speech clips behind
`audio.empireenglish.online`, egress is free, and the free tier covers this.
Staged objects are deleted once every destination confirms, because
otherwise the pipeline slowly becomes a video archive nobody pruned.

**Why almost no CPU.** The owner edits and exports himself, and all
short-form is 9:16 — so **one exported file serves TikTok, Instagram Reels,
YouTube Shorts and the Facebook Page with zero re-encoding.** YouTube
auto-classifies any vertical video ≤3 minutes as a Short with no flag
required. The box only moves bytes and makes API calls, so this does not
compete with the student-facing bot for CPU. Transcription (Whisper, for
caption drafting) is the one real cost and belongs in a single-slot queue.

---

## 4. Per-platform mechanics

The expensive-to-rediscover details. Each of these costs an afternoon.

| Platform | Media transfer | Hard constraints |
|---|---|---|
| **Instagram** | **Public HTTPS URL only** — Meta cURLs it. Cannot POST bytes. | Professional (Business/Creator) account required; personal accounts fail with an unhelpful error. Standalone video **must** use `media_type=REELS` — `VIDEO` is a carousel item and is rejected. Two calls: create container → `media_publish`. ~90s max via API. 50 API posts / 24h. |
| **TikTok** | `source=FILE_UPLOAD` → PUT bytes to returned `upload_url`. No public URL, **no domain verification needed**. | Unaudited ⇒ forced private. Use `MEDIA_UPLOAD` (inbox) instead. Must call `creator_info` before each publish. |
| **YouTube** | Resumable upload, direct bytes. | `videos.insert` sits in its own quota bucket: **100 uploads/day at 1 unit each** — quota is a non-issue. Vertical + ≤3min ⇒ auto-Short. Long-form wants a real 16:9 thumbnail. |
| **Facebook Page** | Direct bytes or URL. | Page access token, not user token. Most forgiving of the four. |

### Instagram: no App Review needed

MACAL's Instagram has **no Facebook Page**, and it does not need one. Meta's
**Instagram API with Instagram Login** (July 2024) authenticates directly
against the Instagram professional account with no Page link, served from
`graph.instagram.com`.

Further: because we only ever publish to accounts the owner owns, the Meta
app can stay in **development mode** with those accounts added as Instagram
Testers. Full App Review is triggered by *other people* connecting their
accounts. **Verify this at setup rather than assuming it** — Meta's
enforcement of dev-mode capability has shifted before.

---

## 5. Credential handling

Six OAuth credential sets are being introduced onto a box that had a
Telegram bot token stolen in August 2026, and whose H3 secret rotation is
still open. Non-negotiable rules:

1. **Tokens live only in n8n's encrypted credential store.** Never in
   workflow JSON, never in a doc, never in a repo. `n8n-workflows/` in this
   repo has *already* leaked real secrets historically.
2. **Exported workflow JSON must be credential-stripped before committing.**
   Verify by grepping the export, not by trusting the exporter.
3. **No new listening ports.** Everything reaches out; nothing is exposed.
   Three internet-exposed ports were closed during the August incident and
   this must not reopen that class of problem.
4. **Token expiry is the top operational failure mode.** Instagram
   long-lived tokens are 60-day; TikTok refresh tokens rotate. They die
   *silently* — the symptom is that nothing posted for a week and no error
   was ever seen. A scheduled refresh job plus an alert **before** expiry is
   part of the build, not a follow-up.

Acquisition steps: [`SOCIAL-PUBLISHING-SETUP.md`](./SOCIAL-PUBLISHING-SETUP.md).

---

## 6. Build order

1. **Plumbing** — Drive trigger, R2 staging, ledger, fan-out to the four
   fully-automatic destinations, captions typed by hand. Unglamorous, and
   nearly all of the time saving.
2. **Batch queue** — approve several clips at once, drip them across the
   week on per-brand slots. Converts a daily obligation into one weekly
   session. Promote this ahead of step 3 if the daily rhythm is the real
   pain.
3. **TikTok draft flow** ×2.
4. **Drafted copy + metrics** — Whisper transcript → captions/hashtags/
   titles per brand voice; pull performance back into the ledger.

Caption generation is deliberately last: it saves the least time and needs
the most iteration to stop sounding generic.

---

## 7. Open decisions

- **Long-form YouTube** — does the owner produce 16:9 thumbnails? Shorts
  don't need them; long-form genuinely does, and pulling a frame is a
  visible quality drop. Also: how often does long-form ship?
- **Caption language per brand.** If EEC captions are Arabic, generated
  hashtags will violate the ecosystem bidi rule (never an Arabic line with
  2+ embedded LTR tokens) — `#EmpireEnglish #Learning` inline is exactly
  that case. Fix is structural: hashtags in their own block, never inline,
  and run `bidi_check.py` over generated captions.
- **Posting slots per brand** — needed before step 2.
