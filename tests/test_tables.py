"""Several Tables at once, leaving one, closing one."""
import random
import re

import table

from tests.support import (board_text, CYD, DEB, entry_texts, GUEST, HOST, keyboard_for,
                           menu_for, PLAYER, seated_four, seated_table, tap, tokens_of)


def bo_wins_a_tai(r, t):
    """Al feeds Bo one tai: seat 1 ends owing, seat 2 is ahead."""
    tap(r, t, HOST, "w", 1)
    tap(r, t, HOST, "a", "t1")
    return tap(r, t, HOST, "p", 0)


# S3.4 — the seat goes back to the pool; the money sitting in it does not (FR20, AD4).
def test_leaving_frees_the_seat_but_leaves_its_money_where_it_is():
    r, t = seated_table()
    bo_wins_a_tai(r, t)

    effects = r.message(GUEST, "/leave")

    assert t.occupants[1] is None
    assert t.balances == [-0.4, 0.4, 0.0, 0.0]
    assert re.search(r"Player 2\s+empty\s+\+\$0\.40", board_text(effects, HOST.user_id))


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
    assert keyboard_for(effects, HOST.user_id) == ["Al", "Player 2", "Player 3", "Player 4"]


# S3.7 — a draft names a seat, not a person, so being the named winner abandons it too. Written
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
    """
    Hands out the planned codes in order, one letter per call. Answered as an index into the alphabet,
    because that is how `new_code` asks — the alphabet stays the source of the letters and this fake
    only chooses positions in it (S7.6).
    """

    def __init__(self, *codes):
        self.chars = "".join(codes)
        self.i = 0

    def randrange(self, n):
        assert n == len(table.CODE_ALPHABET), "the plan is in letters of this alphabet, not their indexes"
        char = self.chars[self.i]
        self.i += 1
        return table.CODE_ALPHABET.index(char) % n


# S3.2 — a code in use is never handed out again while the Table lives (FR3): the repeat is stepped
# over instead of silently replacing the Table that holds it.
def test_a_code_already_in_use_is_never_handed_out_again():
    r = table.Room(rng=PlannedRng("AAAAAA", "AAAAAA", "BBBBBB"))
    r.message(HOST, "/new")

    r.message(GUEST, "/new")

    assert set(r.tables) == {"AAAAAA", "BBBBBB"}
    assert r.table_of(HOST) is not r.table_of(GUEST)


# S7.3 (FR13, AD8) — inverts this suite's old S3.3, which asked for the opposite: "unique while live"
# was not enough. A code is a key, and a key that gets re-cut for the next night lets whoever kept the
# old copy into a room they were not invited to — with no way to tell, because the letters match.
def test_a_closed_code_is_never_dealed_again_while_the_process_lives():
    r = table.Room(rng=PlannedRng("AAAAAA", "AAAAAA", "B2B2B2", "C3C3C3", "D4D4D4"))
    r.message(HOST, "/new")
    r.message(HOST, "/close")

    for who in (GUEST, CYD, DEB):
        r.message(who, "/new")

    assert "AAAAAA" not in r.tables, "the dissolved Table's letters are spent, not free"
    assert sorted(r.tables) == ["B2B2B2", "C3C3C3", "D4D4D4"]


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
    # Both Boards carry their own code, so the tell that these are two nights is that Bo's win reads in
    # Al's Board and nowhere in Cy's.
    assert board.chat_id == CYD.user_id and "$0.00" in board.text and "wins" not in board.text


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
# S6.1 (FR12) — a refusal that names the person is one a player can act on. Pinned as the whole
# sentence; it also pins that opening the settings to the seated did not loosen this one verb.
def test_the_close_refusal_names_the_host():
    r, t = seated_table()

    effects = r.message(GUEST, "/close")

    assert effects[0].text == "Only the host, Al, can close table %s." % t.code


# S6.2 (02/FR12) — the host keeps the role after /leave (there is no host transfer), and the name
# the chat last read on the Board is the one the refusal has to carry. A sentence that drops it names
# nobody, to everyone in the chat's total certainty about which host it means.
def test_the_close_refusal_survives_a_host_who_walked_out():
    r, t = seated_table()
    r.message(HOST, "/leave")

    effects = r.message(GUEST, "/close")

    assert effects[0].text == "Only the host, Al, can close table %s." % t.code


# S3.21 — the slash menu should match where the player stands, so /leave is not offered to somebody
# with no Table and /close is not offered to somebody who cannot use it. `/start` drops out once the
# chat has a Table: it only ever says "the bot is running" (FR26 as amended).
def test_the_command_menu_matches_where_the_player_stands():
    r = table.Room(rng=random.Random(7))

    assert menu_for(r.message(CYD, "/start")) == ("/start", "/new", "/join")

    r.message(CYD, "/new")
    assert menu_for(r.message(CYD, "/board")) == ("/board", "/leave")

    tap(r, r.table_of(CYD), CYD, "s", 0)
    # Every verb in the Command Surface is now live, so the menu is the whole surface for a seated host —
    # /history and /end joined with slice 5, /settings with slice 4, each the day it started doing
    # something. NOT_BUILT is empty by ruling, and kept as a marker of that rule.
    assert menu_for(r.message(CYD, "/board")) == ("/board", "/leave", "/history", "/end",
                                                 "/settings", "/close")


# S5.9 (FR11, FR12) — the whole menu is an exact tuple now, because the two seated menus differ by
# exactly one verb and a substring check would not see `/close` leak onto the wrong keyboard.
def test_the_two_seated_menus_differ_by_close_alone():
    r, t = seated_table()

    assert menu_for(r.message(GUEST, "/board")) == ("/board", "/leave", "/history", "/end", "/settings")
    assert menu_for(r.message(HOST, "/board")) == ("/board", "/leave", "/history", "/end",
                                                  "/settings", "/close")


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
    assert set(keyboard_for(r.message(CYD, "/board"), CYD.user_id)) == set(PLAYER)
    assert CYD.user_id not in r.table_of(CYD).occupants      # bound; the seat pick is still theirs


# S3.26 — a code that matches nothing is refused, and the asking stops: one attempt per ask, so no
# player can be left sitting in a prompt they did not mean to answer.
def test_a_wrong_code_is_refused_and_the_asking_stops():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    r.message(CYD, "/join")

    effects = r.message(CYD, "ZZZZZZ")

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


# S4.8 (AD4) — a seat keeps what it earned, and the next person to sit there inherits it: the money was
# never in the person. The older line still reads `Player 3`, because that is what the night wrote and
# nothing re-renders a past win from the seat it happens to name today.
def test_money_earned_by_an_empty_seat_waits_for_whoever_sits_there():
    r, t = seated_table()
    tap(r, t, HOST, "w", 2)                              # an empty seat wins
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)
    assert t.balances == [0.0, -0.4, 0.4, 0.0]

    r.message(CYD, "/join " + t.code)
    tap(r, t, CYD, "s", 2)

    assert t.balances == [0.0, -0.4, 0.4, 0.0], "taking a seat moved nobody's money"
    assert t.seat_of(CYD.user_id) == 2
    assert entry_texts(t)[-1] == "Player 3 wins 1 Tai from Bo: +$0.40"


# S4.9 (FR14 of mission 01, relabelled) — the picker still offers only the seats that are free. What
# changed is how they are named: a slot, not a wind, and the number is the same one the Board uses.
def test_the_seat_picker_offers_only_the_free_seats_by_number():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    t = r.table_of(HOST)
    tap(r, t, HOST, "s", 0)                              # the host takes the first seat
    r.message(CYD, "/join " + t.code)                     # bound, and nothing under them

    offered = keyboard_for(r.message(CYD, "/board"), CYD.user_id)

    assert offered == [PLAYER[1], PLAYER[2], PLAYER[3]]


# S4.10 — two people, one empty chair: the second is refused, and refused in the words the picker
# showed them. The seat ends up with exactly one occupant either way.
def test_a_seat_someone_else_holds_is_refused_by_its_slot_name():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)
    r.message(DEB, "/join " + t.code)

    tap(r, t, CYD, "s", 2)
    second = tap(r, t, DEB, "s", 2)

    assert "Player 3 is taken" in next(e.text for e in second if isinstance(e, table.Toast))
    assert t.occupants[2] == CYD.user_id, "the seat has one occupant, not two and not nobody"


# S6.3 (FR12, FR21) — naming the host is not the same as letting them: the departed host is a stranger to
# the Table now, and the Table they meant to close is still standing.
def test_a_departed_host_may_still_not_close_the_table():
    r, t = seated_table()
    r.message(HOST, "/leave")

    effects = r.message(HOST, "/close")

    assert "not at a table" in effects[0].text.lower()
    assert r.tables[t.code] is t, "the Table outlived the attempt"


# S6.4 (FR21) — once the Table is gone the sentence must not imply it is still there, and it must never
# claim somebody can close a Table that no longer exists.
def test_a_former_member_who_asks_to_close_a_dissolved_table_hears_it_is_gone():
    r, t = seated_table()
    r.message(HOST, "/close")
    assert r.tables == {}, "the Table is gone"

    effects = r.message(GUEST, "/close")

    assert "not at a table" in effects[0].text.lower()
    assert "close table" not in effects[0].text.lower()


# --- Task 7: codes are six characters, and dealt once -----------------------------------------------

class WorstRng:
    """
    An rng trying to sabotage the code: the widest index every time, and a `choice` that reaches
    straight for `O`. A code dealt against it still cannot hold a confusable letter, because the
    alphabet is the only thing that supplies letters (S7.6 — the rng is not trusted to behave).
    """

    def randrange(self, n):
        return n - 1

    def choice(self, seq):
        return "O"


# S7.1 (02/FR13, 01/FR3) — six characters of the confusable-free alphabet, and it is *on the screen* the host is
# left looking at: a code nobody can read out loud is a code nobody can hand on.
def test_a_dealt_code_is_six_confusable_free_characters_and_reads_on_the_board():
    r = table.Room(rng=random.Random(7))

    effects = r.message(HOST, "/new")
    code = r.table_of(HOST).code

    assert len(code) == 6 and set(code) <= set(table.CODE_ALPHABET)
    board = next(e for e in effects if isinstance(e, table.Board))
    assert board.text.splitlines()[0] == "Table %s · 0 of 4 seated" % code


# S7.6 (01/FR3) — the guarantee is the alphabet's, not the random source's.
def test_a_code_cannot_come_back_with_a_confusable_letter_even_from_a_mutinous_rng():
    code = table.new_code(set(), WorstRng())

    assert len(code) == 6
    assert set(code) <= set(table.CODE_ALPHABET)
    assert not set(code) & set("OoIl10"), "no letter a phone renders as another one"


# 01/FR2 — however the code is typed it is the code, and nothing the bot sends back reads
# it is the code, and the joining player is seated.
def test_a_code_typed_any_which_way_seats_a_player():
    for spell in (lambda c: c, lambda c: c.lower(), lambda c: "  " + c + "  "):
        r = table.Room(rng=random.Random(7))
        r.message(HOST, "/new")
        code = r.table_of(HOST).code

        effects = r.message(CYD, "/join " + spell(code))

        assert r.table_of(CYD) is r.table_of(HOST), spell(code)
        assert set(keyboard_for(effects, CYD.user_id)) == set(PLAYER)   # the seat picker is the answer


# 01/AD21 — six letters that name no live Table cost one refusal, and the player is not handed
# anything from the Table they merely typed the code of: no Board, no seat row, nothing to score with.
def test_six_letters_that_name_no_live_table_seat_nobody_and_offer_nothing():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    live = r.table_of(HOST).code
    wrong = live[:-1] + ("A" if live[-1] != "A" else "B")

    effects = r.message(CYD, "/join " + wrong)

    assert r.table_of(CYD) is None
    assert "no live table" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
    assert not [e for e in effects if isinstance(e, table.Board)]


# 01/FR2 — the whole message is the code, or it is a message. Reading a code out of the end of a
# sentence would seat a player from text that never meant to seat them.
def test_a_code_wearing_a_word_is_not_read_as_a_code():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    code = r.table_of(HOST).code
    r.message(CYD, "/join")

    effects = r.message(CYD, "table " + code)

    assert r.table_of(CYD) is None
    assert "no live table" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# S7.2 (FR14) — the ask says six and *shows* six: a question that describes a shape it does not
# demonstrate makes the player count the letters in their own code to decide whether they have it.
def test_the_join_ask_shows_an_example_of_the_length_it_wants():
    r = table.Room(rng=random.Random(7))

    ask = next(e.text for e in r.message(CYD, "/join") if isinstance(e, table.Line))

    assert "code" in ask.lower() and "six" in ask.lower()
    example = ask.split("like ")[1].rstrip(".")
    assert len(example) == table.CODE_LENGTH and set(example) <= set(table.CODE_ALPHABET)


# S7.4 (FR3, AD8) — five deals, codes offered on purpose that are already live or already spent. A hang
# here is a Table nobody can open, so this test failing loudly is the point of it.
def test_five_deals_repeat_no_code_that_is_live_or_spent():
    r = table.Room(rng=PlannedRng("AAAAAA", "AAAAAA", "AAAAAA", "B2B2B2", "B2B2B2",
                                  "C3C3C3", "D4D4D4", "E5E5E5"))

    for who in (HOST, GUEST, CYD, DEB, table.User(66, "Fay")):
        r.message(who, "/new")

    assert sorted(r.tables) == ["AAAAAA", "B2B2B2", "C3C3C3", "D4D4D4", "E5E5E5"]
    assert len({r.table_of(who) for who in (HOST, GUEST, CYD, DEB)}) == 4


# FR2, FR21 — the code belongs to the Table, not the person who opened it: the host walking out
# changes nothing, and the code goes only when the Table does.
def test_a_code_outlives_its_host_and_dies_with_its_table():
    r, t = seated_table()
    code = t.code
    r.message(HOST, "/leave")

    assert t.code == code and r.tables[code] is t
    r.message(DEB, "/join " + code)
    assert r.table_of(DEB) is t, "the code still seats people with its host gone"

    r.message(GUEST, "/leave")                   # the last member with any claim on it walks out too
    assert r.tables[code] is t, "an empty Table is still a Table — only /close dissolves it"


# S7.6 (02/FR13) — the old bot dealt four characters and this one deals six, so any code still in a player's
# chat history from before is a four-letter thing that must join nothing at all.
def test_an_old_four_character_code_joins_nothing():
    r, t = seated_table()

    effects = r.message(CYD, "/join 4KHB")

    assert r.table_of(CYD) is None
    assert "no live table" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# FR5 — two live Tables, one code typed casually: the right Table takes them, and the wrong
# Table is not even named, let alone shown.
def test_a_code_typed_in_lower_case_picks_its_own_table_out_of_two():
    r, a = seated_table()
    b = seated_second_table(r)
    eli = table.User(55, "Eli")

    effects = r.message(eli, "/join " + b.code.lower())

    assert r.table_of(eli) is b
    said = "".join(e.text for e in effects if hasattr(e, "text"))
    assert b.code in said, "his own Table, where its code says it is"
    assert a.code not in said, "and the other Table is not even named (FR5)"


# FR2, FR13 — the code persists across every screen of the night, in the same header slot, whatever the
# Board has been edited into. A player who has to open something else to find their own Table's name
# cannot tell a newcomer what to send.
def test_the_code_sits_in_the_header_of_every_screen_the_night_shows():
    r, t = seated_four()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)
    shown = [e.text for e in r.message(GUEST, "/board") if isinstance(e, table.Board)]
    shown += [e.text for e in r.message(GUEST, "/history") if isinstance(e, table.Board)]
    tap(r, t, GUEST, "b", "menu")
    shown += [e.text for e in r.message(GUEST, "/end") if isinstance(e, table.Board)]
    shown += [e.text for e in tap(r, t, GUEST, "k", "end") if isinstance(e, (table.Board, table.Retired))]
    r.message(CYD, "/leave")
    shown += [e.text for e in r.message(CYD, "/board") if isinstance(e, table.Board)]

    assert shown, "the night was rendered at least once"
    for text in shown:
        assert text.splitlines()[0].startswith("Table %s ·" % t.code), text.splitlines()[0]


# S7.5 (02/NFR4) — Telegram allows 64 bytes of callback data and the token carries the code in the middle of
# it. Six characters is still short enough at the deepest stage, with the longest name a seat can carry
# and a version that has run all night: the stage that ends one tap before money moves is where a token
# has the least room left, and a truncated token is a tap that silently means something else.
def test_a_six_character_code_leaves_room_in_telegrams_64_byte_token():
    r, t = seated_four()
    t.names[HOST.user_id] = "Aarón Miguel Ángel"
    t.version = 999_999
    tap(r, t, HOST, "w", 0)

    deepest = tap(r, t, HOST, "a", "kang")                     # the payer row: the last stage there is

    tokens = [tok for tok in tokens_of(deepest) if tok.startswith("p.")]
    assert tokens, "the feeder row is on screen"
    assert max(len(tok.encode("utf-8")) for tok in tokens) <= 64
