"""The full amount stage — six kinds, Zi Mo, Cancel. Slice 2."""
import pytest

import table
from tests.support import GUEST, HOST, board_text, buttons, seated_table, tap


# S2.1
def test_kang_asks_who_fed():
    r, t = seated_table()
    stage = tap(r, t, HOST, "w", 0)                      # 東 won
    assert "Kang" in buttons(stage), "the amount stage must offer Kang"

    effects = tap(r, t, HOST, "a", "kang")

    assert set(buttons(effects)) == {"Bo", "Zi Mo", "Cancel"}
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


# S2.5 — 🐈 and 🥀 share one kernel but disagree about whether anyone fed it.
def test_the_cat_needs_no_feeder_and_the_flower_does():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)

    effects = tap(r, t, HOST, "a", "animal")
    assert t.pending is None                                   # the cat commits at once
    assert t.balances == pytest.approx([0.3, -0.1, -0.1, -0.1])
    assert "Al wins 🐈: +$0.30" in board_text(effects)

    tap(r, t, HOST, "w", 0)
    stage = tap(r, t, HOST, "a", "flower")
    assert t.pending is not None                               # the flower asks who fed
    assert "Cancel" in buttons(stage)


# S2.6 — the holder can throw a half-entered win away, and it leaves no trace.
def test_the_holder_cancels_a_half_entered_win():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "kang")                              # waiting on a feeder

    effects = tap(r, t, HOST, "x", "c")

    assert t.pending is None
    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.log == []
    assert set(buttons(effects)) == {"Al", "Bo"}               # back to tapping a name


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
    assert any(isinstance(e, table.Toast) and "Al" in e.text for e in effects)


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
    assert set(buttons([boards[GUEST.user_id]])) == {"Al", "Bo"}     # winner row, unchanged
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
    assert any(isinstance(e, table.Toast) and "Al" in e.text for e in effects)


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
    assert "out of date" in toast.text


# S2.13 — a seat keyboard is judged by the seat, not the version: the joiner must still be able
# to sit down after someone else takes a wind.
def test_a_late_seat_pick_is_judged_on_the_seat_not_the_version():
    r, t = seated_table()
    late = table.User(44, "Di")
    r.message(late, "/join " + t.code)                  # their seat keyboard names version N
    tap(r, t, GUEST, "w", 1)                            # ... and the table has moved on
    stale = table.token("s", t.code, t.version - 1, 2)

    effects = r.tap(late, stale)

    assert t.occupants[2] == late.user_id
    assert not [e for e in effects if isinstance(e, table.Toast)]
