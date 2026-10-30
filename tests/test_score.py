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


# S1.16
@pytest.mark.parametrize("case", GOLDEN["kang"], ids=lambda c: str(c)[:40])
def test_kang_delta_matches_golden_fixture(case):
    check("kang_an" if case["blind"] else "kang", case)


# S1.16, S3.3 — animal and flower share one kernel, exactly as the old pay_flower did, and they still
# pay the same. Every row is checked against both buttons: a player tapping 🥀 or 🐈 has to get the
# same money whichever word the bot writes, and that is the whole of FR1.
@pytest.mark.parametrize("case", GOLDEN["flower"], ids=lambda c: str(c)[:40])
def test_flower_delta_matches_golden_fixture(case):
    check("flower_an" if case["blind"] else "flower", case)
    check("animal_an" if case["blind"] else "animal", case)


# S3.11 (FR16) — a payout row no keyboard can reach is not a contract, it is a row that gets skipped,
# and a skipped payout row is a number nobody checked. The reachability rule is asserted here instead
# of deciding what to skip, so a row that drifts back into the file reddens the suite instead of
# quietly disappearing from it.
def test_the_fixture_holds_only_rows_a_keyboard_can_reach():
    for case in GOLDEN["flower"]:
        assert case["payer"] is None, "🥀 asks nobody, so a named feeder is not a tap anybody can make"
    for case in GOLDEN["kang"]:
        assert not (case["blind"] and case["payer"] is not None), "Kang 暗 asks nobody either"


# S3.9, S3.11 — the 48 rows this prunes are the ones Kang plays with Shooter off and a feeder named:
# reachable, and the only thing that pins the quirk FR15 leaves standing. Deleting the unreachable
# rows must not take these with them.
def test_the_reachable_kang_rows_survived_the_prune():
    named_off = [case for case in GOLDEN["kang"]
                 if not case["blind"] and not case["shooter"] and case["payer"] is not None]

    assert len(named_off) == 48
    assert all(score.amount_delta("kang", case["winner"], case["payer"], ntai=None, rate=case["rate"],
                                 shooter=False)[case["winner"]] == case["after"][case["winner"]]
               for case in named_off)


# S1.16 — the night sequence is replayed through real taps in tests/test_ledger.py (S1.1): that is how
# a player produces those balances, and the steps are still the frozen numbers. The kernel is covered by
# every row above, so the chain is not pinned twice.


# S1.16
@pytest.mark.parametrize("case", GOLDEN["settlement"], ids=lambda c: str(c)[:40])
def test_settlement_lines_match_golden_fixture(case):
    assert score.settle(case["balances"], case["names"]) == case["text"]


# S3.4 (02/FR2) — the predicate that decides whether a win asks who fed it, checked at its own boundary.
# Only 🥀's flag moved: Kang asks in both Shooter states, and a shooter argument here would give the
# question two owners that could disagree about Kang by construction (ERR-02, 02/AD7).
def test_only_tai_and_kang_ask_who_fed_the_tile():
    assert not score.has_payer_stage("flower")
    assert not score.has_payer_stage("animal")
    assert not score.has_payer_stage("flower_an")
    assert not score.has_payer_stage("animal_an")
    assert not score.has_payer_stage("kang_an")
    assert score.has_payer_stage("tai")
    assert score.has_payer_stage("kang")


# S3.9 (FR15) — Kang on Zi Mo pays exactly twice what Kang off a named feeder pays, with Shooter off.
# The brief almost had this behaviour deleted; the rows above are what says it must stay.
def test_kang_on_zi_mo_pays_double_a_named_feeder_with_shooter_off():
    named = score.amount_delta("kang", 0, 1, ntai=None, rate=0.1, shooter=False)
    drawn = score.amount_delta("kang", 0, None, ntai=None, rate=0.1, shooter=False)

    assert named == pytest.approx([0.3, -0.1, -0.1, -0.1])
    assert drawn == pytest.approx([0.6, -0.2, -0.2, -0.2])


# S1.11
def test_which_seat_wins_does_not_change_the_numbers():
    first = score.amount_delta("tai", 0, 1, ntai=4, rate=0.1, shooter=True)
    last = score.amount_delta("tai", 3, 2, ntai=4, rate=0.1, shooter=True)
    assert last == list(reversed(first))

    drawn = score.amount_delta("tai", 0, None, ntai=2, rate=0.2, shooter=False)
    from_the_back = score.amount_delta("tai", 3, None, ntai=2, rate=0.2, shooter=False)
    assert from_the_back == list(reversed(drawn))
