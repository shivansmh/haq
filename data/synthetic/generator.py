from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticScenario:
    name: str
    csv_text: str
    expected_candidate_count: int


def build_scenarios() -> list[SyntheticScenario]:
    header = "Date,Narration,Debit,Credit,Balance,Reference\n"
    reference = "123456" + "789012"
    return [
        SyntheticScenario(
            "upi-reversed-t1",
            header + f"03/11/2026,UPI payment to shop,2000,,8000,{reference}\n"
            + f"04/11/2026,UPI reversal shop, ,2000,10000,{reference}\n",
            0,
        ),
        SyntheticScenario(
            "upi-never-reversed",
            header + f"03/11/2026,UPI payment to shop,2000,,8000,{reference}\n",
            1,
        ),
        SyntheticScenario(
            "atm-no-cash",
            header + "05/11/2026,ATM cash withdrawal,5000,,5000,\n",
            1,
        ),
        SyntheticScenario(
            "salary-credit-not-reversal",
            header + "06/11/2026,SALARY CREDIT,,,,15000,\n".replace(",,,,", ",,,"),
            0,
        ),
    ]


def render_scenario(scenario: SyntheticScenario) -> str:
    return scenario.csv_text
