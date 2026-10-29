"""What the Table pays: the three settings a host may change, and what the money follows."""
import random

import pytest

import render
import score
import table
from tests.support import DEB, GUEST, HOST, buttons, seated_four, seated_table, tap
from tests.support import board_text, buttons_for, keyboard_for, tokens_of


def tai_ladder(keyboard):
    return {label for label in keyboard if label.endswith(" Tai")}


# S4.1 — a night's money rules belong where the night's money is read out, so a player can see
# whether +$1.60 was a $0.10 win or a $0.20 one (FR13, amended at slice-4 scrutiny).
def test_a_table_opens_on_the_settings_the_old_bot_opened_on():
    r, t = seated_table()

    text = board_text(r.message(HOST, "/board"))

    assert (t.rate, t.shooter, t.maxtai) == (0.1, True, 5)   # util.py::session at 145b24b
    assert "$0.10" in text and "Shooter on" in text and "Max tai 5" in text


# S4.10 — 🔴 the defect slice 3 handed over: `_tai_number` judged an amount against `table.maxtai`
# while `score._tai` indexes a ladder that stops at rung 10, so a scoring tap at rung 11 raised
# IndexError. The ladder is frozen by tests/golden_payouts.json, so the cap comes down to it.
def test_a_cap_the_frozen_ladder_cannot_pay_is_clamped_to_the_ladder():
    r, t = seated_table()
    t.maxtai = 20                                   # what no host can set, but the attribute allowed

    offered = tai_ladder(buttons(tap(r, t, HOST, "w", 0)))
    tap(r, t, HOST, "a", "t10")
    effects = tap(r, t, HOST, "p", "z")

    assert offered == {"%d Tai" % n for n in range(1, 11)}      # rung 11 was never offered
    assert t.balances == pytest.approx([307.2, -102.4, -102.4, -102.4])   # the golden 10-tai line
    assert "Max tai 10" in board_text(effects)                 # and the Board says what it can pay


# S4.2 — a member cannot move the night's money, and a flat "no" would leave them hunting for who
# can, so the refusal names the host the way /close's does (FR18).
def test_a_member_who_asks_to_set_the_settings_is_told_who_may():
    r, t = seated_table()
    version = t.version

    effects = r.message(GUEST, "/settings")

    assert effects[0].text == "Only the host, Al, can change settings at table %s." % t.code
    assert not [e for e in effects if isinstance(e, table.Board)]    # nothing new on their screen
    assert (t.rate, t.shooter, t.maxtai, t.version) == (0.1, True, 5, version)


# S4.3 — the host who opened a Table and never sat down. Settings ride the Board, and a Board is owed
# only to a seated player, so this is a refusal that says what to do next, not a screen that their
# very next message would flicker away.
def test_a_host_who_has_not_taken_a_seat_is_asked_to_take_one_first():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")

    effects = r.message(HOST, "/settings")

    line = next(e.text for e in effects if isinstance(e, table.Line))
    assert "seat" in line.lower()
    assert set(buttons(effects)) == set(table.WINDS)      # their screen is still the seat picker


# S4.4 — the settings screen is one viewer's keyboard, not a new message and not the group's screen
# (AD17): the host taps, and the only keyboard that moves is the host's.
def test_the_host_s_settings_screen_moves_nobody_elses_keyboard():
    r, t = seated_table()

    effects = r.message(HOST, "/settings")

    boards = {e.chat_id: e for e in effects if isinstance(e, table.Board)}
    assert set(boards) == {HOST.user_id}                       # nobody else is owed a rewrite
    assert list(buttons([boards[HOST.user_id]])) == ["Pay Rate", "Shooter", "Max Tai", "Back"]
    assert boards[HOST.user_id].text == render.board(t)        # the text stays the shared one


# S4.20 — the host's keyboard is not what makes a setting host-only. Telegram replays the data an old
# button carried, so FR18 is a rule about the tap, not about who was shown the button.
@pytest.mark.parametrize("kind,meaning", [("g", "maxtai"), ("v", "maxtai3")])
def test_a_member_who_taps_a_settings_button_is_refused_by_name(kind, meaning):
    r, t = seated_table()

    effects = tap(r, t, GUEST, kind, meaning)

    assert t.maxtai == 5
    toast = next(e.text for e in effects if isinstance(e, table.Toast))
    assert toast == "Only the host, Al, can change settings at table %s." % t.code


# S4.9 — the picker is drawn from the frozen ladder, not from a wish list: the biggest thing a host can
# pick is the biggest rung that has a payout behind it. It is the ladder's whole span, not the current
# cap — a host raising a 5-tai night to 8 has to be able to see 8.
def test_the_max_tai_picker_offers_the_ladder_and_stops_there():
    r, t = seated_table()

    effects = tap(r, t, HOST, "g", "maxtai")

    board = next(e for e in effects if isinstance(e, table.Board))
    assert tai_ladder(buttons([board])) == {"%d Tai" % n for n in range(1, score.MAX_TAI + 1)}
    assert "Back" in buttons([board])


# S4.11 — `parse_token` unpacks exactly four `.`-separated fields, so a meaning carrying a dot raises on
# the way back in, and 64 bytes is Telegram's whole-token ceiling. This is part of why the rate is
# typed: `0.2` cannot live in a button payload.
def test_every_settings_token_fits_telegram_and_parses_back():
    r, t = seated_table()
    t.version = 999999                                # the worst case the code will ever hand a token

    screens = [r.message(HOST, "/settings")] + [tap(r, t, HOST, "g", key) for key in table.SETTINGS]

    made = [tok for screen in screens for tok in tokens_of(screen)]
    assert made
    for tok in made:
        assert len(tok.encode("utf-8")) <= 64
        assert "." not in table.parse_token(tok)[3]


# S4.21 — opening a settings screen is a read, not a change. A version bump there would strand every
# other player's live buttons behind an invisible staleness refusal (AD24 only bumps when it fans out).
def test_opening_a_settings_picker_leaves_the_rest_of_the_table_tappable():
    r, t = seated_table()
    version = t.version

    tap(r, t, HOST, "g", "maxtai")

    assert t.version == version
    effects = tap(r, t, GUEST, "w", 1)                       # Bo's winner button is still alive
    assert t.pending["winner"] == 1
    assert not [e for e in effects if isinstance(e, table.Toast)]


# S4.12 — a screen the host can walk into has to be one they can walk out of, and walking out must not
# cost them the win they were halfway through recording.
def test_back_out_of_settings_returns_the_host_to_the_draft_they_left():
    r, t = seated_table()
    tap(r, t, HOST, "w", 1)                                   # Bo won; an amount is still owed

    tap(r, t, HOST, "g", "maxtai")                            # the host wanders off mid-draft
    effects = tap(r, t, HOST, "b", "menu")

    assert t.pending["winner"] == 1
    assert tai_ladder(keyboard_for(effects, HOST.user_id)) == {"1 Tai", "2 Tai", "3 Tai",
                                                               "4 Tai", "5 Tai"}


# S4.12 — and Back means one level up: a rung list returns to the settings it came from rather than
# dumping the host back on the score. Which screen a button belonged to travels in the button, so the
# Table holds no idea of who is looking at what.
def test_back_out_of_a_picker_returns_to_the_settings_menu():
    r, t = seated_table()

    tap(r, t, HOST, "g", "maxtai")
    effects = tap(r, t, HOST, "b", "picker")

    assert keyboard_for(effects, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]


# S4.5 — the whole point of the command: the ladder a player is offered is what *this* Table pays, not
# what the bot shipped with. The money at the new cap is still the frozen number for that rung.
def test_the_amount_ladder_follows_the_cap_the_host_set():
    r, t = seated_table()

    applied = tap(r, t, HOST, "v", "maxtai3")

    assert t.maxtai == 3
    assert "Max tai 3" in board_text(applied, GUEST.user_id)       # Bo's Board says it too
    assert keyboard_for(applied, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]

    tap(r, t, HOST, "b", "menu")                                   # back to where the host scores
    stage = tap(r, t, HOST, "w", 1)                                # Bo won
    assert tai_ladder(keyboard_for(stage, HOST.user_id)) == {"1 Tai", "2 Tai", "3 Tai"}

    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", "z")
    # The frozen number for rung 3, winner 南, drawn straight from tests/golden_payouts.json.
    assert t.balances == pytest.approx([-0.8, 2.4000000000000004, -0.8, -0.8])


# S4.6 — a cap lowered under somebody else's draft in progress has to reach the screen that is already
# open. If it does not, the holder is left holding a button for an amount this Table no longer pays.
def test_a_cap_lowered_under_a_live_draft_shrinks_that_ladder_in_place():
    r, t = seated_table()
    stage = tap(r, t, GUEST, "w", 1)                     # Bo is entering a win
    ladder = buttons_for(stage, GUEST.user_id)
    assert {"4 Tai", "5 Tai"} <= set(ladder)

    effects = tap(r, t, HOST, "v", "maxtai2")

    assert tai_ladder(keyboard_for(effects, GUEST.user_id)) == {"1 Tai", "2 Tai"}
    assert t.pending["holder"] == GUEST.user_id          # and the draft is still Bo's

    refused = r.tap(GUEST, ladder["5 Tai"])              # the button still on Bo's screen
    assert t.pending["amount"] is None
    assert "out of date" in next(e.text for e in refused if isinstance(e, table.Toast))


# S4.14 — a tap that changes nothing must not disturb the night: AD9 refuses an edit that changes
# nothing, and a version bump would strand every other player's live buttons for no reason at all.
def test_setting_a_value_that_is_already_the_value_costs_nobody_anything():
    r, t = seated_table()
    version = t.version

    effects = tap(r, t, HOST, "v", "maxtai5")            # the default it already is

    assert (t.maxtai, t.version) == (5, version)
    assert keyboard_for(effects, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]
    assert not [e for e in effects if isinstance(e, table.Board) and e.chat_id == GUEST.user_id]


# S4.22 — AD23 seen from the write: a rung above the frozen ladder has no payout behind it, so it is
# refused rather than stored, no matter which client sent the tap.
@pytest.mark.parametrize("meaning", ["maxtai0", "maxtai11", "maxtai999"])
def test_a_value_above_the_frozen_ladder_is_refused(meaning):
    r, t = seated_table()
    version = t.version

    effects = tap(r, t, HOST, "v", meaning)

    assert (t.maxtai, t.version) == (5, version)
    assert "tai" in next(e.text for e in effects if isinstance(e, table.Toast)).lower()


# S4.15 — a cap constrains what may be chosen from now on, not what was already tapped mid-hand. The
# holder offered 8 tai; the Table pays 8 tai, and nobody's win evaporates because the host fiddled.
def test_a_draft_above_a_cap_lowered_after_it_pays_what_it_was_tapped_for():
    r, t = seated_four()
    tap(r, t, HOST, "v", "maxtai10")
    tap(r, t, HOST, "w", 1)                                # Bo won
    tap(r, t, HOST, "a", "t8")

    tap(r, t, HOST, "v", "maxtai3")                        # the host fiddles mid-draft
    committed = tap(r, t, HOST, "p", "z")

    assert t.pending is None
    assert t.balances == pytest.approx([-25.6, 76.8, -25.6, -25.6])   # rung 8, the frozen 512
    assert "Bo wins 8 Tai on Zi Mo" in board_text(committed)


# S4.8 — the shooter switch has to reach the kernel, not just the wording: with it off a named feeder
# pays half and the other two seats a quarter each — the frozen non-shooter factors, quirks included.
def test_turning_the_shooter_off_moves_money_to_the_seats_that_did_not_feed():
    r, t = seated_four()

    applied = tap(r, t, HOST, "v", "shooter0")

    assert t.shooter is False
    assert "Shooter off" in board_text(applied, GUEST.user_id)
    assert "Shooter off" in board_text(applied, DEB.user_id)

    tap(r, t, HOST, "w", 1)                                # Bo won
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 0)                                # ... and Al fed it

    # Golden, not inferred: tai 3, rate 0.1, shooter off, winner 南, payer 東.
    assert t.balances == pytest.approx([-0.8, 1.6, -0.4, -0.4])


# S4.23 — a menu that opens for two of its three buttons is a menu lying about the third.
def test_the_shooter_picker_offers_both_ways_to_pay():
    r, t = seated_table()

    effects = tap(r, t, HOST, "g", "shooter")

    assert keyboard_for(effects, HOST.user_id) == ["On", "Off", "Back"]


# S4.16 — the rate is typed, not tapped: the old bot took any number, and four buttons would quietly
# narrow what a host can run a night at. The ask has to be an ask — it names the answer it wants and
# changes nothing by itself — and the player's next message is that answer (AD21, amended).
def test_the_rate_is_asked_for_and_the_next_message_is_the_answer():
    r, t = seated_table()

    asked = tap(r, t, HOST, "g", "rate")
    question = next(e.text for e in asked if isinstance(e, table.Line))

    assert "rate" in question.lower() and "0." in question      # it says what to send
    assert t.rate == 0.1                                        # and asking changed nothing

    version = t.version
    applied = r.message(HOST, "0.2")

    assert t.rate == 0.2
    assert t.version == version + 1                             # one change, one bump
    assert "$0.20" in board_text(applied, GUEST.user_id)        # Bo's Board moved with it
    assert keyboard_for(applied, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]


# S4.17 — one attempt per ask. A rate that is not a rate costs one refusal, and the following message
# is an ordinary message again: nobody gets to sit inside a prompt they did not mean to answer.
def test_a_rate_that_is_not_a_rate_costs_one_refusal_and_the_asking_stops():
    r, t = seated_table()
    version = t.version
    tap(r, t, HOST, "g", "rate")

    refused = r.message(HOST, "banana")

    assert (t.rate, t.version) == (0.1, version)
    assert "0.2" in next(e.text for e in refused if isinstance(e, table.Line))

    later = r.message(HOST, "hello")                        # an ordinary stray message, not a retry
    assert t.rate == 0.1
    assert any(isinstance(e, table.Board) for e in later)
    assert not [e for e in later if isinstance(e, table.Line) and "not a rate" in e.text]


# S4.18 — a command is never an answer, and sending one must close the ask rather than leave it open
# to eat whatever the player types next (AD21).
def test_a_command_while_asked_for_a_rate_is_not_eaten_as_the_rate():
    r, t = seated_table()
    tap(r, t, HOST, "g", "rate")

    effects = r.message(HOST, "/board")

    assert any(isinstance(e, table.Board) for e in effects)  # /board is still /board
    assert t.rate == 0.1
    r.message(HOST, "0.9")                                  # nothing is waiting for it now
    assert t.rate == 0.1


# S4.15b — the ask grants nothing. Answering after the Table is gone is an ordinary message from
# somebody who has no Table, not a write into a Table that no longer exists.
def test_a_rate_answered_after_the_table_closed_changes_nothing():
    r, t = seated_table()
    tap(r, t, HOST, "g", "rate")

    r.message(HOST, "/close")
    effects = r.message(HOST, "0.5")

    assert t.rate == 0.1
    assert "not at a table" in next(e.text for e in effects if isinstance(e, table.Line)).lower()


# S4.7 — the rate is the setting the players actually care about: the same win at the same rung, twice
# the ladder and ten times the money, with the reason visible in every DM (FR13 amended).
def test_a_new_rate_moves_the_money_and_every_dm_reads_it():
    r, t = seated_table()

    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    first = tap(r, t, HOST, "p", 1)

    assert t.balances == pytest.approx([1.6, -1.6, 0.0, 0.0])       # golden: rung 3 at $0.10
    assert "Rate $0.10" in board_text(first, GUEST.user_id)

    tap(r, t, HOST, "g", "rate")
    raised = r.message(HOST, "1")

    assert "$1.00" in board_text(raised, HOST.user_id)
    assert "$1.00" in board_text(raised, GUEST.user_id)             # the same words in Bo's DM

    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)
    assert t.balances == pytest.approx([17.6, -17.6, 0.0, 0.0])     # 1.6 + golden 16.0 at $1


# S4.24 — the answer to a command is the Board itself, edited. Two lines here were cut on Jon's ruling
# at the slice-4 self-check: "Change what the table pays" and a restatement of the settings after
# typing a rate, both redundant when the buttons and the rate line change under the player's eyes —
# and anything posted lands *below* the Board, which is the drift FR12 exists to stop.
def test_opening_settings_and_answering_the_rate_post_no_commentary():
    r, t = seated_table()

    opened = r.message(HOST, "/settings")
    tap(r, t, HOST, "g", "rate")

    answered = r.message(HOST, "0.2")

    assert [e.text for e in opened if isinstance(e, table.Line)] == []
    assert [e.text for e in answered if isinstance(e, table.Line)] == []
    assert t.rate == 0.2                                    # the work still got done
    assert "$0.20" in board_text(answered, HOST.user_id)    # and it reads on the Board
