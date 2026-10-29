"""What each seated player sees in their own DM."""

import pytest

import render
import table
from tests.support import GUEST, HOST, seated_four, seated_table, tap




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
    assert set(table.WINDS) <= set(text)                 # the seating arrangement, FR13
    assert "Al" in text and "Bo" in text
    assert "+$1.60" in text and "-$1.60" in text
    assert t.code in text
    # The win itself belongs to S3.13 (test_render::test_a_committed_win_reads_on_the_board…).
    # It used to be asserted here as a separate line per DM — FR14 moved it onto the Board.


# S1.12
def test_an_unoccupied_wind_is_shown_as_empty_with_its_balance():
    r, t = seated_table()
    text = render.board(t)
    assert "empty" in text
    assert "+$0.00" not in text                # a flat seat reads $0.00, never +$0.00
    assert text.count("$0.00") == 4


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
    for n in range(15):                              # 15 Entries, each a distinct winner + amount
        tap(r, t, HOST, "w", n % 4)
        tap(r, t, HOST, "a", "t%d" % (n // 4 + 1))
        tap(r, t, HOST, "p", (n + 1) % 4)
    assert len(t.log) == 15 and len(set(t.log)) == 15

    text = next(e.text for e in r.message(HOST, "/board") if isinstance(e, table.Board))

    assert text.count(" wins ") == render.LAST_ENTRIES
    assert "… %d earlier" % (len(t.log) - render.LAST_ENTRIES) in text
    assert t.log[-1] in text and t.log[0] not in text


# S3.20 — three recent Entries is the window Jon asked for: enough to see what just happened, small
# enough that the Board stays a glance rather than a scroll.
def test_the_board_keeps_three_recent_entries_and_no_more():
    r, t = seated_four()
    for n in range(5):
        tap(r, t, HOST, "w", n % 4)
        tap(r, t, HOST, "a", "t%d" % (n + 1))
        tap(r, t, HOST, "p", (n + 1) % 4)
    assert len(t.log) == 5

    text = next(e.text for e in r.message(HOST, "/board") if isinstance(e, table.Board))

    assert text.count(" wins ") == 3
    assert "… 2 earlier" in text and t.log[-1] in text and t.log[0] not in text
