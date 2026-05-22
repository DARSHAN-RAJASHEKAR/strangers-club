# Strangers Club — Cobalt redesign · install guide

This folder is a drop-in replacement for the visual layer of your Strangers Club app. Every Alpine.js binding, fetch URL, FastAPI endpoint, template variable (`{{ token }}`, `{{ error }}`), and WebSocket route is preserved exactly as in the original.

## What changed

- `static/css/styles.css` — completely rewritten using CSS custom properties. Same class names as before so existing markup keeps working. New palette is **Cobalt**: deep cobalt-blue paper, warm cream ink, persimmon action accent, brass-gold details.
- `templates/base.html` — simplified header, italic serif wordmark, persistent monogram, footer in mono-caps.
- `templates/index.html` — landing redesigned (editorial headline + glass card + 3-feature grid).
- `templates/invite.html` — invite-code entry restyled, same `invitationForm()` Alpine logic.
- `templates/verify-phone.html` — restyled phone+OTP form, same `phoneVerification()` Alpine logic.
- `templates/join-group.html` — restyled group-code entry, same `joinGroupForm()` Alpine logic.
- `templates/dashboard.html` — restyled sidebar + chat + 3 modals. **All** Alpine state (`app()`, WebSocket setup, message queue, typing indicators, modal toggles) is preserved verbatim.

## What was NOT touched

- No Python files (`app/*.py`).
- No Alembic migrations.
- No API URLs (`/api/v1/...`).
- No request/response shapes.
- No localStorage keys.
- No WebSocket protocol.
- No `static/js/main.js` (kept as-is).

## How to install

From your project root (`strangers-club/`):

```bash
# 1. Back up the originals
cp static/css/styles.css static/css/styles.css.bak
cp -r templates templates.bak

# 2. Copy the new files in
cp /path/to/this/backend/static/css/styles.css static/css/styles.css
cp /path/to/this/backend/templates/*.html templates/

# 3. Restart your server — no migrations, no deps to install
uvicorn app.main:app --reload
```

## Theme tokens

All colors live in CSS custom properties at the top of `static/css/styles.css`:

```css
:root {
  --paper:    #1B2D5C;   /* page background */
  --surface:  #2A3B70;   /* cards, sidebar surface, chat-other bubble */
  --ink:      #F4E2B8;   /* primary text (warm cream) */
  --muted:    #8595BD;   /* secondary text */
  --accent:   #E25D2F;   /* persimmon — buttons, mine bubble, unread pill */
  --gold:     #C49333;   /* monogram, borders, ornaments */
  ...
}
```

To try a different palette, swap these 5–6 values in `:root`. Nothing else needs to change.

## Asset references

The only external resources are Google Fonts (Instrument Serif, Geist, Geist Mono), loaded via `@import` at the top of `styles.css`. If you ship offline you'll want to self-host these — drop the WOFF2 files into `static/fonts/` and replace the `@import` with `@font-face` blocks.

## Browser support

- Chrome / Edge / Safari / Firefox — last 2 versions.
- `backdrop-filter` (header, modals) — falls back to a solid background on older browsers; nothing breaks.
- `clamp()` on typography for fluid scaling — supported everywhere current.

## Where the design lives

The interactive 3-direction Figma-style canvas at the project root (`Strangers Club Redesign.html`) shows the full system across 18 frames including the picked Cobalt direction and the other two alternatives (Pocket Society, After Hours). Open it for reference.

## Smoke-test checklist

After copying files in, verify:

1. `/` (landing) — Google OAuth button renders, "By invitation only" copy.
2. `/invite` — code input is monospaced+spaced, "Enter the club" button.
3. `/verify-phone` — flag prefix, OTP code input is large+spaced.
4. `/join-group` — same as invite, "Join group" button.
5. `/app` — sidebar shows your real groups with auto-colored avatars; chat opens, messages send via WebSocket, typing indicators work, all 3 modals (Create Group, Group Invite Code, Platform Invite Code) open and close.

If anything looks off, the diff vs. the original markup is minimal — Alpine attributes (`x-data`, `x-show`, `x-model`, `x-text`, `x-for`, `@click`, `@submit.prevent`) are byte-for-byte identical to the original. Only the wrapping HTML/CSS changed.
