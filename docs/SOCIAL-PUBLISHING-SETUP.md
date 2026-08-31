# Social Publishing Pipeline — Credential Setup Runbook

> **Owner-gated. An agent cannot do any of this.** Every step needs a login
> to a provider console. Budget 1–2 hours. **Nothing in the pipeline can be
> built or tested until these exist**, so this is the critical path.
>
> Design and rationale: [`SOCIAL-PUBLISHING-DESIGN.md`](./SOCIAL-PUBLISHING-DESIGN.md).

## Rules while doing this

- **Never paste a token value into this repo, any doc, or a chat message
  that ends up committed.** `n8n-workflows/` in this repo has leaked real
  secrets before. Values go **only** into n8n's encrypted credential store.
- Record *that* a credential exists and where it came from — never what it
  is. That is the convention used by `empire-chronicle`'s credentials table.
- Do this in one sitting per provider. Half-finished OAuth apps are the
  main source of confusing errors later.

---

## What you end up with

| # | Credential | Unlocks | Console |
|---|---|---|---|
| 1 | Meta app ID + secret | — | developers.facebook.com |
| 2 | IG long-lived token — EEC | EEC Instagram | via #1 |
| 3 | IG long-lived token — MACAL | MACAL Instagram | via #1 |
| 4 | FB Page access token (non-expiring) | EEC Facebook Page | via #1 |
| 5 | Google OAuth client + refresh token | YouTube upload **and** Drive trigger | console.cloud.google.com |
| 6 | TikTok client key + secret | — | developers.tiktok.com |
| 7 | TikTok refresh token — EEC | EEC TikTok drafts | via #6 |
| 8 | TikTok refresh token — MACAL | MACAL TikTok drafts | via #6 |
| 9 | R2 access key + bucket | Temporary public URLs for Instagram | Cloudflare dashboard |

---

## A. Meta — covers 3 of 6 destinations

Do this first; it is the highest-value block.

**Prerequisite:** both Instagram accounts must be **Professional**
(Business or Creator). Personal accounts cannot publish via API at all, and
the error you get is unhelpful enough to waste an afternoon.

1. **developers.facebook.com** → My Apps → Create App → type **Business**.
   One app serves both brands; you do not need two.
2. Add the **Instagram** product, choosing **Instagram API with Instagram
   Login**. *(Not "with Facebook Login" — that variant demands a Facebook
   Page linked to each Instagram account, and MACAL has no Page. The
   Instagram Login variant needs none.)*
3. Request scopes: `instagram_business_basic` +
   `instagram_business_content_publish`.
4. Add **both** Instagram accounts as **Instagram Testers**, then accept
   each invitation from inside the Instagram app
   (Settings → Apps and websites → Tester invites). Acceptance is easy to
   miss and everything fails until it is done.
5. Leave the app in **Development mode.** Because you only ever publish to
   accounts you own, full App Review should not be required — it is
   triggered by *other people* connecting accounts.
   **Confirm this by actually publishing one test post before assuming it.**
6. For the **Facebook Page**: add Facebook Login, request
   `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`. Then
   exchange short-lived user token → long-lived user token → **Page**
   token. A Page token derived from a long-lived user token does not expire,
   which is why this ordering matters.
7. Record each account's **IG user ID** (an identifier, not a secret).

**Verify before moving on:** publish one Reel to each Instagram account and
one video to the Page, via Graph API Explorer or curl. Use
`media_type=REELS` — `VIDEO` is carousel-only and will be rejected.

---

## B. Google — YouTube + Drive ingest

1. **console.cloud.google.com** → new project.
2. Enable **YouTube Data API v3** *and* **Google Drive API**.
3. OAuth consent screen → User type **External**.
4. **⚠️ Set Publishing status to "In production" before you authorize.**
   Leaving it on **Testing** makes every authorization — including the
   refresh token — **expire 7 days after consent**, so YouTube uploads
   silently stop weekly and the only symptom is nothing being posted.
   Going to production does **not** require completing verification; you
   will see an "unverified app" warning at consent and click through it once.
   Do not skip this to avoid the scary screen.
5. Create an **OAuth client ID** (Desktop or Web).
6. Authorize with `access_type=offline` and scopes:
   `https://www.googleapis.com/auth/youtube.upload` and
   `https://www.googleapis.com/auth/drive` (or `drive.readonly` if the
   pipeline never deletes from Drive — decide before authorizing, since
   narrowing later means re-consenting).
7. Store the **refresh token**.

**Create the three Drive folders now** — the folder *is* the routing
decision, so these names are load-bearing:

```
01-EEC-only/
02-EEC-and-MACAL/
03-MACAL-only/
```

Record each folder ID.

**Verify:** upload one unlisted test video via the API and confirm a
refresh-token exchange still works after 8+ days.

---

## C. TikTok — both accounts

Expect this to be the most tedious of the four.

1. **developers.tiktok.com** → register an app.
2. Add the **Content Posting API** product.
3. Request the **inbox/upload** scope (`video.upload`) — **not**
   `video.publish`. Direct Post requires passing TikTok's audit, which we
   are deliberately not pursuing; see the design doc for why.
4. Add **Login Kit** for OAuth.
5. Authorize **each** account separately and store two separate refresh
   tokens. Label them unambiguously — EEC and MACAL tokens are
   indistinguishable once stored, and posting the wrong brand's video is
   exactly the failure the design guards against.
6. No domain verification needed: we use `source=FILE_UPLOAD` and PUT the
   bytes directly.

**Verify:** push one video to each inbox and confirm it appears as a draft
notification in the right account's TikTok app.

---

## D. Cloudflare R2 — staging for Instagram

Instagram will not accept uploaded bytes; Meta cURLs the media from a public
URL. R2 already serves 9,360 speech clips, so this reuses a working pattern.

1. Create a bucket, e.g. `empire-social-staging`.
2. Attach a public custom domain (same approach as
   `audio.empireenglish.online`).
3. API token scoped to **R2 edit only** — not an account-wide token.
4. Confirm a staged object is reachable over public HTTPS **with no browser
   User-Agent**. Cloudflare bot protection has previously 403'd working R2
   endpoints when the caller sent no UA, and that failure looked like a
   broken deploy for a while. Meta's fetcher is not a browser.

Staged files are deleted after all destinations confirm.

---

## E. Sign-off checklist

- [ ] Both Instagram accounts are Professional
- [ ] Meta app created; both IG accounts accepted tester invites
- [ ] One Reel published to **each** Instagram account via API
- [ ] One video published to the EEC Facebook Page via API
- [ ] Page token confirmed non-expiring (derived from long-lived user token)
- [ ] Google OAuth publishing status reads **In production** ← re-check
- [ ] Test video uploaded to YouTube via API
- [ ] Three Drive folders created; folder IDs recorded
- [ ] Two TikTok refresh tokens stored and **labelled by brand**
- [ ] One draft landed in each TikTok inbox
- [ ] R2 bucket public URL fetchable with no User-Agent
- [ ] Every value entered **only** into n8n credentials — `git grep` finds none

---

## Token expiry — the failure mode that will actually bite

These credentials do not fail loudly. They fail as *silence*: nothing
posted, no error seen, discovered a week later.

| Credential | Lifetime | Renewal |
|---|---|---|
| IG long-lived token | 60 days | Refresh before day 60 |
| FB Page token | Non-expiring *if* derived correctly | Verify at setup, not later |
| Google refresh token | Indefinite **only** in production status | Re-check status after any consent-screen edit |
| TikTok refresh token | Rotates | Persist the new one on every refresh |

A scheduled refresh job **plus an alert before expiry** is part of the
build, not a follow-up. Also note: after a database restore the pipeline
must be re-armed deliberately — same property as flags failing closed.
