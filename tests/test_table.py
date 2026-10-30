"""Table state and rules — opening, joining, seats, command resolution."""
import random

import pytest

import table

from tests.support import CYD, GUEST, HOST, PLAYER, seated_table


def new_room():
    return table.Room(rng=random.Random(7))


def token(r, kind, meaning, who=None):
    t = r.table_of(who or HOST)
    return table.token(kind, t.code, t.version, meaning)


def boards(effects):
    return [e for e in effects if isinstance(e, table.Board)]


def labels(effects):
    """Button captions on whatever keyboard these effects carry (menus carry none)."""
    return [label for e in effects for row in getattr(e, "rows", ()) for label, _ in row]


seated_two_player_table = seated_table


# S1.1
def test_opening_a_table_issues_a_join_code_and_asks_for_a_seat():
    r = new_room()
    effects = r.message(HOST, "/new")
    # FR2, FR13 — the code is on the Board's first line, where it stays for the whole night: that is the
    # message a seated player reads aloud to whoever is still outside.
    assert r.table_of(HOST).code in " ".join(b.text for b in boards(effects))
    assert set(labels(effects)) >= set(PLAYER)


# S1.2
def test_codes_avoid_look_alikes_and_are_never_reused_while_live():
    live = set()
    for n in range(300):
        code = table.new_code(live, random.Random(n))
        assert len(code) == table.CODE_LENGTH, "02/FR13 — six of them"
        assert not set(code) & set("0O1Iil o"), "nothing a phone renders as something else"
        live.add(code)
    assert len(live) == 300


# S1.3
def test_joining_by_code_binds_the_player_and_offers_the_free_seats():
    r = new_room()
    r.message(HOST, "/new")
    code = r.table_of(HOST).code
    effects = r.message(GUEST, "/join " + code)
    assert r.table_of(GUEST) is r.table_of(HOST)
    assert set(labels(effects)) >= set(PLAYER)
    assert r.table_of(GUEST).seat_of(GUEST.user_id) is None


# S1.4
def test_a_code_no_live_table_holds_is_refused():
    r = new_room()
    r.message(HOST, "/new")
    effects = r.message(GUEST, "/join ZZZZ")
    assert r.table_of(GUEST) is None
    assert effects


# S1.5
def test_a_taken_seat_cannot_be_chosen():
    r = new_room()
    r.message(HOST, "/new")
    t = r.table_of(HOST)
    r.tap(HOST, table.token("s", t.code, t.version, 0))
    r.message(GUEST, "/join " + t.code)
    effects = r.tap(GUEST, table.token("s", t.code, t.version, 0))
    assert r.table_of(GUEST).seat_of(GUEST.user_id) is None
    assert r.table_of(HOST).seat_of(HOST.user_id) == 0
    assert effects


# S1.6
def test_a_bound_player_cannot_open_or_join_a_second_table():
    r, first = seated_two_player_table()
    r.message(CYD, "/new")
    second = r.table_of(CYD).code
    r.message(GUEST, "/new")
    r.message(GUEST, "/join " + second)
    assert r.table_of(GUEST) is first


# S1.7
def test_a_bare_command_resolves_to_the_bound_table():
    r, t = seated_two_player_table()
    effects = r.message(GUEST, "/board")
    assert {b.chat_id for b in boards(effects)} == {HOST.user_id, GUEST.user_id}


# S3.11 — one live message per chat. The seat offer is the chat's Board, not a note beside it, so
# seating spends those buttons instead of leaving a dead row on screen.
def test_the_seat_offer_rides_the_board_message():
    r = new_room()

    effects = r.message(HOST, "/new")

    board = next((e for e in effects if isinstance(e, table.Board)), None)
    assert board is not None, "the seat offer should be the chat's Board message"
    assert board.chat_id == HOST.user_id
    assert set(labels([board])) == set(PLAYER)


# S3.11 — and the seat tap turns that same message into the score Board, with nothing beside it.
def test_seating_spends_the_seat_offer_in_place():
    r = new_room()
    r.message(HOST, "/new")
    t = r.table_of(HOST)

    effects = r.tap(HOST, table.token("s", t.code, t.version, 0))

    assert [type(e) for e in effects if not isinstance(e, table.Commands)] == [table.Board]
    assert "empty" in boards(effects)[0].text         # three seats still unclaimed
