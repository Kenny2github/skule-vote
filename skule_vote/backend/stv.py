"""
EngSoc-style STV implementation.

## Usage
These use cases are all basically the same, but are separated here for convenience.

### Referendum/confidence voting
```python
results = STV(candidates=2, seats=1, ballots=ballots, ron=1).results()
```

### Single-seat election
```python
results = STV(candidates=n, seats=1, ballots=ballots, ron=n-1).results()
```

### Multi-seat election
```python
results = STV(candidates=n, seats=m, ballots=ballots, ron=n-1).results()
```

### Non-EngSoc-style STV (no RoN)
```python
results = STV(candidates=n, seats=m, ballots=ballots, ron=None).results()
```

### Old method of EngSoc-style STV (fixed quota)
```python
results = STV(candidates=n, seats=m, ballots=ballots, ron=n-1, old=True).results()
```

## License
Copyright (c) 2026 Ken Hilton <ken@skule.ca>. MIT Licensed.
"""
from __future__ import annotations
from collections.abc import Iterator
from typing import TypedDict
from decimal import Decimal as _D

class Results(TypedDict):
    # elected candidate IDs, in order of their election
    winners: list[int]
    # list of rounds
    # each round is the number of votes each candidate has in that round,
    # and the quota applied that round
    rounds: list[tuple[list[_D], _D]]

class STV:

    winners: list[int]

    def __init__(
        self, *,
        candidates: int,
        seats: int,
        ballots: list[list[int]],
        ron: int | None,
        old: bool = False
    ) -> None:
        """
        Arguments:
            candidates: Number of candidates in this election
            seats: Number of seats available
            ron: Candidate ID (in [0, candidates)) representing the
                "Reopen Nominations" candidate, or None if not applicable
            ballots: List of ballots. Each ballot is a list of candidate IDs
                (in [0, candidates)), in order of first to last preference.
            old: If True (default False), use the old system where quota is
                fixed instead of updating each round.
        """
        self.candidates = candidates
        self.seats = seats
        self.ron = ron
        self.ballots = ballots
        self.old = old

    def __iter__(self) -> Iterator[tuple[list[_D], _D]]:
        # elected candidates, in order of their election
        elected: list[int] = []
        # candidates still in the running
        # elected/eliminated candidates are removed from this set
        candidates: set[int] = set(range(self.candidates))
        # current index into each ballot's preferences
        # incremented when preference is eliminated/elected
        current_pref = [0] * len(self.ballots)
        # current value of each ballot
        # normally 1; reduced during fractional transfer
        # from elected candidate
        values = [_D(1)] * len(self.ballots)
        # vote counts for each candidate in the current round
        counts = [_D(0)] * self.candidates
        # initialize counts based on first preferences
        for (candidate, *_) in self.ballots:
            counts[candidate] += 1
        if self.old:
            # under the "old" system, quota is fixed at the beginning
            # and election requires *at least* this many votes
            quota = int(_D(len(self.ballots)) / (self.seats + 1)) + _D(1)
        else:
            # under the "new" system, quota is updated every round
            # and election requires *more than* this many votes
            quota = _D(sum(counts)) / (self.seats + 1)
        # count history for tiebreaking
        history = []

        # RoN cannot be eliminated, so don't count it when checking
        # if we're out of candidates (or have finished electing them)
        # if self.ron is None, it will be silently ignored
        while (candidates - {self.ron}) and len(elected) < self.seats:
            # track this round in history
            history.append(counts[:])
            # update quota in the "new" system
            if not self.old:
                quota = _D(sum(counts)) / (self.seats + 1)
            # surface last round's information
            yield counts[:], quota
            # find candidate (still in the running) with most votes this round
            candidate = max(
                # unlike elimination, this includes RoN
                candidates,
                # look backwards into previous rounds to break ties
                key=lambda i: [entry[i] for entry in reversed(history)]
            )
            # met-quota rules are different under "old" and "new" systems
            met_quota = (counts[candidate] >= quota) if self.old else (counts[candidate] > quota)
            if met_quota:
                elected.append(candidate)
                candidates.remove(candidate)
                # Gregory method
                ratio = 1 - quota/counts[candidate]
                for i, ballot in enumerate(self.ballots):
                    # skip exhausted ballots to avoid IndexError
                    if values[i] == 0:
                        continue
                    # for each vote for this candidate this round,
                    if ballot[current_pref[i]] == candidate:
                        # skip that ballot's preference to the next
                        # un-elected/eliminated choice,
                        while current_pref[i] < len(ballot) and ballot[current_pref[i]] not in candidates:
                            current_pref[i] += 1
                        # reduce value of this ballot using Gregory method,
                        values[i] *= ratio
                        # if the ballot is not exhausted,
                        if current_pref[i] < len(ballot):
                            # transfer new value to next preference
                            counts[ballot[current_pref[i]]] += values[i]
                        else:
                            # exhausted ballots get a value of 0
                            values[i] = _D(0)
                # "collapse" the elected candidate's vote total to exactly
                # quota, to maintain the overall vote count
                counts[candidate] = quota
                # if the winning candidate was RoN, election ends here
                if candidate == self.ron:
                    break
            else: # nobody won, eliminate least-voted candidate
                candidate = min(
                    # can't eliminate RoN, so remove it from consideration
                    # if self.ron is None, it will be silently ignored
                    candidates - {self.ron},
                    # look backwards into previous rounds to break ties
                    key=lambda i: [entry[i] for entry in reversed(history)]
                )
                candidates.remove(candidate)
                for i, ballot in enumerate(self.ballots):
                    # skip exhausted ballots to avoid IndexError
                    if values[i] == 0:
                        continue
                    # for each vote for this candidate this round,
                    if ballot[current_pref[i]] == candidate:
                        # skip that ballot's preference to the next
                        # un-elected/eliminated choice,
                        while current_pref[i] < len(ballot) and ballot[current_pref[i]] not in candidates:
                            current_pref[i] += 1
                        # do NOT reduce value of this ballot,
                        # if the ballot is not exhausted,
                        if current_pref[i] < len(ballot):
                            # transfer at present value to next preference
                            counts[ballot[current_pref[i]]] += values[i]
                        else:
                            # exhausted ballots get a value of 0
                            values[i] = _D(0)
                # "collapse" the eliminated candidate's vote total to 0,
                # to maintain the overall vote count after transfer
                counts[candidate] = _D(0)
        # track this information in an attribute because getting iterator
        # return values is difficult
        self.winners = elected
        return self.winners

    def results(self) -> Results:
        rounds = list(self)
        return Results(
            winners=self.winners,
            rounds=rounds
        )
