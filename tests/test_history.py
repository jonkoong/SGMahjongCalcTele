"""/history — the night's Entries, all of them, in the chat's own message."""
import random

import render
import table
from tests.support import CYD, GUEST, HOST, board_text, keyboard_for, seated_four, seated_table, tap


def night(n):
    """A four-seat Table with n committed Entries, each a distinct winner + amount + feeder."""
    r, t = seated_four()
    for i in range(n):
        tap(r, t, HOST, "w", i % 4)
        tap(r, t, HOST, "a", "t%d" % (i // 4 + 1))
        tap(r, t, HOST, "p", (i + 1) % 4)
    return r, t


def entry_lines(text):
    """
    The Board's Entry lines, oldest first. The tell is the money figure every one ends with
    (render.entry_line) — prose like `No wins yet.` cannot imitate it, which `" wins " in text` can.
    """
    return [ln for ln in text.splitlines() if ln.rstrip()[-1:].isdigit() and " wins " in ln]


# S5.1 — the Board keeps three Entries and counts the rest; the count is a promise that the whole night
# is still there, and /history is what honours it (FR17).
def test_history_lists_every_entry_the_board_dropped():
    r, t = night(7)

    text = render.history(t)

    assert len(t.log) == len(set(t.log)) == 7, "7 distinct Entries or this proves nothing"
    assert "earlier" not in text                       # nothing hidden, so nothing counted
    assert entry_lines(text) == t.log                  # all 7, oldest first, in log order


# S5.3 — a count with no verb under it is a dead end: the Board says four wins fell off the top and, until
# now, gave the player nothing to do about it (FR17 amended at scrutiny).
def test_the_board_cue_names_the_verb_that_shows_the_rest():
    r, t = night(7)

    text = render.board(t)

    assert "… 4 earlier — /history" in text


# S5.4 — how long the night was belongs to the player who asked. Reading it must not cost the other
# three their Board: the text differs here on purpose, and only in one chat.
def test_reading_the_history_moves_nobody_elses_screen():
    r, t = night(7)

    effects = r.message(HOST, "/history")

    assert [e.chat_id for e in effects if isinstance(e, table.Board)] == [HOST.user_id]
    assert len(entry_lines(board_text(effects, HOST.user_id))) == 7
    assert len(entry_lines(render.board(t))) == render.LAST_ENTRIES   # what the others keep


# S5.5 — a screen the player can walk into has to be one they can walk out of without typing, and
# walking out must not look like work: the same message, edited back, nothing posted.
def test_back_out_of_the_history_returns_the_score_board():
    r, t = night(7)
    r.message(HOST, "/history")
    before = t.version

    effects = tap(r, t, HOST, "b", "menu")

    assert entry_lines(board_text(effects, HOST.user_id)) == t.log[-render.LAST_ENTRIES:]
    assert keyboard_for(effects, HOST.user_id) == ["Al", "Bo", "Cy", "De"]
    assert t.version == before, "reading the night is not a change, so nobody's buttons went stale"


# S5.6 — the history is read *during* a night, so it has to be survivable mid-draft: the holder's ladder
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


# S5.7 — /history is in the slash menu from the first minute of the night, so tapping it before anyone
# has won must answer, not hand back a header and four silent seats.
def test_an_empty_night_says_so_instead_of_going_blank():
    r, t = seated_four()

    text = board_text(r.message(GUEST, "/history"), GUEST.user_id)

    assert entry_lines(text) == []
    assert "No wins yet" in text


# S5.8 — /history sits in the slash menu of anyone the bot has ever met, so it has to answer a chat that
# is bound to nothing with the same sentence every other verb uses.
def test_history_with_no_table_is_the_answer_every_verb_gives():
    r = table.Room(rng=random.Random(7))

    effects = r.message(CYD, "/history")

    assert [e for e in effects if isinstance(e, table.Board)] == []
    assert "not at a table" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# S5.9 — a member who has joined but not sat is owed the seat picker they are owed for every other verb,
# and a refusal saying why the night is not theirs to read yet. The picker alone can look like nothing
# happened, because their screen already shows it.
def test_history_before_taking_a_seat_names_what_is_missing():
    r, t = seated_table()                          # two seats filled, 西 and 北 still free
    for _ in range(5):
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "t1")
        tap(r, t, HOST, "p", 1)
    r.message(CYD, "/join " + t.code)                # bound, not seated

    effects = r.message(CYD, "/history")

    offered = {table.WINDS[w] for w in t.free_winds()}
    assert set(keyboard_for(effects, CYD.user_id)) == offered        # the picker they were owed
    assert "seat" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
