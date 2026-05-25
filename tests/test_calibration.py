"""Tests for calibration functions."""

import pytest

from model.config import BirdSpeciesConfig, EcosystemConfig
from data.calibration import (
    scale_initial_count,
    scale_reproduce_rate,
    scale_gain_from_food,
    build_ecosystem_config_from_birds,
)


# ---------------------------------------------------------------------------
# scale_initial_count
# ---------------------------------------------------------------------------

def test_scale_initial_count_respects_max_density():
    grid_cells = 2500
    max_density = 0.3
    result = scale_initial_count(10_000_000, grid_cells, max_density)
    assert result <= int(max_density * grid_cells)


def test_scale_initial_count_minimum_one():
    result = scale_initial_count(0, 2500)
    assert result >= 1


def test_scale_initial_count_positive_count():
    result = scale_initial_count(1000, 2500)
    assert result >= 1


# ---------------------------------------------------------------------------
# scale_reproduce_rate
# ---------------------------------------------------------------------------

def test_scale_reproduce_rate_clamps_to_valid_range():
    # Extremely high breeding ratio
    rate = scale_reproduce_rate(breeding_pairs=1_000_000, observed_count=10)
    assert 0.001 <= rate <= 0.2

    # Effectively zero ratio
    rate = scale_reproduce_rate(breeding_pairs=1, observed_count=10_000_000)
    assert 0.001 <= rate <= 0.2


def test_scale_reproduce_rate_zero_observed():
    """Should not crash and returns fallback."""
    rate = scale_reproduce_rate(breeding_pairs=100, observed_count=0)
    assert 0.001 <= rate <= 0.2


# ---------------------------------------------------------------------------
# scale_gain_from_food
# ---------------------------------------------------------------------------

def test_scale_gain_from_food_in_range_predator():
    gain = scale_gain_from_food(territory_km2=0.5, role="predator")
    assert 2 <= gain <= 40


def test_scale_gain_from_food_in_range_prey():
    gain = scale_gain_from_food(territory_km2=0.01, role="prey")
    assert 2 <= gain <= 40


def test_scale_gain_from_food_zero_territory():
    gain = scale_gain_from_food(territory_km2=0.0, role="predator")
    assert 2 <= gain <= 40


# ---------------------------------------------------------------------------
# build_ecosystem_config_from_birds
# ---------------------------------------------------------------------------

def _make_config(role, name="TestBird"):
    return BirdSpeciesConfig(
        name=name,
        role=role,
        initial_count=50,
        reproduce_rate=0.05,
        gain_from_food=10,
        initial_energy=30,
    )


def test_build_ecosystem_config_raises_if_no_predator():
    prey_only = [_make_config("prey", "Blue Tit"), _make_config("prey", "Sparrow")]
    with pytest.raises(ValueError, match="No predator"):
        build_ecosystem_config_from_birds(prey_only)


def test_build_ecosystem_config_raises_if_no_prey():
    predator_only = [_make_config("predator", "Sparrowhawk")]
    with pytest.raises(ValueError, match="No prey"):
        build_ecosystem_config_from_birds(predator_only)


def test_build_ecosystem_config_returns_valid_config():
    species = [
        _make_config("predator", "Sparrowhawk"),
        _make_config("prey", "Blue Tit"),
    ]
    cfg = build_ecosystem_config_from_birds(species)
    assert isinstance(cfg, EcosystemConfig)
    assert cfg.initial_wolves == 50
    assert cfg.initial_sheep == 50


def test_build_ecosystem_config_averages_multiple_prey():
    species = [
        _make_config("predator", "Hawk"),
        BirdSpeciesConfig(
            name="Bird A", role="prey",
            initial_count=40, reproduce_rate=0.04,
            gain_from_food=8, initial_energy=24,
        ),
        BirdSpeciesConfig(
            name="Bird B", role="prey",
            initial_count=60, reproduce_rate=0.06,
            gain_from_food=12, initial_energy=36,
        ),
    ]
    cfg = build_ecosystem_config_from_birds(species)
    assert cfg.initial_sheep == 50   # (40 + 60) / 2
    assert cfg.sheep_gain_from_food == 10  # (8 + 12) / 2
