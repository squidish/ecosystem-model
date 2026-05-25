"""
Main Mesa model class for the Wolf-Sheep predator-prey ecosystem.
"""

from typing import Optional

import numpy as np
import pandas as pd
from mesa import Model
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector

from .agents import GrassPatch, Sheep, Wolf
from .config import EcosystemConfig
from .validation import ConfigValidator, RuntimeMonitor


class EcosystemModel(Model):
    """
    Wolf-Sheep predator-prey ecosystem model.

    Implements a classic Lotka-Volterra style agent-based model on a toroidal
    grid. Grass patches are primary producers; Sheep are primary consumers;
    Wolves are secondary consumers.

    Args:
        config: EcosystemConfig dataclass. Uses defaults if None.
        seed: RNG seed. Overrides config.seed if provided.

    Usage:
        model = EcosystemModel(config=EcosystemConfig(initial_sheep=150), seed=42)
        for _ in range(200):
            model.step()
        df = model.get_results()
    """

    def __init__(
        self,
        config: Optional[EcosystemConfig] = None,
        seed: Optional[int] = None,
    ) -> None:
        effective_seed = seed if seed is not None else (config.seed if config else 42)
        super().__init__(seed=effective_seed)

        self.config = config or EcosystemConfig()

        # Validate before initialising anything
        validator = ConfigValidator()
        result = validator.validate(self.config)
        if not result.valid:
            raise ValueError(f"Invalid config: {result.errors}")
        for w in result.warnings:
            print(f"[EcosystemModel WARNING] {w}")

        # Thread numpy RNG from the same seed for any numpy operations
        self.np_random = np.random.default_rng(effective_seed)

        self.grid = MultiGrid(self.config.width, self.config.height, torus=True)
        self.monitor = RuntimeMonitor(self)
        self._setup_datacollector()
        self._place_agents()
        self.datacollector.collect(self)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _setup_datacollector(self) -> None:
        self.datacollector = DataCollector(
            model_reporters={
                "Wolves": lambda m: len(m.agents.select(agent_type=Wolf)),
                "Sheep": lambda m: len(m.agents.select(agent_type=Sheep)),
                "Grass_Coverage_Pct": lambda m: (
                    sum(
                        1
                        for a in m.agents.select(agent_type=GrassPatch)
                        if a.fully_grown
                    )
                    / (m.config.width * m.config.height)
                    * 100
                ),
                "Mean_Wolf_Energy": lambda m: (
                    float(
                        np.mean([a.energy for a in m.agents.select(agent_type=Wolf)])
                    )
                    if len(m.agents.select(agent_type=Wolf)) > 0
                    else 0.0
                ),
                "Mean_Sheep_Energy": lambda m: (
                    float(
                        np.mean([a.energy for a in m.agents.select(agent_type=Sheep)])
                    )
                    if len(m.agents.select(agent_type=Sheep)) > 0
                    else 0.0
                ),
            }
        )

    def _place_agents(self) -> None:
        cfg = self.config

        # Place one GrassPatch per cell
        # Note: coord_iter() yields (cell_contents, (x, y)) in Mesa 3.x;
        # iterating x/y directly is simpler and version-safe.
        for x in range(cfg.width):
            for y in range(cfg.height):
                fully_grown = self.random.random() < 0.5
                countdown = (
                    0
                    if fully_grown
                    else self.random.randrange(cfg.grass_regrowth_time)
                )
                patch = GrassPatch(self, fully_grown=fully_grown, countdown=countdown)
                self.grid.place_agent(patch, (x, y))

        # Place Sheep at random positions
        for _ in range(cfg.initial_sheep):
            x = self.random.randrange(cfg.width)
            y = self.random.randrange(cfg.height)
            sheep = Sheep(self, energy=cfg.initial_sheep_energy)
            self.grid.place_agent(sheep, (x, y))

        # Place Wolves at random positions
        for _ in range(cfg.initial_wolves):
            x = self.random.randrange(cfg.width)
            y = self.random.randrange(cfg.height)
            wolf = Wolf(self, energy=cfg.initial_wolf_energy)
            self.grid.place_agent(wolf, (x, y))

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(self) -> None:
        """
        Advance the model by one step.

        Step order:
          1. Sheep shuffle and step (move, eat, metabolise, die, reproduce)
          2. Wolves shuffle and step (move, hunt, metabolise, die, reproduce)
          3. GrassPatches step (deterministic countdown / regrow)
          4. DataCollector collects
          5. RuntimeMonitor checks for extinctions
        """
        self.agents.select(agent_type=Sheep).shuffle_do("step")
        self.agents.select(agent_type=Wolf).shuffle_do("step")
        self.agents.select(agent_type=GrassPatch).do("step")
        self.datacollector.collect(self)
        self.monitor.check()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_results(self) -> pd.DataFrame:
        """Returns datacollector output as a clean DataFrame indexed by step."""
        return self.datacollector.get_model_vars_dataframe()

    def is_extinct(self) -> bool:
        """True if any species has gone extinct."""
        return self.monitor.any_extinct
