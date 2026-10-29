"""Recording a win: winner, then amount, then who fed."""

import pytest

import table
from tests.support import GUEST, HOST, seated_table
from tests.support import tap as tap_wind
from tests.support import tokens_of





def start_win(r, t, who, wind):
    """Tap a winner and prove the table is holding it — otherwise the arrange is a lie."""
    effects = tap_wind(r, t, who, "w", wind)
    assert t.pending is not None
    return effects


# S1.8
def test_winner_then_amount_then_payer_moves_the_golden_money():
    r, t = seated_table()
    tap_wind(r, t, HOST, "w", 0)
    tap_wind(r, t, HOST, "a", "t3")
    tap_wind(r, t, HOST, "p", 1)
    assert t.balances == [1.6, -1.6, 0.0, 0.0]
    assert len(t.log) == 1
    assert t.pending is None


# S1.8 (amended in slice 2: FR10 retired) — anyone may start an Entry for any winner, and the
# player who started it is the one who finishes it.
def test_whoever_starts_the_draft_is_the_one_who_finishes_it():
    r, t = seated_table()
    tap_wind(r, t, GUEST, "w", 0)          # Bo records a win for Al
    tap_wind(r, t, GUEST, "a", "t3")
    tap_wind(r, t, GUEST, "p", 1)          # ... and Bo names who fed it
    assert t.balances == [1.6, -1.6, 0.0, 0.0]


# S1.9
def test_an_amount_with_no_winner_waiting_is_refused():
    r, t = seated_table()
    before = list(t.balances)
    effects = tap_wind(r, t, HOST, "a", "t3")
    assert t.balances == before
    assert t.pending is None
    assert any(isinstance(e, table.Toast) for e in effects)


# S1.10
def test_a_payer_with_no_amount_waiting_is_refused():
    r, t = seated_table()
    before = list(t.balances)
    start_win(r, t, HOST, 0)
    effects = tap_wind(r, t, GUEST, "p", 1)
    assert t.balances == before
    assert any(isinstance(e, table.Toast) for e in effects)


# S1.10 — a winner is not a payer for their own win.
def test_the_winner_cannot_be_tapped_as_the_payer():
    r, t = seated_table()
    before = list(t.balances)
    start_win(r, t, HOST, 0)
    tap_wind(r, t, HOST, "a", "t3")
    effects = tap_wind(r, t, HOST, "p", 0)
    assert t.balances == before
    assert any(isinstance(e, table.Toast) for e in effects)


# S1.17 — a joined-but-unseated player is not at the table yet
def test_a_player_who_has_not_taken_a_seat_cannot_score():
    r, t = seated_table()
    late = table.User(44, "Di")
    r.message(late, "/join " + t.code)
    before = list(t.balances)
    start_win(r, t, HOST, 0)
    tap_wind(r, t, HOST, "a", "t3")
    effects = tap_wind(r, t, late, "p", 1)
    assert t.balances == before
    assert t.pending is not None
    assert any(isinstance(e, table.Toast) for e in effects)


# S1.15
def test_every_keyboard_token_fits_telegrams_64_byte_limit():
    r, t = seated_table()
    t.maxtai = 10
    t.names[GUEST.user_id] = "Aarón Miguel Ángel"
    t.version = 999999
    stages = [start_win(r, t, HOST, 0), tap_wind(r, t, HOST, "a", "t10"),
              tap_wind(r, t, GUEST, "p", "z")]
    made = tokens_of(stages[0]) + tokens_of(stages[1]) + tokens_of(stages[2])
    assert made
    assert max(len(tok.encode("utf-8")) for tok in made) <= 64
