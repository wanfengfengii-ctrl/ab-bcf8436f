"""Exact global scheduler for night-time radio observations.

A plan is a sequence of distinct targets.  Slewing from one attitude to the
next takes ``max(ceil(azimuth_distance / azimuth_speed),
ceil(elevation_distance / elevation_speed))`` seconds (both axes move at the
same time, azimuth along the shortest circular arc).  The telescope may wait
at a target for its window to open, and every observation must finish inside
its visibility window.

Objective (lexicographic, exactly in this order):

1. every mandatory target must be scheduled (otherwise the problem is
   reported as infeasible);
2. maximise the total priority;
3. maximise the number of observed targets;
4. minimise the final end time (end of the last observation);
5. break remaining ties by the lexicographically smallest sequence of
   target ids.

The solver is exact (no greedy approximation):

* Phase 1 - forward subset DP ``f[mask][last]`` = earliest feasible end time
  of a plan observing exactly ``mask`` and finishing at target ``last``.
* Phase 2 - scan all supersets of the mandatory set for the optimal
  ``(total_priority, target_count, end_time) = (P*, C*, E*)``.
* Phase 3 - backward DP ``L[v][mask]`` = latest time at which one may be at
  node ``v`` and still observe exactly ``mask`` (in some order) finishing by
  ``E*``.
* Phase 4 - reconstruction of the lexicographically smallest optimal id
  sequence, using ``L`` as an exact feasibility oracle.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Sequence

_EPS = 1e-9
_INF = float("inf")


def ceil_travel(distance: float, speed: float) -> int:
    """Smallest integer number of seconds needed to cover ``distance``.

    ``speed`` is degrees per second; the result is ``ceil(distance / speed)``
    computed with a small epsilon so that exact integer quotients are not
    rounded up by floating point noise.
    """
    if distance <= 0:
        return 0
    return max(0, int(math.ceil(distance / speed - _EPS)))


def azimuth_distance(a: int, b: int) -> int:
    """Shortest circular distance in degrees between two azimuths."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


@dataclass(frozen=True)
class TargetSpec:
    id: str
    azimuth: int
    elevation: int
    duration: int
    window_start: int
    window_end: int
    priority: int
    mandatory: bool


@dataclass(frozen=True)
class ProblemSpec:
    initial_time: int
    initial_azimuth: int
    initial_elevation: int
    azimuth_speed: float
    elevation_speed: float
    targets: Sequence[TargetSpec]


@dataclass
class Step:
    target_id: str
    slew_start: int
    slew_end: int
    wait_start: int
    wait_end: int
    observe_start: int
    observe_end: int


@dataclass
class Solution:
    feasible: bool
    steps: list[Step] = field(default_factory=list)
    unselected: list[str] = field(default_factory=list)
    total_priority: int = 0
    end_time: Optional[int] = None


def _slew_matrix(problem: ProblemSpec) -> list[list[int]]:
    """slew[v][j]: seconds to rotate from node v to target j.

    Node 0 is the initial attitude, node i+1 is target i.
    """
    targets = problem.targets
    n = len(targets)
    node_az = [problem.initial_azimuth] + [t.azimuth for t in targets]
    node_el = [problem.initial_elevation] + [t.elevation for t in targets]
    matrix: list[list[int]] = []
    for v in range(n + 1):
        row = []
        for j in range(n):
            t_az = ceil_travel(
                azimuth_distance(node_az[v], targets[j].azimuth),
                problem.azimuth_speed,
            )
            t_el = ceil_travel(
                abs(node_el[v] - targets[j].elevation), problem.elevation_speed
            )
            row.append(max(t_az, t_el))
        matrix.append(row)
    return matrix


def solve(problem: ProblemSpec) -> Solution:
    targets = problem.targets
    n = len(targets)
    ids = [t.id for t in targets]
    dur = [t.duration for t in targets]
    ws = [t.window_start for t in targets]
    we = [t.window_end for t in targets]
    prio = [t.priority for t in targets]
    slew = _slew_matrix(problem)
    t0 = problem.initial_time

    full = 1 << n
    all_mask = full - 1

    popcount = [0] * full
    prio_sum = [0] * full
    for mask in range(1, full):
        lb = mask & -mask
        i = lb.bit_length() - 1
        popcount[mask] = popcount[mask ^ lb] + 1
        prio_sum[mask] = prio_sum[mask ^ lb] + prio[i]

    # ---- Phase 1: earliest end time f[mask][last] ----
    f = [_INF] * (full * n)
    for j in range(n):
        arrive = t0 + slew[0][j]
        start = ws[j] if ws[j] > arrive else arrive
        end = start + dur[j]
        if end <= we[j]:
            f[(1 << j) * n + j] = end
    for mask in range(1, full):
        base = mask * n
        rest_all = all_mask ^ mask
        m = mask
        while m:
            lb = m & -m
            last = lb.bit_length() - 1
            m ^= lb
            t = f[base + last]
            if t == _INF:
                continue
            row = slew[last + 1]
            r = rest_all
            while r:
                nb = r & -r
                j = nb.bit_length() - 1
                r ^= nb
                arrive = t + row[j]
                start = ws[j] if ws[j] > arrive else arrive
                end = start + dur[j]
                if end <= we[j]:
                    idx = (mask | nb) * n + j
                    if end < f[idx]:
                        f[idx] = end

    # ---- Phase 2: optimal (priority, count, end_time) ----
    mand_mask = 0
    for i, t in enumerate(targets):
        if t.mandatory:
            mand_mask |= 1 << i

    best_key: Optional[tuple[int, int]] = None
    best_end = 0
    for mask in range(full):
        if mask & mand_mask != mand_mask:
            continue
        if mask == 0:
            end = t0  # empty plan is allowed when nothing is mandatory
        else:
            base = mask * n
            end = _INF
            for last in range(n):
                v = f[base + last]
                if v < end:
                    end = v
            if end == _INF:
                continue
        key = (prio_sum[mask], popcount[mask])
        if best_key is None or key > best_key or (key == best_key and end < best_end):
            best_key = key
            best_end = end

    if best_key is None:
        return Solution(feasible=False, unselected=list(ids))

    p_star, c_star = best_key
    e_star = best_end

    # ---- Phase 3: latest depart time L[v][mask] to finish mask by E* ----
    neg = -_INF
    L = [neg] * ((n + 1) * full)
    for v in range(n + 1):
        L[v * full] = e_star  # nothing left to observe: current time <= E*
    for mask in range(1, full):
        for v in range(n + 1):
            row = slew[v]
            best_t = neg
            m = mask
            while m:
                lb = m & -m
                j = lb.bit_length() - 1
                m ^= lb
                rest = L[(j + 1) * full + (mask ^ lb)]
                limit = we[j] if we[j] < rest else rest
                b = limit - dur[j]
                if b >= ws[j]:
                    cand = b - row[j]
                    if cand > best_t:
                        best_t = cand
            L[v * full + mask] = best_t

    # ---- Phase 4: lexicographically smallest optimal id sequence ----
    groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    for mask in range(full):
        groups[(prio_sum[mask], popcount[mask])].append(mask)

    order = sorted(range(n), key=lambda i: ids[i])
    used = 0
    v = 0
    t = t0
    seq: list[int] = []
    remaining_prio = p_star
    remaining_count = c_star
    while remaining_count > 0:
        chosen = -1
        chosen_end = 0
        for j in order:
            if used >> j & 1:
                continue
            arrive = t + slew[v][j]
            start = ws[j] if ws[j] > arrive else arrive
            end = start + dur[j]
            if end > we[j]:
                continue
            need_prio = remaining_prio - prio[j]
            need_count = remaining_count - 1
            if need_prio < 0:
                continue
            avail = all_mask ^ used ^ (1 << j)
            node = (j + 1) * full
            ok = False
            for sub in groups.get((need_prio, need_count), ()):
                if sub & ~avail == 0 and L[node + sub] >= end:
                    ok = True
                    break
            if ok:
                chosen = j
                chosen_end = end
                break
        if chosen < 0:  # pragma: no cover - indicates an internal inconsistency
            raise RuntimeError("failed to reconstruct an optimal sequence")
        seq.append(chosen)
        used |= 1 << chosen
        v = chosen + 1
        t = chosen_end
        remaining_prio -= prio[chosen]
        remaining_count -= 1

    # ---- Forward simulation of the chosen sequence ----
    steps: list[Step] = []
    v = 0
    t = t0
    for j in seq:
        arrive = t + slew[v][j]
        start = ws[j] if ws[j] > arrive else arrive
        end = start + dur[j]
        steps.append(
            Step(
                target_id=ids[j],
                slew_start=t,
                slew_end=arrive,
                wait_start=arrive,
                wait_end=start,
                observe_start=start,
                observe_end=end,
            )
        )
        v = j + 1
        t = end

    selected = set(seq)
    unselected = [ids[i] for i in range(n) if i not in selected]
    return Solution(
        feasible=True,
        steps=steps,
        unselected=unselected,
        total_priority=p_star,
        end_time=t,
    )
