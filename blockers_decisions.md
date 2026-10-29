# Blockers & decisions taken while you were out

Mission `01-pooled-table`, run as `/trace-n` for slices 5, 6 and 7. You asked me to finish the slices,
commit and push, and take my own recommendations on anything blocked — this is that list, newest first.
**Delete this file once you have read it** (it is not part of the bot).

---

## ✅ Cleared: the live self-check — Jon ran it, 2026-10-30

Jon ran the ten-step protocol with Jess on the live bot: **"other than the above all lgtm"**. The fan-out
witness every slice after 4 leaned on is now seen rather than inferred — her screen moving while he typed,
`/history` leaving it alone, settlement landing where the Board was with a zeroed Board beneath it in both
DMs. He quoted two strings back at me, so those are directly witnessed: the `/end` refusal, and the Board's
`⏳ @koongster is entering a win`.

**Two amendments came out of it**, both implemented and green (1028 passed), both recorded in full in
`.fac-a/01-pooled-table/tasking.md` under *Self-check round 7*:

- **`/start` starts the bot and nothing more** — the verb listing is gone. `mjbot.py:200` sends every verb
  to Telegram *with* its `COMMAND_HELP` description, so what `/start` printed was the slash menu reprinted
  into the chat. `/start` now returns one line, edits no Board, and leaves the menu once the chat has a Table.
- **A refused `/end` names the rule** — `Game cannot end when someone is entering a win — @Bo is entering a
  win.` The Board's `⏳` line and the tap-time refusal stay as they were, per Jon.

**Seen 2026-10-30 — Jon: "lgtm". Nothing owed on this file except reading it, then deleting it.**
`/start` in a chat with a Table is one line with the Board untouched below it and no `/start` in the menu;
the refused `/end` reads the new sentence. Slices 5 and 6 are ✅ in `tasking.md`.

**The `@` you see** comes from `mjbot.py:248` (`'@' + username if username else first_name`) — an account
that has never set a username reads as a bare first name, and nothing can promise the `@` for those.

**One thing neither of us has seen:** the toast `@Al is already entering a win.`, which needs a *second*
seated player to tap a winner while someone else holds a draft. If nobody ever taps out of turn, that path
stays unexercised in the wild.

---

## The protocol as run (round 7, 2026-10-30) — kept so the wording is auditable

Step 9 of `/trace-n` needs a real human in a real Telegram DM. Jon was out when slices 5–7 landed, so the
protocol below was written for him to run later, and he ran it. Steps 1–10 are what he ticked; the two
amendments are at the top of this file.

**The 5-minute protocol that closes all three at once** (Jon + Jess, real DMs, `MJ_DEBUG=1`, log to a file):

1. `/new`, Jess `/join <CODE>` — **watch her screen move while you are typing** (the fan-out slice 4 never
   showed and slices 5–7 all lean on).
2. Score five wins → the Board should read `… 2 earlier — /history`.
3. `/history` in your DM → **her screen must not move** → `Back` returns the score Board, same message.
4. Any non-command message (a word, a sticker, a photo) → your Board refreshes and one short line names
   what you can tap; **it must arrive below the Board and never above it** (slice 6).
5. `/end` → `Confirm end` / `Keep playing`. Tap `Keep playing` first: nothing settles. Then `/end` →
   `Confirm end` → the settlement lands where your Board was and a fresh `$0.00` Board arrives beneath it
   **in both DMs**; one look at the chat should show exactly one live keyboard each.
6. Then have Jess start an Entry and you try `/end` → it must refuse and name her, not wipe the night.
7. Slice 4's three, still unwitnessed by me: change Max Tai and count the ladder shrink on *her* screen;
   have her tap `/settings` and read the refusal naming you; `/history` on a two-seat night so a line like
   `西 (empty) pays Al: $…` appears.

Anything that looks wrong, tell me which step and what you saw — I'd rather have a wire log than an
impression.

---

## Slice 5 — decisions I took on your recommendation

| # | Decision | Why, and what to reverse if you disagree |
| --- | --- | --- |
| 1 | **`/end` asks first, and the answer is a token, not state.** `Confirm end` carries a new callback kind `k`; `Keep playing` reuses slice 4's `b…menu`. Nothing is stored about who was asked. | AD21 has been the source of every stuck-chat defect in the 2022 bot; a dialog that lives in the button cannot strand anyone, and an unanswered one is simply replaced by the next Board. This is the shape your ruling implied, made concrete. |
| 2 | **The `k` token is version-checked** (a *write*), so a `Confirm end` left on screen after another win scored is refused as out of date rather than settling the new numbers with the old text on screen. | One tap more after any intervening win. Weakening it would let a stale dialog settle a night it never described. |
| 3 | **A confirmed `/end` still refuses while anyone holds a draft**, and the refusal reuses `_holder_notice`'s existing wording — so if the holder taps their own `/end` they read "You are entering a win — tap an amount, or Cancel", and anyone else reads "Bo is entering a win — only they can finish it." | Your ruling exactly. The wording is shared with the FR10 refusal rather than minted twice. |
| 4 | **`/end`'s refusal also re-renders that player's Board**, so the `⏳ Bo is entering a win` line shows them the reason next to the sentence that says it. | Costs one edit. Cut it if you want the refusal to be the only thing that moves. |
| 5 | **A vacant wind is named `西 (empty)`** in the settlement — your pick — via one new function, `render.transfer_names`, which is now the only source of names for `score.settle` and cannot return `None`. | Closes the latent `None pays Di: $3.20` the kernel would have produced on a short-handed night. |
| 6 | **The settlement repeats the four totals** above the transfer lines (your pick), because `/end` zeroes the Board in the same breath and `Bo pays Al: $2.80 / Bo pays Cy: $0.40` otherwise has nothing to check its `−$3.20` against. | 4 extra lines per settlement. |
| 7 | **`/history` is the chat's own Board message edited into the full log, with one `Back`.** This is the first view in the app whose *text* differs per viewer, so I widened the spec's "the Board text is identical in every DM" line and added two rows to the Board-keyboard table. | Spec amendments are marked `[slice-5 scrutiny amendment 2026-10-29]`. The alternative (posting the list) would have stranded a second live message, which FR12 forbids. |
| 8 | **`/history` and `/end` from a member with no seat** get the seat picker plus one line ("Take a seat first — pick a wind, then read the night back / settle it up"), matching what slice 4 ruled for `/settings`. | The three copies of that sentence became one helper, `Room._take_a_seat`. |
| 9 | **`NOT_BUILT` is now empty but kept**, with the comment that states the rule ("a menu offering a verb that only re-shows the Board teaches players that menus lie"). | Your call. `/prune` should delete the tuple, the filter in `commands_for`, and this comment once you agree the rule is recorded elsewhere. |
| 10 | ⚠️ **I over-claimed in scrutiny and withdrew it.** I wrote that S5.18 covered the `score.ZERO` alias risk; mutating `clear_round` to alias it **survived the whole suite**, because nothing in this codebase mutates a balance list in place (`_commit` rebinds a fresh one). The copy of `ZERO` stays as hygiene, but no test claims it. | If you want that risk actually walled, it needs an in-place mutation to exist first — i.e. it is not today's problem. |

---

## Slice 6 — decisions I took on your recommendation

| # | Decision | Why, and what to reverse if you disagree |
| --- | --- | --- |
| 1 | **A message with no text is not an attempted answer.** An empty payload still forgets the ask (a code question left lying around would otherwise turn their next real message into a table code), but it answers nothing. |
| 2 | **`/start` is a no-reset screen.** It edits or shows their Board and never posts a second live message; the help listing is built from `commands_for`, so a spectator's `/start` cannot advertise `/end`. |
| 3 | **A help line is allowed to ride the one Board message** — as text, one blank line under the state — rather than as its own message. | Costs one scroll. A second message would strand it below a live keyboard, which is FR12's whole point. |
| 4 | **A bare word is a refresh, not an attempted answer.** Spec FR14 literally says an answer "either advances its stage or is refused"; a word can never advance a stage (the stage advances on *taps* now), and the typed-answer exceptions are the two named by AD21. | I recorded this reading in `tasking.md`. If you want a stray `asdkjh` refused instead of refreshing, that is a one-line change and one test. |

---

## Slice 7 — docs: the wall, not the prose

| # | Decision | Why, and what to reverse if you disagree |
| --- | --- | --- |
| 1 | **The first act was a test, not a rewrite.** `tests/test_docs.py` checks both docs against the code: verbs named must exist, retired ones must appear nowhere, and the README's `MJ_*` table must match what `mjbot.py`/`config.py` read — in both directions. | `flow.md` was accurate in August and wrong by October with nothing noticing. Prose rots; a wall does not. |
| 2 | **Ban, don't name.** The wall forbids the retired verbs anywhere in the player docs, so there is no "these used to exist, don't type them" section. The README's command table is the record. | If you want a migration note for players who learned the old verb, put it here or in a CHANGELOG — somewhere the wall does not reach. |
| 3 | **The money tables were re-derived, not copied.** Every factor row in § 7 was recomputed from `score._tai/_kang/_flower` at rate 0.1 before being kept. They matched — including the two quirks, which stay documented rather than fixed (FR23). |
| 4 | **telebot internals left alone.** Smoke-testing showed telebot's `skip_pending` probe sends `long_polling_timeout=20` whatever `MJ_POLL_TIMEOUT` says, and `TeleBot(...)` fires a `validate_token` request at construction. Harmless (a poll is safe to repeat; `_request` gives polls a read window of `MJ_POLL_TIMEOUT + 10`), and out of a docs slice's way. | Flagged for `/review` if you disagree. |
| 5 | **The README's screenshots are labelled, not deleted** — they show the retired reply-keyboard UI, and the URLs are the only record of what the 2022 bot looked like. |

---

## Repo-hygiene decisions (reversible in one command each)

- **`.fac-a/`, `.pi/`, `scratchpad.md` are now in `.gitignore` and were NOT pushed.** AGENTS.md § Project
  Context Folders puts `.fac-a/` (mission state) and `.pi/` (personal config) outside the main repo, and
  `scratchpad.md` is a note to yourself. Everything that is *the bot* — `table.py`, `render.py`, `score.py`,
  `mjbot.py`, `libraries.py`, `tests/`, `docs/`, `README.md`, `requirements*.txt`, `pytest.ini`,
  `.env.example` — is committed. To push the mission notes anyway: `git add -f .fac-a/`.
- **`blockers_decisions.md` (this file) is committed**, so you can read it on GitHub or here. Delete it when
  done.
- **`.env` stays ignored** — it holds `MJ_TOKEN` and was never committed (verified before pushing).
- **`tests/support.py` now owns the keyboard helpers.** `board_text` / `keyboard_for` / `buttons_for` were
  written out four times across `test_settings.py`, `test_tables.py` and `test_amounts.py`; the copies are
  gone and all four files import one version. This touched slice 4's test files, which is why it is listed
  here rather than buried in the slice-5 record.
- **Prune candidates left for `/prune`** (I did not touch them — tidying other slices' code is not a slice's
  job): unused `pytest` imports in `test_delivery.py`, `test_entry.py`, `test_render.py` (+ unused `GUEST`
  there) and `test_table.py`; the empty `NOT_BUILT` filter above; `mjbot.py`'s Flask/webhook block, kept
  deliberately per AD14.

## Your scratchpad note — already fixed, please confirm live

`scratchpad.md`: *"after a wind direction is picked, the options to pick your seat should disappear."*
Slice 3's amendment made the seat offer ride the Board message itself, so seating **edits those buttons
away in place** instead of leaving a dead picker below (`tests/test_delivery.py::test_seating_edits_the_seat_offer_in_place`,
S3.11). Nothing was changed for it in slice 5. Worth one look in the real chat during the protocol above —
if you still saw a stale seat row, tell me what the message id was doing.
