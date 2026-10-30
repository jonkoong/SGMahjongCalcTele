"""Several Tables at once, leaving one, closing one."""
import random
import re

import table

from tests.support import (board_text, buttons_for, CYD, DEB, entry_texts, GUEST, HOST, keyboard_for,
                           menu_for, PLAYER, seated_four, seated_table, tap, tap_end_exit, tokens_of)


def bo_wins_a_tai(r, t):
    """Al feeds Bo one tai: seat 1 ends owing, seat 2 is ahead."""
    tap(r, t, HOST, "w", 1)
    tap(r, t, HOST, "a", "t1")
    return tap(r, t, HOST, "p", 0)


# The seat goes back to the pool; the money sitting in it does not.
def test_leaving_frees_the_seat_but_leaves_its_money_where_it_is():
    r, t = seated_table()
    bo_wins_a_tai(r, t)

    effects = r.message(GUEST, "/leave")

    assert t.occupants[1] is None
    assert t.balances == [-0.4, 0.4, 0.0, 0.0]
    assert re.search(r"Player 2\s+empty\s+\+\$0\.40", board_text(effects, HOST.user_id))


# A seat is not a leash. /leave drops the binding too, so the player can sit elsewhere
# and the Table they left stops pushing them a Board.
def test_leaving_frees_them_to_sit_at_another_table():
    r, first = seated_table()
    r.message(CYD, "/new")
    second = r.table_of(CYD).code

    refused = r.message(GUEST, "/join " + second)
    assert r.table_of(GUEST) is first
    assert "/leave it first" in refused[0].text

    r.message(GUEST, "/leave")

    assert r.table_of(GUEST) is None
    assert "not in a session" in r.message(GUEST, "/board")[0].text
    r.message(GUEST, "/join " + second)
    assert r.table_of(GUEST) is r.table_of(CYD)



# A draft dies with its holder. Only they may cancel it, so a holder walking
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


# A draft names a seat, not a person, so being the named winner abandons it too.
def test_leaving_discards_a_draft_that_named_the_leaver_as_winner():
    r, t = seated_table()
    tap(r, t, HOST, "w", 1)
    assert t.pending["winner"] == 1

    r.message(GUEST, "/leave")

    assert t.pending is None
    assert t.balances == [0.0, 0.0, 0.0, 0.0]


# The screen they were left on must stop offering buttons.
def test_the_leaver_is_told_they_have_left_and_offers_nothing():
    r, t = seated_table()

    effects = r.message(GUEST, "/leave")

    notice = next(e for e in effects if isinstance(e, table.Retired))
    assert notice.chat_id == GUEST.user_id
    assert t.code in notice.text and "left" in notice.text.lower()


# Closing dissolves the Table for everyone at it, seated or not: the night left readable in every
# chat, old keyboards refused, bindings freed, and each player able to start afresh.
def test_closing_dissolves_the_table_for_everyone():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)
    code = t.code

    effects = tap_end_exit(r, t, HOST, table.CLOSE_SESSION)

    notices = [e for e in effects if isinstance(e, table.Retired)]
    assert {n.chat_id for n in notices} == {HOST.user_id, GUEST.user_id, CYD.user_id}
    assert all("Closed" in n.text for n in notices)
    assert code not in r.tables
    assert all(r.table_of(p) is None for p in (HOST, GUEST, CYD))
    dead_tap = r.tap(HOST, table.token("w", code, t.version, 0))
    refused = [e for e in dead_tap if isinstance(e, table.Toast)]
    assert refused == [table.Toast("That session does not exist anymore.")]

    r.message(HOST, "/new")
    assert r.table_of(HOST) is not t


class PlannedRng:
    """
    Hands out the planned codes in order, one letter per call. Answered as an index into the alphabet,
    because that is how `new_code` asks — the alphabet stays the source of the letters and this fake
    only chooses positions in it.
    """

    def __init__(self, *codes):
        self.chars = "".join(codes)
        self.i = 0

    def randrange(self, n):
        assert n == len(table.CODE_ALPHABET), "the plan is in letters of this alphabet, not their indexes"
        char = self.chars[self.i]
        self.i += 1
        return table.CODE_ALPHABET.index(char) % n


# A code in use is never handed out again while the Table lives: the repeat is stepped
# over instead of silently replacing the Table that holds it.
def test_a_code_already_in_use_is_never_handed_out_again():
    r = table.Room(rng=PlannedRng("AAAAAA", "AAAAAA", "BBBBBB"))
    r.message(HOST, "/new")

    r.message(GUEST, "/new")

    assert set(r.tables) == {"AAAAAA", "BBBBBB"}
    assert r.table_of(HOST) is not r.table_of(GUEST)


# "Unique while live" is not enough: a code is a key, and one re-cut for the next night lets whoever
# kept the old copy into a room they weren't invited to, undetectably.
def test_a_closed_code_is_never_dealed_again_while_the_process_lives():
    r = table.Room(rng=PlannedRng("AAAAAA", "AAAAAA", "B2B2B2", "C3C3C3", "D4D4D4"))
    r.message(HOST, "/new")
    t = r.table_of(HOST)
    r.tap(HOST, table.token("s", t.code, t.version, 0))            # closing is a seated verb
    tap_end_exit(r, t, HOST, table.CLOSE_SESSION)

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


# Two Tables at once must not see each other: money, Boards and entry lines all stay
# inside their own Table.
def test_two_tables_do_not_bleed_into_each_other():
    r, a = seated_table()
    b = seated_second_table(r)

    bo_wins_a_tai(r, a)

    assert a.balances == [-0.4, 0.4, 0.0, 0.0]
    assert b.balances == [0.0, 0.0, 0.0, 0.0]
    assert b.log == []
    board = next(e for e in r.message(CYD, "/board") if isinstance(e, table.Board))
    # Both Boards carry their own code; Bo's win reads in Al's Board and nowhere in Cy's.
    assert board.chat_id == CYD.user_id and "$0.00" in board.text and "wins" not in board.text


# Standing up ends the chat's Board: the notice is a `Retired` effect, so that message is never
# edited again and the next Table's Board is sent fresh.
def test_leaving_returns_the_board_slot_instead_of_owing_it():
    r, t = seated_table()

    effects = r.message(GUEST, "/leave")

    retired = [e for e in effects if isinstance(e, table.Retired)]
    assert [e.chat_id for e in retired] == [GUEST.user_id]
    assert t.code in retired[0].text and "left" in retired[0].text.lower()
    assert not [e for e in effects if isinstance(e, table.Board) and e.chat_id == GUEST.user_id]


# The slash menu matches where the player stands: no /leave without a Table, no /close at all.
# `/start` drops out once the chat has a Table. `/board` is not in the menu since the Board edits
# itself, but it remains the trigger below: the catch-all answers a typed verb the menu doesn't offer.
def test_the_command_menu_matches_where_the_player_stands():
    r = table.Room(rng=random.Random(7))

    assert menu_for(r.message(CYD, "/start")) == ("/start", "/new", "/join")

    r.message(CYD, "/new")
    assert menu_for(r.message(CYD, "/board")) == ("/leave",)

    tap(r, r.table_of(CYD), CYD, "s", 0)
    # Every verb is live, so the menu is the whole surface for a seated host.
    assert menu_for(r.message(CYD, "/board")) == ("/leave", "/history", "/end", "/settings")


# The whole menu is an exact tuple, as a substring check would miss a verb leaking onto the wrong
# keyboard. The two seated menus are identical.
def test_the_two_seated_menus_are_now_identical():
    r, t = seated_table()

    assert menu_for(r.message(GUEST, "/board")) == ("/leave", "/history", "/end", "/settings")
    assert menu_for(r.message(HOST, "/board")) == ("/leave", "/history", "/end", "/settings")


# `/close` is not a verb any more. A player who types it from muscle memory is neither refused nor
# punished for it: they are shown where they stand, and the night they are in survives the typo.
def test_typing_the_old_close_verb_costs_the_night_nothing():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)
    before = (list(t.balances), list(t.log))

    effects = r.message(HOST, "/close")

    assert t.code in r.tables and r.table_of(HOST) is t, "nothing was dissolved"
    assert (t.balances, t.log) == before
    assert any(isinstance(e, table.Board) for e in effects), "they are shown where they stand"


# /join from the command menu has no argument to carry, so it must ask for the code instead
# of answering with generic help the player cannot act on.
def test_a_bare_join_asks_for_the_code():
    r = table.Room(rng=random.Random(7))

    effects = r.message(CYD, "/join")

    ask = next(e.text for e in effects if isinstance(e, table.Line))
    # Generic help also contains "code", so the tell is that the ask doesn't send the player elsewhere.
    assert "code" in ask.lower() and "/new" not in ask


# And the next plain message is that code: bound, seated offer, nothing else required.
def test_the_next_message_is_read_as_the_code():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    code = r.table_of(HOST).code

    r.message(CYD, "/join")
    r.message(CYD, code.lower())                              # typed casually, lowercase

    assert r.table_of(CYD) is r.table_of(HOST)
    assert set(keyboard_for(r.message(CYD, "/board"), CYD.user_id)) == set(PLAYER)
    assert CYD.user_id not in r.table_of(CYD).occupants      # bound; the seat pick is still theirs


# A code that matches nothing is refused, and the asking stops: one attempt per ask, so no
# player can be left sitting in a prompt they did not mean to answer.
def test_a_wrong_code_is_refused_and_the_asking_stops():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    r.message(CYD, "/join")

    effects = r.message(CYD, "ZZZZZZ")

    assert r.table_of(CYD) is None
    assert "no live session" in next(e.text for e in effects if isinstance(e, table.Line)).lower()

    later = r.message(CYD, "hello")                           # a stray message is just a stray message
    assert r.table_of(CYD) is None
    assert not any(isinstance(e, table.Line) and "no live session" in e.text for e in later)


# A command is not an answer to the prompt: /board must not be eaten as a code.
def test_a_command_while_asked_is_not_read_as_a_code():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    r.message(CYD, "/join")

    effects = r.message(CYD, "/board")

    assert r.table_of(CYD) is None                            # /board is not a code
    assert "not in a session" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# A seat keeps what it earned and the next person to sit there inherits it; the money was never in
# the person. The older line still reads `Player 3`, as nothing re-renders a past win.
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


# The picker offers only free seats, named by slot with the same number the Board uses.
def test_the_seat_picker_offers_only_the_free_seats_by_number():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    t = r.table_of(HOST)
    tap(r, t, HOST, "s", 0)                              # the host takes the first seat
    r.message(CYD, "/join " + t.code)                     # bound, and nothing under them

    offered = keyboard_for(r.message(CYD, "/board"), CYD.user_id)

    assert offered == [PLAYER[1], PLAYER[2], PLAYER[3]]


# Two people, one empty chair: the second is refused, and refused in the words the picker
# showed them. The seat ends up with exactly one occupant either way.
def test_a_seat_someone_else_holds_is_refused_by_its_slot_name():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)
    r.message(DEB, "/join " + t.code)

    tap(r, t, CYD, "s", 2)
    second = tap(r, t, DEB, "s", 2)

    assert "Player 3 is taken" in next(e.text for e in second if isinstance(e, table.Toast))
    assert t.occupants[2] == CYD.user_id, "the seat has one occupant, not two and not nobody"


# Once the Table is gone, a player typing the old dissolving verb is told they hold no Table.
def test_a_former_member_who_types_the_old_close_verb_hears_they_have_no_table():
    r, t = seated_table()
    tap_end_exit(r, t, HOST, table.CLOSE_SESSION)
    assert r.tables == {}, "the Table is gone"

    effects = r.message(GUEST, "/close")

    assert "not in a session" in effects[0].text.lower()
    assert "close table" not in effects[0].text.lower()


# --- codes are six characters, and dealt once -------------------------------------------------------

class WorstRng:
    """
    An rng trying to sabotage the code: the widest index every time, and a `choice` that reaches
    straight for `O`. A code dealt against it still cannot hold a confusable letter, because the
    alphabet is the only thing that supplies letters (the rng is not trusted to behave).
    """

    def randrange(self, n):
        return n - 1

    def choice(self, seq):
        return "O"


# Six characters of the confusable-free alphabet, shown on the host's screen: a code nobody can
# read aloud can't be handed on.
def test_a_dealt_code_is_six_confusable_free_characters_and_reads_on_the_board():
    r = table.Room(rng=random.Random(7))

    effects = r.message(HOST, "/new")
    code = r.table_of(HOST).code

    assert len(code) == 6 and set(code) <= set(table.CODE_ALPHABET)
    board = next(e for e in effects if isinstance(e, table.Board))
    assert board.text.splitlines()[0] == "Session %s · 0 of 4 seated" % code


# The guarantee is the alphabet's, not the random source's.
def test_a_code_cannot_come_back_with_a_confusable_letter_even_from_a_mutinous_rng():
    code = table.new_code(set(), WorstRng())

    assert len(code) == 6
    assert set(code) <= set(table.CODE_ALPHABET)
    assert not set(code) & set("OoIl10"), "no letter a phone renders as another one"


# However the code is typed it is the code, and the joining player is seated.
def test_a_code_typed_any_which_way_seats_a_player():
    for spell in (lambda c: c, lambda c: c.lower(), lambda c: "  " + c + "  "):
        r = table.Room(rng=random.Random(7))
        r.message(HOST, "/new")
        code = r.table_of(HOST).code

        effects = r.message(CYD, "/join " + spell(code))

        assert r.table_of(CYD) is r.table_of(HOST), spell(code)
        assert set(keyboard_for(effects, CYD.user_id)) == set(PLAYER)   # the seat picker is the answer


# Six letters naming no live Table cost one refusal and hand over nothing: no Board, no seat row.
def test_six_letters_that_name_no_live_table_seat_nobody_and_offer_nothing():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    live = r.table_of(HOST).code
    wrong = live[:-1] + ("A" if live[-1] != "A" else "B")

    effects = r.message(CYD, "/join " + wrong)

    assert r.table_of(CYD) is None
    assert "no live session" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
    assert not [e for e in effects if isinstance(e, table.Board)]


# The whole message is the code, or it is a message: reading a code out of a sentence would seat a
# player from text that never meant to.
def test_a_code_wearing_a_word_is_not_read_as_a_code():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    code = r.table_of(HOST).code
    r.message(CYD, "/join")

    effects = r.message(CYD, "table " + code)

    assert r.table_of(CYD) is None
    assert "no live session" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# The code ask describes no shape or example: the shape is on a seated player's Board, and a
# made-up code costs one refusal either way. The length rule itself is pinned by the tests above.
def test_the_code_ask_says_the_decided_words_and_nothing_else():
    r = table.Room(rng=random.Random(7))

    ask = next(e.text for e in r.message(CYD, "/join") if isinstance(e, table.Line))

    assert ask == "Enter the session code.", "fixed copy, word for word"
    assert "/new" not in ask, "the ask asks — it does not send the player off to do something else"


# Five deals, with codes offered on purpose that are already live or spent. A hang here is a Table
# nobody can open.
def test_five_deals_repeat_no_code_that_is_live_or_spent():
    r = table.Room(rng=PlannedRng("AAAAAA", "AAAAAA", "AAAAAA", "B2B2B2", "B2B2B2",
                                  "C3C3C3", "D4D4D4", "E5E5E5"))

    for who in (HOST, GUEST, CYD, DEB, table.User(66, "Fay")):
        r.message(who, "/new")

    assert sorted(r.tables) == ["AAAAAA", "B2B2B2", "C3C3C3", "D4D4D4", "E5E5E5"]
    assert len({r.table_of(who) for who in (HOST, GUEST, CYD, DEB)}) == 4


# The code belongs to the Table, not the person who opened it: the host walking out
# changes nothing, and the code goes only when the Table does.
def test_a_code_outlives_its_host_and_dies_with_its_table():
    r, t = seated_table()
    code = t.code
    r.message(HOST, "/leave")

    assert t.code == code and r.tables[code] is t
    r.message(DEB, "/join " + code)
    assert r.table_of(DEB) is t, "the code still seats people with its host gone"

    r.message(GUEST, "/leave")                   # the last member with any claim on it walks out too
    assert r.tables[code] is t, "an empty Table is still a Table — only `Close session` dissolves it"


# Codes were once four characters; one still in a player's chat history must join nothing.
def test_an_old_four_character_code_joins_nothing():
    r, t = seated_table()

    effects = r.message(CYD, "/join 4KHB")

    assert r.table_of(CYD) is None
    assert "no live session" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# Two live Tables, one code typed casually: the right Table takes them, and the wrong
# Table is not even named, let alone shown.
def test_a_code_typed_in_lower_case_picks_its_own_table_out_of_two():
    r, a = seated_table()
    b = seated_second_table(r)
    eli = table.User(55, "Eli")

    effects = r.message(eli, "/join " + b.code.lower())

    assert r.table_of(eli) is b
    said = "".join(e.text for e in effects if hasattr(e, "text"))
    assert b.code in said, "his own Table, where its code says it is"
    assert a.code not in said, "and the other Table is not even named"


# The code persists in the same header slot across every screen of the night, so a player never has
# to open something else to tell a newcomer what to send.
def test_the_code_sits_in_the_header_of_every_screen_the_night_shows():
    r, t = seated_four()
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", 1)
    shown = [e.text for e in r.message(GUEST, "/board") if isinstance(e, table.Board)]
    shown += [e.text for e in r.message(GUEST, "/history") if isinstance(e, table.Board)]
    tap(r, t, GUEST, "b", "menu")
    settle = r.message(GUEST, "/end")                        # the settle-up screen is one of them too
    shown += [e.text for e in settle if isinstance(e, table.Board)]
    reset = buttons_for(settle, GUEST.user_id)[table.RESET_SCOREBOARD]
    shown += [e.text for e in r.tap(GUEST, reset) if isinstance(e, (table.Board, table.Retired))]
    r.message(CYD, "/leave")
    shown += [e.text for e in r.message(CYD, "/board") if isinstance(e, table.Board)]

    assert shown, "the night was rendered at least once"
    for text in shown:
        assert text.splitlines()[0].startswith("Session %s ·" % t.code), text.splitlines()[0]


# Telegram allows 64 bytes of callback data, with the code in the middle of the token. Checked at
# the deepest stage (least room left, one tap before money moves) with the longest name and a
# version that has run all night: a truncated token silently means something else.
def test_a_six_character_code_leaves_room_in_telegrams_64_byte_token():
    r, t = seated_four()
    t.names[HOST.user_id] = "Aarón Miguel Ángel"
    t.version = 999_999
    tap(r, t, HOST, "w", 0)

    deepest = tap(r, t, HOST, "a", "kang")                     # the payer row: the last stage there is

    tokens = [tok for tok in tokens_of(deepest) if tok.startswith("p.")]
    assert tokens, "the feeder row is on screen"
    assert max(len(tok.encode("utf-8")) for tok in tokens) <= 64
