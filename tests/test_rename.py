"""Renaming a seat: the button, the picker, the typed name, and what a name may say (mission 05)."""
import random

import pytest

import render
import table
from tests.support import arm_rename, board_for, CYD, DEB, GUEST, HOST, PLAYER, board_text, \
    buttons_for, entry_texts, keyboard_for, rename, rename_picker, score_wins, seated_four, \
    seated_table, tap, tap_end_exit, tokens_of


# S3.1 (FR2) — the money rules are three, and the fourth button is not one of them: it rides the same
# screen because it is where a seated player already comes to change the night, alone on its own row so
# a thumb cannot land on it while reaching for `Back`.
def test_a_free_seat_brings_the_fourth_button_alone_above_back():
    r, t = seated_table()

    opened = r.message(HOST, "/settings")

    assert keyboard_for(opened, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                  "Change player names", "Back"]
    row = board_for(opened, HOST.user_id).rows[-2]
    assert len(row) == 1, "its own row — it shares nothing with the way out"


# S3.2 (D4) — both directions of one rule. A full Table has no seat to rename, so the button is not
# drawn; and it is the *Table's* freeness that decides, so the moment a player stands up the offer is
# back on the very next screen.
def test_a_full_table_never_draws_it_and_a_seat_freed_later_brings_it_back():
    r, t = seated_four()

    full = r.message(HOST, "/settings")
    assert keyboard_for(full, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]

    r.message(CYD, "/leave")
    freed = r.message(HOST, "/settings")
    assert keyboard_for(freed, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                 "Change player names", "Back"]


# S3.3 (FR3) — the picker is the Board with the free seats as its buttons: one seat to a row, `Back` last,
# and the decided line above them saying what they are for. It edits the chat's own message rather than
# posting one (01/FR12) — a screen that climbed the chat would push the Board out of reach.
def test_the_picker_names_every_free_seat_one_row_each_then_back():
    r, t = seated_table()

    picker = rename_picker(r, t, HOST)

    rows = board_for(picker, HOST.user_id).rows
    assert [[label for label, _ in row] for row in rows] == [[PLAYER[2]], [PLAYER[3]], ["Back"]]
    assert board_text(picker).splitlines()[-1] == "Pick whose name to change:"
    assert [e for e in picker if isinstance(e, table.Line)] == [], "the picker edits, it does not post"


# S3.6 (FR3) — one level up, the same rule the shooter and max-tai pickers already follow: `Back` returns
# the settings menu the player came from, not the score underneath it.
def test_back_out_of_the_rename_picker_returns_the_settings_menu():
    r, t = seated_table()
    picker = rename_picker(r, t, HOST)

    effects = r.tap(HOST, buttons_for(picker, HOST.user_id)["Back"])

    assert keyboard_for(effects, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                   "Change player names", "Back"]


# S3.5 (FR4) — a seat tapped is a question asked and nothing else. The words are the decided ones: this
# message is the whole contract between the tap and the answer, and the ask naming its seat is what lets
# the answer land on that seat and nowhere else (05/AD7).
def test_tapping_a_picker_seat_asks_for_the_name_and_changes_nothing():
    r, t = seated_table()
    version = t.version

    armed = arm_rename(r, t, HOST, PLAYER[2])

    assert [e.text for e in armed if isinstance(e, table.Line)] == ["Enter the player's name:"]
    assert (t.version, t.seat_label(2)) == (version, PLAYER[2]), "a pick is a read: nothing moved"
    assert r.asked[HOST.user_id].seat == 2


# S3.7 (AD6) — `n` is versioned, so a picker left open across somebody's win is a screen Telegram has
# already replaced: the shared line, this player's own Board behind it, and no write. Both shapes of the
# one fact — the button that was really on screen, and the longhand stale token.
def test_a_rename_picker_left_open_across_someone_else_s_win_is_stale():
    r, t = seated_table()
    picker = rename_picker(r, t, HOST)
    drawn = buttons_for(picker, HOST.user_id)[PLAYER[2]]

    tap(r, t, GUEST, "w", 1)
    tap(r, t, GUEST, "a", "t3")
    tap(r, t, GUEST, "p", 0)                              # Bo books a win: the version moved on

    for stale in (drawn, table.token("n", t.code, t.version - 1, 2)):
        refused = r.tap(HOST, stale)
        assert next(e.text for e in refused if isinstance(e, table.Toast)) == table.OUTDATED
        assert any(isinstance(e, table.Board) and e.chat_id == HOST.user_id for e in refused)
        assert HOST.user_id not in r.asked, "a refused picker arms nothing"
    assert t.seat_label(2) == PLAYER[2], "and no label moved"


# S3.10 (ERR-05) — the button hides itself when no seat is free, but the keyboard is not the rule: a
# replayed tap must not draw `Pick whose name to change:` over zero buttons. A screen promising buttons that
# are not there is the lie 02b/E2 refused, so the tap gets the shared line and the player's own Board.
def test_a_replayed_names_button_on_a_full_table_promises_no_empty_picker():
    r, t = seated_four()

    refused = tap(r, t, HOST, "g", "names")

    assert next(e.text for e in refused if isinstance(e, table.Toast)) == table.OUTDATED
    assert any(isinstance(e, table.Board) and e.chat_id == HOST.user_id for e in refused)
    assert not [e for e in refused if isinstance(e, table.Board)
                and render.PICK_SEAT_TO_RENAME in e.text], "no Board carries the empty promise"


# S3.8 (AD6) — a seat is the whole rule, at the tap and not only at the keyboard: a member bound to the
# session but holding nothing is owed the picker they were already shown, plus the words saying what is
# missing. Both doors of the settings screen are covered — the button and the picker's own seat token.
@pytest.mark.parametrize("kind,meaning", [("g", "names"), ("n", 2)])
def test_a_member_with_no_seat_may_not_choose_whose_name_changes(kind, meaning):
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)
    version = t.version

    effects = tap(r, t, CYD, kind, meaning)

    assert set(buttons_for(effects, CYD.user_id)) == {PLAYER[2], PLAYER[3]}, "the picker they were owed"
    assert "seat" in next(e.text for e in effects if isinstance(e, table.Line)).lower()
    assert r.asked == {}, "nothing armed: a refusal that leaves a question open is a stuck chat"
    assert t.version == version and t.seat_label(2) == PLAYER[2]


# S3.9 (FR13, D7, AD13) — the draft holder is refused at the one door where the rule can still be
# discovered, with the screen he stands on coming back beside the popup: the `⏳` clause in the words is the
# same `render.entering` his Board prints, so the refusal and the screen say one thing (02b/D10).
def test_the_player_holding_their_own_win_is_refused_where_he_stands():
    r, t = seated_table()
    stage = tap(r, t, HOST, "w", 1)                          # Al is one tap from the ladder
    version = t.version

    refused = tap(r, t, HOST, "g", "names")

    toasts = [e for e in refused if isinstance(e, table.Toast)]
    assert len(toasts) == 1, "one popup, in the words the Board already uses"
    assert render.entering("Al") in toasts[0].text
    assert keyboard_for(refused, HOST.user_id) == keyboard_for(stage, HOST.user_id), "his ladder, back"
    assert HOST.user_id not in r.asked
    assert (t.version, t.seat_label(2)) == (version, PLAYER[2])


# S4.1 (FR5) — the name lands on the free seat, and the player is left where they asked. Being dropped back
# on the score after a rename would make `/settings` a place things happen *to* you rather than a screen
# you are working on (05/D9).
def test_a_typed_name_renames_the_free_seat_and_leaves_the_player_on_settings():
    r, t = seated_table()

    answer = rename(r, t, HOST, PLAYER[2], "Wifey")

    assert t.seat_label(2) == "Wifey"
    assert keyboard_for(answer, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                 "Change player names", "Back"]


# S4.2 (FR5, D9, AD24) — a rename is a write to the Table, so the two always move together: one bump, and
# every seated Board redrawn in the same breath. A bump with no fan-out leaves half the night tapping
# buttons labelled with a name that no longer exists.
def test_every_seated_board_moves_in_the_same_breath_with_one_bump():
    r, t = seated_table()
    version = t.version

    applied = rename(r, t, HOST, PLAYER[2], "Wifey")

    assert t.version == version + 1, "one change, one bump"
    assert "Wifey" in board_text(applied, HOST.user_id)
    assert "Wifey" in board_text(applied, GUEST.user_id), "Bo sees it without asking"
    assert sorted(e.chat_id for e in applied if isinstance(e, table.Board)) == sorted(t.seated_ids())


# S4.3 (FR7) — the vertical slice: one rename, three screens. `name_for` and `seats_view` are why nothing
# else had to change, and every one of these buttons still carries the seat's *index* (05/FR17), so the name
# that reads it cannot change what tapping it means.
def test_the_label_reads_on_every_button_that_used_to_say_player_n():
    r, t = seated_table()
    rename(r, t, HOST, PLAYER[2], "Wifey")
    eve = table.User(55, "Eve")

    board = r.message(HOST, "/board")
    tap(r, t, HOST, "w", 0)                                   # Al won
    fed = tap(r, t, HOST, "a", "t3")
    joined = r.message(eve, "/join " + t.code)

    winner_row = keyboard_for(board, HOST.user_id)
    who_fed_row = keyboard_for(fed, HOST.user_id)
    seat_picker = keyboard_for(joined, eve.user_id)
    for screen in (winner_row, who_fed_row, seat_picker):
        assert "Wifey" in screen, screen
        assert PLAYER[2] not in screen, "the old label is nowhere left to read"
    assert table.parse_token(buttons_for(board, HOST.user_id)["Wifey"])[3] == "2"
    assert table.parse_token(buttons_for(joined, eve.user_id)["Wifey"])[3] == "2"


# S4.4 (FR7) — the sentences too, not only the buttons: the Entry line a fresh win writes, and the money the
# night is settled with. The frozen figure is asserted beside the name because a rename that moved the money
# is the one defect this mission must not have (NFR1).
def test_the_label_is_in_the_sentences_too_a_new_entry_line_and_the_settlement():
    r, t = seated_table()
    rename(r, t, HOST, PLAYER[2], "Wifey")

    tap(r, t, HOST, "w", 2)                                   # the empty seat, by its new name, wins
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)                                   # ... and Bo fed it

    assert entry_texts(t)[-1] == "Wifey wins 3 Tai from Bo: +$1.60"
    assert t.balances == pytest.approx([0.0, -1.6, 1.6, 0.0]), "the golden rung-3 number, in the seat"
    assert "Wifey (empty)" in board_text(r.message(HOST, "/end"), HOST.user_id)


# S4.5 (FR18, AD11) — a label that already holds is not a change, which is `_write_setting`'s rule for a
# name: no bump, nobody else's message rewritten, and no keyboard gone stale to say nothing.
def test_renaming_a_seat_to_the_name_it_already_has_costs_nobody_a_call():
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    answer = r.message(HOST, PLAYER[2])

    assert t.version == version, "nothing changed, so nothing went stale"
    assert [e.chat_id for e in answer if isinstance(e, table.Board)] == [HOST.user_id]
    assert keyboard_for(answer, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                 "Change player names", "Back"]


# S4.6 (FR16) — `list(SEAT_LABELS)` in `__init__` is the whole of this requirement, and the kind of bug that
# only surfaces at 3am with two nights running: sharing one list would rename De's seat from Al's chat.
def test_two_live_tables_never_share_a_label_list():
    r, t = seated_table()
    r.message(DEB, "/new")
    other = r.table_of(DEB)
    r.tap(DEB, table.token("s", other.code, other.version, 0))     # a seat is what lets De set anything

    rename(r, t, HOST, PLAYER[2], "Wifey")

    assert other.seat_label(2) == PLAYER[2], "De's night never heard about it"
    assert t.seat_labels is not other.seat_labels


# S4.7 (FR17, NFR8) — the token-shape pin, widened to everything the rename draws. A label in callback data
# is a name Telegram would redeliver after it stopped being true, and a meaning carrying a dot would break
# `parse_token`'s four fields on the way back in.
def test_nothing_the_picker_drew_carries_a_letter_of_the_label():
    r, t = seated_table()
    t.version = 999999                                 # the longest version the code will ever hand a token
    rename(r, t, HOST, PLAYER[2], "Wifey")

    screens = [r.message(HOST, "/settings"), rename_picker(r, t, HOST), tap(r, t, HOST, "w", 0)]
    made = [tok for screen in screens for tok in tokens_of(screen)]

    assert made
    for tok in made:
        assert len(tok.encode("utf-8")) <= 64, tok
        assert "." not in table.parse_token(tok)[3], tok
    assert "Wifey" not in "".join(made), "no button carries a letter of the name"
    picked = [table.parse_token(tok)[3] for tok in made if tok.startswith("n.")]
    assert picked == ["2", "3"], "the picker's buttons name seats by index"


# S4.8 (FR8) — trimmed, and every interior run of whitespace collapsed to one space, before it lands: what
# the player meant is what the seat is called, and the row stays exactly one line (05/FR19).
def test_a_name_is_trimmed_and_its_inner_runs_collapsed_before_it_lands():
    r, t = seated_table()

    rename(r, t, HOST, PLAYER[2], "   Jon    Lee  ")

    assert t.seat_label(2) == "Jon Lee"
    assert len([ln for ln in render.board(t).splitlines()
                if ln.startswith("Player 3  Jon Lee")]) == 1, "one line, name and all (05/FR19)"


# S4.9 (01/AD21 as amended, 05/AD7) — one question per player, answered by whichever one is armed *now*. The
# rename has to displace the rate ask rather than queue behind it, or a player who moved on to naming a seat
# would have their answer read as a rate.
def test_arming_a_rename_replaces_the_rate_ask():
    r, t = seated_table()
    tap(r, t, HOST, "g", "rate")

    arm_rename(r, t, HOST, PLAYER[2])
    r.message(HOST, "0.5")

    assert t.rate == 0.1, "the tap that armed the rename ended the rate ask"
    assert t.seat_label(2) == "0.5"


# S5.1 (01/AD21 as amended) — a blank is input, not an attempt at an answer: it ends the ask and is answered
# where the player stands, exactly as a sticker is. Refusing a name nobody typed is the S6.3 defect wearing a
# different label.
def test_a_name_that_is_only_whitespace_ends_the_ask_and_the_board_answers():
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    effects = r.message(HOST, "   ")

    assert any(isinstance(e, table.Board) for e in effects), "shown where they stand"
    assert [e for e in effects if isinstance(e, table.Line)] == [], "nobody is refused for a blank"
    assert (t.version, t.seat_label(2)) == (version, PLAYER[2])
    assert r.asked == {}, "the ask is over: the next message is an ordinary one"


# S5.2 (FR8) — the length rule, reached the way a player reaches it: by typing. No test in this suite calls a
# private parser, so the breadth comes from the parameter instead (`_rate_value` is pinned the same way).
@pytest.mark.parametrize("name,accepted", [("x" * 13, False), ("x" * 12, True), ("x", True)])
def test_a_name_off_the_length_rule_costs_one_conditions_message(name, accepted):
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    answer = r.message(HOST, name)

    lines = [e.text for e in answer if isinstance(e, table.Line)]
    assert lines == ([] if accepted else [table.NAME_CONDITIONS])
    assert (t.seat_label(2) == name) == accepted
    assert (t.version == version) == (not accepted), "a refusal moves nobody's screen"


# S5.3 (FR8) — a leading `@` is how a player tags a person, not a name a seat answers to, and it is the one
# shape Telegram itself treats specially. Refused whole; the same word without it is a name.
def test_a_name_starting_with_the_at_sign_is_refused():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, "@Wifey")
    applied = r.message(HOST, "Wifey")

    assert [e.text for e in refused if isinstance(e, table.Line)] == [table.NAME_CONDITIONS]
    assert t.seat_label(2) == "Wifey", "no re-tap needed: the refusal leaves the ask armed (05/FR6)"
    assert [e for e in applied if isinstance(e, table.Line)] == []


# S5.8 (FR6, D6) — the stuck-chat rule, seen as a sequence: one message says the rules, the next message is
# the retry, and the player never has to find the button again. A rejection that dropped the ask would make
# them tap through the picker a second time for a typo.
def test_a_rejection_costs_one_message_and_one_re_type_with_no_retap():
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, "x" * 13)

    assert [e.text for e in refused if isinstance(e, table.Line)] == [table.NAME_CONDITIONS]
    assert [e for e in refused if isinstance(e, table.Board)] == [], "no screen moves with a refusal"
    assert r.asked[HOST.user_id] == table.Ask("name", 2), "the same seat is still being asked about"

    applied = r.message(HOST, "Wifey")

    assert t.seat_label(2) == "Wifey"
    assert t.version == version + 1, "the refusal cost no bump: one change, one bump in total"
    assert r.asked == {}, "and the accepted answer ends it"


# S5.4 (ERR-01, FR19) — the whole `str.splitlines()` set, not the two characters a player would name. One
# U+2028 reached a label on the tree this mission started from and split the settlement's money line in two:
# `Bo pays Wife` / `y (empty): $1.60`. The belt behind the rule is a line count on the two screens that
# produced it, because a name that adds a line to a screen is the bug nobody asked for.
@pytest.mark.parametrize("break_char", ["\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e",
                                        "\x85", "\u2028", "\u2029"])
def test_a_name_carrying_any_line_break_character_is_refused_and_no_screen_gains_a_line(break_char):
    r, t = seated_table()
    assert break_char in table.LINE_BREAKS, \
        "the test names the set `str.splitlines()` breaks on, so the code cannot quietly shrink it"
    tap(r, t, HOST, "w", 1)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 0)                              # a real Entry, so both screens have lines
    arm_rename(r, t, HOST, PLAYER[2])
    before = (len(render.board(t).splitlines()), len(render.settlement(t).splitlines()))
    version = t.version

    refused = r.message(HOST, "Wife" + break_char + "y")

    assert [e.text for e in refused if isinstance(e, table.Line)] == [table.NAME_CONDITIONS]
    assert (t.version, t.seat_label(2)) == (version, PLAYER[2]), "nothing was written"
    assert (len(render.board(t).splitlines()),
            len(render.settlement(t).splitlines())) == before, "no screen gained a line"

    assert [e.text for e in r.message(HOST, "Wifey") if isinstance(e, table.Line)] == []
    assert t.seat_label(2) == "Wifey"
    assert (len(render.board(t).splitlines()),
            len(render.settlement(t).splitlines())) == before, "and the legal name keeps it that way"


# S5.5 (FR8, ERR-12) — the words are the bot's own, read off the constants the screens are built from rather
# than retyped. A seat called `Back` beside the `Back` button teaches a player that tapping one does the
# other; and the list is matched for equality, so the case variant is refused and a longer word is not.
@pytest.mark.parametrize("word", [table.ZI_MO, table.CANCEL, table.BACK, table.KEEP_PLAYING,
                                 table.UNDO_LAST, table.RESET_SCOREBOARD, table.CLOSE_SESSION,
                                 table.CHANGE_NAMES, "Pay Rate", "Shooter", "Max Tai", "zi mo"])
def test_a_name_that_is_one_of_the_bot_s_own_words_is_refused(word):
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, word)

    assert [e.text for e in refused if isinstance(e, table.Line)] == [table.NAME_CONDITIONS]
    assert (t.seat_label(2), t.version) == (PLAYER[2], version), "the seat was never renamed"


# S5.6 (FR9, ERR-03) — a duplicate is the other three seats' labels *plus the seated players' names*, both
# casefolded after trimming; `Table.names` would over-refuse, because it holds the seatless too.
@pytest.mark.parametrize("name", ["Bo", "Player 4", "BO", "  bo  "])
def test_a_name_another_seat_or_a_seated_player_answers_to_is_a_duplicate(name):
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, name)

    assert [e.text for e in refused if isinstance(e, table.Line)] == [table.NAME_CONDITIONS]
    assert (t.seat_label(2), t.version) == (PLAYER[2], version)


# S5.6's other edge, the one ERR-03 was written for: Cy is bound to the Table and in `names`, but holds no
# seat and so appears in no row. Refusing their name would blame this player for somebody who is not at the
# Table in the only sense the Board shows.
def test_a_seatless_member_s_display_name_is_not_a_duplicate():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)                    # bound, holding nothing: in `names`, not on any row
    arm_rename(r, t, HOST, PLAYER[2])

    r.message(HOST, "Cy")

    assert t.seat_label(2) == "Cy"


# S5.7 (FR8, NFR2) — no parse mode is ever sent, so `_`, `*`, CJK and emoji are the literal words on the
# button and the row. The line count is the FR19 belt: a name is allowed to be long and strange, never taller.
# (The name is 12 characters because that is the cap FR8 sets — see S5.2; the character classes are the point.)
def test_punctuation_emoji_and_cjk_are_legal_and_render_literally():
    r, t = seated_table()
    name = "W_2 *x* 太 🎴."
    assert len(name) == table.NAME_LIMIT
    before = len(render.board(t).splitlines())
    arm_rename(r, t, HOST, PLAYER[2])

    applied = r.message(HOST, name)

    assert t.seat_label(2) == name
    boards = [e for e in applied if isinstance(e, table.Board)]
    assert sorted(b.chat_id for b in boards) == sorted(t.seated_ids())
    for board in boards:
        assert name in board.text and len(board.text.splitlines()) == before


# S5.9 (ERR-11) — the sentence that says the rules must not disagree with the code that applies them. The
# bound is interpolated from `NAME_LIMIT`, the way `CODE_LENGTH` is not restated as "six characters".
def test_the_conditions_message_states_the_cap_the_code_enforces():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, "x" * (table.NAME_LIMIT + 1))

    text = next(e.text for e in refused if isinstance(e, table.Line))
    assert "1-%d" % table.NAME_LIMIT in text, text
    for rule in ("trim", "@", "duplicate", "reserved"):
        assert rule in text.lower(), "%s is not named by %r" % (rule, text)


# S6.1 (FR12) — the ask grants nothing: freeness is read again when the answer lands, not when the seat was
# tapped. The typed name is not swallowed either — the answer is the picker, with whatever seats are still
# free on it, because a sentence alone about a seat that went missing is the refusal 02b/D9 retired.
def test_a_seat_that_filled_between_the_ask_and_the_answer_is_refused_and_the_name_is_not_swallowed():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])
    r.message(CYD, "/join " + t.code)
    r.tap(CYD, table.token("s", t.code, t.version, 2))          # Cy sits in `Player 3` mid-ask
    version = t.version

    answer = r.message(HOST, "Wifey")

    assert (t.seat_label(2), t.version) == (PLAYER[2], version), "no write, no bump"
    assert [e.text for e in answer if isinstance(e, table.Line)] == ["Player 3 is taken. Pick another seat."]
    picker = board_for(answer, HOST.user_id)
    assert picker.text.splitlines()[-1] == render.PICK_SEAT_TO_RENAME
    assert [label for label, _ in picker.rows[0]] == [PLAYER[3]], "the seat still free, still on offer"


# S6.1's harder edge, same rule: when the seat that filled was the *last* free one there is no picker to hand
# back, and ERR-05 refuses the tail line above zero seat buttons. The sentence stands alone.
def test_a_taken_seat_with_no_other_seat_free_promises_no_empty_picker():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])
    r.message(CYD, "/join " + t.code)
    r.tap(CYD, table.token("s", t.code, t.version, 2))
    r.message(DEB, "/join " + t.code)
    r.tap(DEB, table.token("s", t.code, t.version, 3))          # nothing left to name

    answer = r.message(HOST, "Wifey")

    assert [e.text for e in answer if isinstance(e, table.Line)] == ["Player 3 is taken. Pick another seat."]
    assert not [e for e in answer if isinstance(e, table.Board)
                and render.PICK_SEAT_TO_RENAME in e.text], "no tail line over zero buttons"


# S6.2 (FR12, 02/ERR-04's shape) — authority is re-read too, and the player is landed on the picker rather
# than on the score. The seat is freed by hand because no honest input can do it: every move that frees a
# seat is a command or a tap, and since 05/FR14 both end the ask (05/AD8).
def test_authority_gone_at_the_answer_lands_the_player_on_the_picker_not_on_the_score():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])
    t.occupants[0] = None                                      # Al holds no seat any more
    version = t.version

    answer = r.message(HOST, "Wifey")

    assert "seat" in next(e.text for e in answer if isinstance(e, table.Line)).lower()
    assert (t.seat_label(2), t.version) == (PLAYER[2], version)
    assert set(keyboard_for(answer, HOST.user_id)) == {PLAYER[0], PLAYER[2], PLAYER[3]}, \
        "the picker they were owed, not the score they cannot use"


# S6.3 (FR12) — the same rule seen from the other end of the night: the Table itself is gone, so the answer
# is what any message from a chat with no session is — one sentence, and no Board to write on.
def test_a_table_closed_by_another_player_mid_ask_leaves_an_ordinary_message_not_a_write():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])

    tap_end_exit(r, t, GUEST, table.CLOSE_SESSION)
    answer = r.message(HOST, "Wifey")

    assert t.seat_label(2) == PLAYER[2]
    assert "not in a session" in next(e.text for e in answer if isinstance(e, table.Line)).lower()
    assert [e for e in answer if isinstance(e, table.Board)] == [], "there is no Table left to draw"


# S6.4 (briefing) — the seat is the resource, not the ask: two players may hold a question about one free
# seat, and the seat cannot hold both answers. Last write wins, and each write fans out on its own.
def test_two_renames_of_one_seat_land_last_write_wins_with_both_fanouts():
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])
    arm_rename(r, t, GUEST, PLAYER[2])

    r.message(HOST, "Wifey")
    applied = r.message(GUEST, "Madam")

    assert t.seat_label(2) == "Madam", "the later answer wins, it does not merge or refuse"
    assert t.version == version + 2, "two writes, two bumps"
    boards = [e for e in applied if isinstance(e, table.Board)]
    assert sorted(b.chat_id for b in boards) == sorted(t.seated_ids())
    assert all("Madam" in b.text for b in boards)


# --- Task 7: the night's past, and the night's exits -----------------------------------------------
# These five are behaviour Task 1 already bought: the labels live on the Table, the Entries live in the log,
# and nothing on either side reads the other. They are pinned anyway, because "the rename did not leak into
# the ledger" is a claim about four different screens and no earlier test makes it.

def win_by_the_empty_seat(r, t):
    """One Entry booked by `Player 3` while nobody sits there, fed by Bo — the night S7 reads."""
    tap(r, t, HOST, "w", 2)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)


# S7.1 (FR11, 02/ERR-01) — both directions of the freeze: the stored sentence byte for byte what it was, and
# the Board's rows reading the new name. A rename that rewrote the ledger would re-credit a win to whoever
# holds the seat later, which is the defect 02/ERR-01 killed.
def test_a_rename_after_a_win_does_not_rewrite_that_win():
    r, t = seated_table()
    win_by_the_empty_seat(r, t)
    before = entry_texts(t)

    rename(r, t, HOST, PLAYER[2], "Wifey")

    assert before == ["Player 3 wins 3 Tai from Bo: +$1.60"]
    assert entry_texts(t) == before, "the Entry is frozen words and frozen money"
    assert "Wifey" in board_text(r.message(HOST, "/board"), HOST.user_id)


# S7.2 (FR11) — the same freeze one screen later: `/history` is the night as it happened, so it keeps the name
# the win was booked under, while the seat rows above it read the name the seat has now.
def test_history_keeps_the_old_label_while_the_board_shows_the_new_one():
    r, t = seated_table()
    win_by_the_empty_seat(r, t)
    rename(r, t, HOST, PLAYER[2], "Wifey")

    lines = board_text(r.message(HOST, "/history"), HOST.user_id).splitlines()

    assert [ln for ln in lines if " wins " in ln] == ["Player 3 wins 3 Tai from Bo: +$1.60"]
    assert any(ln.startswith("Player 3  Wifey") for ln in lines), "the seat row reads the new name"


# S7.3 (FR15) — a rename is a rule of the Table, like the rate and the shooter: wiping the slate for the next
# round wipes the money and nothing else.
def test_reset_scoreboard_keeps_the_labels_like_the_rate_and_the_shooter():
    r, t = seated_table()
    win_by_the_empty_seat(r, t)
    rename(r, t, HOST, PLAYER[2], "Wifey")

    tap_end_exit(r, t, HOST, table.RESET_SCOREBOARD)

    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.seat_labels == [PLAYER[0], PLAYER[1], "Wifey", PLAYER[3]]


# S7.4 (FR15) — leaving takes the person's name off the row and leaves the slot's own name where it is, with
# the money still in the seat they vacated (01/AD4). Two different facts, and `/leave` moves only one.
def test_leave_keeps_the_label_and_drops_the_person_s_name():
    r, t = seated_table()
    win_by_the_empty_seat(r, t)
    rename(r, t, HOST, PLAYER[2], "Wifey")
    bo_left = t.balances[1]

    r.message(GUEST, "/leave")

    board = board_text(r.message(HOST, "/board"), HOST.user_id)
    assert any(ln.startswith("Player 2  empty") for ln in board.splitlines()), board
    assert any(ln.startswith("Player 3  Wifey") for ln in board.splitlines()), "the rename survived"
    assert t.balances[1] == bo_left, "the money stays in the seat"


# S7.5 (FR15) — the other exit destroys the labels with everything else, because there is no Table left to
# own them; the farewell the chats keep is the settlement, and it reads the rename one last time.
def test_close_session_takes_the_labels_with_the_table():
    r, t = seated_table()
    win_by_the_empty_seat(r, t)
    rename(r, t, HOST, PLAYER[2], "Wifey")

    effects = tap_end_exit(r, t, HOST, table.CLOSE_SESSION)

    farewell = [e for e in effects if isinstance(e, table.Retired)]
    assert len(farewell) == len(t.members)
    assert all("Wifey" in e.text for e in farewell), "the last record of the night reads the new name"
    assert r.tables == {} and r.table_of(HOST) is None, "the code names no live Table"
    assert t.seat_labels[2] == "Wifey", "the labels went with the Table, not out of it"


# S10.1 (05/AD18) — the Board's first column is the seat's number, always. A hand-named seat is `quammenn` to
# the buttons and to the night's sentences, but the row still says which slot it is, so a renamed seat reads
# like every other row: slot, then who or what is sitting in it.
def test_the_board_row_keeps_the_seat_number_and_the_hand_name_goes_in_the_name_column():
    r, t = seated_table()

    rename(r, t, HOST, PLAYER[2], "quammenn")

    rows = [ln for ln in render.board(t).splitlines() if ln.startswith("Player ")]
    assert [ln.split("  ")[0] for ln in rows] == PLAYER, "all four slots, in seat order"
    assert rows[2].startswith("Player 3  quammenn")
    assert not rows[3].startswith("Player 4  quammenn"), "and it did not move down the Board"
    assert "quammenn" in keyboard_for(r.message(HOST, "/board"), HOST.user_id), "the button stays the name"


# S10.2 (05/AD18, D1) — a person in the seat is the row's name, exactly as an unnamed seat's is. The hand-name
# is what the *empty* seat is called, so it comes back the moment they stand up; the money stayed put the
# whole time (01/AD4), which is the only reason the row can swap names at all.
def test_a_named_seat_somebody_sits_in_reads_that_person_and_gives_the_name_back_when_they_leave():
    r, t = seated_table()
    rename(r, t, HOST, PLAYER[2], "quammenn")
    eve = table.User(55, "Eve")
    r.message(eve, "/join " + t.code)

    def seat_rows():
        return [ln for ln in render.board(t).splitlines() if ln.startswith("Player ")]

    r.tap(eve, table.token("s", t.code, t.version, 2))
    assert seat_rows()[2].startswith("Player 3  Eve")
    assert "quammenn" not in render.board(t), "the person wins the column, both names do not fit"

    r.message(eve, "/leave")
    assert seat_rows()[2].startswith("Player 3  quammenn"), "the empty seat is called that again"


# NFR3 / AS1 — the 4096-character ceiling, made a pin rather than an eye-test. Three seats at the cap — the
# fourth is the one the actor is sitting in, and a filled seat is out of scope (D1) — every visible Entry
# naming one of them, and the wide characters Telegram measures a message in. If a future change lets a label
# grow, or the Board window widen, this is the test that says the Board is what breaks.
def test_labels_at_the_cap_keep_the_board_and_the_settlement_inside_telegrams_ceiling():
    r = table.Room(rng=random.Random(7))
    r.message(HOST, "/new")
    t = r.table_of(HOST)
    r.tap(HOST, table.token("s", t.code, t.version, 0))

    for seat in t.free_seats():
        rename(r, t, HOST, PLAYER[seat], "太明白🎴🎴🎴🎴🎴🎴🎴🎴%d" % seat)
    score_wins(r, t, 5)

    assert [len(label) for label in t.seat_labels[1:]] == [table.NAME_LIMIT] * 3, "the renames landed"
    board, settled = render.board(t), render.settlement(t)
    assert t.seat_labels[1] in board and t.seat_labels[1] in settled
    assert len(board) < 4096, "Board: %d characters" % len(board)
    assert len(settled) < 4096, "settlement: %d characters" % len(settled)
