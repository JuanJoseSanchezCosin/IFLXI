#!/usr/bin/env python3
"""Tests estáticos del mapper MATCH_EVENT (sin API, sin PG, sin mapas)."""

from __future__ import annotations

from api_football_import_events import event_natural_key, map_event_type


def test_map_event_type() -> None:
    cases = [
        ("Goal", "Normal Goal", "goal"),
        ("Goal", "Penalty", "penalty_goal"),
        ("Goal", "Missed Penalty", "penalty_miss"),
        ("Goal", "Own Goal", "own_goal"),
        ("Card", "Yellow Card", "yellow_card"),
        ("Card", "Yellow Red Card", "second_yellow"),
        ("Card", "Yellow-Red Card", "second_yellow"),
        ("Card", "Red Card", "red_card"),
        ("subst", None, "substitution_out"),
        ("Var", "Goal cancelled", None),
        ("Goal", "Something Weird", None),
    ]
    for api_t, detail, expected in cases:
        got = map_event_type(api_t, detail)
        assert got == expected, f"{api_t}/{detail}: {got!r} != {expected!r}"


def test_idempotency_key_stable() -> None:
    a = event_natural_key(
        "123",
        event_type="goal",
        minute=12,
        extra=None,
        player_api="10",
        secondary_api="20",
        team_api="5",
        sort_order=0,
    )
    b = event_natural_key(
        "123",
        event_type="goal",
        minute=12,
        extra=None,
        player_api="10",
        secondary_api="20",
        team_api="5",
        sort_order=0,
    )
    assert a == b
    assert a.startswith("AFEVT_123_")


def test_no_assist_type() -> None:
    # No existe camino a event_type assist
    assert map_event_type("Goal", "Assist") is None
    assert map_event_type("Assist", None) is None


if __name__ == "__main__":
    test_map_event_type()
    test_idempotency_key_stable()
    test_no_assist_type()
    print("OK — mapper MATCH_EVENT (tests estáticos)")
