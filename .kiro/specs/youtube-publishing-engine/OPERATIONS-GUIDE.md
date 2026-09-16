# Empire English — YouTube Auto-Publishing Engine
## Plain-language Operations Guide

> This explains, in simple terms, what we built, how to use it day-to-day, and
> what still needs a human touch. No technical background needed.

---

## 1. What this engine does (in one paragraph)

You drop a finished video clip into a Google Drive folder. The system
automatically writes an Arabic-first, YouTube-algorithm-friendly title,
description and hashtags, uploads it to your YouTube channel **as a private
video** (so nothing goes public without your say-so), posts a friendly Arabic
engagement question in the comments, and pings your Telegram to review and
publish. Separately, it watches your videos' comments and drafts smart replies
you approve with one tap, and each day it checks how your videos are performing
and warns you about weak ones.

---

## 2. How to publish a video (your daily routine)

1. **Put the clip in Drive.** Drop your finished 9:16 clip into the Google Drive
   folder for its brand:
   - `output/01-EEC-only/` → posts to EEC YouTube
   - (`02-EEC-and-MACAL/` and `03-MACAL-only/` exist for Instagram routing later)
   - **Best:** include the clip's `<name>_metadata.json` file (your Kaggle editor
     makes this automatically) — that gives the richest AI title/caption.
2. **The engine takes over** within ~1 minute:
   - Builds the title/description/hashtags
   - Uploads to YouTube **as Private**
   - Posts the engagement comment
   - Sends you a **Telegram message** (from "EEC YouTube Ops" bot) with a link.
3. **You review + publish.** Open the Telegram link → it takes you to YouTube
   Studio → check the title/description look good → **pin the engagement comment**
   (one click in Studio) → set the video to **Public** (or schedule it).

> That's it. The engine does the heavy lifting; you do a 30-second review.

---

## 3. The four things running for you (all LIVE)

| # | What it does | You do |
|---|---|---|
| **Publishing engine** | Drop clip → private upload with pro metadata + engagement comment + Telegram nudge | Review & publish (30 sec) |
| **Comment replies** | Every 30 min it finds new comments on your videos, drafts a warm Arabic/English reply with AI, and sends it to your Telegram | Tap **✅ Approve** or **✖ Skip** |
| **Daily analytics** | Each morning logs each video's views + watch-through, warns you about weak performers | Read the alert; decide what to improve |
| **Quota + duplicate guard** | Stops accidental double-uploads and protects your daily YouTube limit | Nothing — automatic |

---

## 4. How the comment-reply approval works

- When someone comments on your video, within 30 minutes you'll get a Telegram
  message showing **their comment** and a **suggested reply** (written by AI in
  your brand voice, matching their language).
- Tap **✅ Approve** → the reply is posted publicly on your channel.
- Tap **✖ Skip** → nothing is posted.
- **Why approval?** YouTube bans bulk/robotic auto-replies. Keeping you in the
  loop (one tap) keeps the channel safe and the replies genuine.

---

## 5. Why videos upload as "Private" (this is intentional)

You asked for a review step. Every upload lands **Private** so you can check it
before the world sees it. Two ways to go live:
- **Manually:** in YouTube Studio, switch it to Public when happy.
- **Scheduled:** the engine can auto-publish at peak Egypt hours (7–10pm) — this
  is switched on per-clip via the clip's metadata.

---

## 6. What still needs YOU (honest list)

- **Pinning the engagement comment** — YouTube's system does **not** allow apps
  to pin comments (only a human can, in Studio). So the engine posts the comment
  and reminds you; you tap "pin" once. ~5 seconds.
- **Publishing** the private video (your chosen review step).
- **Approving** comment replies (one tap each).
- **Thumbnails** — not automated yet (a future add-on).

---

## 7. The "brains" behind the metadata (why it's built this way)

Based on how YouTube actually ranks content in 2026:
- **Shorts are ranked on watching behaviour**, not keywords — so the engine
  focuses on a strong Arabic hook, a clear title, and an engagement question to
  spark comments (which the algorithm rewards).
- **Titles** lead with the topic in Arabic (your audience), include the English
  term being taught, and stay short.
- **First 48 hours matter most** — that's why peak-time scheduling exists.
- **Tags barely matter** (YouTube's own guidance) — so we don't waste effort
  there; the work goes into title, description, and engagement.

---

## 8. If something looks wrong

- **No Telegram message after a clip?** Check the clip was in the right Drive
  folder and was a video file (`.mp4`).
- **Reply drafts not arriving?** They only appear when there are **new** comments.
- **A weak-video alert?** That's the analytics loop doing its job — consider a
  stronger hook or re-cut for that topic.
- Every action is logged to the **ledger Google Sheet** (tabs: `ledger`,
  `analytics`) for a full history.

---

## 9. Behind the scenes (for reference)

- Runs on the n8n automation server (`bot.empireenglish.online`).
- Four workflows: publishing, comment-reply approval, comment-reply callback,
  daily analytics — all active.
- Uses your YouTube channel credential, a dedicated "EEC YouTube Ops" Telegram
  bot for notifications/approvals, Google Gemini for reply drafting, and a Google
  Sheet as the ledger.
- Full technical spec: `requirements.md`, `design.md`, `tasks.md` in this folder.
