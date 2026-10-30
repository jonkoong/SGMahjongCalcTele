"""Renaming a seat: the button, the picker, the typed name, and what a name may say."""
import random

import pytest

import render
import table
from tests.support import arm_rename, board_for, CYD, DEB, GUEST, HOST, PLAYER, board_text, \
    buttons_for, entry_texts, keyboard_for, rename, rename_picker, score_wins, seated_four, \
    seated_table, tap, tap_end_exit, tokens_of


# The fourth button is not a money rule: it rides the settings screen because that is where a
# seated player already changes the night, alone on its row so a thumb reaching for `Back` misses it.
def test_a_free_seat_brings_the_fourth_button_alone_above_back():
    r, t = seated_table()

    opened = r.message(HOST, "/settings")

    assert keyboard_for(opened, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                  "Change player names", "Back"]
    row = board_for(opened, HOST.user_id).rows[-2]
    assert len(row) == 1, "its own row — it shares nothing with the way out"


# Both directions of one rule: a full Table has no seat to rename, so the button isn't drawn, and
# the *Table's* freeness decides, so it returns on the next screen once a player stands up.
def test_a_full_table_never_draws_it_and_a_seat_freed_later_brings_it_back():
    r, t = seated_four()

    full = r.message(HOST, "/settings")
    assert keyboard_for(full, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai", "Back"]

    r.message(CYD, "/leave")
    freed = r.message(HOST, "/settings")
    assert keyboard_for(freed, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                 "Change player names", "Back"]


# The picker is the Board with free seats as buttons, one per row, `Back` last, and a line above
# saying what they are for. It edits the chat's message; a posted one would push the Board away.
def test_the_picker_names_every_free_seat_one_row_each_then_back():
    r, t = seated_table()

    picker = rename_picker(r, t, HOST)

    rows = board_for(picker, HOST.user_id).rows
    assert [[label for label, _ in row] for row in rows] == [[PLAYER[2]], [PLAYER[3]], ["Back"]]
    assert board_text(picker).splitlines()[-1] == "Pick whose name to change:"
    assert [e for e in picker if isinstance(e, table.Line)] == [], "the picker edits, it does not post"


# One level up, as with the shooter and max-tai pickers: `Back` returns to the settings menu, not the score.
def test_back_out_of_the_rename_picker_returns_the_settings_menu():
    r, t = seated_table()
    picker = rename_picker(r, t, HOST)

    effects = r.tap(HOST, buttons_for(picker, HOST.user_id)["Back"])

    assert keyboard_for(effects, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                   "Change player names", "Back"]


# A seat tap is a question and nothing else. The ask is the whole contract between tap and answer,
# and its seat is what lets the answer land there and nowhere else.
def test_tapping_a_picker_seat_asks_for_the_name_and_changes_nothing():
    r, t = seated_table()
    version = t.version

    armed = arm_rename(r, t, HOST, PLAYER[2])

    assert [e.text for e in armed if isinstance(e, table.Line)] == ["Enter the player's name:"]
    assert (t.version, t.seat_label(2)) == (version, PLAYER[2]), "a pick is a read: nothing moved"
    assert r.asked[HOST.user_id].seat == 2


# `n` is versioned, so a picker left open across someone's win is already replaced: the shared line,
# the player's own Board, and no write. Covers the real button and a longhand stale token.
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


# The button hides when no seat is free, but the keyboard is not the rule: a replayed tap must not
# draw `Pick whose name to change:` over zero buttons, so it gets the shared line and the player's Board.
def test_a_replayed_names_button_on_a_full_table_promises_no_empty_picker():
    r, t = seated_four()

    refused = tap(r, t, HOST, "g", "names")

    assert next(e.text for e in refused if isinstance(e, table.Toast)) == table.OUTDATED
    assert any(isinstance(e, table.Board) and e.chat_id == HOST.user_id for e in refused)
    assert not [e for e in refused if isinstance(e, table.Board)
                and render.PICK_SEAT_TO_RENAME in e.text], "no Board carries the empty promise"


# A seat is the whole rule, at the tap as well as the keyboard: a seatless member gets the picker
# plus the missing reason. Covers both doors: the button and the picker's own seat token.
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


# The draft holder is refused at the one door where the rule can be discovered, with their screen
# coming back beside the popup; the popup's `⏳` clause is `render.entering`, as on their Board.
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


# The name lands on the free seat and the player stays on the settings screen; dropping them back on
# the score would make `/settings` a place things happen *to* them.
def test_a_typed_name_renames_the_free_seat_and_leaves_the_player_on_settings():
    r, t = seated_table()

    answer = rename(r, t, HOST, PLAYER[2], "Wifey")

    assert t.seat_label(2) == "Wifey"
    assert keyboard_for(answer, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                 "Change player names", "Back"]


# A rename is a write: one bump and every seated Board redrawn together. A bump without fan-out
# leaves half the night tapping buttons labelled with a name that no longer exists.
def test_every_seated_board_moves_in_the_same_breath_with_one_bump():
    r, t = seated_table()
    version = t.version

    applied = rename(r, t, HOST, PLAYER[2], "Wifey")

    assert t.version == version + 1, "one change, one bump"
    assert "Wifey" in board_text(applied, HOST.user_id)
    assert "Wifey" in board_text(applied, GUEST.user_id), "Bo sees it without asking"
    assert sorted(e.chat_id for e in applied if isinstance(e, table.Board)) == sorted(t.seated_ids())


# One rename, three screens. `name_for` and `seats_view` mean nothing else changes, and every button
# still carries the seat's *index*, so the name can't change what tapping it means.
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


# The sentences too, not only the buttons: the Entry line a fresh win writes and the settlement.
# The frozen figure is asserted beside the name because a rename must never move money.
def test_the_label_is_in_the_sentences_too_a_new_entry_line_and_the_settlement():
    r, t = seated_table()
    rename(r, t, HOST, PLAYER[2], "Wifey")

    tap(r, t, HOST, "w", 2)                                   # the empty seat, by its new name, wins
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)                                   # ... and Bo fed it

    assert entry_texts(t)[-1] == "Wifey wins 3 Tai from Bo: +$1.60"
    assert t.balances == pytest.approx([0.0, -1.6, 1.6, 0.0]), "the golden rung-3 number, in the seat"
    assert "Wifey (empty)" in board_text(r.message(HOST, "/end"), HOST.user_id)


# A label that already holds is no change, as in `_write_setting`: no bump, no rewritten messages.
def test_renaming_a_seat_to_the_name_it_already_has_costs_nobody_a_call():
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    answer = r.message(HOST, PLAYER[2])

    assert t.version == version, "nothing changed, so nothing went stale"
    assert [e.chat_id for e in answer if isinstance(e, table.Board)] == [HOST.user_id]
    assert keyboard_for(answer, HOST.user_id) == ["Pay Rate", "Shooter", "Max Tai",
                                                 "Change player names", "Back"]


# `list(SEAT_LABELS)` in `__init__` is the whole requirement: sharing one list would rename De's
# seat from Al's chat once two nights run.
def test_two_live_tables_never_share_a_label_list():
    r, t = seated_table()
    r.message(DEB, "/new")
    other = r.table_of(DEB)
    r.tap(DEB, table.token("s", other.code, other.version, 0))     # a seat is what lets De set anything

    rename(r, t, HOST, PLAYER[2], "Wifey")

    assert other.seat_label(2) == PLAYER[2], "De's night never heard about it"
    assert t.seat_labels is not other.seat_labels


# The token-shape pin, widened to everything the rename draws. A label in callback data would be
# redelivered after it stopped being true, and a dot in a meaning would break `parse_token`.
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


# Trimmed, with interior whitespace runs collapsed to one space, before it lands; the row stays one line.
def test_a_name_is_trimmed_and_its_inner_runs_collapsed_before_it_lands():
    r, t = seated_table()

    rename(r, t, HOST, PLAYER[2], "   Jon    Lee  ")

    assert t.seat_label(2) == "Jon Lee"
    assert len([ln for ln in render.board(t).splitlines()
                if ln.startswith("Player 3  Jon Lee")]) == 1, "one line, name and all"


# One question per player, answered by whichever is armed *now*. The rename must displace the rate
# ask, or a player who moved on to naming a seat would have the answer read as a rate.
def test_arming_a_rename_replaces_the_rate_ask():
    r, t = seated_table()
    tap(r, t, HOST, "g", "rate")

    arm_rename(r, t, HOST, PLAYER[2])
    r.message(HOST, "0.5")

    assert t.rate == 0.1, "the tap that armed the rename ended the rate ask"
    assert t.seat_label(2) == "0.5"


# A blank is input, not an answer: it ends the ask and is answered where the player stands, as a
# sticker is. Refusing a name nobody typed would blame them for a message they never sent.
def test_a_name_that_is_only_whitespace_ends_the_ask_and_the_board_answers():
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    effects = r.message(HOST, "   ")

    assert any(isinstance(e, table.Board) for e in effects), "shown where they stand"
    assert [e for e in effects if isinstance(e, table.Line)] == [], "nobody is refused for a blank"
    assert (t.version, t.seat_label(2)) == (version, PLAYER[2])
    assert r.asked == {}, "the ask is over: the next message is an ordinary one"


# The length rule, reached by typing as a player does. No test calls a private parser, so breadth
# comes from the parameter (`_rate_value` is pinned the same way).
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


# A leading `@` tags a person and Telegram treats it specially, so it is refused whole; the same
# word without it is a name.
def test_a_name_starting_with_the_at_sign_is_refused():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, "@Wifey")
    applied = r.message(HOST, "Wifey")

    assert [e.text for e in refused if isinstance(e, table.Line)] == [table.NAME_CONDITIONS]
    assert t.seat_label(2) == "Wifey", "no re-tap needed: the refusal leaves the ask armed"
    assert [e for e in applied if isinstance(e, table.Line)] == []


# As a sequence: one message says the rules and the next is the retry, so the player never
# re-finds the button. Dropping the ask on rejection would make them re-tap the picker for a typo.
def test_a_rejection_costs_one_message_and_one_re_type_with_no_retap():
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, "x" * 13)

    assert [e.text for e in refused if isinstance(e, table.Line)] == [table.NAME_CONDITIONS]
    assert [e for e in refused if isinstance(e, table.Board)] == [], "no screen moves with a refusal"
    assert r.asked[HOST.user_id] == table.Ask("name", 2), "the same seat is still being asked about"

    r.message(HOST, "Wifey")

    assert t.seat_label(2) == "Wifey"
    assert t.version == version + 1, "the refusal cost no bump: one change, one bump in total"
    assert r.asked == {}, "and the accepted answer ends it"


# The whole `str.splitlines()` set, not the two characters a player would name. One U+2028 once
# reached a label and split the settlement's money line in two (`Bo pays Wife` / `y (empty): $1.60`).
# Backed by a line count on the two screens that produced it.
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


# The words are the bot's own, read off the screens' constants rather than retyped. A seat called
# `Back` beside the `Back` button would confuse players. Matched for equality: the case variant is
# refused, a longer word is not.
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


# A duplicate is the other seats' labels *plus the seated players' names*, casefolded after
# trimming; `Table.names` would over-refuse because it holds the seatless too.
@pytest.mark.parametrize("name", ["Bo", "Player 4", "BO", "  bo  "])
def test_a_name_another_seat_or_a_seated_player_answers_to_is_a_duplicate(name):
    r, t = seated_table()
    version = t.version
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, name)

    assert [e.text for e in refused if isinstance(e, table.Line)] == [table.NAME_CONDITIONS]
    assert (t.seat_label(2), t.version) == (PLAYER[2], version)


# The other edge: Cy is bound to the Table and in `names` but holds no seat, so appears in no row.
# Refusing Cy's name would blame this player for someone not at the Table in any sense the Board shows.
def test_a_seatless_member_s_display_name_is_not_a_duplicate():
    r, t = seated_table()
    r.message(CYD, "/join " + t.code)                    # bound, holding nothing: in `names`, not on any row
    arm_rename(r, t, HOST, PLAYER[2])

    r.message(HOST, "Cy")

    assert t.seat_label(2) == "Cy"


# No parse mode is sent, so `_`, `*`, CJK and emoji are literal words on the button and row. The
# line count guards that a name may be long and strange, never taller. (12 characters is the cap;
# the character classes are the point.)
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


# The sentence stating the rules must not disagree with the code applying them, so the bound is
# interpolated from `NAME_LIMIT`.
def test_the_conditions_message_states_the_cap_the_code_enforces():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])

    refused = r.message(HOST, "x" * (table.NAME_LIMIT + 1))

    text = next(e.text for e in refused if isinstance(e, table.Line))
    assert "1-%d" % table.NAME_LIMIT in text, text
    for rule in ("trim", "@", "duplicate", "reserved"):
        assert rule in text.lower(), "%s is not named by %r" % (rule, text)


# The ask grants nothing: freeness is read when the answer lands, not when the seat was tapped. The
# typed name isn't swallowed; the answer is the picker with the seats still free.
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


# Harder edge, same rule: when the seat that filled was the *last* free one there is no picker to
# hand back, and the tail line is never shown above zero seat buttons. The sentence stands alone.
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


# Authority is re-read too, and the player lands on the picker, not the score. The seat is freed by
# hand because no honest input can: every move that frees a seat is a command or tap, which ends the ask.
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


# The Table itself is gone, so the answer is what any message from a sessionless chat gets: one
# sentence, no Board.
def test_a_table_closed_by_another_player_mid_ask_leaves_an_ordinary_message_not_a_write():
    r, t = seated_table()
    arm_rename(r, t, HOST, PLAYER[2])

    tap_end_exit(r, t, GUEST, table.CLOSE_SESSION)
    answer = r.message(HOST, "Wifey")

    assert t.seat_label(2) == PLAYER[2]
    assert "not in a session" in next(e.text for e in answer if isinstance(e, table.Line)).lower()
    assert [e for e in answer if isinstance(e, table.Board)] == [], "there is no Table left to draw"


# The seat is the resource, not the ask: two players may hold a question about one free seat, but
# it can't hold both answers. Last write wins, and each write fans out on its own.
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


# --- the night's past, and the night's exits ---------------------------------------------------
# Labels live on the Table and Entries in the log, and neither reads the other. Pinned because "the
# rename did not leak into the log" is a claim about four screens that no earlier test makes.

def win_by_the_empty_seat(r, t):
    """One Entry booked by `Player 3` while nobody sits there, fed by Bo."""
    tap(r, t, HOST, "w", 2)
    tap(r, t, HOST, "a", "t3")
    tap(r, t, HOST, "p", 1)


# Both directions of the freeze: the stored sentence is byte-for-byte unchanged and the Board's
# rows read the new name. Rewriting the log would re-credit a win to whoever holds the seat later.
def test_a_rename_after_a_win_does_not_rewrite_that_win():
    r, t = seated_table()
    win_by_the_empty_seat(r, t)
    before = entry_texts(t)

    rename(r, t, HOST, PLAYER[2], "Wifey")

    assert before == ["Player 3 wins 3 Tai from Bo: +$1.60"]
    assert entry_texts(t) == before, "the Entry is frozen words and frozen money"
    assert "Wifey" in board_text(r.message(HOST, "/board"), HOST.user_id)


# The same freeze on `/history`: the night as it happened keeps the name the win was booked under,
# while the seat rows read the current name.
def test_history_keeps_the_old_label_while_the_board_shows_the_new_one():
    r, t = seated_table()
    win_by_the_empty_seat(r, t)
    rename(r, t, HOST, PLAYER[2], "Wifey")

    lines = board_text(r.message(HOST, "/history"), HOST.user_id).splitlines()

    assert [ln for ln in lines if " wins " in ln] == ["Player 3 wins 3 Tai from Bo: +$1.60"]
    assert any(ln.startswith("Player 3  Wifey") for ln in lines), "the seat row reads the new name"


# A rename is a Table rule like the rate and shooter: wiping the slate wipes the money and nothing else.
def test_reset_scoreboard_keeps_the_labels_like_the_rate_and_the_shooter():
    r, t = seated_table()
    win_by_the_empty_seat(r, t)
    rename(r, t, HOST, PLAYER[2], "Wifey")

    tap_end_exit(r, t, HOST, table.RESET_SCOREBOARD)

    assert t.balances == [0.0, 0.0, 0.0, 0.0]
    assert t.seat_labels == [PLAYER[0], PLAYER[1], "Wifey", PLAYER[3]]


# Leaving takes the person's name off the row but leaves the slot's own name and the money in the
# vacated seat; `/leave` moves only the first.
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


# The other exit destroys the labels with the Table; the farewell the chats keep is the settlement,
# which reads the rename one last time.
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


# The Board's first column is always the seat's number. A hand-named seat is `quammenn` to buttons
# and sentences, but its row still reads slot first, then who or what is in it.
def test_the_board_row_keeps_the_seat_number_and_the_hand_name_goes_in_the_name_column():
    r, t = seated_table()

    rename(r, t, HOST, PLAYER[2], "quammenn")

    rows = [ln for ln in render.board(t).splitlines() if ln.startswith("Player ")]
    assert [ln.split("  ")[0] for ln in rows] == PLAYER, "all four slots, in seat order"
    assert rows[2].startswith("Player 3  quammenn")
    assert not rows[3].startswith("Player 4  quammenn"), "and it did not move down the Board"
    assert "quammenn" in keyboard_for(r.message(HOST, "/board"), HOST.user_id), "the button stays the name"


# A person in the seat is the row's name, as with an unnamed seat. The hand-name is what the
# *empty* seat is called, so it returns when they stand up; the money stays put throughout.
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


# The 4096-character ceiling as a pin: three seats at the name cap (the fourth is the actor's),
# every visible Entry naming one, in the wide characters Telegram measures. If a label or the
# Board window grows, this is where the Board breaks.
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
