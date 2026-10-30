"""/end — the night's transfers, then a wiped slate and the same four players for the next round."""
import render
import table
from tests.support import CYD, GUEST, DEB, HOST, board_text, keyboard_for, PLAYER, seated_four, \
    seated_table, tap


def a_night_two_up_two_down():
    """Al and Cy ahead, Bo and De behind — the shape that needs more than one transfer."""
    r, t = seated_four()
    for winner, payer, rung in ((0, 1, 3), (0, 3, 2), (2, 1, 1), (2, 1, 2), (0, 1, 1)):
        tap(r, t, HOST, "w", winner)
        tap(r, t, HOST, "a", "t%d" % rung)
        tap(r, t, HOST, "p", payer)
    return r, t


def transfer_lines(text):
    """The `X pays Y: $n` lines, in the order the kernel chose them."""
    return [ln for ln in text.splitlines() if " pays " in ln]


# S5.17, S4.7 — 🔴 the short-handed night slice 1 witnessed (two empty seats charged −$3.20 each)
# reaches score.settle with a name it was never written for. The money lives in the seat, not the
# person (AD4), so the seat is what the sentence must name — the 2022 kernel printed `None pays Di`.
def test_an_empty_seat_is_named_by_its_slot_in_the_settlement():
    r, t = seated_table()                          # seats 3 and 4 sit empty but still pay
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", "z")                      # Zi Mo — all three other slots pay

    text = render.settlement(t)

    assert "None" not in text
    assert "Bo pays Al: $0.20" in text
    assert "Player 3 (empty) pays Al: $0.20" in text and "Player 4 (empty) pays Al: $0.20" in text


# S5.12 — /end exists so the money can actually move, so the numbers come out of the frozen kernel in
# its own order (FR23), and the totals are repeated because the Board is about to forget them.
def test_the_settlement_repeats_the_totals_and_says_the_kernels_own_transfers():
    r, t = a_night_two_up_two_down()

    text = render.settlement(t)

    # Not `t.balances == [...]`: float residue is part of the frozen contract (Out of Scope), so the
    # numbers that count are the ones money() renders to cents for the players.
    assert transfer_lines(text) == ["Bo pays Al: $2.80", "Bo pays Cy: $0.40", "De pays Cy: $0.80"]
    assert "Player 1  Al" in text and "+$2.80" in text and "-$3.20" in text
    assert text.startswith("Table %s · settled" % t.code)


# S5.19 — /end is offered from the first hand, so a night with nothing to settle still answers. Out of
# Scope rules out inventing a case for it, so this pins the fall-through to the kernel's own words.
def test_a_night_with_nothing_to_settle_says_so():
    r, t = seated_four()

    text = render.settlement(t)

    assert transfer_lines(text) == [] and "No Payment" in text
    assert text.splitlines()[0] == "Table %s · settled" % t.code


# S5.10 — settlement is irreversible (no undo, memory only), so a mistyped /end must not wipe a night.
# The ask shows what is about to be lost, and asking is not doing (AD25).
def test_end_asks_before_anything_settles():
    r, t = a_night_two_up_two_down()
    before = (list(t.balances), list(t.log), t.version)

    effects = r.message(HOST, "/end")

    text = board_text(effects, HOST.user_id)
    assert len(transfer_lines(text)) == 3, "the ask has to show what confirming costs"
    assert keyboard_for(effects, HOST.user_id) == ["Confirm end", "Keep playing"]
    assert (t.balances, t.log, t.version) == before, "nothing has moved yet"
    assert [e.chat_id for e in effects if isinstance(e, table.Board)] == [HOST.user_id]


# S5.12 — the headline (FR19): say the night's money in the kernel's own words, then zero the balances and
# drop the log while the four players, the host and the settings all stay exactly where they were.
def test_a_confirmed_end_settles_then_zeroes_and_keeps_the_players():
    r, t = a_night_two_up_two_down()
    seats, host, rules = list(t.occupants), t.host_id, (t.rate, t.shooter, t.maxtai)
    names = dict(t.names)
    asked = t.version
    r.message(HOST, "/end")

    effects = tap(r, t, HOST, "k", "end")

    settled = [e for e in effects if isinstance(e, table.Retired)]
    assert len(settled) == 4, "every seated DM is owed the night's transfers, not just the one who asked"
    assert transfer_lines(settled[0].text) == ["Bo pays Al: $2.80", "Bo pays Cy: $0.40",
                                               "De pays Cy: $0.80"]
    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.log == []
    assert t.occupants == seats and t.host_id == host and (t.rate, t.shooter, t.maxtai) == rules
    assert t.names == names and r.tables[t.code] is t, "the roster is kept for the next round"
    assert t.version == asked + 1
    for board in [e for e in effects if isinstance(e, table.Board)]:
        assert "$0.00" in board.text and " wins " not in board.text


# S5.11 — the escape hatch works, which is the whole difference between a confirmation and a trap.
def test_keeping_playing_settles_nothing_and_gives_the_board_back():
    r, t = a_night_two_up_two_down()
    before = (list(t.balances), list(t.log))
    r.message(HOST, "/end")

    effects = tap(r, t, HOST, "b", "menu")

    assert keyboard_for(effects, HOST.user_id) == ["Al", "Bo", "Cy", "De", "Undo last win"]
    assert (t.balances, t.log) == before


# S5.10b — /end sits in the slash menu of the seated only. A member who joined and never sat, and typed it
# anyway, is told what is missing rather than watching a picker reappear that their screen already showed.
# (Leaving is not this state: /leave unbinds the player entirely, so a member with no seat is a joiner.)
def test_end_before_taking_a_seat_names_what_is_missing():
    r, t = seated_table()
    for _ in range(3):
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "t1")
        tap(r, t, HOST, "p", 1)
    r.message(CYD, "/join " + t.code)                 # bound, and seats 3 and 4 are still free

    effects = r.message(CYD, "/end")

    assert {PLAYER[w] for w in t.free_seats()} <= set(keyboard_for(effects, CYD.user_id))
    assert "seat" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
    assert len(t.log) == 3 and any(t.balances), "a night nobody sat through is not settled by a bystander"


# S5.12b — the keyboard is not the rule (S4.20's lesson, applied to the new verb): Telegram replays whatever
# data a button carried, so seating is re-checked at the tap and not only at the keyboard.
def test_a_confirm_tapped_without_a_seat_changes_nothing():
    r, t = seated_table()
    for _ in range(3):
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "t1")
        tap(r, t, HOST, "p", 1)
    r.message(CYD, "/join " + t.code)

    effects = tap(r, t, CYD, "k", "end")

    assert "seat" in next(e.text for e in effects if isinstance(e, table.Toast)).lower()
    assert len(t.log) == 3 and any(t.balances)


# S5.16 — the dialog is a write, so it is version-checked: a night that scored again after the ask is a
# different night, and the transfers it would print are no longer the ones on screen.
def test_a_confirm_from_a_superseded_screen_is_refused():
    r, t = a_night_two_up_two_down()
    r.message(HOST, "/end")
    stale = table.token("k", t.code, t.version, "end")
    tap(r, t, GUEST, "w", 1)
    tap(r, t, GUEST, "a", "t1")
    tap(r, t, GUEST, "p", 0)                          # a win lands after the ask

    effects = r.tap(HOST, stale)

    assert "out of date" in next(e.text for e in effects if isinstance(e, table.Toast)).lower()
    assert len(t.log) == 6 and any(t.balances), "nothing was said and nothing was wiped"


# S5.14 — the night is shared, so the settlement is too; the member who joined but never sat holds no
# slot and is owed none of it.
def test_every_seated_dm_is_settled_and_an_unseated_member_is_left_alone():
    r, t = seated_table()
    for _ in range(3):
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "t1")
        tap(r, t, HOST, "p", 1)
    r.message(DEB, "/join " + t.code)                 # bound, unseated: holds no money (AD4)
    r.message(HOST, "/end")

    effects = tap(r, t, HOST, "k", "end")

    owed = sorted([HOST.user_id, GUEST.user_id])
    settled = [e for e in effects if isinstance(e, table.Retired)]
    assert sorted(e.chat_id for e in settled) == owed
    assert settled[0].text == settled[1].text, "one night, said identically in both DMs"
    assert sorted(e.chat_id for e in effects if isinstance(e, table.Board)) == owed
    assert DEB.user_id not in [e.chat_id for e in effects]


# S5.18 — two nights run in one process (FR5), and /end belongs to exactly one of them. Mutation-checked:
# point `_end` at the wrong Table and this is the test that says so.
def test_settling_one_table_leaves_the_other_nights_money_alone():
    r, t = a_night_two_up_two_down()
    r.message(CYD, "/leave")
    r2 = r.table_of(CYD)
    r.message(CYD, "/new")
    t2 = r.table_of(CYD)
    r.tap(CYD, table.token("s", t2.code, t2.version, 0))
    tap(r, t2, CYD, "w", 0)
    tap(r, t2, CYD, "a", "t1")
    tap(r, t2, CYD, "p", "z")
    other = (list(t2.balances), list(t2.log))
    assert any(t2.balances), "the second night has money to lose, or this proves nothing"
    r.message(HOST, "/end")

    r.tap(HOST, table.token("k", t.code, t.version, "end"))

    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert (t2.balances, t2.log) == other


# S5.15 — FR10 is not overridable by a confirmation. /end is offered to every seated player, so without
# this a bystander could destroy the Entry someone else is halfway through; the Board is re-rendered so
# they can see *why*, not just be told (FR9, FR15).
def test_confirming_end_while_someone_is_entering_a_win_refuses_and_names_them():
    r, t = a_night_two_up_two_down()
    tap(r, t, GUEST, "w", 1)                          # Bo is halfway through an Entry (a draft bumps)
    before = (list(t.balances), list(t.log), t.version)
    r.message(HOST, "/end")

    effects = tap(r, t, HOST, "k", "end")

    refusal = next(e.text for e in effects if isinstance(e, table.Line))
    # FR27 (Jon, 2026-10-30) — the sentence names the reason, not just the holder. It replaces the wording
    # the tap-time refusal uses, because "only they can finish it" answers a question the refuser did not ask.
    assert refusal == "Game cannot end when someone is entering a win — Bo is entering a win.", refusal
    assert (t.balances, t.log, t.version) == before, "no money said, no slate wiped, nothing bumped"
    assert t.pending is not None, "Bo's draft is untouched"
    assert "⏳ Bo is entering a win" in board_text(effects, HOST.user_id)   # the Board says why too


# S5.15b — the holder, told the same sentence, would not be told what to do next. Their own `/end` still
# reads the stage they are standing in (the one line that makes the refusal actionable).
def test_the_holder_who_tries_to_end_reads_what_to_tap_next():
    r, t = a_night_two_up_two_down()
    tap(r, t, GUEST, "w", 1)
    r.message(GUEST, "/end")

    effects = tap(r, t, GUEST, "k", "end")

    assert next(e.text for e in effects if isinstance(e, table.Line)) == \
        "You are entering a win — tap an amount, or Cancel."
    assert t.pending is not None
