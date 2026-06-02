from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class EcosystemConfig:
    """
    Configuration for the Wolf-Sheep predator-prey ecosystem model.

    All parameters are validated by ConfigValidator before a run starts.
    Defaults represent a stable oscillating system on a 50x50 grid.
    """

    # Grid
    width: int = 50
    height: int = 50

    # Populations
    initial_sheep: int = 100
    initial_wolves: int = 50

    # Sheep parameters
    sheep_reproduce: float = 0.04       # probability per step
    sheep_gain_from_food: int = 4       # energy gained from eating grass

    # Wolf parameters
    wolf_reproduce: float = 0.05        # probability per step
    wolf_gain_from_food: int = 25       # energy gained from eating sheep

    # Grass parameters
    grass_regrowth_time: int = 30       # steps for grass to regrow

    # Starting energies
    initial_sheep_energy: int = 6       # starting energy for sheep
    initial_wolf_energy: int = 15       # starting energy for wolves

    # RNG
    seed: Optional[int] = 42


@dataclass
class BirdSpeciesConfig:
    """
    Maps a real bird species to either a predator (Wolf) or prey (Sheep) role.

    All model parameters are derived via calibration.py scaling functions.
    This is NOT automatic inference — each field has a docstring explaining
    the ecological assumption behind it.

    Fields:
        name: Common name of the species, e.g. "Sparrowhawk".
        role: Whether this species acts as predator (Wolf) or prey (Sheep).
        initial_count: Maps to initial_wolves or initial_sheep in EcosystemConfig.
        reproduce_rate: Maps to wolf_reproduce or sheep_reproduce.
            Derived from breeding_pairs / observed_count scaled to weekly timestep.
        gain_from_food: Maps to wolf_gain_from_food or sheep_gain_from_food.
            Derived from territory size via inverse log scaling.
        initial_energy: Maps to initial_wolf_energy or initial_sheep_energy.
            Set proportionally to gain_from_food to give agents a fair start.
        source_file: Path to source CSV if this config was loaded from data.
    """

    name: str
    role: Literal["predator", "prey"]
    initial_count: int
    reproduce_rate: float
    gain_from_food: int
    initial_energy: int
    source_file: Optional[str] = None
