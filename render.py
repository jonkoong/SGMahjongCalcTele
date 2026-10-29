"""Text the players read. The Board and everything inside it, settlement, help."""
import score

# How many of the night's Entries the Board keeps visible. A real night is a few dozen hands,
# and the Board has to stay well inside Telegram's 4096-character message (AS5). What it stops
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
    What this Table pays, read out where its money is read out (FR13). A balance on its own is not
    evidence: without the rate a player cannot tell a $0.10 win from a $0.20 one, and the old bot
    printed these three numbers into the chat for exactly that reason.
    """
    return "Rate $%.2f · Shooter %s · Max tai %d" % (
        table.rate, "on" if table.shooter else "off", table.tai_cap())


def board(table):
    """The Board as every seated DM sees it, with the most recent Entries inside it (FR14)."""
    return _board(table, table.log[-LAST_ENTRIES:])


def history(table):
    """
    Every Entry the night has, oldest first (FR17). The Board window exists because that message is
    edited for four chats on every win and must stay a glance; this is the whole night behind it, and
    what the Board's `… N earlier — /history` cue points at.
    """
    return _board(table, table.log, when_empty="No wins yet.")


def _board(table, entries, when_empty=None):
    seats = table.seats_view()
    seated = sum(1 for seat in seats if seat[1] is not None)
    lines = ["Table %s — %d of %d seated" % (table.code, seated, len(seats)), settings(table)]
    lines += _seat_lines(table)
    if table.pending is not None:
        # The draft itself is private, but that one exists is public (FR9): a bystander should not
        # have to wonder whether the table has gone idle.
        lines.append("⏳ %s is entering a win" % table.names[table.pending["holder"]])
    lines += _log_lines(table, entries) if entries else (["", when_empty] if when_empty else [])
    return "\n".join(lines)


def _seat_lines(table):
    """One line per wind: label, whoever holds it, and the money sitting there (AD4)."""
    return ["%s  %-14s %s" % (label, name or "empty", money(value))
            for label, name, value in table.seats_view()]


def settlement(table):
    """
    Who transfers what to whom (FR19) — `score.settle`'s own lines, in the order the 2022 `howtopay`
    chose them, with the four totals repeated above them.

    The repetition is the point: `/end` zeroes the Board in the same breath, so a player reading
    `Bo pays Al: $2.80` would otherwise have nothing to check its −$3.20 against. The 2022 bot kept the
    two halves apart (`ompm()` on `/play`, `howtopay()` on `/end`) because its Board never forgot the
    totals; this one does.

    Said *before* the slate is wiped — this is the last place the night's numbers exist.
    """
    lines = ["Table %s — settled" % table.code] + _seat_lines(table) + [""]
    lines += score.settle(table.balances, transfer_names(table)).rstrip("\n").splitlines()
    return "\n".join(lines)


def transfer_names(table):
    """
    The four names the frozen kernel puts in its sentences.

    A vacant wind is not nobody. Money lives in the slot and not the person (AD4), so an empty seat
    owes and is owed exactly like a player — it just has no one to say, and the Board already calls that
    row `empty`. Handing the kernel `None` instead would read `None pays Di: $3.20`.
    """
    return [name or "%s (empty)" % label for label, name, _ in table.seats_view()]


def _log_lines(table, entries):
    """
    The night's Entries, oldest first, read out inside the Board message. That is what keeps the
    Board in front of the player scoring the next win: a tap then adds nothing to the chat, so the
    Board never climbs away under a stack of messages (FR14, amended 2026-10-29).

    Called only with something to show — an empty window is an empty Board, and only `history` has
    anything to say about having nothing to say.
    """
    dropped = len(table.log) - len(entries)
    lines = [""]
    if dropped:
        # The cue names the verb, because a bare count tells the player the night is longer without
        # saying how to read it (FR17).
        lines.append("… %d earlier — /history" % dropped)
    return lines + entries


def entry_line(table, winner, label, payer, delta, concealed=False):
    """
    One short line per committed Entry — `label` is the same words the button showed.

    A named feeder reads "from X" and a self-drawn win reads "on Zi Mo". A concealed win (暗, or an
    animal) is neither: nobody fed it and nobody drew it, so the line names no-one.
    """
    if payer is not None:
        how = " from %s" % table.occupant_name(payer)
    elif not concealed:
        how = " on Zi Mo"
    else:
        how = ""
    return "%s wins %s%s: %s" % (table.occupant_name(winner), label, how,
                                 money(delta[winner]))
