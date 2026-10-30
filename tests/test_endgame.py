"""/end — the night's transfers, then a wiped slate and the same four players for the next round."""
import render
import table
from tests.support import CYD, GUEST, DEB, HOST, board_text, buttons_for, keyboard_for, PLAYER, \
    seated_four, seated_table, tap, tap_end_exit, tokens_of


def a_night_two_up_two_down():
    """Al and Cy ahead, Bo and De behind — the shape that needs more than one transfer."""
    r, t = seated_four()
    for winner, payer, rung in ((0, 1, 3), (0, 3, 2), (2, 1, 1), (2, 1, 2), (0, 1, 1)):
        tap(r, t, HOST, "w", winner)
        tap(r, t, HOST, "a", "t%d" % rung)
        tap(r, t, HOST, "p", payer)
    return r, t


def transfer_lines(text):
    """The `X pays Y: $n` lines, in the order the kernel chose them."""
    return [ln for ln in text.splitlines() if " pays " in ln]


# S5.17, S4.7 — 🔴 the short-handed night slice 1 witnessed (two empty seats charged −$3.20 each)
# reaches score.settle with a name it was never written for. The money lives in the seat, not the
# person (AD4), so the seat is what the sentence must name — the 2022 kernel printed `None pays Di`.
def test_an_empty_seat_is_named_by_its_slot_in_the_settlement():
    r, t = seated_table()                          # seats 3 and 4 sit empty but still pay
    tap(r, t, HOST, "w", 0)
    tap(r, t, HOST, "a", "t1")
    tap(r, t, HOST, "p", "z")                      # Zi Mo — all three other slots pay

    text = render.settlement(t)

    assert "None" not in text
    assert "Bo pays Al: $0.20" in text
    assert "Player 3 (empty) pays Al: $0.20" in text and "Player 4 (empty) pays Al: $0.20" in text


# S5.12 — /end exists so the money can actually move, so the numbers come out of the frozen kernel in
# its own order (FR23), and the totals are repeated because the Board is about to forget them.
def test_the_settlement_repeats_the_totals_and_says_the_kernels_own_transfers():
    r, t = a_night_two_up_two_down()

    text = render.settlement(t)

    # Not `t.balances == [...]`: float residue is part of the frozen contract (Out of Scope), so the
    # numbers that count are the ones money() renders to cents for the players.
    assert transfer_lines(text) == ["Bo pays Al: $2.80", "Bo pays Cy: $0.40", "De pays Cy: $0.80"]
    assert "Player 1  Al" in text and "+$2.80" in text and "-$3.20" in text
    assert text.startswith("Session %s · settled" % t.code)


# S5.19 — /end is offered from the first hand, so a night with nothing to settle still answers. Out of
# Scope rules out inventing a case for it, so this pins the fall-through to the kernel's own words.
def test_a_night_with_nothing_to_settle_says_so():
    r, t = seated_four()

    text = render.settlement(t)

    assert transfer_lines(text) == [] and "No Payment" in text
    assert text.splitlines()[0] == "Session %s · settled" % t.code


# S5.10 — settlement is irreversible (no undo, memory only), so a mistyped /end must not wipe a night.
# The ask shows what is about to be lost, and asking is not doing (AD25).
def test_end_asks_before_anything_settles():
    r, t = a_night_two_up_two_down()
    before = (list(t.balances), list(t.log), t.version)

    effects = r.message(HOST, "/end")

    text = board_text(effects, HOST.user_id)
    assert len(transfer_lines(text)) == 3, "the ask has to show what confirming costs"
    assert keyboard_for(effects, HOST.user_id) == ["Reset scoreboard", "Close session", "Keep playing"]
    assert (t.balances, t.log, t.version) == before, "nothing has moved yet"
    assert [e.chat_id for e in effects if isinstance(e, table.Board)] == [HOST.user_id]


# 04/D1 — a screen that offers two exits must not let either one do the other's job on the way past it.
# Written the other way round from the money: whatever `Close session` ends up doing, it is not this.
# Asserted on the ledger rather than on a message, so the test still holds once the exit does something.
def test_the_close_exit_does_not_settle_the_round():
    r, t = a_night_two_up_two_down()
    before = (list(t.balances), list(t.log))

    tap_end_exit(r, t, HOST, table.CLOSE_SESSION)

    assert (t.balances, t.log) == before, "closing the night is a different act from resetting it"


# 04/D3, D4 — ending the night is nobody's private verb. The seat is the whole test, as it already is
# for the money and the settings (02/FR11): whoever holds a seat may end the night they are paying in.
def test_any_seated_player_can_close_the_session():
    r, t = seated_table()

    tap_end_exit(r, t, GUEST, table.CLOSE_SESSION)

    assert t.code not in r.tables, "the Table is gone, not merely settled"
    assert all(r.table_of(who) is None for who in (HOST, GUEST)), "every binding is freed"


# 04/D6 — closing destroys the Table, so the text left standing in the chat is the last copy of the
# night's money that will ever exist. It has to be the numbers themselves, said once and identically in
# every chat, with no button left behind to tap on a Table that no longer exists.
def test_closing_leaves_the_final_scoreboard_readable_in_every_chat():
    r, t = a_night_two_up_two_down()

    effects = tap_end_exit(r, t, HOST, table.CLOSE_SESSION)

    receipts = [e for e in effects if isinstance(e, table.Retired)]
    assert len(receipts) == 4, "every member keeps a copy, not only the one who closed it"
    assert transfer_lines(receipts[0].text) == ["Bo pays Al: $2.80", "Bo pays Cy: $0.40",
                                                "De pays Cy: $0.80"]
    assert "+$2.80" in receipts[0].text, "the totals are what the transfers are checked against"
    assert "Closed" in receipts[0].text, "and the chat says the night is over"
    assert all(r.text == receipts[0].text for r in receipts), "one night, said identically in every DM"
    assert not tokens_of(effects), "a dead Table offers no buttons"


# 04/D5 — the settle-up screen is the confirm, but it buys no override, and 02b/E3 moved that ruling to the
# ask: a win halfway through being entered means the close exit is never offered in the first place, at
# either exit, because throwing away someone else's half-entered Entry is what each of them would do.
def test_a_close_asked_while_someone_is_entering_a_win_is_never_offered():
    r, t = a_night_two_up_two_down()
    tap(r, t, GUEST, "w", 1)                          # Bo is halfway through an Entry
    before = (list(t.balances), list(t.log), t.version)

    effects = r.message(HOST, "/end")

    assert next(e.text for e in effects if isinstance(e, table.Line)) == \
        "Game cannot end when someone is entering a win — Bo is entering a win."
    assert table.CLOSE_SESSION not in keyboard_for(effects, HOST.user_id)
    assert t.code in r.tables and r.table_of(HOST) is t, "nobody was freed"
    assert (t.balances, t.log, t.version) == before
    assert t.pending is not None, "Bo's draft is untouched"


# 02b/E3 — the ask is the rule; this is the backstop behind it. A `k…reset` token cannot reach a live
# settle-up screen over somebody else's draft (the draft bumps the version, and the ask refuses), so this
# is a forged or badly-replayed payload — and it still must not wipe the slate over a live Entry. It
# shares the one line every replaced screen gets (02b/D9): the screen it arrived from is gone.
def test_a_reset_reaching_the_tap_over_someone_elses_draft_pops_the_shared_line():
    r, t = a_night_two_up_two_down()
    tap(r, t, GUEST, "w", 1)
    before = (list(t.balances), list(t.log), t.version)

    effects = r.tap(HOST, table.token("k", t.code, t.version, table.RESET_SCOREBOARD))

    assert next(e.text for e in effects if isinstance(e, table.Toast)) == table.OUTDATED
    assert (t.balances, t.log, t.version) == before, "the slate is intact"
    assert t.pending is not None, "Bo's draft is untouched"
    assert any(isinstance(e, table.Board) and e.chat_id == HOST.user_id for e in effects), \
        "and the tapper is landed back on their own screen"


# 04/D5 — one fewer confirmation is not one fewer version check. A win scored after the settle-up screen
# was drawn makes the transfers printed on it wrong, so neither of its exits may still fire.
def test_a_close_from_a_superseded_screen_frees_nobody():
    r, t = a_night_two_up_two_down()
    stale = buttons_for(r.message(HOST, "/end"), HOST.user_id)[table.CLOSE_SESSION]
    tap(r, t, GUEST, "w", 1)
    tap(r, t, GUEST, "a", "t1")
    tap(r, t, GUEST, "p", 0)                          # a win lands after the screen was drawn

    effects = r.tap(HOST, stale)

    assert next(e.text for e in effects if isinstance(e, table.Toast)) == table.OUTDATED
    assert t.code in r.tables and r.table_of(HOST) is t, "nobody was freed by a stale button"


# 04/D3 — closing is about the binding, not the money, so unlike the reset it reaches everyone bound:
# the joiner who never sat holds no slot (01/AD4) and is freed all the same, or they are left unable to
# open or join anything at all.
def test_closing_frees_a_member_who_never_took_a_seat():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)                 # bound, unseated

    effects = tap_end_exit(r, t, HOST, table.CLOSE_SESSION)

    assert CYD.user_id in {e.chat_id for e in effects if isinstance(e, table.Retired)}
    assert CYD.user_id in [e.chat_id for e in effects if isinstance(e, table.Commands)]
    assert r.table_of(CYD) is None


# 04/D3, FR5 — two nights run in one process, and ending one is nobody else's business.
def test_closing_one_session_leaves_the_other_night_playing():
    r, t = a_night_two_up_two_down()
    r.message(CYD, "/leave")
    r.message(CYD, "/new")
    t2 = r.table_of(CYD)
    r.tap(CYD, table.token("s", t2.code, t2.version, 0))
    tap(r, t2, CYD, "w", 0)
    tap(r, t2, CYD, "a", "t1")
    tap(r, t2, CYD, "p", "z")
    other = (list(t2.balances), list(t2.log))
    assert any(t2.balances), "the second night has money to lose, or this proves nothing"

    tap_end_exit(r, t, HOST, table.CLOSE_SESSION)

    assert t2.code in r.tables and r.table_of(CYD) is t2
    assert (t2.balances, t2.log) == other


# S5.12 — the headline (FR19): say the night's money in the kernel's own words, then zero the balances and
# drop the log while the four players and the settings all stay exactly where they were.
def test_a_confirmed_end_settles_then_zeroes_and_keeps_the_players():
    r, t = a_night_two_up_two_down()
    seats, rules = list(t.occupants), (t.rate, t.shooter, t.maxtai)
    names = dict(t.names)
    asked = t.version

    effects = tap_end_exit(r, t, HOST, table.RESET_SCOREBOARD)

    settled = [e for e in effects if isinstance(e, table.Retired)]
    assert len(settled) == 4, "every seated DM is owed the night's transfers, not just the one who asked"
    assert transfer_lines(settled[0].text) == ["Bo pays Al: $2.80", "Bo pays Cy: $0.40",
                                               "De pays Cy: $0.80"]
    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.log == []
    assert t.occupants == seats and (t.rate, t.shooter, t.maxtai) == rules
    assert t.names == names and r.tables[t.code] is t, "the roster is kept for the next round"
    assert t.version == asked + 1
    for board in [e for e in effects if isinstance(e, table.Board)]:
        assert "$0.00" in board.text and " wins " not in board.text


# S5.11 — the escape hatch works, which is the whole difference between a confirmation and a trap.
def test_keeping_playing_settles_nothing_and_gives_the_board_back():
    r, t = a_night_two_up_two_down()
    before = (list(t.balances), list(t.log))
    r.message(HOST, "/end")

    effects = tap(r, t, HOST, "b", "menu")

    assert keyboard_for(effects, HOST.user_id) == ["Al", "Bo", "Cy", "De", "Undo last win"]
    assert (t.balances, t.log) == before


# S5.10b — /end sits in the slash menu of the seated only. A member who joined and never sat, and typed it
# anyway, is told what is missing rather than watching a picker reappear that their screen already showed.
# (Leaving is not this state: /leave unbinds the player entirely, so a member with no seat is a joiner.)
def test_end_before_taking_a_seat_names_what_is_missing():
    r, t = seated_table()
    for _ in range(3):
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "t1")
        tap(r, t, HOST, "p", 1)
    r.message(CYD, "/join " + t.code)                 # bound, and seats 3 and 4 are still free

    effects = r.message(CYD, "/end")

    assert {PLAYER[w] for w in t.free_seats()} <= set(keyboard_for(effects, CYD.user_id))
    assert "seat" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
    assert len(t.log) == 3 and any(t.balances), "a night nobody sat through is not settled by a bystander"


# S5.12b — the keyboard is not the rule (S4.20's lesson, applied to the new verb): Telegram replays whatever
# data a button carried, so seating is re-checked at the tap and not only at the keyboard.
def test_a_confirm_tapped_without_a_seat_changes_nothing():
    r, t = seated_table()
    for _ in range(3):
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "t1")
        tap(r, t, HOST, "p", 1)
    r.message(CYD, "/join " + t.code)

    effects = tap(r, t, CYD, "k", "reset")

    # 02b/D9 — a money tap from a member holding no seat answers with the picker they were owed anyway,
    # not a sentence describing it. The guard is what keeps a seatless tap from wiping a night.
    assert not [e for e in effects if isinstance(e, table.Toast)], "no popup: the picker answers"
    assert set(keyboard_for(effects, CYD.user_id)) == {PLAYER[w] for w in t.free_seats()}
    assert len(t.log) == 3 and any(t.balances)


# S5.16 — the dialog is a write, so it is version-checked: a night that scored again after the ask is a
# different night, and the transfers it would print are no longer the ones on screen.
def test_a_confirm_from_a_superseded_screen_is_refused():
    r, t = a_night_two_up_two_down()
    stale = buttons_for(r.message(HOST, "/end"), HOST.user_id)[table.RESET_SCOREBOARD]
    tap(r, t, GUEST, "w", 1)
    tap(r, t, GUEST, "a", "t1")
    tap(r, t, GUEST, "p", 0)                          # a win lands after the ask

    effects = r.tap(HOST, stale)

    assert next(e.text for e in effects if isinstance(e, table.Toast)) == table.OUTDATED
    assert len(t.log) == 6 and any(t.balances), "nothing was said and nothing was wiped"


# S5.14 — the night is shared, so the settlement is too; the member who joined but never sat holds no
# slot and is owed none of it.
def test_every_seated_dm_is_settled_and_an_unseated_member_is_left_alone():
    r, t = seated_table()
    for _ in range(3):
        tap(r, t, HOST, "w", 0)
        tap(r, t, HOST, "a", "t1")
        tap(r, t, HOST, "p", 1)
    r.message(DEB, "/join " + t.code)                 # bound, unseated: holds no money (AD4)

    effects = tap_end_exit(r, t, HOST, table.RESET_SCOREBOARD)

    owed = sorted([HOST.user_id, GUEST.user_id])
    settled = [e for e in effects if isinstance(e, table.Retired)]
    assert sorted(e.chat_id for e in settled) == owed
    assert settled[0].text == settled[1].text, "one night, said identically in both DMs"
    assert sorted(e.chat_id for e in effects if isinstance(e, table.Board)) == owed
    assert DEB.user_id not in [e.chat_id for e in effects]


# S5.18 — two nights run in one process (FR5), and /end belongs to exactly one of them. Mutation-checked:
# point `_end` at the wrong Table and this is the test that says so.
def test_settling_one_table_leaves_the_other_nights_money_alone():
    r, t = a_night_two_up_two_down()
    r.message(CYD, "/leave")
    r2 = r.table_of(CYD)
    r.message(CYD, "/new")
    t2 = r.table_of(CYD)
    r.tap(CYD, table.token("s", t2.code, t2.version, 0))
    tap(r, t2, CYD, "w", 0)
    tap(r, t2, CYD, "a", "t1")
    tap(r, t2, CYD, "p", "z")
    other = (list(t2.balances), list(t2.log))
    assert any(t2.balances), "the second night has money to lose, or this proves nothing"
    tap_end_exit(r, t, HOST, table.RESET_SCOREBOARD)

    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert (t2.balances, t2.log) == other


# S5.15 / 02b-E3 — FR10 is not overridable by a confirmation, and it is now said at the ask: `/end` is
# offered to every seated player, so a bystander used to be shown `Reset scoreboard` over someone else's
# draft and refused one tap later. The exits are never offered at all now.
def test_asking_to_end_while_someone_is_entering_a_win_refuses_and_names_them():
    r, t = a_night_two_up_two_down()
    tap(r, t, GUEST, "w", 1)                          # Bo is halfway through an Entry (a draft bumps)
    before = (list(t.balances), list(t.log), t.version)

    effects = r.message(HOST, "/end")

    refusal = next(e.text for e in effects if isinstance(e, table.Line))
    # FR27 (Jon, 2026-10-30) — the sentence names the reason, not just the holder. It replaces the wording
    # the tap-time refusal uses, because "only they can finish it" answers a question the refuser did not ask.
    assert refusal == "Game cannot end when someone is entering a win — Bo is entering a win.", refusal
    assert (t.balances, t.log, t.version) == before, "no money said, no slate wiped, nothing bumped"
    assert t.pending is not None, "Bo's draft is untouched"
    assert "⏳ Bo is entering a win" in board_text(effects, HOST.user_id)   # the Board says why too
    assert table.RESET_SCOREBOARD not in keyboard_for(effects, HOST.user_id), \
        "02b/E3: an exit that will be refused is never offered"


# S5.15b / 02b-D8 and 02b-D17 — the holder's own exit goes over the top of their own draft: no confirmation
# was ever what bought the right to discard *another* player's entry, and their thumb reaching the button
# says they want the night gone. The draft must leave with the slate — a `pending` left pointing at a wiped
# ledger would judge the next tap against a win that no longer exists.
def test_the_holder_who_taps_close_on_their_own_draft_settles_the_night():
    r, t = a_night_two_up_two_down()
    tap(r, t, GUEST, "w", 1)

    effects = tap_end_exit(r, t, GUEST, table.RESET_SCOREBOARD)

    assert [e for e in effects if isinstance(e, table.Line)] == [], "no refusal at their own exit"
    assert t.pending is None, "the draft went with the slate"
    assert t.log == [] and set(t.balances) == {0.0}
    assert any(isinstance(e, table.Retired) for e in effects), "the settlement landed"
    assert "⏳" not in board_text(effects, GUEST.user_id), "the fresh Board shows no half-entered win"
