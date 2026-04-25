# -*- coding: utf-8 -*-
"""
tests/test_circuit_breaker.py — Unit tests for core/circuit_breaker.py.

Tests all three state machine transitions (CLOSED → OPEN → HALF-OPEN → CLOSED)
and edge cases like manual reset and nested breaker calls.
"""

import asyncio
import pytest

from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, BreakerState


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _ok():
    return "success"

async def _fail():
    raise ValueError("simulated failure")


# ── Initial state ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initial_state_is_closed():
    cb = CircuitBreaker("test", failure_threshold=3, recovery_window=60)
    assert cb.state == BreakerState.CLOSED
    assert not cb.is_open


# ── Successful calls ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_success_passes_through():
    cb = CircuitBreaker("test", failure_threshold=3, recovery_window=60)
    result = await cb.call(_ok)
    assert result == "success"


# ── Failure accumulation ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stays_closed_below_threshold():
    cb = CircuitBreaker("test", failure_threshold=3, recovery_window=60)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(_fail)
    assert cb.state == BreakerState.CLOSED


@pytest.mark.asyncio
async def test_trips_open_at_threshold():
    cb = CircuitBreaker("test", failure_threshold=3, recovery_window=60)
    for _ in range(3):
        with pytest.raises(Exception):
            await cb.call(_fail)
    assert cb.state == BreakerState.OPEN
    assert cb.is_open


# ── OPEN state rejects calls ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_open_rejects_immediately():
    cb = CircuitBreaker("test", failure_threshold=1, recovery_window=999)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    assert cb.is_open
    with pytest.raises(CircuitBreakerOpen) as exc_info:
        await cb.call(_ok)
    assert exc_info.value.name == "test"
    assert exc_info.value.retry_after > 0


# ── Recovery window → HALF-OPEN ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transitions_to_half_open_after_window():
    cb = CircuitBreaker("test", failure_threshold=1, recovery_window=0.05)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    assert cb.is_open
    await asyncio.sleep(0.1)  # wait for recovery window
    # Next call should be allowed (HALF-OPEN probe)
    result = await cb.call(_ok)
    assert result == "success"
    assert cb.state == BreakerState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_reopens():
    cb = CircuitBreaker("test", failure_threshold=1, recovery_window=0.05)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    await asyncio.sleep(0.1)
    # Probe fails → back to OPEN
    with pytest.raises(ValueError):
        await cb.call(_fail)
    assert cb.state == BreakerState.OPEN


# ── Manual reset ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manual_reset():
    cb = CircuitBreaker("test", failure_threshold=1, recovery_window=999)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    assert cb.is_open
    cb.reset()
    assert cb.state == BreakerState.CLOSED
    result = await cb.call(_ok)
    assert result == "success"


# ── Success resets failure count ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_success_resets_failure_streak():
    cb = CircuitBreaker("test", failure_threshold=3, recovery_window=60)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(_fail)
    # Success before threshold resets counter
    await cb.call(_ok)
    # Now failures need to accumulate again from zero
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(_fail)
    assert cb.state == BreakerState.CLOSED  # still closed (only 2 failures)
