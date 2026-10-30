"""/history — the night's Entries, all of them, in the chat's own message."""
import random

import render
import table
from tests.support import CYD, GUEST, HOST, board_text, entry_texts, keyboard_for, PLAYER, \
    score_wins, seated_four, seated_table, shown_wins, tap


def night(n):
    """A four-seat Table with n committed Entries, each a distinct winner + amount + feeder."""
    r, t = seated_four()
    score_wins(r, t, n)
    return r, t


# The Board keeps three Entries and counts the rest; the count is a promise that the whole night
# is still there, and /history is what honours it.
def test_history_lists_every_entry_the_board_dropped():
    r, t = night(7)

    text = render.history(t)

    assert len(t.log) == len(set(t.log)) == 7, "7 distinct Entries or this proves nothing"
    assert "earlier" not in text                       # nothing hidden, so nothing counted
    assert shown_wins(text) == entry_texts(t)          # all 7, oldest first, in log order


# A count with no verb under it is a dead end: the Board says four wins fell off the top and, until
# now, gave the player nothing to do about it.
def test_the_board_cue_names_the_verb_that_shows_the_rest():
    r, t = night(7)

    text = render.board(t)

    assert "… 4 earlier — /history" in text


# How long the night was belongs to the player who asked. Reading it must not cost the other
# three their Board: the text differs here on purpose, and only in one chat.
def test_reading_the_history_moves_nobody_elses_screen():
    r, t = night(7)

    effects = r.message(HOST, "/history")

    assert [e.chat_id for e in effects if isinstance(e, table.Board)] == [HOST.user_id]
    assert len(shown_wins(board_text(effects, HOST.user_id))) == 7
    assert len(shown_wins(render.board(t))) == render.LAST_ENTRIES   # what the others keep


# A screen the player can walk into has to be one they can walk out of without typing, and
# walking out must not look like work: the same message, edited back, nothing posted.
def test_back_out_of_the_history_returns_the_score_board():
    r, t = night(7)
    r.message(HOST, "/history")
    before = t.version

    effects = tap(r, t, HOST, "b", "menu")

    assert shown_wins(board_text(effects, HOST.user_id)) == entry_texts(t)[-render.LAST_ENTRIES:]
    assert keyboard_for(effects, HOST.user_id) == ["Al", "Bo", "Cy", "De", "Undo last win"]
    assert t.version == before, "reading the night is not a change, so nobody's buttons went stale"


# The history is read *during* a night, so it has to be survivable mid-draft: the holder's ladder
# is replaced for a moment, and Back must hand the same draft back rather than a dead screen.
def test_back_out_of_the_history_returns_a_draft_still_in_progress():
    r, t = night(7)
    tap(r, t, GUEST, "w", 1)                        # Bo is at the amount stage
    stage = t.version
    r.message(GUEST, "/history")

    effects = tap(r, t, GUEST, "b", "menu")

    ladder = {label for label in keyboard_for(effects, GUEST.user_id) if label.endswith(" Tai")}
    assert ladder == {"%d Tai" % n for n in range(1, t.tai_cap() + 1)}
    assert t.version == stage, "the draft, and everyone else's tokens, are exactly as they were"


# /history is in the slash menu from the first minute, so tapping it before anyone has won must
# answer. An empty log gets no sentence of its own, as the `… N earlier — /history` cue only
# appears with Entries behind it.
def test_an_empty_night_shows_the_bare_board_and_no_sentence_of_its_own():
    r, t = seated_four()

    text = board_text(r.message(GUEST, "/history"), GUEST.user_id)

    assert shown_wins(text) == []
    assert text == render.board(t), "an empty night's history is the Board, with nothing said about it"


# /history sits in the slash menu of anyone the bot has ever met, so it has to answer a chat that
# is bound to nothing with the same sentence every other verb uses.
def test_history_with_no_table_is_the_answer_every_verb_gives():
    r = table.Room(rng=random.Random(7))

    effects = r.message(CYD, "/history")

    assert [e for e in effects if isinstance(e, table.Board)] == []
    assert "not in a session" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# A member who has joined but not sat is owed the seat picker they are owed for every other verb,
# and a refusal saying why the night is not theirs to read yet. The picker alone can look like nothing
# happened, because their screen already shows it.
def test_history_before_taking_a_seat_names_what_is_missing():
    r, t = seated_table()                          # two seats filled, seats 3 and 4 still free
    for _ in range(5):
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "t1")
        tap(r, t, HOST, "p", 1)
    r.message(CYD, "/join " + t.code)                # bound, not seated

    effects = r.message(CYD, "/history")

    offered = {PLAYER[w] for w in t.free_seats()}
    assert set(keyboard_for(effects, CYD.user_id)) == offered        # the picker they were owed
    assert "seat" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
