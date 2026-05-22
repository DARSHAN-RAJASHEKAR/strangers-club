# Strangers Club — Salon · Cobalt frontend

This time, this is **the actual mockup**. Templates rebuilt from scratch to match `Strangers Club — Redesign 01 · The Salon` in the Cobalt palette. Not just a recolor.

## What's actually different from the old code

| | old templates | this folder |
|---|---|---|
| Landing | `card-glass` form + 3-feature grid (Invite-only / Meet-up groups / House rules) | Monogram + edition number + big serif headline + **star ornament** + **members card with 4 overlapping avatars** + Google button + footer line. No feature grid. |
| Invite | Plain form input | **Ticket stub** with perforated edges + `admit one` foil label + 8-cell code grid + "invited by" / "valid until" footer |
| Phone verify | Plain `tel` input | Serif phone input with `🇮🇳 +91` country prefix, dashed hint card, star ornament, and a separate OTP step on the same page |
| Join group | Plain form input | Second ticket stub with `group pass` foil label |
| Dashboard | Sidebar + chat (2 panes) | **3 panes**: sidebar (brand + search + groups + dark "Invite a stranger" ribbon) · chat (header with meet-up details + serif italic composer) · **right rail** (meet-up name + date + members list + "house rules") |
| Base layout | Full-width header with brand-logo wordmark + nav + footer | Bare shell — each page handles its own chrome |

## Preview without installing

Open `preview.html` in this folder. Click any of the five cards (Landing, Invite, Phone verify, Join group, Dashboard) to see exactly what each screen looks like with mock content. **This** is the pixel target.

## What's in here

```
backend/
├── INSTALL.md                  ← you are here
├── preview.html                ← hub: open this first
├── preview/                    ← static demos with mock data
│   ├── landing.html
│   ├── invite.html
│   ├── verify-phone.html
│   ├── join-group.html
│   └── dashboard.html
├── static/css/styles.css       ← drop in over your existing styles.css
└── templates/                  ← drop in over your existing templates/
    ├── base.html
    ├── index.html
    ├── invite.html
    ├── verify-phone.html
    ├── join-group.html
    └── dashboard.html
```

## Backend contracts the templates expect

I kept all the Alpine binding names (`app()`, `invitationForm()`, `phoneVerification()`, `joinGroupForm()`) the same so your existing wiring still works. The fetch URLs the templates call are:

| Screen | Method · URL | Purpose |
|---|---|---|
| Landing | `GET /api/v1/auth/login/google` | OAuth start (link href) |
| Invite | `POST /api/v1/invitations/verify-code`  body `{code}` | Verify platform invite code |
| Phone verify | `POST /api/v1/auth/send-otp` body `{phone}` | Send WhatsApp OTP |
| Phone verify | `POST /api/v1/auth/verify-otp` body `{phone, code}` | Verify OTP |
| Join group | `POST /api/v1/invitations/join-group` body `{code}` | Join group with code |
| Dashboard | `GET /api/v1/auth/me` | Current user |
| Dashboard | `GET /api/v1/groups` | All groups (filtered into meet-up vs general by `is_general`) |
| Dashboard | `GET /api/v1/groups/{id}/members` ★ new | Members list for right rail |
| Dashboard | `GET /api/v1/groups/{id}/channels` | First channel becomes selected |
| Dashboard | `GET /api/v1/messages/channel/{id}` | Messages |
| Dashboard | `WSS /api/v1/messages/ws/{channelId}?token=...` | Realtime |
| Dashboard | `POST /api/v1/groups` | Create group |
| Dashboard | `POST /api/v1/groups/{id}/leave` | Leave group |
| Dashboard | `POST /api/v1/invitations/generate-new-code/{groupId}` | Group invite code |
| Dashboard | `POST /api/v1/invitations/generate-platform-code` | Platform invite code |

★ The only **new** endpoint is `GET /api/v1/groups/{id}/members`. If you don't have one yet, the right rail just falls back to "Just you, so far." It expects an array of `{id, username, joined_at}` objects.

Group objects can optionally include `unread_count` and `meetup_date` — the sidebar uses them if present.

## Install

From your project root (`strangers-club/`):

```bash
cp static/css/styles.css static/css/styles.css.bak
cp -r templates templates.bak

cp /path/to/backend/static/css/styles.css static/css/styles.css
cp /path/to/backend/templates/*.html templates/

uvicorn app.main:app --reload
```

## Tweaking the palette

All colors are CSS custom properties at the top of `styles.css`:

```css
:root {
  --paper:    #1B2D5C;   /* page background — deep cobalt */
  --paper-2:  #12224F;   /* darker insets */
  --surface:  #2A3B70;   /* raised cards, sidebar, chat bubbles */
  --ink:      #F4E2B8;   /* warm cream text */
  --muted:    #8595BD;   /* low-contrast meta */
  --border:   #3D5396;
  --accent:   #E25D2F;   /* persimmon — buttons, mine bubble */
  --gold:     #C49333;   /* monogram ring, ornaments, foil labels */
  ...
}
```

Swap those 6 values to try Salmon Court, Mint Garden, Butter, or Wine Cellar (see `Strangers Club Redesign.html` for the full set).

## The mockup, for reference

Open `Strangers Club Redesign.html` at the project root and look at **Direction 01 · The Salon**. This folder is that direction, in Cobalt, with the Alpine plumbing intact.
