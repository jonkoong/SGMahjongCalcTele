"""The full amount stage — six kinds, Zi Mo, Cancel. Slice 2."""
import pytest

import table
from tests.support import GUEST, HOST, board_text, buttons, buttons_for, entry_texts, keyboard_for, \
    PLAYER, seated_four, seated_table, tap


# S2.1
def test_kang_asks_who_fed():
    r, t = seated_table()
    stage = tap(r, t, HOST, "w", 0)                      # seat 1 won
    assert "Kang" in buttons(stage), "the amount stage must offer Kang"

    effects = tap(r, t, HOST, "a", "kang")

    # S4.3 (FR4): the two empty seats are offered too — an empty slot pays exactly as it is paid.
    assert set(buttons(effects)) == {"Bo", PLAYER[2], PLAYER[3], "Zi Mo", "Cancel"}
    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.pending["holder"] == HOST.user_id


# S2.2 — Kang is only real once somebody is named as the feeder.
def test_naming_the_feeder_settles_kang_at_the_golden_number():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")

    effects = tap(r, t, HOST, "p", 1)          # the holder names the feeder

    # 0.1 × 3 leaves float residue — a frozen quirk, so assert the number, not clean cents.
    assert t.balances == pytest.approx([0.3, -0.3, 0.0, 0.0])
    assert t.pending is None
    assert len(t.log) == 1
    assert "Al wins Kang from Bo: +$0.30" in board_text(effects)


# S2.3 — Kang may also be self-drawn, in which case all three others pay.
def test_kang_on_zi_mo_is_paid_by_every_other_seat():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")

    effects = tap(r, t, HOST, "p", "z")

    assert t.balances == pytest.approx([0.3, -0.1, -0.1, -0.1])
    assert "Al wins Kang on Zi Mo: +$0.30" in board_text(effects)


# S2.4 — a concealed Kang does not ask who fed, and it is not Zi Mo either.
def test_kang_an_settles_on_one_tap_with_no_feeder_wording():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "kang_an")

    assert t.pending is None                                    # stage 3 is skipped
    assert t.balances == pytest.approx([0.6, -0.2, -0.2, -0.2])   # rate 0.1 × factor 6
    assert "Al wins Kang 暗: +$0.60" in board_text(effects)
    assert "from" not in board_text(effects) and "Zi Mo" not in board_text(effects)


# S2.5 (amended by FR1) — 🐈 still commits on one tap, pays the rate three times over, and names nobody
# in the line. The old version of this test existed to contrast the cat with 🥀, which then *did* ask;
# the flower stopped asking, so the cat keeps its own assertions instead of losing them with the contrast.
def test_the_cat_needs_no_feeder_and_names_none():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "animal")

    assert t.pending is None
    assert t.balances == pytest.approx([0.3, -0.1, -0.1, -0.1])
    line = [ln for ln in board_text(effects).splitlines() if " wins " in ln][-1]
    assert line == "Al wins 🐈: +$0.30"


# S3.1 — 🥀 is not a tile somebody fed (FR1). The stage it used to open asked a question the money then
# ignored, and with Shooter off it asked, got an answer, and paid nobody at all.
def test_the_flower_commits_on_one_tap_and_asks_nobody():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "flower")

    assert t.pending is None, "the tap that chose 🥀 booked the win — there was no second stage"
    assert len(t.log) == 1
    assert "Zi Mo" not in buttons(effects) and "Cancel" not in buttons(effects)


# S3.2 (FR1) — the number every flower pays: the rate out of all three other seats, in the frozen
# residue it leaves (`pytest.approx`, for the reason S2.2 gives).
def test_the_flower_takes_the_rate_from_all_three_other_seats():
    r, t = seated_four()
    tap(r, t, HOST, "w", 0)

    tap(r, t, HOST, "a", "flower")

    assert t.balances == pytest.approx([0.3, -0.1, -0.1, -0.1])


# S3.3 (FR1) — the bug itself: Shooter used to decide whether 🥀 paid anybody at all. The same tap now
# leaves the same four numbers whichever way the setting sits.
@pytest.mark.parametrize("shooter", [True, False], ids=["shooter on", "shooter off"])
def test_the_flower_pays_the_same_with_shooter_on_and_off(shooter):
    r, t = seated_four()
    tap(r, t, HOST, "v", "shooter1" if shooter else "shooter0")
    tap(r, t, HOST, "w", 0)

    tap(r, t, HOST, "a", "flower")

    assert t.balances == pytest.approx([0.3, -0.1, -0.1, -0.1])


# S3.4 (02/FR2) — no feeder row for 🥀 in either Shooter state. What a player can act on is the keyboard;
# the rule behind it is pinned at its own boundary in tests/test_score.py.
@pytest.mark.parametrize("shooter", [True, False], ids=["shooter on", "shooter off"])
def test_the_flower_offers_no_feeder_row_in_either_shooter_state(shooter):
    r, t = seated_four()
    tap(r, t, HOST, "v", "shooter1" if shooter else "shooter0")
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "flower")

    assert t.pending is None
    assert "Zi Mo" not in buttons(effects) and "Cancel" not in buttons(effects)


# S3.5 (FR15) — 🥀 暗 paid six times the rate in both Shooter states before this mission, and still
# does. The only money that moves is the open flower's.
@pytest.mark.parametrize("shooter", [True, False], ids=["shooter on", "shooter off"])
def test_the_concealed_flower_still_pays_six_times_the_rate(shooter):
    r, t = seated_four()
    tap(r, t, HOST, "v", "shooter1" if shooter else "shooter0")
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "flower_an")

    assert t.pending is None
    assert t.balances == pytest.approx([0.6, -0.2, -0.2, -0.2])
    assert "Al wins 🥀 暗: +$0.60" in board_text(effects)


# S3.6 — nobody fed a flower, so the line names nobody. `from X` used to sit there, naming a player
# whose name made no difference to the money printed beside it.
def test_the_flower_line_names_no_feeder():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "flower")

    line = [ln for ln in board_text(effects).splitlines() if " wins " in ln][-1]
    assert line == "Al wins 🥀: +$0.30"
    assert "from" not in line and "Zi Mo" not in line


# S3.7 — the keyboard is not the rule. Telegram redelivers the feeder button a 🥀 screen used to
# carry, and the win it would have finished is already booked: the tap is refused, and the money does
# not go round a second time. 02b/D9 ruled which words it gets: the button exists only at another
# stage, so the honest story is that its screen has been replaced — one line, shared by ten guards.
def test_a_stray_flower_feeder_tap_books_nothing():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "flower")                        # booked at once
    stranded = table.token("p", t.code, t.version, 1)     # the button the old screen carried
    before, wins = list(t.balances), len(t.log)

    effects = r.tap(HOST, stranded)

    assert next(e.text for e in effects if isinstance(e, table.Toast)) == table.OUTDATED
    assert t.balances == before and len(t.log) == wins


# S3.8 (02/FR2, ERR-02) — Kang keeps asking. With Shooter off the answer does not change which seats pay,
# but it still decides Zi Mo (twice the rate) against a named feeder, so the question is a real one.
@pytest.mark.parametrize("shooter", [True, False], ids=["shooter on", "shooter off"])
def test_kang_still_asks_who_fed_it(shooter):
    r, t = seated_four()
    tap(r, t, HOST, "v", "shooter1" if shooter else "shooter0")
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "kang")

    assert t.pending is not None and t.pending["amount"] == ("kang", None)
    assert set(buttons(effects)) == {"Bo", "Cy", "De", "Zi Mo", "Cancel"}


# S3.9 (FR15) — the two Kang answers with Shooter off, driven through the taps: Zi Mo pays six times
# the rate, a named feeder three.
def test_kang_named_and_zi_mo_still_pay_differently_with_shooter_off():
    paid = []
    for feeder in ("z", "1"):
        r, t = seated_four()
        tap(r, t, HOST, "v", "shooter0")
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "kang")
        tap(r, t, HOST, "p", feeder)
        paid.append(list(t.balances))

    assert paid[0] == pytest.approx([0.6, -0.2, -0.2, -0.2])       # Zi Mo — twice the named feeder
    assert paid[1] == pytest.approx([0.3, -0.1, -0.1, -0.1])       # Bo fed it


# S3.10 — with Shooter off, naming seat 2 or seat 3 moves the same money: the named seat is ignored,
# which is the documented quirk. What is not ignored is the line — it names whoever was tapped.
def test_which_seat_kang_names_with_shooter_off_moves_the_same_money():
    nights = []
    for feeder in (2, 3):
        r, t = seated_four()
        tap(r, t, HOST, "v", "shooter0")
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "kang")
        effects = tap(r, t, HOST, "p", feeder)
        nights.append((list(t.balances), board_text(effects)))

    assert nights[0][0] == nights[1][0], "the named seat decides nothing with Shooter off"
    assert "Al wins Kang from Cy: +$0.30" in nights[0][1]
    assert "Al wins Kang from De: +$0.30" in nights[1][1]


# S4.3 (FR4) — an empty seat may be named as the feeder: it pays out of its own slot, the same way an
# empty seat is paid when it wins. The only seat that may not feed is the winner's own.
def test_an_empty_seat_can_be_named_feeder_and_pays():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)                                 # Al won
    tap(r, t, HOST, "a", "t1")

    tap(r, t, HOST, "p", 3)                                 # seat 4 holds nobody

    assert t.balances == pytest.approx([0.4, 0.0, 0.0, -0.4])
    assert entry_texts(t)[-1] == "Al wins 1 Tai from Player 4: +$0.40"


# S4.4 (FR4, unchanged by opening the seats) — the winner is still not a feeder, and their seat is not
# offered in their place: naming the slot they hold would be naming them.
def test_the_winner_is_still_not_their_own_feeder():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "kang")

    assert set(buttons(effects)) == {"Bo", PLAYER[2], PLAYER[3], "Zi Mo", "Cancel"}
    assert "Al" not in buttons(effects), "their own seat is not on this row under any label"
    before = list(t.balances)
    refused = tap(r, t, HOST, "p", 0)
    # 02b/D9 — a winner as their own feeder is a rule, not a stale screen, and the rule is stated by the
    # row itself: the winner's own seat is not on it. So the tap answers with the player's own screen.
    assert not [e for e in refused if isinstance(e, table.Toast)], "no popup: the board answers"
    assert any(isinstance(e, table.Board) and e.chat_id == HOST.user_id for e in refused)
    assert t.balances == before and t.pending is not None


# S4.12 — four seated is what a night looks like (AS4), and opening the empty seats changed nothing for
# a table that has none: the same four names, and a scoreless night still offers no way to undo.
def test_a_full_table_is_offered_what_it_always_was():
    r, t = seated_four()

    row = keyboard_for(r.message(HOST, "/board"), HOST.user_id)

    assert row == ["Al", "Bo", "Cy", "De"]
    assert not [label for label in row if label.startswith("Player")]


# S2.6 — the holder can throw a half-entered win away, and it leaves no trace.
def test_the_holder_cancels_a_half_entered_win():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")                              # waiting on a feeder

    effects = tap(r, t, HOST, "x", "c")

    assert t.pending is None
    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.log == []
    assert set(buttons(effects)) == {"Al", "Bo", PLAYER[2], PLAYER[3]}    # back to tapping a seat


# S2.7 — a half-entered win belongs to whoever started it.
def test_only_the_holder_may_cancel_and_a_refusal_leaves_the_keyboard_live():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")
    version = t.version

    effects = tap(r, t, GUEST, "x", "c")

    assert t.pending is not None
    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.version == version                    # a refusal must not kill the holder's keyboard
    # 02b/D9 — the guard is what stops a bystander discarding the holder's draft; the sentence naming the
    # holder went, and the heal is the tapper's own Board. `⏳ Al is entering a win` is on it.
    assert not [e for e in effects if isinstance(e, table.Toast)], "no popup: the board answers"
    assert "⏳ Al is entering a win" in board_text(effects, GUEST.user_id)


# S2.8 — a stray message names the holder; FR15 says it also names *their own* options, and
# since slice 2 those differ per player: only the holder may act on the draft.
def test_a_stray_message_tells_a_bystander_who_holds_it_and_no_more():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")

    effects = r.message(GUEST, "/board")

    text = next(e.text for e in effects if isinstance(e, table.Line))
    assert "Al" in text
    assert "Cancel" not in text            # they have no Cancel button to tap


# S2.8 — the holder asking where they stand gets told what is left to tap.
def test_the_holder_is_told_what_they_are_waiting_for():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")

    effects = r.message(HOST, "/board")

    text = next(e.text for e in effects if isinstance(e, table.Line))
    assert "You" in text and "Cancel" in text


# S2.9 — the whole stage on Telegram, with a hostile name, max tai and version number.
def test_the_full_amount_stage_offers_todays_six_kinds_and_fits_telegram():
    r, t = seated_table()
    t.maxtai = 10
    t.names[GUEST.user_id] = "Aarón Miguel Ángel"
    t.version = 999999

    stage = buttons(tap(r, t, HOST, "w", 0))

    assert set(stage) == {"%d Tai" % n for n in range(1, 11)} | {
        "Kang", "Kang 暗", "🐈", "🐈 暗", "🥀", "🥀 暗", "Cancel"}
    assert max(len(tok.encode("utf-8")) for tok in stage.values()) <= 64


# S2.10 — a row of six does not survive a phone screen.
def test_the_six_specials_are_three_rows_of_two():
    r, t = seated_table()

    board = next(e for e in tap(r, t, HOST, "w", 0) if isinstance(e, table.Board))
    rows = [[label for label, _ in row] for row in board.rows]

    assert [row for row in rows if len(row) == 2] == [
        ["Kang", "Kang 暗"], ["🐈", "🐈 暗"], ["🥀", "🥀 暗"]]


# S2.11 — the stage belongs to whoever started it, so only they are offered its buttons.
def test_only_the_holder_is_offered_the_stage_buttons():
    r, t = seated_table()

    effects = tap(r, t, HOST, "w", 0)

    boards = {e.chat_id: e for e in effects if isinstance(e, table.Board)}
    assert set(buttons([boards[HOST.user_id]])) == (
        {"%d Tai" % n for n in range(1, 6)} |
        {"Kang", "Kang 暗", "🐈", "🐈 暗", "🥀", "🥀 暗", "Cancel"})
    assert set(buttons([boards[GUEST.user_id]])) == {"Al", "Bo", PLAYER[2], PLAYER[3]}  # winner row
    assert boards[HOST.user_id].text == boards[GUEST.user_id].text   # the score stays shared


# S2.12 — retiring FR10: a draft is not a group edit.
def test_a_second_player_cannot_finish_someone_elses_draft():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")
    before, version = list(t.balances), t.version

    effects = tap(r, t, GUEST, "p", 1)

    assert t.balances == before and t.pending is not None
    assert t.version == version                                # their screen stays live
    # 02b/D9 — the rule is the whole point of the guard, and the tapper's own Board carries the `⏳` line
    # that says who holds it, so the popup naming the holder is gone.
    assert not [e for e in effects if isinstance(e, table.Toast)], "no popup: the board answers"
    assert "⏳ Al is entering a win" in board_text(effects, GUEST.user_id)


# S2.13 — the six taps that looked like a broken Cancel: a button from a dead screen.
def test_a_button_from_a_superseded_screen_is_refused_as_out_of_date():
    r, t = seated_table()
    stale = table.token("w", t.code, t.version, 0)      # the screen still in the player's hand
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    before, version = list(t.balances), t.version

    effects = r.tap(GUEST, stale)

    assert t.balances == before and t.version == version
    assert t.pending["winner"] == 0 and t.pending["amount"] == ("tai", 3)
    toast = next(e for e in effects if isinstance(e, table.Toast))
    assert toast.text == table.OUTDATED, "decided copy, word for word (02b/D10)"
    assert any(isinstance(e, table.Board) and e.chat_id == GUEST.user_id for e in effects), \
        "and the tap re-draws this player's own screen — that is the refresh the sentence promises"


# S2.13 — a seat keyboard is judged by the seat, not the version: the joiner must still be able
# to sit down after someone else takes a seat.
def test_a_late_seat_pick_is_judged_on_the_seat_not_the_version():
    r, t = seated_table()
    late = table.User(44, "Di")
    r.message(late, "/join " + t.code)                  # their seat keyboard names version N
    tap(r, t, GUEST, "w", 1)                            # ... and the table has moved on
    stale = table.token("s", t.code, t.version - 1, 2)

    effects = r.tap(late, stale)

    assert t.occupants[2] == late.user_id
    assert not [e for e in effects if isinstance(e, table.Toast)]


# F-04 — "tai" is a key of score.AMOUNTS because the kernel names its ladder that way, which is a
# different fact from "a player may tap tai". The tap was taken as a concealed win at zero tai and
# died in the entry line on SPECIAL_AMOUNTS["tai"] — out through the polling thread, where F-04 threw
# away the taps queued behind it. Same accident, two layers. The keyboard is not the rule; S4.20
# ruled that for the winner stage already.
def test_tapping_the_name_of_the_ladder_is_refused_where_a_rung_would_score():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    version = t.version

    refused = tap(r, t, HOST, "a", "tai")

    assert t.pending["amount"] is None
    assert t.version == version, "a refused tap spends nothing"
    assert next(e.text for e in refused if isinstance(e, table.Toast)) == table.OUTDATED

    tap(r, t, HOST, "a", "t3")                             # the ladder itself is unharmed
    assert t.pending["amount"] == ("tai", 3)


# F-05 — a payer meaning that is neither Zi Mo nor a seat fell through to `payer = None`, which is
# exactly what Zi Mo means: a stale or forged tap booked a self-fed win at the frozen number. The
# amount stage refuses its own junk; the payer stage refused nothing.
def test_a_payer_that_is_neither_a_seat_nor_zi_mo_is_refused():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")
    before, log = list(t.balances), len(t.log)

    refused = tap(r, t, HOST, "p", "9")

    assert t.pending is not None, "the draft is still open — nothing was booked"
    assert t.balances == before and len(t.log) == log
    # 02b/D15 — junk that no screen ever carried, so it shares the out-of-date line rather than naming a
    # choice the player was never offered.
    assert next(e.text for e in refused
                if isinstance(e, table.Toast)) == table.OUTDATED


# F-09 — the FR10 sentence is the whole answer a spectator gets, and nothing pinned it: both holder
# tests assert `pending is None` and a substring the seat-refusal branch also satisfies, and neither
# looks at the keyboard the non-holder is shown. That Al is offered no way to finish Bo's win is what
# was witnessed live and has never been tested. 02b/D9 took the sentence; what it left behind is the
# witness that matters more — the tapper's own screen, whose ladder has no way to finish it.
def test_a_member_who_taps_a_finish_that_is_not_theirs_earns_no_draft():
    r, t = seated_table()
    stage = tap(r, t, GUEST, "w", 1)                           # Bo is entering a win
    assert "3 Tai" not in buttons_for(stage, HOST.user_id), "Al was never offered a way to finish it"
    finish = buttons_for(stage, GUEST.user_id)["3 Tai"]        # what Bo's screen offered

    refused = r.tap(HOST, finish)                              # Al taps it from somewhere else

    assert t.pending is not None and t.pending["amount"] is None, "Al may not finish Bo's win"
    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert not [e for e in refused if isinstance(e, table.Toast)], "no popup: the board answers"
    assert "⏳ Bo is entering a win" in board_text(refused, HOST.user_id), \
        "and the Board says who holds it, beside the buttons that cannot finish it"
