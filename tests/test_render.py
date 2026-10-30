"""What each seated player sees in their own DM."""

import random

import pytest

import render
import table
from tests.support import board_text, GUEST, HOST, entry_texts, keyboard_for, PLAYER, score_wins, \
    seated_four, seated_table, tap




def record_one_win(r, t):
    """HOST starts and finishes the Entry — the draft belongs to whoever started it."""
    r.tap(HOST, table.token("w", t.code, t.version, 0))
    r.tap(HOST, table.token("a", t.code, t.version, "t3"))
    return r.tap(HOST, table.token("p", t.code, t.version, 1))


# S1.12
def test_every_seated_dm_shows_the_same_board():
    r, t = seated_table()
    effects = record_one_win(r, t)

    boards = [e for e in effects if isinstance(e, table.Board)]
    assert len(boards) == 2
    assert boards[0].text == boards[1].text

    text = boards[0].text
    assert all(label in text for label in PLAYER)     # every seat is named on the Board, FR13
    assert "Al" in text and "Bo" in text
    assert "+$1.60" in text and "-$1.60" in text
    # FR2, FR13 — the code lives in the header, permanently. A seated player is the only route a new
    # player has into the night, and "ask someone for the code" is pointless unless they can read it out.
    assert text.splitlines()[0] == "Session %s · 2 of 4 seated" % t.code
    # The win itself belongs to S3.13 (test_render::test_a_committed_win_reads_on_the_board…).
    # It used to be asserted here as a separate line per DM — FR14 moved it onto the Board.


# S4.5 (AD5) — one row per seat, in seat order, named by slot, and the vacant ones say so. This is the
# test that catches a seat label leaking into the occupancy test: the row is named, and still empty.
def test_the_board_names_all_four_seats_and_marks_the_vacant_ones():
    r, t = seated_table()                                    # Al and Bo sit; two seats are empty

    lines = [ln for ln in render.board(t).splitlines() if ln.startswith("Player")]

    assert [ln.split("  ")[0] for ln in lines] == PLAYER     # all four, in seat order
    assert lines[0].startswith("Player 1  Al") and lines[1].startswith("Player 2  Bo")
    assert lines[2].startswith("Player 3  empty") and lines[3].startswith("Player 4  empty")
    assert all(ln.endswith(" $0.00") for ln in lines)       # a flat seat reads $0.00, never +$0.00
    assert "+$0.00" not in render.board(t)


# S4.6 (FR17, ERR-03) — the header counts people, not labels. Give an empty seat a label of its own and
# counting labels reads `4 of 4 seated` on a table with nobody sitting at it.
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


# S2.15 — a bystander must be able to see a draft is live, without messaging the bot.
def test_the_board_names_the_live_draft_in_every_dm():
    r, t = seated_table()

    effects = r.tap(HOST, table.token("w", t.code, t.version, 0))

    boards = [e for e in effects if isinstance(e, table.Board)]
    assert len(boards) == 2
    assert all("Al is entering a win" in b.text for b in boards)   # same text in both DMs
    assert boards[0].text == boards[1].text


# S2.15 — once the Entry is committed the cue goes away; a committed win is not "entering".
def test_the_cue_disappears_once_the_entry_is_committed():
    r, t = seated_table()
    record_one_win(r, t)

    effects = r.message(HOST, "/board")

    text = next(e.text for e in effects if isinstance(e, table.Board))
    assert "entering a win" not in text


# 02b/D3 — position, not presence. S2.15 and S3.13 both assert the `⏳` line as a substring, so either of
# them stays green however the tail is arranged. This is the pin that says *where* it sits: last line of
# the message, and below the night's Entries rather than above them.
def test_the_draft_line_is_the_last_line_and_sits_below_the_ledger():
    r, t = seated_four()
    score_wins(r, t, 5)                                        # past the window, so the cue prints too
    tap(r, t, HOST, "w", 1)                                    # a draft opens: Al is entering a win

    lines = render.board(t).splitlines()

    assert lines[-1] == "⏳ Al is entering a win", lines[-3:]
    assert lines.count("⏳ Al is entering a win") == 1, "one tail line, never both"
    assert " wins " in lines[-2], "the Entries first, then the tail: %r" % lines[-4:]


# 02b/D2 — for every other moment of the night the last line carries the standing ask instead. One line,
# always last, one or the other: never both and never neither.
def test_the_board_always_ends_by_naming_what_to_do():
    r, t = seated_four()

    assert render.board(t).splitlines()[-1] == render.PICK_WINNER          # nobody drafting
    tap(r, t, HOST, "w", 1)
    assert render.board(t).splitlines()[-1] == "⏳ Al is entering a win"    # one is halfway in
    tap(r, t, HOST, "x", "c")
    assert render.board(t).splitlines()[-1] == render.PICK_WINNER          # cancelled: the ask is back
    record_one_win(r, t)
    assert render.board(t).splitlines()[-1] == render.PICK_WINNER          # and holds over a real win


# 02b/D4 — the phrase is decided copy, colon and all, and lives in exactly one place now that the popup
# which quoted it is gone. A test on the constant is what catches the colon drifting off it.
def test_the_invitation_says_the_decided_words():
    assert render.PICK_WINNER == "Pick who won the round:"


# 02b/E1 (Jon, 2026-10-30) — the last line is asked of the buttons under it. A member who joined and holds
# no seat is offered seats, so `Pick who won the round:` over them asks a stranger to score the night.
# Seating is what swaps the line back; nothing else does.
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


# 02b/E1's wording, pinned on the constant for the same reason `PICK_WINNER` is: the colon is the whole
# difference between a heading over a list and a sentence about nothing.
def test_the_choose_line_says_the_decided_words():
    assert render.CHOOSE_SEAT == "Choose which player you are:"


# 02b/E1's one hard case: both facts want the last line, and there is room for one. A seatless member
# cannot score, so a draft in progress is not their news — the seat is. The four seats keep the `⏳` line,
# which is who 01/FR9 was written for.
def test_the_choose_line_outranks_the_hourglass_for_someone_with_no_seat():
    r, t = seated_table()
    tap(r, t, HOST, "w", 0)                                   # Al is entering a win
    late = table.User(55, "Eve")

    effects = r.message(late, "/join " + t.code)

    assert board_text(effects, late.user_id).splitlines()[-1] == render.CHOOSE_SEAT
    assert "⏳" not in board_text(effects, late.user_id), "one tail line, never both"
    assert "⏳ Al is entering a win" in board_text(r.message(HOST, "/board"), HOST.user_id)


# 02b/E2 — a full session has no seat to choose, so the line points at the one verb that works instead of
# promising buttons that are not there. This is the case the zero-button Board ships with (see
# test_delivery's full-session test): text, and no keyboard at all.
def test_a_member_of_a_full_session_is_pointed_at_leave_instead():
    r, t = seated_four()
    late = table.User(55, "Eve")

    effects = r.message(late, "/join " + t.code)

    assert render.SESSION_FULL == "Full — /leave to join another session."
    assert board_text(effects, late.user_id).splitlines()[-1] == render.SESSION_FULL
    assert keyboard_for(effects, late.user_id) == [], "nothing is on offer, and nothing is claimed"


# S3.13 — the night's wins read on the Board itself, so a tap adds no message to the chat and the
# Board stays the newest thing in it. [FR14 amendment 2026-10-29: the entry line is a line of the
# Board, not a message of its own — the drift it caused is what Jon hit at 21:52.]
def test_a_committed_win_reads_on_the_board_and_sends_nothing_else():
    r, t = seated_table()

    effects = record_one_win(r, t)

    boards = [e for e in effects if isinstance(e, table.Board)]
    assert [e for e in effects if isinstance(e, table.Line)] == []
    assert all("Al wins 3 Tai from Bo: +$1.60" in b.text for b in boards)
    assert boards[0].text == boards[1].text


# S3.14 — folding the log into the Board puts the night's length inside Telegram's 4096-character
# message limit (AS5), so the Board keeps a recent window and counts what it stopped showing.
def test_a_long_night_shows_the_recent_wins_and_counts_the_rest():
    r, t = seated_four()
    score_wins(r, t, 15)                             # 15 Entries, each a distinct winner + amount
    assert len(t.log) == 15 and len(set(t.log)) == 15

    text = next(e.text for e in r.message(HOST, "/board") if isinstance(e, table.Board))

    assert text.count(" wins ") == render.LAST_ENTRIES
    assert "… %d earlier" % (len(t.log) - render.LAST_ENTRIES) in text
    assert entry_texts(t)[-1] in text and entry_texts(t)[0] not in text


# S3.20 — three recent Entries is the window Jon asked for: enough to see what just happened, small
# enough that the Board stays a glance rather than a scroll.
def test_the_board_keeps_three_recent_entries_and_no_more():
    r, t = seated_four()
    score_wins(r, t, 5)
    assert len(t.log) == 5

    text = next(e.text for e in r.message(HOST, "/board") if isinstance(e, table.Board))

    assert text.count(" wins ") == 3
    assert "… 2 earlier" in text and entry_texts(t)[-1] in text and entry_texts(t)[0] not in text
