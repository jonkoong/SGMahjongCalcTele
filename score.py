"""Payout math. The numbers are a frozen contract — see tests/golden_payouts.json.

Both seats, money, and settings are plain values; nothing here knows about Telegram.
"""

TAI_LADDER = [0, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]
MAX_TAI = len(TAI_LADDER) - 1     # the highest rung that exists — nothing above it can be paid

ZERO = [0.0, 0.0, 0.0, 0.0]   # a wind slot nobody is sitting at still holds a balance


def _tai(ntai, winner, payer, rate, shooter):
    factor = [0.0, 0.0, 0.0, 0.0]
    if payer is None:  # Zi Mo — nobody fed the tile, all three pay
        factor = [-0.5, -0.5, -0.5, -0.5]
        factor[winner] = 1.5
    elif shooter:
        factor[winner] = 1.0
        factor[payer] = -1.0
    else:
        factor = [-0.25, -0.25, -0.25, -0.25]
        factor[winner] = 1.0
        factor[payer] = -0.5
    amount = rate * TAI_LADDER[ntai]
    return [amount * f for f in factor]


def _kang(winner, payer, blind, rate, shooter):
    factor = list(ZERO)
    if shooter:
        if not blind and payer is not None:
            factor[winner] = 3.0
            factor[payer] = -3.0
        elif not blind:
            factor = [-1.0, -1.0, -1.0, -1.0]
            factor[winner] = 3.0
        elif blind:
            factor = [-2.0, -2.0, -2.0, -2.0]
            factor[winner] = 6.0
    else:
        # Known quirk: with Shooter off, a named payer is ignored and all three pay.
        if not blind and payer is not None:
            factor = [-1.0, -1.0, -1.0, -1.0]
            factor[winner] = 3.0
        elif not blind:
            factor = [-2.0, -2.0, -2.0, -2.0]
            factor[winner] = 6.0
        elif blind:
            factor = [-4.0, -4.0, -4.0, -4.0]
            factor[winner] = 12.0
    return [rate * f for f in factor]


def _flower(winner, payer, blind, rate, shooter):
    factor = list(ZERO)
    if shooter:
        if not blind and payer is not None:
            factor[winner] = 1.0
            factor[payer] = -1.0
        elif not blind:
            factor = [-1.0, -1.0, -1.0, -1.0]
            factor[winner] = 3.0
        elif blind:
            factor = [-2.0, -2.0, -2.0, -2.0]
            factor[winner] = 6.0
    else:
        # Known quirk: with Shooter off, an animal or flower cannot be charged to one player.
        if not blind and payer is None:
            factor = [-1.0, -1.0, -1.0, -1.0]
            factor[winner] = 3.0
        elif blind:
            factor = [-2.0, -2.0, -2.0, -2.0]
            factor[winner] = 6.0
    return [rate * f for f in factor]


# kind -> (kernel, concealed, has a payer stage). A concealed win and an animal never ask.
AMOUNTS = {
    "tai": (_tai, False, True),
    "kang": (_kang, False, True),
    "kang_an": (_kang, True, False),
    "animal": (_flower, False, False),
    "animal_an": (_flower, True, False),
    "flower": (_flower, False, True),
    "flower_an": (_flower, True, False),
}


def has_payer_stage(kind):
    return AMOUNTS[kind][2]


def amount_delta(kind, winner, payer, *, ntai=None, rate, shooter):
    kernel, blind, asks_payer = AMOUNTS[kind]
    if kernel is _tai:
        return kernel(ntai, winner, payer if asks_payer else None, rate, shooter)
    return kernel(winner, payer if asks_payer else None, blind, rate, shooter)


def settle(balances, names):
    """Who pays whom, in the order the old howtopay printed. Zero-sum by construction."""
    owed = [(name, value) for name, value in zip(names, balances) if value != 0]
    losers = [value for value in balances if value < 0]
    if not owed:
        return "No Payment"

    if len(losers) == 1:
        payer = names[next(i for i, v in enumerate(balances) if v < 0)]
        deals = [(payer, name, abs(value)) for name, value in owed if value > 0]
    elif len(losers) == 2 and len(owed) == 4:
        biggest_first = sorted(owed, key=lambda pair: pair[1], reverse=True)
        deals = _two_and_two(biggest_first)
    else:
        payee = names[next(i for i, v in enumerate(balances) if v > 0)]
        deals = [(name, payee, abs(value)) for name, value in owed if value < 0]
    return "".join("%s pays %s: $%.2f\n" % deal for deal in deals)


def _two_and_two(paid):
    """Two winners and two losers: settle the biggest loser first, then mop up."""
    top_name, top = paid[0]
    second_name, second = paid[1]
    other_loser, small_lose = paid[2]
    biggest_loser, big_lose = paid[3]
    top_win, big_loss, small_win = abs(top), abs(big_lose), abs(small_lose)

    if big_loss >= top_win:
        deals = [(biggest_loser, top_name, top_win)]
        if big_loss - top_win:
            deals.append((biggest_loser, second_name, big_loss - top_win))
        deals.append((other_loser, second_name, small_win))
        return deals
    return [
        (biggest_loser, top_name, big_loss),
        (other_loser, top_name, top_win - big_loss),
        (other_loser, second_name, second),
    ]
