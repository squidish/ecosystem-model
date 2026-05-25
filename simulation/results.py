"""
ResultSet: lightweight wrapper around DataCollector output.
Kept separate so callers can work with results without importing Mesa.
"""

from dataclasses import dataclass
from typing import List

import pandas as pd


@dataclass
class ResultSet:
    """
    Wraps the datacollector DataFrame with convenience properties.

    Attributes:
        data: Step-indexed DataFrame with columns:
              Wolves, Sheep, Grass_Coverage_Pct,
              Mean_Wolf_Energy, Mean_Sheep_Energy
        steps_completed: Total steps the model ran.
        extinction_events: Species names that went extinct, e.g. ["wolves"].
    """

    data: pd.DataFrame
    steps_completed: int
    extinction_events: List[str]

    @property
    def peak_wolves(self) -> int:
        return int(self.data["Wolves"].max())

    @property
    def peak_sheep(self) -> int:
        return int(self.data["Sheep"].max())

    @property
    def final_wolves(self) -> int:
        return int(self.data["Wolves"].iloc[-1])

    @property
    def final_sheep(self) -> int:
        return int(self.data["Sheep"].iloc[-1])

    @property
    def final_grass_pct(self) -> float:
        return float(self.data["Grass_Coverage_Pct"].iloc[-1])

    def summary_dict(self) -> dict:
        """Returns a flat dict suitable for display in a DataFrame widget."""
        wolf_peak_step = int(self.data["Wolves"].idxmax())
        sheep_peak_step = int(self.data["Sheep"].idxmax())
        return {
            "Steps Completed": self.steps_completed,
            "Final Wolf Count": self.final_wolves,
            "Final Sheep Count": self.final_sheep,
            f"Peak Wolves (step {wolf_peak_step})": self.peak_wolves,
            f"Peak Sheep (step {sheep_peak_step})": self.peak_sheep,
            "Grass Coverage at End (%)": round(self.final_grass_pct, 1),
            "Extinction Events": ", ".join(self.extinction_events) or "None",
        }
