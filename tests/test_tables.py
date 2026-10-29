"""Several Tables at once, leaving one, closing one."""
import random
import re

import table

from tests.support import CYD, DEB, GUEST, HOST, board_text, keyboard_for, seated_table, tap


def bo_wins_a_tai(r, t):
    """Al feeds Bo one tai: 東 ends owing, 南 is ahead."""
    tap(r, t, HOST, "w", 1)
    tap(r, t, HOST, "a", "t1")
    return tap(r, t, HOST, "p", 0)


# S3.4 — the seat goes back to the pool; the money sitting in it does not (FR20, AD4).
def test_leaving_frees_the_wind_but_leaves_its_money_where_it_is():
    r, t = seated_table()
    bo_wins_a_tai(r, t)

    effects = r.message(GUEST, "/leave")

    assert t.occupants[1] is None
    assert t.balances == [-0.4, 0.4, 0.0, 0.0]
    assert re.search(r"南\s+empty\s+\+\$0\.40", board_text(effects, HOST.user_id))


# S3.5 — a seat is not a leash. /leave drops the binding too (FR4), so the player can sit elsewhere
# and the Table they left stops pushing them a Board.
def test_leaving_frees_them_to_sit_at_another_table():
    r, first = seated_table()
    r.message(CYD, "/new")
    second = r.table_of(CYD).code

    refused = r.message(GUEST, "/join " + second)
    assert r.table_of(GUEST) is first
    assert "/leave first" in refused[0].text

    r.message(GUEST, "/leave")

    assert r.table_of(GUEST) is None
    assert "not at a table" in r.message(GUEST, "/board")[0].text
    r.message(GUEST, "/join " + second)
    assert r.table_of(GUEST) is r.table_of(CYD)



# S3.6 — a draft dies with its holder. Only they may cancel it (FR10 retired), so a holder walking
# off would leave the whole Table waiting behind someone who has already gone.
def test_leaving_discards_the_draft_the_leaver_started():
    r, t = seated_table()
    tap(r, t, GUEST, "w", 1)
    assert t.pending is not None

    effects = r.message(GUEST, "/leave")

    assert t.pending is None
    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.log == []
    assert keyboard_for(effects, HOST.user_id) == ["Al"]


# S3.7 — a draft names a wind, not a person, so being the named winner abandons it too. Written
# after T3.2's GREEN already handled both directions: this is a pin, not a new behaviour.
def test_leaving_discards_a_draft_that_named_the_leaver_as_winner():
    r, t = seated_table()
    tap(r, t, HOST, "w", 1)
    assert t.pending["winner"] == 1

    r.message(GUEST, "/leave")

    assert t.pending is None
    assert t.balances == [0.0, 0.0, 0.0, 0.0]


# S3.8 — the screen they were left on must stop offering buttons (Q4).
def test_the_leaver_is_told_they_have_left_and_offers_nothing():
    r, t = seated_table()

    effects = r.message(GUEST, "/leave")

    notice = next(e for e in effects if isinstance(e, table.Retired))
    assert notice.chat_id == GUEST.user_id
    assert t.code in notice.text and "left" in notice.text.lower()


# S3.9 — closing is the host's call, so a member is refused rather than left holding the night's
# data by accident (FR21).
def test_only_the_host_may_close_the_table():
    r, t = seated_table()

    effects = r.message(GUEST, "/close")

    assert r.table_of(GUEST) is t
    assert "host" in effects[0].text.lower()
    tap(r, t, HOST, "w", 1)                      # and the Table is still live
    assert t.pending is not None


# S3.10 — /close dissolves the Table for everyone at it, seated or not: a button-less notice in
# every chat, old keyboards refused, bindings freed, and each player able to start afresh (FR21).
def test_closing_dissolves_the_table_for_everyone():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)
    code = t.code

    effects = r.message(HOST, "/close")

    notices = [e for e in effects if isinstance(e, table.Retired)]
    assert {n.chat_id for n in notices} == {HOST.user_id, GUEST.user_id, CYD.user_id}
    assert all("closed" in n.text for n in notices)
    assert code not in r.tables
    assert all(r.table_of(p) is None for p in (HOST, GUEST, CYD))
    dead_tap = r.tap(HOST, table.token("w", code, t.version, 0))
    refused = [e for e in dead_tap if isinstance(e, table.Toast)]
    assert refused == [table.Toast("That table is gone.")]

    r.message(HOST, "/new")
    assert r.table_of(HOST) is not t


class PlannedRng:
    """Hands out the planned codes in order, one character per call, whatever the alphabet is."""

    def __init__(self, *codes):
        self.chars = "".join(codes)
        self.i = 0

    def choice(self, seq):
        char = self.chars[self.i]
        self.i += 1
        return char


# S3.2 — a code in use is never handed out again while the Table lives (FR3): the repeat is stepped
# over instead of silently replacing the Table that holds it.
def test_a_code_already_in_use_is_never_handed_out_again():
    r = table.Room(rng=PlannedRng("AAAA", "AAAA", "BBBB"))
    r.message(HOST, "/new")

    r.message(GUEST, "/new")

    assert set(r.tables) == {"AAAA", "BBBB"}
    assert r.table_of(HOST) is not r.table_of(GUEST)


# S3.3 — "unique while live" ends when the Table dissolves: a closed code is free again (FR3).
def test_a_closed_code_can_be_handed_out_again():
    r = table.Room(rng=PlannedRng("AAAA", "AAAA"))
    r.message(HOST, "/new")
    r.message(HOST, "/close")

    r.message(GUEST, "/new")

    assert r.table_of(GUEST).code == "AAAA"
    assert r.table_of(HOST) is None


def seated_second_table(r):
    """Cy + Deb seated at their own Table, alongside the first one."""
    r.message(CYD, "/new")
    b = r.table_of(CYD)
    tap(r, b, CYD, "s", 0)
    r.message(DEB, "/join " + b.code)
    tap(r, b, DEB, "s", 1)
    return b


# S3.1 — two Tables at once must not see each other (FR5): money, Boards and entry lines all stay
# inside their own Table.
def test_two_tables_do_not_bleed_into_each_other():
    r, a = seated_table()
    b = seated_second_table(r)

    bo_wins_a_tai(r, a)

    assert a.balances == [-0.4, 0.4, 0.0, 0.0]
    assert b.balances == [0.0, 0.0, 0.0, 0.0]
    assert b.log == []
    board = next(e for e in r.message(CYD, "/board") if isinstance(e, table.Board))
    assert board.chat_id == CYD.user_id and b.code in board.text and "$0.00" in board.text


# S3.15 — standing up ends the chat's Board rather than leaving it owed: the notice is a `Retired`
# effect, so nothing is promised to that message again and the next Table's Board is sent fresh.
def test_leaving_returns_the_board_slot_instead_of_owing_it():
    r, t = seated_table()

    effects = r.message(GUEST, "/leave")

    retired = [e for e in effects if isinstance(e, table.Retired)]
    assert [e.chat_id for e in retired] == [GUEST.user_id]
    assert t.code in retired[0].text and "left" in retired[0].text.lower()
    assert not [e for e in effects if isinstance(e, table.Board) and e.chat_id == GUEST.user_id]


# S3.9 extended — a refusal is worth more when it says who to go and ask (Jon, 2026-10-29 22:14).
def test_the_close_refusal_names_the_host():
    r, t = seated_table()

    effects = r.message(GUEST, "/close")

    assert effects[0].text == "Only the host, Al, can close table %s." % t.code


# S3.9 extended — the host keeps the role after /leave (there is no host transfer), so by then the
# Table no longer even knows their name. The refusal must not lean on a name it has forgotten.
def test_the_close_refusal_survives_a_host_who_walked_out():
    r, t = seated_table()
    r.message(HOST, "/leave")

    effects = r.message(GUEST, "/close")

    assert effects[0].text == "Only the host can close table %s." % t.code


def menu_for(effects):
    return next(e.names for e in effects if isinstance(e, table.Commands))


# S3.21 — the slash menu should match where the player stands, so /leave is not offered to somebody
# with no Table and /close is not offered to somebody who cannot use it.
def test_the_command_menu_matches_where_the_player_stands():
    r = table.Room(rng=random.Random(7))

    assert menu_for(r.message(CYD, "/start")) == ("/start", "/new", "/join")

    r.message(CYD, "/new")
    assert menu_for(r.message(CYD, "/board")) == ("/start", "/board", "/leave")

    tap(r, r.table_of(CYD), CYD, "s", 0)
    # Every verb in the Command Surface is now live, so the menu is the whole surface for a seated host —
    # /history and /end joined with slice 5, /settings with slice 4, each the day it started doing
    # something. NOT_BUILT is empty by ruling, and kept as a marker of that rule (see tasking.md S5.20).
    assert menu_for(r.message(CYD, "/board")) == ("/start", "/board", "/leave", "/history", "/end",
                                                 "/settings", "/close")


# S3.21 — a member who is not the host is not handed the host's two commands.
def test_a_seated_member_is_not_offered_the_host_commands():
    r, t = seated_table()

    assert menu_for(r.message(GUEST, "/board")) == ("/start", "/board", "/leave", "/history", "/end")


# S3.24 — /join from the command menu has no argument to carry, so it must ask for the code instead
# of answering with generic help the player cannot act on.
def test_a_bare_join_asks_for_the_code():
    r = table.Room(rng=random.Random(7))

    effects = r.message(CYD, "/join")

    ask = next(e.text for e in effects if isinstance(e, table.Line))
    # The old answer was generic help, which also contains the word "code" — so the tell is that an
    # ask does not send the player off to do something else instead.
    assert "code" in ask.lower() and "/new" not in ask


# S3.25 — and the next plain message is that code: bound, seated offer, nothing else required.
def test_the_next_message_is_read_as_the_code():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    code = r.table_of(HOST).code

    r.message(CYD, "/join")
    effects = r.message(CYD, code.lower())                    # typed casually, lowercase

    assert r.table_of(CYD) is r.table_of(HOST)
    assert set(keyboard_for(r.message(CYD, "/board"), CYD.user_id)) == set(table.WINDS)
    assert CYD.user_id not in r.table_of(CYD).occupants      # bound; the seat pick is still theirs


# S3.26 — a code that matches nothing is refused, and the asking stops: one attempt per ask, so no
# player can be left sitting in a prompt they did not mean to answer.
def test_a_wrong_code_is_refused_and_the_asking_stops():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    r.message(CYD, "/join")

    effects = r.message(CYD, "ZZZZ")

    assert r.table_of(CYD) is None
    assert "no live table" in next(e.text for e in effects if isinstance(e, table.Line)).lower()

    later = r.message(CYD, "hello")                           # a stray message is just a stray message
    assert r.table_of(CYD) is None
    assert not any(isinstance(e, table.Line) and "no live table" in e.text for e in later)


# S3.27 — a command is not an answer to the prompt: /board must not be eaten as a code.
def test_a_command_while_asked_is_not_read_as_a_code():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    r.message(CYD, "/join")

    effects = r.message(CYD, "/board")

    assert r.table_of(CYD) is None                            # /board is not a code
    assert "not at a table" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
