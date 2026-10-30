"""
The ledger — every win is written once, and the night's totals are the fold of what was written.

These tests guard the change itself: the numbers in `golden_payouts.json` are frozen, so the fold has
to reproduce the balances the old incremental addition produced, residue and all. S1.1, S1.3, S1.6 and
S1.7 are pins rather than REDs — they hold before the ledger lands and after it, which is the only way
they can catch the money or the wording moving later.
"""
import random

import pytest

import render
import score
import table
from tests.support import CYD, GUEST, HOST, board_text, entry_deltas, entry_texts, fold, \
    score_wins, seated_four, seated_table, shown_wins, tap
from tests.test_score import GOLDEN

# The night the fixture walks: (kind, ntai, winner, payer), one Entry per step, in `steps` order.
NIGHT = [("tai", 3, 0, 1), ("tai", 1, 3, None), ("tai", 5, 1, 2),
         ("kang", None, 2, 0), ("animal_an", None, 3, None), ("tai", 2, 1, 0)]


def set_rules(r, t, rate, shooter):
    """Set the Table's money rules the way a host does — tapped, not assigned."""
    tap(r, t, HOST, "v", "shooter1" if shooter else "shooter0")
    tap(r, t, HOST, "g", "rate")
    r.message(HOST, str(rate))


def score_a(r, t, win):
    """One fixture win driven through the real taps: winner, amount, and feeder if it asks."""
    kind, ntai, winner, payer = win
    tap(r, t, HOST, "w", winner)
    tap(r, t, HOST, "a", "t%d" % ntai if kind == "tai" else kind)
    if score.has_payer_stage(kind):
        tap(r, t, HOST, "p", "z" if payer is None else payer)


# S1.1 — the frozen contract, read the way a player produces it. Every step of the fixture's night is
# what four real taps leave behind, so the derived totals and the 2022 bot's running totals are the
# same numbers (`tests/golden_payouts.json`).
@pytest.mark.parametrize("night", GOLDEN["sequences"], ids=lambda n: "rate %s" % n["rate"])
def test_a_night_driven_through_real_taps_lands_on_the_frozen_balances(night):
    r, t = seated_four()
    set_rules(r, t, night["rate"], night["shooter"])

    for step, win in enumerate(NIGHT):
        score_a(r, t, win)
        assert t.balances == night["steps"][step], "after win %d of the night" % (step + 1)


# S1.2 — undo and the two screens that list the night all need the win as one object: the sentence the
# players read, and the numbers behind it, written in the same breath so neither can be revised
# without the other (FR1, AD1).
def test_a_committed_win_carries_its_sentence_and_its_money_together():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)

    assert entry_texts(t)[-1] == "Al wins 3 Tai from Bo: +$1.60"
    assert entry_deltas(t)[-1] == (1.6, -1.6, 0.0, 0.0)


# S1.3 — the totals are not a second fact about the night, they are this fold (AD2). Asserted bit for
# bit, not to the cent: the residue the frozen numbers carry is part of the contract, and folding in
# any other order moves it (ERR-05).
def test_the_balances_are_the_fold_of_the_stored_money():
    r, t = seated_four()
    score_wins(r, t, 5)

    assert fold(entry_deltas(t)) == t.balances


# S1.4 — the rate is allowed to move, tonight is not (AD3). A win is priced once, at the tap that
# committed it; re-pricing the ledger at the live rate would let one settings change rewrite every
# sentence and every total the night already agreed to.
def test_a_later_rate_change_does_not_reprice_a_past_win():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)                             # 3 Tai at $0.10 = $1.60
    assert shown_wins(render.board(t)) == ["Al wins 3 Tai from Bo: +$1.60"]

    set_rules(r, t, 1.0, t.shooter)                     # ten times the rate, after the win

    assert entry_deltas(t) == [(1.6, -1.6, 0.0, 0.0)]
    assert entry_texts(t) == ["Al wins 3 Tai from Bo: +$1.60"]
    assert shown_wins(render.board(t)) == ["Al wins 3 Tai from Bo: +$1.60"], "the Board still says $1.60"
    assert t.balances == [1.6, -1.6, 0.0, 0.0], "and so does the fold"

    tap(r, t, HOST, "w", 0)                             # and the rate did move forward
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)
    assert entry_deltas(t)[-1] == (16.0, -16.0, 0.0, 0.0)
    assert entry_texts(t)[-1] == "Al wins 3 Tai from Bo: +$16.00"


# S1.5 — the two screens that list the night show the sentences written at commit, in the order they
# were written (AD4). Neither rebuilds a win from the seats and the rate it happens to read off today —
# that is what ERR-01 and ERR-05 are about.
def test_the_board_and_history_read_exactly_what_the_night_wrote():
    r, t = seated_four()
    score_wins(r, t, 7)
    wrote = entry_texts(t)
    assert len(wrote) == 7, "7 distinct wins, or this proves nothing"

    assert shown_wins(render.history(t)) == wrote
    assert shown_wins(render.board(t)) == wrote[-3:]
    assert "… 4 earlier" in render.board(t)


# S1.6 — a win belongs to the night, not to the seat (ERR-01). The tempting saving throw is to store
# who won as a seat index and let the screens read a name off it each time; that is how a history
# starts crediting yesterday's win to whoever sits down today.
def test_a_win_keeps_naming_who_won_after_they_leave():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    t = r.table_of(HOST)
    r.message(GUEST, "/join " + t.code)
    tap(r, t, GUEST, "s", 0)
    tap(r, t, HOST, "s", 1)                             # Al sits at seat 1
    tap(r, t, HOST, "w", 1)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 0)
    assert shown_wins(render.history(t)) == ["Al wins 1 Tai from Bo: +$0.40"]

    r.message(HOST, "/leave")
    r.message(CYD, "/join " + t.code)
    tap(r, t, CYD, "s", 1)
    assert t.occupants[1] == CYD.user_id, "Cy holds the seat now, or this proves nothing"

    text = board_text(r.message(GUEST, "/history"), GUEST.user_id)

    assert shown_wins(text) == ["Al wins 1 Tai from Bo: +$0.40"]
    assert "Cy" not in "\n".join(shown_wins(text)), "the night does not credit the newcomer"


# S1.7 — a night is a set of wins, not a pile of sentences (NFR3): comparing two nights, or counting
# the distinct ones, is a thing the ledger has to support. A record holding a list is not a record you
# can put in a set, and the failure would land here rather than in whatever wanted to compare them.
def test_a_nights_wins_can_be_set_compared():
    r, t = seated_four()
    score_wins(r, t, 7)

    assert len(set(t.log)) == 7
