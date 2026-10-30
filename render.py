"""
The sentences the players read. The Board and everything inside it, settlement, history, help.

Button labels are not here: a button is a `kind.code.version.meaning` token, and which tokens a screen
offers is a rule, so that lives with the rules in `table.py` (docs/flow.md § 10).
"""
import score

# How to read the ids below: a bare FR/AD/AS names mission `01-pooled-table`; `02/…` marks the
# `02-uiux-overhaul` fact that owns the line, and ERR-nn is that mission's scrutiny list.

# How many of the night's Entries the Board keeps visible. A real night is a few dozen hands,
# and the Board has to stay well inside Telegram's 4096-character message (01/AS5). What it stops
# showing is counted on the Board and listed in full by `history` below.
LAST_ENTRIES = 3


def money(value):
    if value < 0:
        return "-$%.2f" % abs(value)
    if value == 0:
        return "$0.00"
    return "+$%.2f" % value


def settings(table):
    """
    What this Table pays, read out where its money is read out (01/FR13). A balance on its own is not
    evidence: without the rate a player cannot tell a $0.10 win from a $0.20 one, and the old bot
    printed these three numbers into the chat for exactly that reason.
    """
    return "Rate $%.2f · Shooter %s · Max tai %d" % (
        table.rate, "on" if table.shooter else "off", table.tai_cap())


def board(table, tail=None):
    """
    The Board as every seated DM sees it, with the most recent Entries inside it (01/FR14).

    `tail` replaces the last line for a Board shown to someone who does not hold a seat — the same score,
    a different thing to do next (02b/E1). Callers use `seat_ask`; nobody hand-writes a tail.
    """
    return _board(table, table.log[-LAST_ENTRIES:], tail)


def history(table):
    """
    Every Entry the night has, oldest first (01/FR17). The Board window exists because that message is
    edited for four chats on every win and must stay a glance; this is the whole night behind it, and
    what the Board's `… N earlier — /history` cue points at.

    An empty night gets no sentence of its own (02b/D1): the cue only ever appears with Entries behind it,
    so a night with nothing in it has nothing to point at and nothing to say about it.
    """
    return _board(table, table.log)


def entering(name):
    """
    The one clause that says a win is halfway in (01/FR9).

    Three sentences quote it: the Board's `⏳` line, the undo refusal, and the refusal both `/end` exits
    give a bystander. They describe the same fact, so they say it with one set of words — written once
    here, in the file that owns the words players read. The tap-side sentence that restated it by hand
    ("… is entering *that* win") is gone: a fourth sentence in its own words is how this clause drifted
    once already, and 02b/D9 left the guard without any words at all.
    """
    return "%s is entering a win" % name


# The Board's standing ask (02b/D2) — the line every draft is started from. Named because the words are the
# whole of it: it is the one place a player is told what the buttons under the score are for, and the popup
# that used to repeat it is gone (02b/D9), so a colon dropped here would have nowhere else to be caught.
PICK_WINNER = "Pick who won the round:"

# The other thing the last line can be asked to do (02b/E1, Jon 2026-10-30): a member who joined a session
# and holds no seat is offered seat buttons, and `Pick who won the round:` over those buttons asks them to
# score a night they are not standing in. Same colon for the same reason — the buttons below are the list.
CHOOSE_SEAT = "Choose which player you are:"

# …and when the session is full there is nothing to choose, so the line points at the one verb that works
# instead of promising buttons that are not there (02b/E2).
SESSION_FULL = "Full — /leave to join another session."


def seat_ask(table):
    """
    The last line of the Board a member with **no seat** is shown.

    They cannot score, so the `⏳ … is entering a win` line is not their news; the one thing they can do is
    take a seat, and if none is free, leave. Both facts fit in one line because that is all the room the
    tail has.
    """
    return CHOOSE_SEAT if table.free_seats() else SESSION_FULL


def _board(table, entries, tail=None):
    seats = table.seats_view()
    # 02/FR17 (ERR-03) — the header counts seats by who is in them, never by how they are labelled: once an
    # empty seat has a label of its own, counting labels would read `4 of 4 seated` on an empty table.
    # The code holds the first line, in the one message that lives in every seated chat for the whole
    # night — not a requirement (02/FR13 fixes six characters and one deal, not visibility): Jon reverted
    # the hiding rule, 2026-10-30. It is how a newcomer gets in: a seated player
    # reads their own header aloud, or screenshots it, and the four of them are done. Nowhere else would
    # do — a code that only appears once, at `/new`, is one nobody can find again at 9pm.
    lines = ["Session %s · %d of %d seated" % (table.code, len(table.seated_ids()), len(seats)),
             settings(table)]
    lines += _seat_lines(table)
    if entries:
        lines += _log_lines(table, entries)
    # The last line always names what to do next, and exactly one of these says it (02b/D2, 02b/D3).
    # One `if`/`else` and one append, always last in the message: two appends is the shape that could print
    # both sentences or neither. The draft itself is private, but that one exists is public (01/FR9) — a
    # bystander should not have to wonder whether the night has gone idle.
    lines.append(tail if tail is not None else
                 ("⏳ " + entering(table.names[table.pending["holder"]])
                  if table.pending is not None else PICK_WINNER))
    return "\n".join(lines)


def _seat_lines(table):
    """One line per seat: its label, whoever holds it or `empty`, and the money sitting there (01/AD4)."""
    return ["%s  %-14s %s" % (label, name or "empty", money(value))
            for label, name, value in table.seats_view()]


def settlement(table):
    """
    Who transfers what to whom (01/FR19) — `score.settle`'s own lines, in the order the 2022 `howtopay`
    chose them, with the four totals repeated above them.

    The repetition is the point: `Reset scoreboard` zeroes the Board in the same breath, so a player
    reading `Bo pays Al: $2.80` would otherwise have nothing to check its −$3.20 against. The 2022 bot kept
    the two halves apart (`ompm()` on `/play`, `howtopay()` on `/end`) because its Board never forgot the
    totals; this one does.

    Said *before* the slate is wiped — this is the last place the night's numbers exist.
    """
    lines = ["Session %s · settled" % table.code] + _seat_lines(table) + [""]
    lines += score.settle(table.balances, transfer_names(table)).rstrip("\n").splitlines()
    return "\n".join(lines)


def session_closed(table):
    """
    What a closed Table leaves in every member's chat (04/D6): the night's numbers, still readable, with
    the word that the night is over underneath them.

    The Table is destroyed by the act that prints this, so these lines are the last record of who owed whom
    that anybody will ever have — the money is settled by hand, off the bot, and it is read off this screen.
    A notice in place of the numbers would destroy the debt in order to announce it.
    """
    return settlement(table) + "\n\nClosed — everyone is free to /new or /join."


def transfer_names(table):
    """
    The four names the frozen kernel puts in its sentences.

    An empty seat is not nobody. Money lives in the slot and not the person (01/AD4), so an empty seat
    owes and is owed exactly like a player — it just has no one to say, and the Board already calls that
    row `empty`. Handing the kernel `None` instead would read `None pays Di: $3.20`.
    """
    return [name or "%s (empty)" % label for label, name, _ in table.seats_view()]


def _log_lines(table, entries):
    """
    The night's Entries, oldest first, read out inside the Board message. That is what keeps the
    Board in front of the player scoring the next win: a tap then adds nothing to the chat, so the
    Board never climbs away under a stack of messages (01/FR14, amended 2026-10-29).

    Called only with something to show: an empty window is an empty Board, and an empty night has no
    words of its own (02b/D1).
    """
    dropped = len(table.log) - len(entries)
    lines = [""]
    if dropped:
        # The cue names the verb, because a bare count tells the player the night is longer without
        # saying how to read it (01/FR17).
        lines.append("… %d earlier — /history" % dropped)
    return lines + [entry.text for entry in entries]


def entry_line(table, winner, label, payer, delta, concealed=False):
    """
    One short line per committed Entry — `label` is the same words the button showed.

    A named feeder reads "from X" and a self-drawn win reads "on Zi Mo". A concealed win (暗, or an
    animal) is neither: nobody fed it and nobody drew it, so the line names no-one. A seat nobody holds
    is named by its slot, so an empty seat wins and pays in its own name (02/FR5).
    """
    if payer is not None:
        how = " from %s" % table.name_for(payer)
    elif not concealed:
        how = " on Zi Mo"
    else:
        how = ""
    return "%s wins %s%s: %s" % (table.name_for(winner), label, how,
                                 money(delta[winner]))
