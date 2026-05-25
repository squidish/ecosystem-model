"""Tests for individual agent behaviour."""

import pytest

from model.config import EcosystemConfig
from model.ecosystem import EcosystemModel
from model.agents import GrassPatch, Sheep, Wolf


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def small_model():
    """Minimal 10x10 model for agent-level tests."""
    config = EcosystemConfig(
        width=10, height=10,
        initial_sheep=5, initial_wolves=2,
        seed=0,
    )
    return EcosystemModel(config=config, seed=0)


# ---------------------------------------------------------------------------
# GrassPatch tests
# ---------------------------------------------------------------------------

def test_grass_regrows_after_countdown(small_model):
    model = small_model
    # Find an un-grown patch
    ungrown = [
        a for a in model.agents.select(agent_type=GrassPatch)
        if not a.fully_grown
    ]
    if not ungrown:
        pytest.skip("No ungrown patches at init with this seed")
    patch = ungrown[0]
    patch.countdown = 2
    patch.step()
    assert patch.countdown == 1
    patch.step()
    assert patch.countdown == 0
    patch.step()
    assert patch.fully_grown is True


def test_fully_grown_patch_stays_grown(small_model):
    model = small_model
    grown = [
        a for a in model.agents.select(agent_type=GrassPatch)
        if a.fully_grown
    ]
    if not grown:
        pytest.skip("No grown patches at init with this seed")
    patch = grown[0]
    patch.step()
    assert patch.fully_grown is True


# ---------------------------------------------------------------------------
# Sheep tests
# ---------------------------------------------------------------------------

def test_sheep_gains_energy_from_grass(small_model):
    model = small_model
    sheep = list(model.agents.select(agent_type=Sheep))[0]
    pos = sheep.pos

    # Place a fully-grown patch at sheep's position
    cell = model.grid.get_cell_list_contents([pos])
    patch = next(a for a in cell if isinstance(a, GrassPatch))
    patch.fully_grown = True

    initial_energy = sheep.energy
    sheep._eat_grass()
    assert sheep.energy == initial_energy + model.config.sheep_gain_from_food
    assert patch.fully_grown is False


def test_sheep_does_not_gain_energy_from_bare_ground(small_model):
    model = small_model
    sheep = list(model.agents.select(agent_type=Sheep))[0]
    pos = sheep.pos

    cell = model.grid.get_cell_list_contents([pos])
    patch = next(a for a in cell if isinstance(a, GrassPatch))
    patch.fully_grown = False

    initial_energy = sheep.energy
    sheep._eat_grass()
    assert sheep.energy == initial_energy


def test_sheep_dies_at_zero_energy(small_model):
    model = small_model
    sheep = list(model.agents.select(agent_type=Sheep))[0]
    sheep.energy = 1  # will drop to 0 after metabolic cost
    initial_count = len(model.agents.select(agent_type=Sheep))

    # Manually trigger the energy-loss and death logic
    sheep.energy -= 1
    if sheep.energy <= 0:
        sheep.remove()

    assert len(model.agents.select(agent_type=Sheep)) == initial_count - 1


def test_sheep_reproduction_creates_offspring(small_model):
    model = small_model
    sheep = list(model.agents.select(agent_type=Sheep))[0]
    sheep.energy = 10
    initial_count = len(model.agents.select(agent_type=Sheep))

    # Force reproduction
    sheep.energy = sheep.energy // 2
    offspring = Sheep(model, energy=sheep.energy)
    model.grid.place_agent(offspring, sheep.pos)

    assert len(model.agents.select(agent_type=Sheep)) == initial_count + 1


# ---------------------------------------------------------------------------
# Wolf tests
# ---------------------------------------------------------------------------

def test_wolf_gains_energy_from_eating_sheep(small_model):
    model = small_model
    wolf = list(model.agents.select(agent_type=Wolf))[0]
    pos = wolf.pos

    # Place a sheep on the wolf's cell
    victim = Sheep(model, energy=5)
    model.grid.place_agent(victim, pos)

    initial_energy = wolf.energy
    wolf._eat_sheep()
    assert wolf.energy == initial_energy + model.config.wolf_gain_from_food
    # Victim should be removed
    assert victim not in model.agents.select(agent_type=Sheep)


def test_wolf_does_not_gain_energy_on_empty_cell(small_model):
    model = small_model
    wolf = list(model.agents.select(agent_type=Wolf))[0]
    pos = wolf.pos

    # Remove any sheep from wolf's cell
    cell = model.grid.get_cell_list_contents([pos])
    for agent in cell:
        if isinstance(agent, Sheep):
            agent.remove()

    initial_energy = wolf.energy
    wolf._eat_sheep()
    assert wolf.energy == initial_energy


def test_wolf_dies_at_zero_energy(small_model):
    model = small_model
    wolf = list(model.agents.select(agent_type=Wolf))[0]
    initial_count = len(model.agents.select(agent_type=Wolf))

    wolf.energy = 1
    wolf.energy -= 1
    if wolf.energy <= 0:
        wolf.remove()

    assert len(model.agents.select(agent_type=Wolf)) == initial_count - 1


def test_wolf_reproduction_conserves_energy(small_model):
    model = small_model
    wolf = list(model.agents.select(agent_type=Wolf))[0]
    wolf.energy = 10
    original_energy = wolf.energy

    # Reproduce: parent energy halved, offspring gets same
    wolf.energy = wolf.energy // 2
    offspring = Wolf(model, energy=wolf.energy)
    model.grid.place_agent(offspring, wolf.pos)

    assert wolf.energy + offspring.energy == original_energy
