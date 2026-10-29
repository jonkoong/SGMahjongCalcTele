"""The frozen payout contract. Numbers come from util.py at 145b24b —
see tests/golden_payouts.json."""
import json
from pathlib import Path

import pytest

import score

GOLDEN = json.loads((Path(__file__).parent / "golden_payouts.json").read_text())


def check(kind, case):
    got = score.amount_delta(
        kind,
        case["winner"],
        case["payer"],
        ntai=case.get("ntai"),
        rate=case["rate"],
        shooter=case["shooter"],
    )
    assert got == case["after"]


# S1.16
@pytest.mark.parametrize("case", GOLDEN["tai"], ids=lambda c: str(c)[:40])
def test_tai_delta_matches_golden_fixture(case):
    check("tai", case)


# A concealed win never asks for a payer, so blind + named payer is not tappable.
def unreachable(case):
    return case["blind"] and case["payer"] is not None


# S1.16
@pytest.mark.parametrize("case", GOLDEN["kang"], ids=lambda c: str(c)[:40])
def test_kang_delta_matches_golden_fixture(case):
    if unreachable(case):
        pytest.skip("the 暗 button has no payer stage")
    check("kang_an" if case["blind"] else "kang", case)


# S1.16 — animal and flower share one kernel, exactly as the old pay_flower did.
@pytest.mark.parametrize("case", GOLDEN["flower"], ids=lambda c: str(c)[:40])
def test_flower_delta_matches_golden_fixture(case):
    if unreachable(case):
        pytest.skip("the 暗 button has no payer stage")
    check("flower_an" if case["blind"] else "flower", case)
    if case["payer"] is not None:
        pytest.skip("an animal win has no payer to charge")
    check("animal_an" if case["blind"] else "animal", case)


# S1.16
@pytest.mark.parametrize("night", GOLDEN["sequences"], ids=lambda n: str(n)[:40])
def test_night_sequence_balances_match_golden_fixture(night):
    banks = [0.0, 0.0, 0.0, 0.0]
    taps = [
        ("tai", 3, 0, 1),
        ("tai", 1, 3, None),
        ("tai", 5, 1, 2),
        ("kang", None, 2, 0),
        ("animal_an", None, 3, None),
        ("tai", 2, 1, 0),
    ]
    for step, (kind, ntai, winner, payer) in enumerate(taps):
        banks = [b + d for b, d in zip(banks, score.amount_delta(
            kind, winner, payer, ntai=ntai, rate=night["rate"], shooter=night["shooter"]))]
        assert banks == night["steps"][step]


# S1.16
@pytest.mark.parametrize("case", GOLDEN["settlement"], ids=lambda c: str(c)[:40])
def test_settlement_lines_match_golden_fixture(case):
    assert score.settle(case["balances"], case["names"]) == case["text"]


# S1.11
def test_wind_choice_does_not_change_numbers():
    east = score.amount_delta("tai", 0, 1, ntai=4, rate=0.1, shooter=True)
    north = score.amount_delta("tai", 3, 2, ntai=4, rate=0.1, shooter=True)
    assert north == list(reversed(east))

    drawn = score.amount_delta("tai", 0, None, ntai=2, rate=0.2, shooter=False)
    from_the_back = score.amount_delta("tai", 3, None, ntai=2, rate=0.2, shooter=False)
    assert from_the_back == list(reversed(drawn))
