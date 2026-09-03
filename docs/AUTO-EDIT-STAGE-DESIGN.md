# Auto-Edit Stage — Design

> **Status: DESIGN ONLY — nothing is built or deployed.**
> No editing pipeline exists, no OpenShorts instance runs, no clips are
> produced automatically today. This document proposes the stage that sits
> *upstream* of the social-publishing pipeline. It must not be read as a
> description of a running system. When it ships, update the ecosystem
> `SYSTEM-MAP.md` in the same PR that deploys it.
>
> Downstream design it feeds: [`SOCIAL-PUBLISHING-DESIGN.md`](./SOCIAL-PUBLISHING-DESIGN.md).
>
> **Revision (post repo-audit):** §3–§5, §7–§8 were revised after auditing
> the wider org. Heavy compute moved from the owner's 8GB laptop CPU to
> Kaggle's free GPU tier, **reusing the proven remote-exec bridge pattern
> from `macal-empire-image-forge`**. Moment-scoring can use the local Ollama
> already installed by `macal-overseer`. Caption/hashtag style reuses the
> existing `tiktok-captions-*.md` brand library. The point of the revision
> was to stop duplicating infrastructure this org already runs.

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
| Moment selection | Gemini free tier **or** local Ollama `qwen3:8b` | Ollama already installed by `macal-overseer` — see §4 |
| Free GPU compute | Kaggle T4×2, driven by `remote_exec_bridge.py` | **Yes — `macal-empire-image-forge` already runs this** |
| 9:16 reframe (face-tracked) | MediaPipe + YOLOv8 fallback | New |
| Cut + burn captions | FFmpeg | Yes — ubiquitous |
| Orchestration for agents | native MCP server + n8n workflow + CLI | **Yes — we already run n8n + an n8n-MCP server** |

The last row is why OpenShorts specifically, and not a hand-rolled
`whisper + ffmpeg` script: it ships an **MCP server and an n8n workflow**,
and this org already runs both (`n8n-mcp/`, `bot.empireenglish.online`). The
editing stage becomes another node the same agent tooling can drive, not a
second orchestration system to babysit.

Fallback if OpenShorts proves awkward to run headless in a Kaggle session
(see §3): the same result is reproducible from its parts — `faster-whisper`
+ `PySceneDetect` + `FFmpeg` in a single CLI script invoked over the same
remote-exec bridge, with local-Ollama or a silence/scene heuristic for
moment-scoring. Lower-quality clip selection, identical output contract and
identical compute path. Kept as a documented Plan B, not built unless
needed.

---

## 3. Where it runs — reuse the free-GPU pattern this org already built

> **This section was rewritten after auditing the wider codebase.** An
> earlier draft put the heavy processing on the owner's 8GB laptop CPU. That
> was wrong: the org has already solved "run a GPU workload at $0" and it
> would be a duplication — and a much slower one — to ignore it.

Three hosts already exist in this ecosystem. The editing stage's compute
goes to the one built for exactly this.

**NOT the Hetzner box.** `empire-n8n` (77.42.43.250) is a ~4GB-RAM VPS —
`server-hardening/scripts/01-swap-setup.sh` exists precisely because it
OOM-crashed, and the n8n container is already capped at 2560M / 1.5 cores.
Video transcription + MediaPipe face tracking + FFmpeg re-encoding is the
single most CPU/RAM-hungry workload in the ecosystem. Running it beside the
live student bot reintroduces the exact OOM failure the hardening package
closed. **Non-negotiable: the editing stage never shares a host with the
production bot.**

**NOT (primarily) the owner's laptop.** i5-1135G7 / 8GB / Iris Xe / Win 11.
CPU-only, it would take ~5–8 min per 8-min video and fight the OS for RAM.
It has a role (orchestration + staging, §5) but it is **not** where frames
get processed.

**The heavy lifting runs on Kaggle's free GPU tier — reusing the
remote-exec pattern from `macal-empire-image-forge`.** That repo already
runs LoRA training and ComfyUI end-to-end at $0 on Kaggle (T4×2 / P100,
~30 hrs/week, no credit card). The mechanism is directly reusable here:

- **`kaggle/remote_exec_bridge.py`** — a stdlib HTTP server pasted into one
  Kaggle cell, exposed over a Cloudflare quick tunnel. It gives an agent
  `/upload`, `/exec` (sync or backgrounded with `/jobs/<id>` polling),
  `/download`, `/list`. This is *already* how this org drives a remote free
  GPU. The editing stage is a new payload for the identical bridge:
  `/upload` the source video → `/exec` the OpenShorts run in background →
  poll → `/download` the finished clips.
- **`kaggle/generate_notebook.py`** — the same generator approach produces
  the setup notebook (the `.ipynb` is a build artifact, the Python is what's
  reviewed). We add a `MACAL_Empire_AutoEdit_Setup.ipynb` sibling that
  installs OpenShorts + FFmpeg + faster-whisper instead of ComfyUI + SDXL.

**Why this is the right call, not just the reuse-y one.** On a T4, an 8-min
video processes in roughly **50 seconds** versus ~5–8 minutes CPU-only —
about an order of magnitude, which is the difference between "clip a week's
footage over coffee" and "leave the laptop grinding overnight." It is $0,
it is a pattern the owner has already operated and debugged, and it keeps
the heavy workload entirely off both production hosts.

**Known limits of the free GPU, carried over from the image-forge
experience:**

- **30 GPU-hours/week.** At ~50s/video this is hundreds of videos/week —
  a non-issue at any realistic volume. Tracked, not assumed.
- **Sessions are ephemeral (max ~12h, then reclaimed).** Fine for a
  batch-and-download model; nothing persistent lives on Kaggle. The bridge
  is torn down with the session.
- **The bridge has no auth** (documented in `remote_exec_bridge.py`): the
  Cloudflare quick-tunnel URL is an unguessable temporary root shell. Same
  handling rule as image-forge — only shared in-session, torn down when the
  batch finishes, never committed.

**Escalation path, if the free tier ever becomes the bottleneck:** a
GPU-by-the-hour box during batch windows — explicitly *not* the production
box, and only once real volume numbers justify a paid line item.

---

## 4. Moment-scoring: Gemini free tier, or local Ollama (already installed)

OpenShorts scores the transcript to pick the strongest 3–15 moments. That
scoring is the one step that wants an LLM. There are two $0 ways to do it,
and the audit found the org already runs the second:

**Option A — Gemini free tier (OpenShorts default).** Gemini 3.1 Flash-Lite,
~1,500 requests/day free; one video is a handful of requests, so this sits
inside the free tier indefinitely. Simplest path, one external dependency.

**Option B — local Ollama (already set up on the PC).** `macal-overseer`
already installs Ollama + `qwen3:8b` on the same Windows machine and drives
it for its agent. Moment-scoring is a plain "rank these transcript
segments" prompt — well within `qwen3:8b`'s ability. Using it means
**zero external dependency and nothing leaves the machine**: no API key to
leak, expire, or throttle. The transcript is scored locally before the
video ever goes to Kaggle (only the already-non-sensitive video frames go to
the GPU; the words stay home).

**Recommendation:** default to **Option B** where the scoring prompt is
simple enough — it is strictly more private and removes a credential and a
silent-failure mode. Keep Gemini as the drop-in fallback if local scoring
quality proves weak on real footage (decide empirically, §7). Either way:

1. **Any API key is a credential** — local `.env` only, never in this repo,
   a committed doc, or workflow JSON. The org has leaked real secrets from
   `n8n-workflows/` before; this gets no pass. (Option B has no key at all,
   which is the point.)
2. **Scoring failure is silent** — same class the publishing design flags
   for token expiry. If scoring returns nothing, clips silently stop. The
   batch job (§5) alerts on zero output via the existing Telegram watchdog
   (`server-hardening/06-monitoring-setup.sh`).

---

## 5. The pipeline

The laptop **orchestrates and stages**; Kaggle's free GPU **processes**. The
laptop role reuses machinery already present in `macal-overseer` (a
`watchdog` file monitor over an inbox folder, and the Tailscale/Cloudflare
mesh that already links the PC and the Hetzner box).

```
Owner films a long video
              ↓
Owner drops it into inbox/<routing-folder>/ on the PC          ← the only manual decision
              ↓
   [PC] watchdog picks it up (macal-overseer pattern) → queued for the next batch
              ↓
   [PC] batch runner (owner-started or scheduled):
          • score transcript locally with Ollama qwen3   (§4 Option B, stays on-machine)
          • open a Kaggle GPU session, paste remote_exec_bridge.py
          • /upload video + scores  →  /exec OpenShorts (background)  →  poll /jobs
              ↓
   [Kaggle T4] transcribe · cut · reframe 9:16 · burn captions · hook  (~50s / 8-min video)
              ↓
   [PC] /download the finished clips  →  write to the matching Drive routing folder
              ↓
   ══════════ hand-off ══════════  (existing SOCIAL-PUBLISHING pipeline takes over)
              ↓
   [Hetzner n8n] Drive trigger → R2 stage → caption draft → Telegram approve → fan out to 6
```

**The manual step shrinks, it does not vanish.** The owner makes exactly one
decision per source video: *which routing folder?* — the same
safety-critical brand decision the publishing design already relies on (§6),
made once per long video, not once per clip.

**Caption + hashtag style is not invented here — it is reused.** The org
already has a written brand caption library and a fixed hashtag block in
`empire-nexus/.../data/tiktok-captions-en.md` (and the Arabic file). Any
caption/hook the stage drafts uses those as the style reference and appends
the existing fixed hashtag set, rather than generating a generic voice from
scratch. RTL captions still pass the ecosystem bidi rule before being burned
in (§8) — and because captions are burned *into* the frame here, that check
matters on-screen, not just in post copy.

**Why a batch job, not a per-file watcher-trigger.** The `watchdog` monitor
*detects* new files immediately (that part is cheap and local), but it only
*queues* them — it does not open a GPU session per file. Processing happens
in a batch window (overnight, or "run before bed"), which matches the
Kaggle session model (spin up, process the queue, tear down) and the
publishing design's own "batch approve once, drip all week" philosophy.
Opening a fresh Kaggle session per dropped file would waste the 30h/week
quota on setup overhead.

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

Sequenced so the riskiest assumption (does OpenShorts run cleanly headless
on a Kaggle GPU session?) is tested first, reusing the image-forge bridge so
step 1 is mostly proving a payload, not building infrastructure.

1. **Prove the Kaggle path.** Reuse `remote_exec_bridge.py`: open a free
   Kaggle GPU session, `/upload` **one** real long video, `/exec` an
   OpenShorts run in the background, poll, `/download` the clips. Measure
   wall-clock time and confirm output quality on a T4. This single data
   point confirms §3 or triggers the Plan-B parts-based CLI (§2). Everything
   else waits on this. The image-forge setup notebook is the template for
   the auto-edit setup notebook.
2. **Wire the inbox → Drive folders.** The three-subfolder inbox on the PC
   (reusing the `macal-overseer` `watchdog` monitor), and the `/download`
   step writing into the same three Drive routing folders the publishing
   trigger watches. At this point the two pipelines are connected end to
   end, even if the batch is still started by hand.
3. **Batch runner + zero-output alert.** One command (or Windows scheduled
   task) that drains each inbox subfolder through a Kaggle session and
   alerts via the existing Telegram watchdog if a run yields zero clips
   (§4). Reuse `macal-overseer`'s daemon/audit-log scaffolding rather than a
   new service.
4. **Tune moment-selection + caption style.** Last, deliberately — same
   reasoning as the publishing design putting caption generation last. Wire
   the existing `tiktok-captions-*.md` brand library + fixed hashtag block
   in as the style reference (§5); tune hook tone per brand (EEC teacherly
   vs MACAL founder voice). Tuning, not plumbing.

---

## 8. Open decisions

- **Whisper model size on Kaggle.** On a T4 the GPU has ~15GB VRAM, so the
  RAM ceiling that constrained the laptop plan is gone — `medium` or even
  `large-v3` are viable for better caption accuracy. Confirm the
  quality/speed trade in step 1. (The laptop no longer runs Whisper, so its
  8GB is irrelevant to model choice.)
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
