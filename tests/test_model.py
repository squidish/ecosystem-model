"""Tests for EcosystemModel."""

import pytest
import pandas as pd

from model.config import EcosystemConfig
from model.ecosystem import EcosystemModel
from model.agents import Wolf, Sheep, GrassPatch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_config():
    return EcosystemConfig(
        width=20, height=20,
        initial_sheep=50, initial_wolves=20,
        seed=42,
    )


@pytest.fixture
def default_model(default_config):
    return EcosystemModel(config=default_config, seed=42)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_model_initialises_correct_agent_counts(default_config):
    model = EcosystemModel(config=default_config, seed=42)
    assert len(model.agents.select(agent_type=Wolf)) == default_config.initial_wolves
    assert len(model.agents.select(agent_type=Sheep)) == default_config.initial_sheep
    # One GrassPatch per cell
    assert len(model.agents.select(agent_type=GrassPatch)) == (
        default_config.width * default_config.height
    )


def test_model_runs_200_steps_without_error(default_config):
    model = EcosystemModel(config=default_config, seed=42)
    for _ in range(200):
        model.step()
    assert model.steps == 200


def test_model_is_reproducible_with_same_seed(default_config):
    m1 = EcosystemModel(config=default_config, seed=99)
    m2 = EcosystemModel(config=default_config, seed=99)
    for _ in range(50):
        m1.step()
        m2.step()
    df1 = m1.get_results()
    df2 = m2.get_results()
    pd.testing.assert_frame_equal(df1, df2)


def test_different_seeds_give_different_results(default_config):
    m1 = EcosystemModel(config=default_config, seed=1)
    m2 = EcosystemModel(config=default_config, seed=2)
    for _ in range(50):
        m1.step()
        m2.step()
    df1 = m1.get_results()
    df2 = m2.get_results()
    # At least one row should differ
    assert not df1.equals(df2)


def test_extinction_detected_correctly():
    """Force wolf extinction by giving them zero food energy."""
    config = EcosystemConfig(
        width=20, height=20,
        initial_sheep=50, initial_wolves=20,
        wolf_gain_from_food=0,
        initial_wolf_energy=2,
        seed=42,
    )
    model = EcosystemModel(config=config, seed=42)
    for _ in range(50):
        model.step()
        if model.is_extinct():
            break
    assert model.is_extinct()
    assert "wolves" in model.monitor.extinction_events


def test_datacollector_returns_correct_columns(default_model):
    default_model.step()
    df = default_model.get_results()
    expected = {"Wolves", "Sheep", "Grass_Coverage_Pct", "Mean_Wolf_Energy", "Mean_Sheep_Energy"}
    assert expected.issubset(set(df.columns))


def test_sheep_count_never_negative(default_config):
    model = EcosystemModel(config=default_config, seed=42)
    for _ in range(100):
        model.step()
    df = model.get_results()
    assert (df["Sheep"] >= 0).all()


def test_wolf_count_never_negative(default_config):
    model = EcosystemModel(config=default_config, seed=42)
    for _ in range(100):
        model.step()
    df = model.get_results()
    assert (df["Wolves"] >= 0).all()


def test_invalid_config_raises():
    """Too many agents for grid should raise ValueError."""
    bad_config = EcosystemConfig(
        width=5, height=5,
        initial_sheep=200, initial_wolves=200,
    )
    with pytest.raises(ValueError, match="Too many agents"):
        EcosystemModel(config=bad_config)
