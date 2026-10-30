"""
Undo: one tap takes the newest win back out of the night.

The money went in as a vector, so it comes back out as a pop. Undoing by subtraction leaves float
residue (56.5% of two-win nights failed to unwind, worst error 1.8e-15) that reached `/end` as
`pays $0.00` lines.
"""
import pytest

import render
import score
import table
from tests.support import CYD, GUEST, HOST, board_text, entry_deltas, entry_texts, fold, \
    keyboard_for, PLAYER, score_wins, seated_four, seated_table, shown_wins, tap, tap_end_exit, tokens_of, undo

UNDO = "Undo last win"



# The money comes back exactly, not to the cent.
def test_undo_hands_the_money_back_exactly():
    r, t = seated_table()
    before = t.balances
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)
    assert t.balances != before, "the win has to have moved money, or this proves nothing"

    undo(r, t, HOST)

    assert t.balances == before
    assert t.log == []


# One win, not two, and the rest are not rewritten; asserted on /history, where a player checks.
def test_undo_removes_the_newest_line_and_keeps_the_rest_in_order():
    r, t = seated_four()
    score_wins(r, t, 3)
    wrote = entry_texts(t)
    assert len(set(wrote)) == 3, "three different wins, or this proves nothing"

    undo(r, t, HOST)

    assert shown_wins(board_text(r.message(HOST, "/history"), HOST.user_id)) == wrote[:2]


# The button is offered only when there is a win to take back; a dead button teaches players that
# buttons lie.
def test_undo_is_offered_only_when_there_is_something_to_undo():
    r, t = seated_four()

    assert UNDO not in keyboard_for(r.message(HOST, "/board"), HOST.user_id)

    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)

    assert UNDO in keyboard_for(r.message(HOST, "/board"), HOST.user_id)


# One undo row, on the scoreboard screen only. On the ladder or who-fed screen it would be a second
# way to abandon the win being entered, and nothing is committed there to undo.
def test_undo_sits_under_the_seats_on_the_scoreboard_only():
    r, t = seated_four()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)

    board = keyboard_for(r.message(HOST, "/board"), HOST.user_id)
    tap(r, t, HOST, "w", 0)
    ladder = keyboard_for(r.message(HOST, "/board"), HOST.user_id)
    tap(r, t, HOST, "a", "t1")
    fed = keyboard_for(r.message(HOST, "/board"), HOST.user_id)

    assert board[:4] == ["Al", "Bo", "Cy", "De"] and board[-1] == UNDO, "under the seats, not over them"
    assert UNDO not in ladder and any(label.endswith(" Tai") for label in ladder)
    assert UNDO not in fed and "Zi Mo" in fed


# The log is about to hold a win somebody is halfway through, so undo waits. Same gate as `/end`;
# a second tap does not override a refusal.
def test_undo_is_refused_while_someone_is_entering_a_win_and_names_them():
    r, t = seated_four()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)
    tap(r, t, GUEST, "w", 1)                          # Bo is holding a draft
    before = (list(t.log), t.balances, t.version)

    effects = undo(r, t, HOST)

    refusal = next(e.text for e in effects if isinstance(e, table.Toast))
    assert "Bo" in refusal and "undo" in refusal.lower(), refusal
    assert (t.log, t.balances, t.version) == before, "nothing moved, nothing bumped"
    assert [e for e in effects if isinstance(e, table.Board)] == [], "nobody else's screen is touched"


# The keyboard is not the rule: Telegram redelivers a token the Board stopped offering, so an
# empty log must be refused at the tap. Unguarded, it is an IndexError that kills the polling thread.
def test_undo_with_nothing_to_undo_is_refused_and_pops_nothing():
    r, t = seated_table()
    before = (list(t.log), t.balances, t.version)

    effects = undo(r, t, HOST)                            # a well-formed token, on a night with no wins

    # The button is hidden on an empty log, so this token came from a screen that is gone: it gets
    # the shared out-of-date line and the tapper's own Board.
    assert next(e.text for e in effects if isinstance(e, table.Toast)) == table.OUTDATED
    assert (t.log, t.balances, t.version) == before
    assert [e.chat_id for e in effects if isinstance(e, table.Board)] == [HOST.user_id], \
        "the tapper's own screen, and no other chat is owed anything"


# The night belongs to all four, so anyone may take a win back, not only whoever made the mistake.
def test_anyone_seated_may_undo_a_win_they_did_not_record():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)

    effects = undo(r, t, GUEST)

    assert t.log == [] and t.balances == [0.0, 0.0, 0.0, 0.0]
    assert [e for e in effects if isinstance(e, table.Toast)] == []
    assert t.seat_of(GUEST.user_id) == 1, "Bo was never asked to take a seat to do it"


# Undo is a write: every seated Board is redrawn once, and the version bump retires the screens
# that showed the win.
def test_undo_redraws_every_board_and_retires_the_screen_it_came_from():
    r, t = seated_four()
    score_wins(r, t, 3)
    stale_winner = table.token("w", t.code, t.version, 1)     # the scoreboard, before the undo
    before = t.version

    effects = undo(r, t, HOST)

    assert sorted(e.chat_id for e in effects if isinstance(e, table.Board)) == sorted(t.seated_ids())
    assert t.version == before + 1, "one bump for one change, not one per Board"
    later = r.tap(HOST, stale_winner)
    assert next(e.text for e in later if isinstance(e, table.Toast)) == table.OUTDATED


# One win per tap, all the way back to an empty night. It takes more than two Entries to catch an
# implementation that clears the log or pops the oldest win. Balances are compared exactly.
def test_undo_steps_back_through_the_whole_night():
    r, t = seated_four()
    score_wins(r, t, 9)
    ledger = list(t.log)
    walked = [t.balances]

    for left in reversed(range(9)):
        undo(r, t, HOST)
        assert t.log == ledger[:left], "undo %d took the newest win, not some other one" % (9 - left)
        assert t.balances == fold(entry_deltas(t)), "the totals are what the rest of the night adds to"
        assert t.balances != walked[-1], "undo %d moved the money back too" % (9 - left)
        walked.append(t.balances)

    assert t.balances == [0.0, 0.0, 0.0, 0.0], "and the night unwinds exactly"


# One win, undone, leaves the clean Board of a night not yet started, with no row that would only
# refuse.
def test_undoing_the_last_win_of_the_night_takes_the_button_away():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)

    undo(r, t, HOST)

    assert UNDO not in keyboard_for(r.message(HOST, "/board"), HOST.user_id)
    assert shown_wins(render.board(t)) == []


# `u` is a write, so it is version-checked: from a stale Board the same tap would eat a win scored
# after that screenshot.
def test_an_undo_token_from_a_superseded_screen_is_refused():
    r, t = seated_four()
    score_wins(r, t, 1)
    stale = table.token("u", t.code, t.version, "last")
    tap(r, t, HOST, "w", 1)
    tap(r, t, HOST, "a", "t2")
    tap(r, t, HOST, "p", 2)                             # a second win lands after that Board
    ledger = list(t.log)

    effects = r.tap(HOST, stale)

    assert next(e.text for e in effects if isinstance(e, table.Toast)) == table.OUTDATED
    assert t.log == ledger, "the newest win survived an undo aimed at the one before it"


# Being at the Table is not being at the table: money sits in seats, so only a seat holder decides
# its fate. With a live token and their own code, the seat is the one remaining check.
def test_a_member_holding_no_seat_cannot_undo():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)
    r.message(CYD, "/join " + t.code)                   # bound to the Table, holding no seat
    ledger, before = list(t.log), t.balances

    effects = tap(r, t, CYD, "u", "last")

    # A seatless member can still see undo's button; the guard stops them, and the picker answers.
    assert not [e for e in effects if isinstance(e, table.Toast)], "no popup: the picker answers"
    assert set(keyboard_for(effects, CYD.user_id)) == {PLAYER[w] for w in t.free_seats()}
    assert t.log == ledger and t.balances == before


# A settled night has no log, and undo does not cross `/end`. The fresh Board offers nothing to
# undo, and an old token is refused by the rule: the version moved, and even a current one has
# nothing to pop.
def test_nothing_is_left_to_undo_once_the_night_is_settled():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)
    effects = tap_end_exit(r, t, HOST, table.RESET_SCOREBOARD)

    assert UNDO not in keyboard_for(effects, HOST.user_id)
    later = tap(r, t, HOST, "u", "last")
    assert next(e.text for e in later if isinstance(e, table.Toast)) == table.OUTDATED


# Telegram allows 64 bytes of callback_data per button, undo included. Checked at the widest
# configuration: the full ladder, the who-fed stage, and a night long enough to advance the version.
def test_every_token_on_a_scored_board_fits_telegrams_64_bytes():
    r, t = seated_four()
    tap(r, t, HOST, "v", "maxtai%d" % score.MAX_TAI)
    score_wins(r, t, 3)
    scored = r.message(HOST, "/board")
    tap(r, t, HOST, "w", 0)
    ladder = r.message(HOST, "/board")
    tap(r, t, HOST, "a", "t%d" % score.MAX_TAI)
    fed = r.message(HOST, "/board")

    tokens = tokens_of(scored) + tokens_of(ladder) + tokens_of(fed)

    assert any(tok.startswith("u.") for tok in tokens), "undo's own token is in this set, or it is untested"
    assert max(len(tok.encode("utf-8")) for tok in tokens) <= 64, max(tokens, key=len)


# Money lives in the seat, so undo takes it back out of the seat. Someone arriving after the win is
# not consulted or charged: the pop touches the log and the fold and reads no names.
def test_the_money_comes_back_out_of_the_seat_that_earned_it():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)                             # seat 0 is +$1.60
    r.message(HOST, "/leave")                           # the money stays in the seat
    r.message(CYD, "/join " + t.code)
    tap(r, t, CYD, "s", 0)                              # Cy inherits it
    assert t.balances == [1.6, -1.6, 0.0, 0.0], "the seat still holds it, or this proves nothing"

    effects = undo(r, t, GUEST)

    assert t.log == [] and t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.seat_of(CYD.user_id) == 0, "Cy was not asked, not moved, and not charged elsewhere"
    assert [e for e in effects if isinstance(e, table.Toast)] == []


# The same, driven literally: an empty seat wins, somebody sits in it, and undo still takes the
# money back out of the slot without asking, charging or telling the newcomer.
def test_undoing_a_win_that_an_empty_seat_scored_before_somebody_sat_in_it():
    r, t = seated_table()
    tap(r, t, HOST, "w", 2)                                 # seat 3 holds nobody and still wins
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)                                 # Bo fed it
    assert t.balances == pytest.approx([0.0, -0.4, 0.4, 0.0])

    r.message(CYD, "/join " + t.code)
    tap(r, t, CYD, "s", 2)                                  # Cy sits into the +$0.40
    assert t.balances == pytest.approx([0.0, -0.4, 0.4, 0.0]), "the seat kept what it earned"

    effects = undo(r, t, GUEST)

    assert t.log == [] and t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.seat_of(CYD.user_id) == 2, "Cy still holds the seat they picked"
    assert [e for e in effects if isinstance(e, table.Toast)] == []
