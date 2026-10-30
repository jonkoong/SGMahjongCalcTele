"""What the Table pays: the three settings the seated players may change, and what the
money follows (FR11)."""
import random

import pytest

import render
import score
import table
from tests.support import CYD, DEB, GUEST, HOST, buttons, menu_for, PLAYER, seated_four, \
    seated_table, tap
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


# S5.2 (FR11) — whoever holds the tiles decides what they pay. Bo sits, so Bo sets: no refusal, no
# sentence telling them to go and find the host, and no `/settings` they can see but not use.
def test_a_seated_player_may_set_shooter_and_max_tai():
    r, t = seated_table()

    opened = r.message(GUEST, "/settings")
    assert keyboard_for(opened, GUEST.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]

    tap(r, t, GUEST, "g", "shooter")
    tap(r, t, GUEST, "v", "shooter0")
    tap(r, t, GUEST, "g", "maxtai")
    tap(r, t, GUEST, "v", "maxtai8")

    assert (t.shooter, t.maxtai) == (False, 8)
    assert not [e for e in opened if isinstance(e, table.Line)], "nothing tells Bo to find a host"


# S5.1 (FR11) — the menu has to offer what the tap will honour. `/close` stays the host's alone.
def test_a_seated_player_is_offered_settings_and_only_the_host_is_offered_close():
    r, t = seated_table()

    guest = menu_for(r.message(GUEST, "/board"))
    host = menu_for(r.message(HOST, "/board"))

    assert "/settings" in guest and "/close" not in guest
    assert "/settings" in host and "/close" in host


# S5.3 (ERR-04) — the rate is typed, so opening settings to a non-host was only half the rule: the
# answer used to be dropped as a stray message. It is the answer, and it lands.
def test_a_seated_player_may_set_the_rate_by_typing_it():
    r, t = seated_table()
    tap(r, t, GUEST, "g", "rate")

    answer = r.message(GUEST, "0.2")

    assert t.rate == 0.2
    assert "$0.20" in board_text(answer, GUEST.user_id)
    assert not [e for e in answer if isinstance(e, table.Line) and "stray" in e.text.lower()]
    assert keyboard_for(answer, GUEST.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]


# S5.4 (FR11) — a seat is what makes the rule theirs. A member bound to the Table but holding nothing
# gets the picker they were owed anyway, plus the sentence saying which ingredient is missing.
def test_a_member_with_no_seat_is_refused_and_shown_the_picker():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)
    rules = (t.rate, t.shooter, t.maxtai)

    effects = tap(r, t, CYD, "g", "maxtai")

    assert set(buttons(effects)) == set(PLAYER) - {PLAYER[0], PLAYER[1]}   # the picker they were owed
    assert "seat" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
    assert (t.rate, t.shooter, t.maxtai) == rules, "no setting moved"


# S5.5 (FR11, AD24) — a setting is a write: every seated Board moves with it, and the ladder somebody
# was looking at is redrawn in place. The rung that has just gone above the cap still carries a live
# token, and it is refused rather than paid.
def test_a_setting_by_a_non_host_reaches_every_board_and_retires_the_ladder():
    r, t = seated_four()
    ladder = buttons_for(tap(r, t, GUEST, "w", 1), GUEST.user_id)     # Bo holds the amount ladder
    assert "5 Tai" in ladder, "the ladder Bo is looking at has a rung De is about to remove"

    effects = tap(r, t, DEB, "v", "maxtai3")                       # De lowers the cap under Bo's feet

    assert sorted(e.chat_id for e in effects if isinstance(e, table.Board)) == sorted(t.seated_ids())
    held = keyboard_for(r.message(GUEST, "/board"), GUEST.user_id)
    assert tai_ladder(held) == {"1 Tai", "2 Tai", "3 Tai"}          # redrawn in place, not dismissed
    refused = tap(r, t, GUEST, "a", "t5")
    assert "not on the board" in next(e.text for e in refused if isinstance(e, table.Toast)).lower()


# S5.6 (mission 01 AD9) — a value that already holds is not a change: no bump, and nobody else's
# screen is rewritten to say nothing.
def test_a_setting_already_at_that_value_costs_nobody_a_call():
    r, t = seated_four()
    tap(r, t, GUEST, "v", "shooter0")                          # Shooter is off now
    version = t.version

    effects = tap(r, t, CYD, "v", "shooter0")                  # Cy taps the same value again

    assert t.version == version, "nothing changed, so nothing went stale"
    assert [e.chat_id for e in effects if isinstance(e, table.Board)] == [CYD.user_id]
    assert keyboard_for(effects, CYD.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]


# S5.7 (FR11) — the rule is about the Table, not the screen: a player bound to nothing gets the same
# answer every other verb gives them, and the setting they aimed at does not move.
def test_a_player_at_no_table_changes_nothing_with_a_borrowed_token():
    r, t = seated_table()
    r.message(DEB, "/new")                                     # De has a Table of their own
    live = table.token("v", t.code, t.version, "shooter1")

    effects = r.tap(DEB, live)

    assert "not at table" in next(e.text for e in effects if isinstance(e, table.Toast)).lower()
    assert t.shooter is True


# S5.8 (FR12) — /close is still the host's alone, and the settings opening did not loosen it.
def test_opening_settings_to_the_seated_left_close_alone_with_the_host():
    r, t = seated_table()

    effects = r.message(GUEST, "/close")

    assert effects[0].text == "Only the host, Al, can close table %s." % t.code
    assert r.tables[t.code] is t, "the Table is still standing"



# S4.3 — the host who opened a Table and never sat down. Settings ride the Board, and a Board is owed
# only to a seated player, so this is a refusal that says what to do next, not a screen that their
# very next message would flicker away.
def test_a_host_who_has_not_taken_a_seat_is_asked_to_take_one_first():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")

    effects = r.message(HOST, "/settings")

    line = next(e.text for e in effects if isinstance(e, table.Line))
    assert "seat" in line.lower()
    assert set(buttons(effects)) == set(PLAYER)         # their screen is still the seat picker


# S4.4 — the settings screen is one viewer's keyboard, not a new message and not the group's screen
# (AD17): the host taps, and the only keyboard that moves is the host's.
def test_the_host_s_settings_screen_moves_nobody_elses_keyboard():
    r, t = seated_table()

    effects = r.message(HOST, "/settings")

    boards = {e.chat_id: e for e in effects if isinstance(e, table.Board)}
    assert set(boards) == {HOST.user_id}                       # nobody else is owed a rewrite
    assert list(buttons([boards[HOST.user_id]])) == ["Pay Rate", "Shooter", "Max Tai", "Back"]
    assert boards[HOST.user_id].text == render.board(t)        # the text stays the shared one


# S5.4 at the tap (FR11) — the keyboard is not the rule: a settings token replayed by somebody the
# picker was never drawn for is refused where they stand, by the same rule the menu encodes.
@pytest.mark.parametrize("kind,meaning", [("g", "maxtai"), ("v", "maxtai3")])
def test_a_settings_token_tapped_without_a_seat_changes_nothing(kind, meaning):
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)
    rules = (t.rate, t.shooter, t.maxtai)

    effects = tap(r, t, CYD, kind, meaning)

    assert (t.rate, t.shooter, t.maxtai) == rules
    assert "seat" in next(e.text for e in effects if isinstance(e, (table.Line, table.Toast))).lower()


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
    # The frozen number for rung 3, winner in Player 2's seat, drawn straight from tests/golden_payouts.json.
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


# The rate gets the opposite ruling to S4.15, because it moves the money under a rung rather than the
# rung under a cap: money is priced at commit, so a rung held across a rate change books a price
# nobody tapped — rung 8 at $0.10 is $51.20, the same rung at $1.00 is $512 — and the who-fed screen
# never shows the amount being paid. The rung comes back, the winner stays picked (F-01, Jon 2026-10-30).
def test_a_rate_moved_mid_draft_hands_the_amount_back_to_its_holder():
    r, t = seated_four()
    tap(r, t, HOST, "v", "maxtai10")
    tap(r, t, HOST, "w", 1)                                # Bo won
    tap(r, t, HOST, "a", "t8")                             # rung 8, chosen at the $0.10 rate
    before, version = list(t.balances), t.version

    tap(r, t, GUEST, "g", "rate")                          # a seated non-host, mid-draft
    applied = r.message(GUEST, "1.0")

    assert t.rate == 1.0 and t.balances == before, "the write itself moves no money"
    assert t.pending["winner"] == 1 and t.pending["amount"] is None, "his winner, not his rung"
    assert "8 Tai" in tai_ladder(keyboard_for(applied, HOST.user_id)), "he is handed the ladder back"
    assert t.version == version + 1                        # one change, one bump, as ever

    tap(r, t, HOST, "a", "t8")                             # re-tapped knowingly, at $1.00
    tap(r, t, HOST, "p", 0)
    assert t.balances == pytest.approx([-512.0, 512.0, 0.0, 0.0]), "the rung pays tonight's rate"


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

    # Golden, not inferred: tai 3, rate 0.1, shooter off, winner in seat 2, payer in seat 1.
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


# A value tap changes the Table, so `g` and `v` belong beside
# `w`/`a`/`p`/`x` in the staleness guard. Neither was in it: a settings screen left open across
# somebody else's win still moved the Table from a keyboard Telegram had already replaced. `b` stays
# exempt — it is the way out of a stale screen, and versioning it would trap the player on one.
@pytest.mark.parametrize("kind,meaning", [("g", "maxtai"), ("v", "maxtai3")])
def test_a_settings_screen_left_open_across_someone_else_s_win_is_stale_too(kind, meaning):
    r, t = seated_table()
    tap(r, t, GUEST, "w", 1)                                  # Bo starts a win: the version moves
    stale = table.token(kind, t.code, t.version - 1, meaning)
    before = (t.maxtai, t.shooter, t.version)

    refused = r.tap(HOST, stale)

    assert (t.maxtai, t.shooter, t.version) == before, "the stale tap changed nothing"
    assert "out of date" in next(e.text for e in refused if isinstance(e, table.Toast))


# F-03 — '²' and the Arabic-Indic digits satisfy str.isdigit(), and float() disagrees with it about
# the first of them. S4.17 ruled that a rate which is not a rate costs one refusal; it must not cost
# the polling thread, which is what a ValueError through the handler was going to cost (F-04 ate the
# taps queued behind it).
def test_a_rate_written_in_what_float_cannot_read_costs_one_refusal():
    r, t = seated_table()
    version = t.version
    tap(r, t, HOST, "g", "rate")

    refused = r.message(HOST, "\u00b2")

    assert (t.rate, t.version) == (0.1, version)
    assert "0.2" in next(e.text for e in refused if isinstance(e, table.Line))


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
