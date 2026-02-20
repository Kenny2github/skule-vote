from collections import Counter
from typing import TypedDict
from decimal import Decimal as _D
from warnings import warn

from backend.stv import STV

RON = "Reopen Nominations"

class Results(TypedDict):
    # names of elected candidates, in order of their election
    winners: list[str]
    # list of rounds
    # each round is the number of votes each candidate has in that round
    rounds: list[dict[str, _D]]
    # quota applied each round
    quota: list[_D]
    # total unexhausted votes each round
    totalVotes: list[_D]
    # number of spoiled ballots (empty from the beginning)
    spoiledBallots: int

class _Ballot(TypedDict):
    sid: str # voterID, useless here
    ranking: list[int] # index of choice in choices array

class _Choice(TypedDict):
    name: str
    statement: str # useless here

def calculate_results(
    ballots: list[_Ballot], choices: list[_Choice], numSeats: int
) -> Results:
    """
    Parameters:
        ballots: Every single ballot cast in that election
        choices: List of all candidates/options
        numSeats: Number of seats available in election

    Returns:
        Results object
    """
    stv_ballots: list[list[int]] = []
    spoiled = 0
    # sanitize ballots
    for ballot in ballots:
        if not ballot['ranking']:
            spoiled += 1
            continue
        ranking = ballot['ranking']
        if (
            # some choices out of range
            not all(choice < len(choices) for choice in ranking)
            # at least one choice selected multiple times
            or Counter(ranking).most_common(1)[0][1] > 1
        ):
            warn(f'Voter {ballot.get("sid")!r} gave invalid ranking: {ranking}')
            spoiled += 1
            continue
        stv_ballots.append(ranking)
    # find RoN
    ron = None
    for i, choice in enumerate(choices):
        if choice["name"] == RON:
            ron = i
            break
    # place RoN first (so that it wins a tie)
    if ron is not None and ron != 0:
        choices.insert(0, choices.pop(ron))
    # compute and transform results
    results = STV(
        candidates=len(choices),
        seats=numSeats,
        ballots=stv_ballots,
        ron=ron,
    ).results()
    return Results(
        winners=([choices[i]["name"] for i in results["winners"]]
                 # single-candidate elections get special no-winner treatment
                 or (['NO (TIE)'] if len(choices) == 2 and ron is not None else [])),
        rounds=[{choices[i]["name"]: count for i, count in enumerate(counts)}
                for counts, quota in results["rounds"]],
        quota=[quota for counts, quota in results["rounds"]],
        totalVotes=[sum(counts, start=_D(0)) for counts, quota in results["rounds"]],
        spoiledBallots=spoiled
    )
