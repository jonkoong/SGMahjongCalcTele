"""
The sentences the players read: the Board and everything inside it, settlement, history, help.

Button labels are not here: which tokens a screen offers is a rule, so it lives in `table.py`
(docs/flow.md, "Where it lives").
"""
import score

# How many of the night's Entries the Board shows. A night is a few dozen hands, and the Board
# must stay well inside Telegram's 4096-character limit. The rest are counted on the Board and
# listed in full by `history`.
LAST_ENTRIES = 3


def money(value):
    if value < 0:
        return "-$%.2f" % abs(value)
    if value == 0:
        return "$0.00"
    return "+$%.2f" % value


def settings(table):
    """
    What this Table pays, shown beside the money: without the rate a player cannot tell a $0.10
    win from a $0.20 one.
    """
    return "Rate $%.2f · Shooter %s · Max tai %d" % (
        table.rate, "on" if table.shooter else "off", table.tai_cap())


def board(table, tail=None):
    """
    The Board as every seated DM sees it, with the most recent Entries inside it.

    `tail` replaces the last line for someone who holds no seat: same score, different next step.
    Callers pass `seat_ask`, never a hand-written tail.
    """
    return _board(table, table.log[-LAST_ENTRIES:], tail)


def history(table):
    """
    Every Entry the night has, oldest first. The Board shows only a window because that message is
    edited for four chats on every win; this is the whole night, which the Board's
    `… N earlier — /history` cue points at.

    An empty night has no sentence of its own: the cue only appears with Entries behind it.
    """
    return _board(table, table.log)


def entering(name):
    """
    The one clause that says a win is halfway in.

    The Board's `⏳` line, the undo refusal and both `/end` refusals all quote it, so it is
    written once here to keep their words from drifting apart.
    """
    return "%s is entering a win" % name


# The last line of the Board is a prompt for the buttons below it, so each ends in a colon:
# the standing ask every draft starts from...
PICK_WINNER = "Pick who won the round:"

# ...the ask for a member who joined but holds no seat (scoring is not theirs to do)...
CHOOSE_SEAT = "Choose which player you are:"

# ...the rename picker, one button per free seat. Like CHOOSE_SEAT it outranks the `⏳` line:
# whoever drew this screen asked to rename...
PICK_SEAT_TO_RENAME = "Pick whose name to change:"

# ...and a full session, which has no buttons to promise, so it names the one verb that works.
SESSION_FULL = "Full — /leave to join another session."


def seat_ask(table):
    """
    The last line of the Board a member with **no seat** is shown.

    They cannot score, so the `⏳ … is entering a win` line is not for them; they can only take a
    seat or, if none is free, leave.
    """
    return CHOOSE_SEAT if table.free_seats() else SESSION_FULL


def _board(table, entries, tail=None):
    seats = table.seats_view()
    # Seats are counted by who is in them, not by label: an empty seat can have a label, and counting
    # labels would read `4 of 4 seated` on an empty table.
    # The code sits on the first line of the one message every seated chat keeps all night, so a
    # newcomer can be given it by reading a header aloud or screenshotting it; a code shown only at
    # `/new` is one nobody can find again at 9pm.
    lines = ["Session %s · %d of %d seated" % (table.code, len(table.seated_ids()), len(seats)),
             settings(table)]
    lines += _seat_lines(table)
    if entries:
        lines += _log_lines(table, entries)
    # The last line always names what to do next, and exactly one sentence says it: a single append
    # cannot print both or neither. The draft itself is private, but that one exists is public, so a
    # bystander need not wonder whether the night has gone idle.
    lines.append(tail if tail is not None else
                 ("⏳ " + entering(table.names[table.pending["holder"]])
                  if table.pending is not None else PICK_WINNER))
    return "\n".join(lines)


def _seat_lines(table):
    """
    One line per seat: the slot, whoever or whatever is in it, and the money sitting there.

    Column one is always the slot (`Player 1` … `Player 4`), so a renamed seat is still findable by
    number. Column two is whoever sits there, else the Table's name for the seat, else `empty`.
    Buttons and sentences use the second column (`name_for`), never the slot.
    """
    return ["%s  %-14s %s" % (slot, name or (label if label != slot else "empty"), money(value))
            for slot, label, name, value in table.seats_view()]


def settlement(table):
    """
    Who transfers what to whom: `score.settle`'s lines under the four totals.

    The totals are repeated because the Board is zeroed in the same breath, so a player reading
    `Bo pays Al: $2.80` would otherwise have nothing to check their −$3.20 against. Said before the
    slate is wiped: it is the last place the night's numbers exist.
    """
    lines = ["Session %s · settled" % table.code] + _seat_lines(table) + [""]
    lines += score.settle(table.balances, transfer_names(table)).rstrip("\n").splitlines()
    return "\n".join(lines)


def session_closed(table):
    """
    What a closed Table leaves in every member's chat: the night's numbers, with the word that the
    night is over underneath.

    Closing destroys the Table, so this is the last record of who owed whom; the money is settled
    by hand, read off this screen.
    """
    return settlement(table) + "\n\nClosed — everyone is free to /new or /join."


def transfer_names(table):
    """
    The four names `score.settle` puts in its sentences.

    Money lives in the slot, not the person, so an empty seat owes and is owed like a player.
    Passing `None` would read `None pays Di: $3.20`.
    """
    return [name or "%s (empty)" % label for _, label, name, _ in table.seats_view()]


def _log_lines(table, entries):
    """
    The night's Entries, oldest first, inside the Board message. A tap then adds nothing to the
    chat, so the Board never scrolls away under a stack of messages.

    Called only with something to show: an empty night has no words of its own.
    """
    dropped = len(table.log) - len(entries)
    lines = [""]
    if dropped:
        # The cue names the verb: a bare count would not say how to read the rest.
        lines.append("… %d earlier — /history" % dropped)
    return lines + [entry.text for entry in entries]


def entry_line(table, winner, label, payer, delta, concealed=False):
    """
    One short line per committed Entry; `label` is the words the button showed.

    A named feeder reads "from X" and a self-drawn win "on Zi Mo". A concealed win (暗, or an
    animal) has neither, so the line names no-one. An unheld seat is named by its slot.
    """
    if payer is not None:
        how = " from %s" % table.name_for(payer)
    elif not concealed:
        how = " on Zi Mo"
    else:
        how = ""
    return "%s wins %s%s: %s" % (table.name_for(winner), label, how,
                                 money(delta[winner]))
