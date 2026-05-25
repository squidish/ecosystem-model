"""
Calibration functions: map real-world bird observation data to model parameters.

Every function documents the ecological assumption it encodes so that users
can make informed decisions about when to override values manually.
"""

import math
from typing import List, Optional

from model.config import BirdSpeciesConfig, EcosystemConfig


def scale_initial_count(
    observed_count: int,
    grid_cells: int,
    max_density: float = 0.3,
) -> int:
    """
    Scale a real-world population count to an initial agent count for a given grid.

    Assumption: we scale proportionally but cap at max_density * grid_cells to
    prevent overcrowding. max_density=0.3 means at most 30% of cells occupied
    at initialisation, matching typical wildlife survey density estimates.

    The proportional scaling uses the ratio of the species count to the total
    observed count across all species, then multiplies by available cells.
    This is a manual calibration choice, not a derived value — for species with
    very large absolute counts (e.g. House Sparrow), the cap will usually bind.

    Args:
        observed_count: Raw field survey count for the species.
        grid_cells: Total cells in the model grid (width * height).
        max_density: Maximum fraction of grid cells an agent type may occupy.

    Returns:
        Integer agent count, at least 1 and at most int(max_density * grid_cells).
    """
    max_agents = max(1, int(max_density * grid_cells))
    # Simple proportional: treat observed_count as an index into [1, max_agents]
    # We log-compress to avoid one very abundant species dominating.
    if observed_count <= 0:
        return 1
    log_count = math.log10(observed_count + 1)
    # Normalise to [1, max_agents] — caller can refine with domain knowledge.
    scaled = max(1, min(max_agents, int(log_count * 10)))
    return scaled


def scale_reproduce_rate(breeding_pairs: int, observed_count: int) -> float:
    """
    Estimate per-step reproduction probability from breeding pair ratio.

    Assumption: breeding_pairs / observed_count gives an approximate annual
    reproduction fraction. We divide by 52 (weeks/year) to approximate
    a weekly timestep. This is a rough heuristic — adjust for species
    with strongly seasonal breeding (e.g. migratory waders that breed only
    once a year in a 6-week window).

    Output is clamped to [0.001, 0.2] to keep model dynamics stable. Values
    outside this range produce either no reproduction or runaway population growth.

    Args:
        breeding_pairs: Number of confirmed breeding pairs from survey data.
        observed_count: Total observed individuals for the species.

    Returns:
        Float in [0.001, 0.2] representing per-step reproduction probability.
    """
    if observed_count <= 0:
        return 0.04  # fallback to default
    annual_rate = (breeding_pairs * 2) / observed_count  # pairs → individuals
    weekly_rate = annual_rate / 52.0
    return float(max(0.001, min(0.2, weekly_rate)))


def scale_gain_from_food(territory_km2: float, role: str) -> int:
    """
    Map territory size to energy gain per feeding event.

    Assumption: for predators, larger territory implies lower prey density,
    so predators expend more energy per hunt but also gain more per kill
    (they hunt larger or more nutritious prey). We use a log scaling.

    For prey, territory maps to food availability — smaller territory means
    denser competition, less energy per graze. Inverse log scaling applies.

    Returns int in range [2, 40].

    Args:
        territory_km2: Mean territory size in km² from field data.
        role: "predator" or "prey".

    Returns:
        Integer energy gain in [2, 40].
    """
    if territory_km2 <= 0:
        territory_km2 = 0.01

    log_t = math.log10(territory_km2 + 0.001)

    if role == "predator":
        # Larger territory → higher gain (hunting larger prey / more calories)
        # log10(0.5) ≈ -0.3 → ~20 (Sparrowhawk default)
        raw = 20 + int(log_t * 10)
    else:
        # Smaller territory → higher gain (dense, accessible food patch)
        # log10(0.01) = -2 → ~24, log10(1) = 0 → ~4
        raw = 4 + int(-log_t * 10)

    return max(2, min(40, raw))


def build_ecosystem_config_from_birds(
    species_configs: List[BirdSpeciesConfig],
    base_config: Optional[EcosystemConfig] = None,
) -> EcosystemConfig:
    """
    Combine a list of BirdSpeciesConfig objects into a single EcosystemConfig.

    Expects exactly one predator species and one or more prey species.
    If multiple prey species are provided, their parameters are averaged
    (simple mean), which is a deliberate simplification — the model supports
    only one prey type. To model multiple prey properly, extend agents.py.

    Raises:
        ValueError: If no predator species found.
        ValueError: If no prey species found.

    Args:
        species_configs: List of BirdSpeciesConfig (from DataLoader.to_species_configs).
        base_config: Optional EcosystemConfig to use as baseline; grid size and
                     grass parameters are taken from here. Uses defaults if None.

    Returns:
        EcosystemConfig with population and energy parameters derived from bird data.
    """
    base = base_config or EcosystemConfig()

    predators = [s for s in species_configs if s.role == "predator"]
    prey = [s for s in species_configs if s.role == "prey"]

    if not predators:
        raise ValueError(
            "No predator species found in species_configs. "
            "At least one BirdSpeciesConfig with role='predator' is required."
        )
    if not prey:
        raise ValueError(
            "No prey species found in species_configs. "
            "At least one BirdSpeciesConfig with role='prey' is required."
        )

    predator = predators[0]  # use first predator

    # Average prey parameters if multiple prey species
    avg_prey_count = int(sum(p.initial_count for p in prey) / len(prey))
    avg_prey_reproduce = sum(p.reproduce_rate for p in prey) / len(prey)
    avg_prey_gain = int(sum(p.gain_from_food for p in prey) / len(prey))
    avg_prey_energy = int(sum(p.initial_energy for p in prey) / len(prey))

    return EcosystemConfig(
        width=base.width,
        height=base.height,
        initial_sheep=avg_prey_count,
        initial_wolves=predator.initial_count,
        sheep_reproduce=float(max(0.001, min(1.0, avg_prey_reproduce))),
        sheep_gain_from_food=max(1, avg_prey_gain),
        wolf_reproduce=float(max(0.001, min(1.0, predator.reproduce_rate))),
        wolf_gain_from_food=max(1, predator.gain_from_food),
        grass_regrowth_time=base.grass_regrowth_time,
        initial_sheep_energy=max(1, avg_prey_energy),
        initial_wolf_energy=max(1, predator.initial_energy),
        seed=base.seed,
    )
