# Auto-Edit Stage — Design

> **Status: DESIGN ONLY — nothing is built or deployed.**
> No editing pipeline exists, no OpenShorts instance runs, no clips are
> produced automatically today. This document proposes the stage that sits
> *upstream* of the social-publishing pipeline. It must not be read as a
> description of a running system. When it ships, update the ecosystem
> `SYSTEM-MAP.md` in the same PR that deploys it.
>
> Downstream design it feeds: [`SOCIAL-PUBLISHING-DESIGN.md`](./SOCIAL-PUBLISHING-DESIGN.md).

---

## 1. The gap this closes

`SOCIAL-PUBLISHING-DESIGN.md` opens with an assumption:

> "The owner films **and edits** content himself. Everything after export
> is manual and costs 30–60 minutes a day. This pipeline removes that."

It removes the *publishing* half. It leaves the *editing* half fully manual —
and editing is the larger, more painful cost. The owner films **long-form**
video (talks, lessons, streams) that a human currently has to slice into
short vertical clips, reframe, caption, and hook before a single file lands
in a Drive routing folder.

This stage removes that. It converts:

```
Owner films long video → [ EDITS BY HAND, 30–90 min/clip ] → Drive folder
```

into:

```
Owner films long video → drop it in → [ AI produces N finished 9:16 clips ] → Drive folder
```

The output of this stage **is** the input the publishing pipeline already
expects: a finished, captioned, 9:16 file in a routing folder. **The two
systems connect with zero glue** — the contract between them is "a file
appears in `01-EEC-only/`, `02-EEC-and-MACAL/`, or `03-MACAL-only/`", and
that contract does not change.

---

## 2. Why not a paid SaaS clipper

The obvious answer is Opus Clip / Submagic / Vizard. Rejected, for the same
reason the publishing pipeline rejected a paid TikTok-audit shortcut: **the
standing constraint is zero paid dependencies.** The volume the owner wants
(many clips/day across two brands) is exactly the volume every SaaS free
tier is designed to choke — credit models "punish volume" by design, and the
finished clips carry a watermark until you pay. A per-seat subscription that
scales with output is the thing we are structurally avoiding.

So the stage is **self-hosted and open source**.

### Chosen tool: OpenShorts (self-hosted, MIT)

[OpenShorts](https://www.openshorts.app/) is an MIT-licensed clip generator
that runs in Docker on hardware we already control. It is not a novel stack —
it is the same open components this ecosystem already uses, assembled:

| Stage | Component | Already in our stack? |
|---|---|---|
| Transcription (word-level) | faster-whisper | Yes — publishing pipeline uses Whisper for caption drafting |
| Scene boundaries | PySceneDetect | New, but pure-Python, no service |
| Moment selection | Google Gemini 3.1 Flash-Lite | New — free tier, see §4 |
| 9:16 reframe (face-tracked) | MediaPipe + YOLOv8 fallback | New |
| Cut + burn captions | FFmpeg | Yes — ubiquitous |
| Orchestration for agents | native MCP server + n8n workflow + CLI | **Yes — we already run n8n + an n8n-MCP server** |

The last row is why OpenShorts specifically, and not a hand-rolled
`whisper + ffmpeg` script: it ships an **MCP server and an n8n workflow**,
and this org already runs both (`n8n-mcp/`, `bot.empireenglish.online`). The
editing stage becomes another node the same agent tooling can drive, not a
second orchestration system to babysit.

Fallback if OpenShorts proves too heavy for the hardware (see §3): the same
result is reproducible from its parts — `faster-whisper` +
`PySceneDetect` + `FFmpeg` in a single CLI script, dropping the Gemini
moment-scoring for a simpler silence/scene heuristic. Lower quality clip
selection, identical output contract. Kept as a documented Plan B, not built
unless needed.

---

## 3. Where it runs — the hardware decision is the whole design

This is the constraint that shapes everything, so it is decided here
explicitly rather than left to setup.

**It does NOT run on the Hetzner box.** `empire-n8n` (77.42.43.250) is a
~4GB-RAM VPS — `server-hardening/scripts/01-swap-setup.sh` exists precisely
because it OOM-crashed, and the n8n container is already capped at
2560M / 1.5 cores. Video transcription + MediaPipe face tracking + FFmpeg
re-encoding is the single most CPU- and RAM-hungry workload in the whole
ecosystem. Putting it on the box that runs the live student-facing bot would
reintroduce exactly the OOM failure mode the hardening package was built to
close. **Non-negotiable: the editing stage never shares a host with the
production bot.**

**It runs on the owner's PC.** i5-1135G7 / 8GB RAM / Iris Xe (no discrete
GPU) / Windows 11 + WSL2 + Docker. This is the only free hardware available,
and it is adequate with caveats:

- **8GB is tight.** faster-whisper's larger models will not fit alongside a
  browser and the OS. Pin the `small` or `base` model, not `medium`/`large`.
- **CPU-only ⇒ slow.** Expect roughly 5–8 minutes of processing per
  8 minutes of source video. This is fine for a **batch-at-night** rhythm,
  and unacceptable for "watch it render." Design for the former (§5).
- **It is the owner's daily-driver laptop.** Processing must be a job the
  owner *starts* and walks away from — not a daemon competing with normal
  use. A `docker compose run` invocation, not an always-on service.

If the laptop proves too slow at the owner's real volume, the escalation
path is a **separate cheap VPS** (a second Hetzner instance, or a
GPU-by-the-hour box run only during batch windows) — explicitly *not* the
production box. This is a cost decision to revisit with real numbers, not a
day-one purchase.

---

## 4. The one recurring external dependency: Gemini

OpenShorts uses Google Gemini 3.1 Flash-Lite to score the transcript and
pick the strongest 3–15 moments. This is the only call that leaves the
machine, and it is **free within limits**: Gemini's free tier covers ~1,500
requests/day, and one video is a handful of requests. At the owner's volume
this stays inside the free tier indefinitely.

Consequences, consistent with the ecosystem's standing rules:

1. **The Gemini API key is a credential.** It lives in the editing stage's
   local `.env` on the PC — never in this repo, never in a committed doc,
   never in workflow JSON. Same rule that governs the six publishing
   credentials. The org has leaked real secrets from `n8n-workflows/`
   before; this key does not get a pass.
2. **The transcript leaves the machine.** Gemini sees the words spoken in
   the video (not the video itself). For public teaching content this is
   acceptable. It is called out here so the decision is on the record rather
   than discovered later.
3. **Free-tier failure is silent** — the same failure class the publishing
   design flags for token expiry. If the key is throttled or revoked, clips
   silently stop being produced. The batch job (§5) must alert on zero
   output, reusing the existing Telegram watchdog channel from
   `server-hardening/06-monitoring-setup.sh`.

---

## 5. The pipeline

```
Owner films a long video
              ↓
Owner drops the file into a local "inbox" folder on the PC     ← the only manual step
              ↓
      Nightly batch job (owner starts it, or a scheduled task)
              ↓
      OpenShorts: transcribe → score moments → cut → reframe 9:16 → caption → hook
              ↓
      N finished 9:16 clips written to the correct Drive routing folder
              ↓
      ══════════ hand-off ══════════  (existing SOCIAL-PUBLISHING pipeline takes over)
              ↓
      n8n Drive trigger → R2 stage → caption draft → Telegram approve → fan out to 6 destinations
```

**The manual step shrinks, it does not vanish.** The owner still makes one
decision per source video: *which routing folder does its clips go to?* That
is the same brand-routing decision the publishing design already relies on,
and it is safety-critical (§6). It is made once per long video, not once per
clip — a 60-minute talk yielding 10 clips is **one** routing decision, not
ten.

**Why a batch job, not a folder-watcher.** A watcher that fires the moment a
file lands would run heavy processing at unpredictable times on the owner's
active laptop. A batch window (e.g. overnight, or "run before bed") matches
the hardware reality in §3 and matches the publishing design's own
philosophy — it already prefers a "batch approve once, drip all week"
rhythm over a per-item obligation.

---

## 6. Routing is inherited, and stays safety-critical

The publishing design makes one rule structurally impossible to violate:

> **MACAL content MUST NEVER reach EEC.** The forbidden direction is made
> structurally impossible, not merely handled correctly.

This stage sits *upstream* of that guard, which means **it must not weaken
it.** The mechanism that protects the rule downstream is *which Drive folder
the file lands in* — so the editing stage's only routing responsibility is
to write a clip to the **same folder its source video was assigned**, and
never to infer or "helpfully" re-route.

Concrete rules for this stage:

1. **Routing is folder-in → folder-out, one-to-one.** The PC inbox has three
   subfolders mirroring the Drive targets:
   `inbox/01-EEC-only/`, `inbox/02-EEC-and-MACAL/`, `inbox/03-MACAL-only/`.
   Clips from a source video inherit its subfolder, full stop. There is no
   content analysis that could move a MACAL video toward an EEC folder,
   because the stage never looks at destination at all — it only preserves
   the folder it was given. A logic bug cannot produce the forbidden
   outcome, because the code path that would do it does not exist. Same
   fail-closed principle as the downstream credential isolation.
2. **No cross-folder batching.** Each batch run processes one subfolder's
   files into that same subfolder's Drive target. The three folders are
   never merged into one processing queue whose outputs are then sorted —
   sorting-after-the-fact is exactly the class of bug the downstream design
   refused to rely on.
3. **The stage produces the file; it does NOT publish.** It has no social
   credentials, no TikTok/IG/YT tokens — nothing. Its entire authority ends
   at "wrote a file to a Drive folder." Every existing publishing guard
   (credential isolation, pre-publish assertion, ledger) still runs
   afterward, unchanged. This stage cannot misroute a *post* because it
   cannot post.

The staggering + distinct-caption-per-brand requirement for
`02-EEC-and-MACAL/` is unchanged and remains the publishing pipeline's job —
this stage just produces one clip file per moment, as before.

---

## 7. Build order

Sequenced so the riskiest assumption (does the laptop cope?) is tested
first, and nothing here starts before the credential prerequisites the
downstream design already documents.

1. **Prove the hardware.** Install Docker + WSL2 on the PC, run OpenShorts
   self-hosted against **one** real long video with the `base` Whisper
   model. Measure wall-clock time and peak RAM. This single data point
   decides whether §3's "laptop" plan holds or the "separate VPS"
   escalation is needed. Everything else waits on this.
2. **Wire the inbox → Drive folders.** The three-subfolder inbox, and the
   output writing into the same three Drive routing folders the publishing
   trigger watches. At this point the two pipelines are connected end to
   end, even if still triggered by hand.
3. **Batch runner + zero-output alert.** A single command (or Windows
   scheduled task) that processes each inbox subfolder and alerts via the
   existing Telegram watchdog if a run produces zero clips (§4).
4. **Tune moment-selection + caption style.** Last, and deliberately so —
   same reasoning as the publishing design putting caption generation last:
   it saves the least time and needs the most iteration to stop looking
   generic. Hook-text tone per brand (EEC teacherly vs MACAL founder voice)
   is tuning, not plumbing.

---

## 8. Open decisions

- **Whisper model size vs 8GB RAM.** `base` almost certainly fits; `small`
  is the stretch target for better caption accuracy. Decide empirically in
  step 1, not now. If neither is acceptable and clips are unusable, that is
  the trigger for the separate-VPS escalation, not a reason to touch the
  production box.
- **Caption language per brand.** Inherited open question from the
  publishing design: if EEC captions are Arabic, generated hashtags must
  obey the ecosystem bidi rule (no Arabic line with 2+ embedded LTR tokens).
  OpenShorts burns captions *into* the video here, so this applies to the
  on-screen caption too, not just the post copy — run `bidi_check.py` over
  any RTL caption text before it is burned in.
- **Clip count per source video.** OpenShorts returns 3–15 candidates. Do
  all get posted, or does the owner approve a subset? The downstream Telegram
  approval step already gives a natural gate — recommend producing all
  candidates and letting the existing `[Approve] [Edit] [Drop]` step be the
  filter, rather than adding a second review here.
- **Long-form original.** The publishing design asks whether the owner ships
  16:9 long-form (which needs a real thumbnail). This stage is short-form
  only; if long-form is also wanted, the source video passes through to
  YouTube *unclipped* on a separate path — out of scope here, flagged so it
  is not silently dropped.

---

## 9. What this stage explicitly does NOT do

Stated so scope creep is visible:

- It does **not** post anywhere. (§6.3)
- It does **not** run on the production Hetzner box. (§3)
- It does **not** make routing decisions from content. (§6.1)
- It does **not** hold any social-media credential. (§6.3)
- It does **not** promise "fully automatic, professional, zero review." It
  removes the manual *edit*; the human still makes one routing decision per
  source video and the downstream approval step is still the quality gate.
  This is the honest ceiling of free + self-hosted, and it is a large win
  over editing every clip by hand.
