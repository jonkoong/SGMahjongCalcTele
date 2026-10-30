"""What each seated player sees in their own DM."""

import random

import render
import table
from tests.support import board_text, DEB, GUEST, HOST, entry_texts, keyboard_for, PLAYER, \
    rename_picker, score_wins, seated_four, seated_table, tap




def record_one_win(r, t):
    """HOST starts and finishes the Entry — the draft belongs to whoever started it."""
    r.tap(HOST, table.token("w", t.code, t.version, 0))
    r.tap(HOST, table.token("a", t.code, t.version, "t3"))
    return r.tap(HOST, table.token("p", t.code, t.version, 1))


def test_every_seated_dm_shows_the_same_board():
    r, t = seated_table()
    effects = record_one_win(r, t)

    boards = [e for e in effects if isinstance(e, table.Board)]
    assert len(boards) == 2
    assert boards[0].text == boards[1].text

    text = boards[0].text
    assert all(label in text for label in PLAYER)     # every seat is named on the Board
    assert "Al" in text and "Bo" in text
    assert "+$1.60" in text and "-$1.60" in text
    # The code lives permanently in the header: a seated player is a newcomer's only way in, and
    # must be able to read it out.
    assert text.splitlines()[0] == "Session %s · 2 of 4 seated" % t.code
    # The win itself is asserted in test_a_committed_win_reads_on_the_board_and_sends_nothing_else.


# One row per seat, in seat order, named by slot, with vacant ones saying so. Catches a seat label
# leaking into the occupancy test: the row is named and still empty.
def test_the_board_names_all_four_seats_and_marks_the_vacant_ones():
    r, t = seated_table()                                    # Al and Bo sit; two seats are empty

    lines = [ln for ln in render.board(t).splitlines() if ln.startswith("Player")]

    assert [ln.split("  ")[0] for ln in lines] == PLAYER     # all four, in seat order
    assert lines[0].startswith("Player 1  Al") and lines[1].startswith("Player 2  Bo")
    assert lines[2].startswith("Player 3  empty") and lines[3].startswith("Player 4  empty")
    assert all(ln.endswith(" $0.00") for ln in lines)       # a flat seat reads $0.00, never +$0.00
    assert "+$0.00" not in render.board(t)


# The header counts people, not labels: counting labels would read `4 of 4 seated` on an empty
# table once seats have labels.
def test_the_header_counts_seats_by_occupancy_not_by_label():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")                                   # bound to it, holding nothing
    t = r.table_of(HOST)

    assert "0 of 4 seated" in render.board(t)

    r.tap(HOST, table.token("s", t.code, t.version, 0))
    r.message(GUEST, "/join " + t.code)
    r.tap(GUEST, table.token("s", t.code, t.version, 1))

    assert "2 of 4 seated" in render.board(t)
    assert "4 of 4 seated" not in render.board(t)


# A bystander must be able to see a draft is live, without messaging the bot.
def test_the_board_names_the_live_draft_in_every_dm():
    r, t = seated_table()

    effects = r.tap(HOST, table.token("w", t.code, t.version, 0))

    boards = [e for e in effects if isinstance(e, table.Board)]
    assert len(boards) == 2
    assert all("Al is entering a win" in b.text for b in boards)   # same text in both DMs
    assert boards[0].text == boards[1].text


# Once the Entry is committed the cue goes away; a committed win is not "entering".
def test_the_cue_disappears_once_the_entry_is_committed():
    r, t = seated_table()
    record_one_win(r, t)

    effects = r.message(HOST, "/board")

    text = next(e.text for e in effects if isinstance(e, table.Board))
    assert "entering a win" not in text


# Position, not presence: other tests assert the `⏳` line as a substring and would pass however the
# tail is arranged. This pins *where* it sits: last line, below the night's Entries.
def test_the_draft_line_is_the_last_line_and_sits_below_the_ledger():
    r, t = seated_four()
    score_wins(r, t, 5)                                        # past the window, so the cue prints too
    tap(r, t, HOST, "w", 1)                                    # a draft opens: Al is entering a win

    lines = render.board(t).splitlines()

    assert lines[-1] == "⏳ Al is entering a win", lines[-3:]
    assert lines.count("⏳ Al is entering a win") == 1, "one tail line, never both"
    assert " wins " in lines[-2], "the Entries first, then the tail: %r" % lines[-4:]


# At every other moment the last line carries the standing ask: exactly one of the two, always last.
def test_the_board_always_ends_by_naming_what_to_do():
    r, t = seated_four()

    assert render.board(t).splitlines()[-1] == render.PICK_WINNER          # nobody drafting
    tap(r, t, HOST, "w", 1)
    assert render.board(t).splitlines()[-1] == "⏳ Al is entering a win"    # one is halfway in
    tap(r, t, HOST, "x", "c")
    assert render.board(t).splitlines()[-1] == render.PICK_WINNER          # cancelled: the ask is back
    record_one_win(r, t)
    assert render.board(t).splitlines()[-1] == render.PICK_WINNER          # and holds over a real win


# The phrase is fixed copy, colon included, living in one place; a test on the constant catches
# the colon drifting off.
def test_the_invitation_says_the_decided_words():
    assert render.PICK_WINNER == "Pick who won the round:"


# The last line is asked of the buttons under it: a seatless member is offered seats, and `Pick who
# won the round:` over them would ask a stranger to score. Only seating swaps the line back.
def test_a_member_holding_no_seat_is_asked_which_player_they_are():
    r, t = seated_table()
    late = table.User(55, "Eve")

    effects = r.message(late, "/join " + t.code)

    assert board_text(effects, late.user_id).splitlines()[-1] == render.CHOOSE_SEAT
    assert set(keyboard_for(effects, late.user_id)) == {PLAYER[2], PLAYER[3]}, "the offer the line points at"

    r.tap(late, table.token("s", t.code, t.version, 2))

    assert board_text(effects, late.user_id).splitlines()[-1] == render.CHOOSE_SEAT, \
        "the offer they were shown does not change retroactively"
    assert board_text(r.message(late, "/board"), late.user_id).splitlines()[-1] == render.PICK_WINNER


# Pinned on the constant like `PICK_WINNER`: the colon makes it a heading over a list.
def test_the_choose_line_says_the_decided_words():
    assert render.CHOOSE_SEAT == "Choose which player you are:"


# The rename picker's tail, pinned like the two lines above: fixed copy whose colon makes it a
# heading over the seats.
def test_the_rename_line_says_the_decided_words():
    assert render.PICK_SEAT_TO_RENAME == "Pick whose name to change:"


# The hard case: both facts want the last line. A seatless member cannot score, so a draft in
# progress is not their news; the seat is. The four seats keep the `⏳` line.
def test_the_choose_line_outranks_the_hourglass_for_someone_with_no_seat():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)                                   # Al is entering a win
    late = table.User(55, "Eve")

    effects = r.message(late, "/join " + t.code)

    assert board_text(effects, late.user_id).splitlines()[-1] == render.CHOOSE_SEAT
    assert "⏳" not in board_text(effects, late.user_id), "one tail line, never both"
    assert "⏳ Al is entering a win" in board_text(r.message(HOST, "/board"), HOST.user_id)


# A third claimant on the last line: whoever drew the rename picker asked to rename, and a `⏳`
# line about somebody else's draft is not their next step. A seated bystander opens it mid-win,
# so both lines genuinely apply and the ranking is tested.
def test_the_rename_line_outranks_the_hourglass():
    r, t = seated_four()
    r.message(DEB, "/leave")                                  # one seat free, or there is no picker to draw
    tap(r, t, HOST, "w", 0)                                   # Al is entering a win

    picker = rename_picker(r, t, GUEST)

    assert board_text(picker, GUEST.user_id).splitlines()[-1] == render.PICK_SEAT_TO_RENAME
    assert "⏳" not in board_text(picker, GUEST.user_id), "one tail line, never both"


# A full session has no seat to choose, so the line names the one verb that works instead of
# promising buttons: text and no keyboard (see test_delivery's full-session test).
def test_a_member_of_a_full_session_is_pointed_at_leave_instead():
    r, t = seated_four()
    late = table.User(55, "Eve")

    effects = r.message(late, "/join " + t.code)

    assert render.SESSION_FULL == "Full — /leave to join another session."
    assert board_text(effects, late.user_id).splitlines()[-1] == render.SESSION_FULL
    assert keyboard_for(effects, late.user_id) == [], "nothing is on offer, and nothing is claimed"


# The night's wins read on the Board itself, so a tap adds no message and the Board stays the
# newest thing in the chat.
def test_a_committed_win_reads_on_the_board_and_sends_nothing_else():
    r, t = seated_table()

    effects = record_one_win(r, t)

    boards = [e for e in effects if isinstance(e, table.Board)]
    assert [e for e in effects if isinstance(e, table.Line)] == []
    assert all("Al wins 3 Tai from Bo: +$1.60" in b.text for b in boards)
    assert boards[0].text == boards[1].text


# Folding the log into the Board puts the night's length inside Telegram's 4096-character
# message limit, so the Board keeps a recent window and counts what it stopped showing.
def test_a_long_night_shows_the_recent_wins_and_counts_the_rest():
    r, t = seated_four()
    score_wins(r, t, 15)                             # 15 Entries, each a distinct winner + amount
    assert len(t.log) == 15 and len(set(t.log)) == 15

    text = next(e.text for e in r.message(HOST, "/board") if isinstance(e, table.Board))

    assert text.count(" wins ") == render.LAST_ENTRIES
    assert "… %d earlier" % (len(t.log) - render.LAST_ENTRIES) in text
    assert entry_texts(t)[-1] in text and entry_texts(t)[0] not in text


# Three recent Entries: enough to see what just happened, small enough to stay a glance.
def test_the_board_keeps_three_recent_entries_and_no_more():
    r, t = seated_four()
    score_wins(r, t, 5)
    assert len(t.log) == 5

    text = next(e.text for e in r.message(HOST, "/board") if isinstance(e, table.Board))

    assert text.count(" wins ") == 3
    assert "… 2 earlier" in text and entry_texts(t)[-1] in text and entry_texts(t)[0] not in text
