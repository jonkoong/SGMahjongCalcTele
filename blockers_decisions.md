# Blockers & decisions taken while you were out

Mission `01-pooled-table`, run as `/trace-n` for slices 5, 6 and 7. You asked me to finish the slices,
commit and push, and take my own recommendations on anything blocked — this is that list, newest first.
**Delete this file once you have read it** (it is not part of the bot).

---

## 🔴 Blocker: the live self-check for slices 5, 6, 7 has not been witnessed

Step 9 of `/trace-n` needs a real human in a real Telegram DM. You were out, and a bot cannot witness its
own chat — so **no slice after slice 4 has a witnessed self-check**. Slices 5–7 close ⚠️, not ✅, for that
reason alone. The tests are green (see each slice's TDD record in `.fac-a/01-pooled-table/tasking.md`) and
each slice carries an offline wire transcript against `FakeBot` — auditable, but *not* the same evidence.

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
