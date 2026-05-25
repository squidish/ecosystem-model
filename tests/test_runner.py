"""Tests for SimulationRunner."""

import pytest

from model.config import EcosystemConfig
from simulation.runner import SimulationRunner, RunConfig, RunResult


@pytest.fixture
def runner():
    return SimulationRunner()


@pytest.fixture
def small_config():
    return EcosystemConfig(
        width=15, height=15,
        initial_sheep=30, initial_wolves=10,
        seed=42,
    )


def test_runner_returns_runresult(runner, small_config):
    rc = RunConfig(ecosystem_config=small_config, n_steps=20, seed=42)
    result = runner.run(rc)
    assert isinstance(result, RunResult)


def test_runner_data_has_rows(runner, small_config):
    rc = RunConfig(ecosystem_config=small_config, n_steps=20, seed=42)
    result = runner.run(rc)
    assert len(result.data) > 0


def test_runner_steps_completed_positive(runner, small_config):
    rc = RunConfig(ecosystem_config=small_config, n_steps=20, seed=42)
    result = runner.run(rc)
    assert result.steps_completed > 0


def test_runner_stops_on_extinction_when_flag_set(runner):
    """Wolves starve out rapidly; runner should terminate early."""
    config = EcosystemConfig(
        width=15, height=15,
        initial_sheep=30, initial_wolves=10,
        wolf_gain_from_food=0,
        initial_wolf_energy=2,
        seed=42,
    )
    rc = RunConfig(
        ecosystem_config=config,
        n_steps=500,
        seed=42,
        stop_on_extinction=True,
    )
    result = runner.run(rc)
    assert result.terminated_early is True
    assert result.steps_completed < 500


def test_runner_completes_full_steps_when_no_extinction(runner):
    """With generous parameters, run should reach n_steps."""
    config = EcosystemConfig(
        width=20, height=20,
        initial_sheep=100, initial_wolves=5,
        wolf_reproduce=0.001,
        wolf_gain_from_food=30,
        sheep_reproduce=0.1,
        seed=42,
    )
    rc = RunConfig(
        ecosystem_config=config,
        n_steps=30,
        seed=42,
        stop_on_extinction=False,
    )
    result = runner.run(rc)
    assert result.steps_completed == 30
    assert result.terminated_early is False


def test_sweep_returns_correct_number_of_results(runner, small_config):
    values = [0.02, 0.05, 0.10]
    seeds = [42, 43]
    results = runner.run_sweep(
        base_config=small_config,
        param_name="sheep_reproduce",
        param_values=values,
        n_steps=20,
        seeds=seeds,
    )
    assert len(results) == len(values) * len(seeds)


def test_sweep_varies_parameter(runner, small_config):
    values = [0.01, 0.15]
    results = runner.run_sweep(
        base_config=small_config,
        param_name="sheep_reproduce",
        param_values=values,
        n_steps=20,
        seeds=[42],
    )
    r1, r2 = results
    assert r1.config.ecosystem_config.sheep_reproduce == 0.01
    assert r2.config.ecosystem_config.sheep_reproduce == 0.15
