"""Recording a win: winner, then amount, then who fed."""

import pytest

import table
from tests.support import GUEST, HOST, PLAYER, entry_texts, keyboard_for, seated_table
from tests.support import tap as tap_seat
from tests.support import tokens_of





def start_win(r, t, who, seat):
    """Tap a winner and prove the table is holding it — otherwise the arrange is a lie."""
    effects = tap_seat(r, t, who, "w", seat)
    assert t.pending is not None
    return effects


# S1.8
def test_winner_then_amount_then_payer_moves_the_golden_money():
    r, t = seated_table()
    tap_seat(r, t, HOST, "w", 0)
    tap_seat(r, t, HOST, "a", "t3")
    tap_seat(r, t, HOST, "p", 1)
    assert t.balances == [1.6, -1.6, 0.0, 0.0]
    assert len(t.log) == 1
    assert t.pending is None


# S1.8 (amended in slice 2: FR10 retired) — anyone may start an Entry for any winner, and the
# player who started it is the one who finishes it.
def test_whoever_starts_the_draft_is_the_one_who_finishes_it():
    r, t = seated_table()
    tap_seat(r, t, GUEST, "w", 0)          # Bo records a win for Al
    tap_seat(r, t, GUEST, "a", "t3")
    tap_seat(r, t, GUEST, "p", 1)          # ... and Bo names who fed it
    assert t.balances == [1.6, -1.6, 0.0, 0.0]


# S1.9
# S1.9 — 02b/D9: an amount tap with no draft open is a button from a screen that is already gone. It
# keeps its guard (the alternative is a `TypeError` through the polling thread) and answers with the
# tapper's own Board — whose last line already asks for the winner.
def test_an_amount_with_no_winner_waiting_costs_nothing():
    r, t = seated_table()
    before = list(t.balances)
    effects = tap_seat(r, t, HOST, "a", "t3")
    assert t.balances == before
    assert t.pending is None
    assert not [e for e in effects if isinstance(e, table.Toast)], "no popup: the board answers"
    assert keyboard_for(effects, HOST.user_id) == ["Al", "Bo", PLAYER[2], PLAYER[3]], \
        "their own Board comes back"


# S1.10
def test_a_payer_with_no_amount_waiting_is_refused():
    r, t = seated_table()
    before = list(t.balances)
    start_win(r, t, HOST, 0)
    effects = tap_seat(r, t, GUEST, "p", 1)
    assert t.balances == before
    assert not [e for e in effects if isinstance(e, table.Toast)], "no popup: the board answers"
    assert keyboard_for(effects, GUEST.user_id) == ["Al", "Bo", PLAYER[2], PLAYER[3]]


# S1.10 — a winner is not a payer for their own win.
def test_the_winner_cannot_be_tapped_as_the_payer():
    r, t = seated_table()
    before = list(t.balances)
    start_win(r, t, HOST, 0)
    tap_seat(r, t, HOST, "a", "t3")
    effects = tap_seat(r, t, HOST, "p", 0)
    assert t.balances == before
    assert t.pending is not None, "the draft is still open — and the row never offered seat 1 anyway"
    assert not [e for e in effects if isinstance(e, table.Toast)], \
        "02b/D9: a rule, not a stale screen, so the screen answers"


# S1.17 — a joined-but-unseated player is not at the table yet
def test_a_player_who_has_not_taken_a_seat_cannot_score():
    r, t = seated_table()
    late = table.User(44, "Di")
    r.message(late, "/join " + t.code)
    before = list(t.balances)
    start_win(r, t, HOST, 0)
    tap_seat(r, t, HOST, "a", "t3")
    effects = tap_seat(r, t, late, "p", 1)
    assert t.balances == before
    assert t.pending is not None
    # 02b/D9 — the picker is the answer, and the only thing a seatless chat can act on.
    assert not [e for e in effects if isinstance(e, table.Toast)], "no popup: the picker answers"
    assert set(keyboard_for(effects, late.user_id)) == {PLAYER[w] for w in t.free_seats()}


# S1.15
def test_every_keyboard_token_fits_telegrams_64_byte_limit():
    r, t = seated_table()
    t.maxtai = 10
    t.names[GUEST.user_id] = "Aarón Miguel Ángel"
    t.version = 999999
    stages = [start_win(r, t, HOST, 0), tap_seat(r, t, HOST, "a", "t10"),
              tap_seat(r, t, GUEST, "p", "z")]
    made = tokens_of(stages[0]) + tokens_of(stages[1]) + tokens_of(stages[2])
    assert made
    assert max(len(tok.encode("utf-8")) for tok in made) <= 64


# S4.1 (FR3) — a short-handed night is played, not waited for. An empty seat is offered as a winner, so
# a win can be booked into the slot the money will actually sit in.
def test_an_empty_seat_is_offered_as_a_winner():
    r, t = seated_table()                              # Al and Bo sit; two seats are empty

    row = keyboard_for(r.message(HOST, "/board"), HOST.user_id)

    assert row == ["Al", "Bo", PLAYER[2], PLAYER[3]]


# S4.2 (FR3, AD5) — and tapping one books the win there. The line names the slot, because no person
# holds it, and the money lands where whoever sits there next will find it (AD4).
def test_an_empty_seat_can_win_and_the_line_names_the_slot():
    r, t = seated_table()
    tap_seat(r, t, HOST, "w", 2)                       # seat 3 holds nobody
    tap_seat(r, t, HOST, "a", "t1")

    effects = tap_seat(r, t, HOST, "p", 1)              # and Bo fed it

    assert entry_texts(t)[-1] == "Player 3 wins 1 Tai from Bo: +$0.40"
    assert t.balances == pytest.approx([0.0, -0.4, 0.4, 0.0])


# S4.11 — a meaning that names no seat is refused, never a traceback (F-03): Telegram redelivers
# whatever an old button carried, and `4` and `-1` are each one keystroke from a real index. 02b/D15 put
# both stages on the shared out-of-date line: no screen this bot ever drew carried either tap.
@pytest.mark.parametrize("meaning", ["4", "-1", "x"])
def test_a_seat_index_off_the_board_is_refused(meaning):
    r, t = seated_table()
    before = list(t.balances)

    refused = tap_seat(r, t, HOST, "s", meaning)
    assert next(e.text for e in refused if isinstance(e, table.Toast)) == table.OUTDATED, \
        "the seat picker offers free seats by number — no seat row ever carried this tap"

    refused = tap_seat(r, t, HOST, "w", meaning)
    assert next(e.text for e in refused if isinstance(e, table.Toast)) == table.OUTDATED
    assert (t.balances, t.version, t.pending) == (before, t.version, None)

    start_win(r, t, HOST, 0)
    tap_seat(r, t, HOST, "a", "kang")
    staged, version = list(t.balances), t.version

    refused = tap_seat(r, t, HOST, "p", meaning)

    assert next(e.text for e in refused if isinstance(e, table.Toast)) == table.OUTDATED
    assert (t.balances, t.version) == (staged, version), "a refused tap spends nothing"
