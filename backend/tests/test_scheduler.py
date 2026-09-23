"""Unit and cross-validation tests for the exact scheduler."""

from __future__ import annotations

import random
from itertools import combinations, permutations

import pytest

from app.scheduler import (
    ProblemSpec,
    Solution,
    TargetSpec,
    azimuth_distance,
    ceil_travel,
    solve,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_problem(
    targets,
    initial_time=0,
    initial_azimuth=0,
    initial_elevation=0,
    azimuth_speed=1.0,
    elevation_speed=1.0,
) -> ProblemSpec:
    return ProblemSpec(
        initial_time=initial_time,
        initial_azimuth=initial_azimuth,
        initial_elevation=initial_elevation,
        azimuth_speed=azimuth_speed,
        elevation_speed=elevation_speed,
        targets=tuple(targets),
    )


def target(
    tid,
    azimuth=0,
    elevation=0,
    duration=10,
    window=(0, 86399),
    priority=1,
    mandatory=False,
) -> TargetSpec:
    return TargetSpec(
        id=tid,
        azimuth=azimuth,
        elevation=elevation,
        duration=duration,
        window_start=window[0],
        window_end=window[1],
        priority=priority,
        mandatory=mandatory,
    )


def brute_force(problem: ProblemSpec):
    """Independent exhaustive reference: every superset of the mandatory
    targets, every order.  Returns ((prio, count, -end), ids, end, prio)."""
    targets = problem.targets
    n = len(targets)
    mandatory = {i for i, t in enumerate(targets) if t.mandatory}
    best = None
    for r in range(0, n + 1):
        for subset in combinations(range(n), r):
            if not mandatory <= set(subset):
                continue
            for perm in permutations(subset):
                t = problem.initial_time
                az, el = problem.initial_azimuth, problem.initial_elevation
                ok = True
                for j in perm:
                    tgt = targets[j]
                    s = max(
                        ceil_travel(
                            azimuth_distance(az, tgt.azimuth), problem.azimuth_speed
                        ),
                        ceil_travel(abs(el - tgt.elevation), problem.elevation_speed),
                    )
                    start = max(t + s, tgt.window_start)
                    end = start + tgt.duration
                    if end > tgt.window_end:
                        ok = False
                        break
                    t = end
                    az, el = tgt.azimuth, tgt.elevation
                if not ok:
                    continue
                prio = sum(targets[j].priority for j in perm)
                ids = tuple(targets[j].id for j in perm)
                key = (prio, len(perm), -t)
                if best is None or key > best[0] or (key == best[0] and ids < best[1]):
                    best = (key, ids, t, prio)
    return best


def check_solution_structure(problem: ProblemSpec, sol: Solution):
    """Verify timing arithmetic, window containment and set bookkeeping."""
    by_id = {t.id: t for t in problem.targets}
    t = problem.initial_time
    az, el = problem.initial_azimuth, problem.initial_elevation
    seen = []
    for step in sol.steps:
        tgt = by_id[step.target_id]
        assert step.target_id not in seen
        seen.append(step.target_id)
        expected_slew = max(
            ceil_travel(azimuth_distance(az, tgt.azimuth), problem.azimuth_speed),
            ceil_travel(abs(el - tgt.elevation), problem.elevation_speed),
        )
        assert step.slew_start == t
        assert step.slew_end == t + expected_slew
        assert step.wait_start == step.slew_end
        assert step.wait_end == max(step.slew_end, tgt.window_start)
        assert step.observe_start == step.wait_end
        assert step.observe_end == step.observe_start + tgt.duration
        assert tgt.window_start <= step.observe_start
        assert step.observe_end <= tgt.window_end
        t = step.observe_end
        az, el = tgt.azimuth, tgt.elevation
    assert sol.end_time == t
    for tgt in problem.targets:
        if tgt.mandatory:
            assert tgt.id in seen, "mandatory target missing"
    assert sol.unselected == [x.id for x in problem.targets if x.id not in seen]
    assert sol.total_priority == sum(by_id[i].priority for i in seen)


def assert_matches_brute(problem: ProblemSpec):
    sol = solve(problem)
    best = brute_force(problem)
    if best is None:
        assert not sol.feasible
        return
    (key, ids, end, prio) = best
    assert sol.feasible
    assert tuple(s.target_id for s in sol.steps) == ids
    assert sol.total_priority == prio
    assert sol.end_time == end
    check_solution_structure(problem, sol)


# ---------------------------------------------------------------------------
# primitive helpers
# ---------------------------------------------------------------------------

def test_azimuth_distance_shortest_arc():
    assert azimuth_distance(10, 40) == 30
    assert azimuth_distance(350, 10) == 20
    assert azimuth_distance(0, 180) == 180
    assert azimuth_distance(5, 5) == 0


def test_ceil_travel():
    assert ceil_travel(0, 2) == 0
    assert ceil_travel(5, 2) == 3
    assert ceil_travel(4, 2) == 2
    assert ceil_travel(3, 0.5) == 6
    assert ceil_travel(7, 0.1) == 70  # exact quotient must not round up


# ---------------------------------------------------------------------------
# crafted scenarios
# ---------------------------------------------------------------------------

def test_waits_for_window_to_open():
    problem = make_problem(
        [target("A", azimuth=10, duration=5, window=(100, 200), mandatory=True)],
        initial_time=0,
    )
    sol = solve(problem)
    assert sol.feasible
    step = sol.steps[0]
    assert (step.slew_start, step.slew_end) == (0, 10)
    assert (step.wait_start, step.wait_end) == (10, 100)
    assert (step.observe_start, step.observe_end) == (100, 105)


def test_axes_slew_simultaneously():
    # azimuth needs 10s, elevation needs 4s -> slew is 10s, not 14s.
    problem = make_problem(
        [target("A", azimuth=10, elevation=4, duration=5, window=(0, 100), mandatory=True)],
        initial_azimuth=0,
        initial_elevation=0,
        azimuth_speed=1,
        elevation_speed=1,
    )
    sol = solve(problem)
    assert sol.steps[0].slew_end == 10


def test_infeasible_when_mandatory_cannot_fit():
    problem = make_problem(
        [target("M", duration=100, window=(100, 150), mandatory=True)]
    )
    sol = solve(problem)
    assert not sol.feasible
    assert sol.unselected == ["M"]


def test_priority_dominates_target_count():
    # X (prio 13) conflicts with Y and Z; Y+Z together are prio 12.
    problem = make_problem(
        [
            target("X", duration=950, window=(0, 1000), priority=13),
            target("Y", duration=100, window=(0, 100), priority=6),
            target("Z", duration=100, window=(100, 200), priority=6),
        ]
    )
    sol = solve(problem)
    assert [s.target_id for s in sol.steps] == ["X"]
    assert sol.total_priority == 13


def test_count_breaks_priority_ties():
    problem = make_problem(
        [
            target("X", duration=950, window=(0, 1000), priority=12),
            target("Y", duration=100, window=(0, 100), priority=6),
            target("Z", duration=100, window=(100, 200), priority=6),
        ]
    )
    sol = solve(problem)
    assert [s.target_id for s in sol.steps] == ["Y", "Z"]
    assert sol.total_priority == 12


def test_end_time_breaks_count_ties_before_lex():
    # Both orders of {A,B} are feasible; (B,A) ends sooner even though
    # (A,B) is lexicographically smaller.
    problem = make_problem(
        [
            target("B", azimuth=0, duration=10, window=(0, 1000)),
            target("A", azimuth=100, duration=10, window=(0, 1000)),
        ],
        initial_azimuth=0,
    )
    sol = solve(problem)
    assert [s.target_id for s in sol.steps] == ["B", "A"]
    assert sol.end_time == 120


def test_lexicographic_tiebreak():
    # Identical geometry/windows: both orders end at the same time, the
    # lexicographically smaller id sequence must win.
    problem = make_problem(
        [
            target("B", azimuth=10, duration=10, window=(0, 1000)),
            target("A", azimuth=10, duration=10, window=(0, 1000)),
        ],
        initial_azimuth=10,
    )
    sol = solve(problem)
    assert [s.target_id for s in sol.steps] == ["A", "B"]


def test_lex_tiebreak_with_waiting_prefix():
    # The lexicographically smallest optimal sequence reaches C later than
    # another prefix would, but waiting at D's window equalises the final end
    # time.  A solver that only keeps the earliest prefix per (set, last)
    # would wrongly return (B, A, C, D).
    problem = make_problem(
        [
            target("A", azimuth=30, duration=10, window=(0, 1000)),
            target("B", azimuth=10, duration=10, window=(0, 1000)),
            target("C", azimuth=40, duration=10, window=(0, 1000)),
            target("D", azimuth=50, duration=10, window=(300, 400)),
        ],
        initial_time=0,
        initial_azimuth=0,
    )
    sol = solve(problem)
    assert [s.target_id for s in sol.steps] == ["A", "B", "C", "D"]
    assert sol.end_time == 310
    check_solution_structure(problem, sol)


def test_mandatory_forces_inclusion_even_when_suboptimal():
    # M has priority 1 and is awkward, but it is mandatory.
    problem = make_problem(
        [
            target("M", azimuth=180, duration=10, window=(500, 1000), priority=1, mandatory=True),
            target("A", azimuth=10, duration=10, window=(0, 100), priority=9),
        ],
        initial_azimuth=0,
    )
    sol = solve(problem)
    assert sol.feasible
    ids = [s.target_id for s in sol.steps]
    assert "M" in ids


def test_empty_plan_when_nothing_mandatory_and_nothing_fits():
    problem = make_problem(
        [
            target("A", duration=50, window=(0, 100), priority=5),
            target("B", duration=50, window=(0, 100), priority=5),
        ],
        initial_time=5000,
    )
    sol = solve(problem)
    assert sol.feasible
    assert sol.steps == []
    assert sol.total_priority == 0
    assert sol.end_time == 5000
    assert sol.unselected == ["A", "B"]


def test_circular_azimuth_slew():
    # 350 -> 10 is 20 degrees across the 0-degree meridian.
    problem = make_problem(
        [target("A", azimuth=10, duration=5, window=(0, 100), mandatory=True)],
        initial_azimuth=350,
        azimuth_speed=1,
    )
    sol = solve(problem)
    assert sol.steps[0].slew_end == 20


# ---------------------------------------------------------------------------
# randomized cross-validation against the exhaustive reference
# ---------------------------------------------------------------------------

def random_problem(rng: random.Random, n: int) -> ProblemSpec:
    targets = []
    for i in range(n):
        ws = rng.randint(0, 86000)
        we = min(86399, ws + rng.randint(0, 4000))
        targets.append(
            target(
                f"T{i:02d}",
                azimuth=rng.randint(0, 359),
                elevation=rng.randint(0, 90),
                duration=rng.randint(1, 600),
                window=(ws, we),
                priority=rng.randint(1, 9),
                mandatory=rng.random() < 0.3,
            )
        )
    return make_problem(
        targets,
        initial_time=rng.randint(0, 80000),
        initial_azimuth=rng.randint(0, 359),
        initial_elevation=rng.randint(0, 90),
        azimuth_speed=rng.choice([0.5, 1, 1.5, 2, 3, 5]),
        elevation_speed=rng.choice([0.5, 1, 1.5, 2, 3, 5]),
    )


@pytest.mark.parametrize("seed", range(250))
def test_matches_brute_force_small(seed):
    rng = random.Random(seed)
    problem = random_problem(rng, n=rng.randint(2, 7))
    assert_matches_brute(problem)


@pytest.mark.parametrize("seed", range(1000, 1008))
def test_matches_brute_force_eight(seed):
    rng = random.Random(seed)
    problem = random_problem(rng, n=8)
    assert_matches_brute(problem)
