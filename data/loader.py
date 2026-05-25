"""
CSV/JSON loader for bird species observation data.

Expected CSV format
-------------------
species,role,observed_count,breeding_pairs,territory_km2,year,source
Sparrowhawk,predator,1200,450,0.5,2023,BTO
Blue Tit,prey,3400000,1200000,0.01,2023,BTO
House Sparrow,prey,5100000,1800000,0.005,2023,RSPB

Columns:
  species        : str  — common name
  role           : str  — "predator" or "prey"
  observed_count : int  — total individuals observed in survey area
  breeding_pairs : int  — confirmed breeding pairs
  territory_km2  : float — mean territory size in km²
  year           : int  — survey year
  source         : str  — data source (BTO, RSPB, GBIF, etc.)
"""

import os
from typing import List

import pandas as pd

from model.config import BirdSpeciesConfig
from data.calibration import (
    scale_initial_count,
    scale_reproduce_rate,
    scale_gain_from_food,
)

_GRID_CELLS_DEFAULT = 50 * 50  # 2500 cells for a default 50x50 grid


class DataLoader:
    """
    Loads bird species observation data and converts to BirdSpeciesConfig.

    Column validation is strict: if any required column is missing, raises a
    descriptive ValueError listing the missing columns and the expected format.
    """

    REQUIRED_COLUMNS = {
        "species",
        "role",
        "observed_count",
        "breeding_pairs",
        "territory_km2",
        "year",
    }

    EXPECTED_FORMAT = (
        "Expected CSV columns: species, role, observed_count, "
        "breeding_pairs, territory_km2, year, source\n"
        "Example row: Sparrowhawk,predator,1200,450,0.5,2023,BTO"
    )

    def load_csv(self, path: str) -> pd.DataFrame:
        """
        Load and validate a bird data CSV.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If required columns are missing, with a message listing
                        which columns are absent and the expected format.

        Returns:
            Validated DataFrame with correct dtypes.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Bird data file not found: {path}")

        df = pd.read_csv(path)

        # Strip whitespace from column names and string values
        df.columns = [c.strip() for c in df.columns]
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].str.strip()

        missing = self.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing required columns: {sorted(missing)}\n{self.EXPECTED_FORMAT}"
            )

        # Validate role values
        invalid_roles = df[~df["role"].isin(["predator", "prey"])]["role"].unique()
        if len(invalid_roles) > 0:
            raise ValueError(
                f"Invalid role values: {list(invalid_roles)}. "
                f"Allowed values: 'predator', 'prey'."
            )

        # Coerce numeric columns
        for col in ["observed_count", "breeding_pairs", "year"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df["territory_km2"] = pd.to_numeric(df["territory_km2"], errors="coerce").fillna(0.01)

        return df

    def to_species_configs(
        self,
        df: pd.DataFrame,
        grid_cells: int = _GRID_CELLS_DEFAULT,
    ) -> List[BirdSpeciesConfig]:
        """
        Convert each row of a validated DataFrame to a BirdSpeciesConfig.

        Uses calibration functions to derive model parameters from field data.
        Returns the list ordered: predators first, then prey.

        Args:
            df: DataFrame returned by load_csv().
            grid_cells: Total grid cells for density scaling (default 2500).

        Returns:
            List[BirdSpeciesConfig] ordered predators first.
        """
        configs: List[BirdSpeciesConfig] = []

        for _, row in df.iterrows():
            role = row["role"]
            gain = scale_gain_from_food(float(row["territory_km2"]), role)
            reproduce = scale_reproduce_rate(
                int(row["breeding_pairs"]), int(row["observed_count"])
            )
            count = scale_initial_count(int(row["observed_count"]), grid_cells)
            # Initial energy set to 3x gain_from_food — gives agents enough runway
            # to act before their first feeding opportunity.
            initial_energy = max(1, gain * 3)

            configs.append(
                BirdSpeciesConfig(
                    name=str(row["species"]),
                    role=role,
                    initial_count=count,
                    reproduce_rate=reproduce,
                    gain_from_food=gain,
                    initial_energy=initial_energy,
                    source_file=None,
                )
            )

        # Sort: predators first, then prey
        configs.sort(key=lambda c: (0 if c.role == "predator" else 1, c.name))
        return configs

    def generate_sample_data(self, output_path: str) -> None:
        """
        Write sample_bird_data.csv with 3 UK species for testing.

        Species chosen to represent a simple predator-prey system:
          - Sparrowhawk (predator): small raptor, feeds on passerines
          - Blue Tit (prey): abundant garden bird, seed/insect feeder
          - House Sparrow (prey): very common urban passerine, seed feeder

        Data sourced from BTO BirdFacts and RSPB species explorer (2023 estimates).
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        sample = pd.DataFrame(
            [
                {
                    "species": "Sparrowhawk",
                    "role": "predator",
                    "observed_count": 35000,
                    "breeding_pairs": 35000,
                    "territory_km2": 6.0,
                    "year": 2023,
                    "source": "BTO",
                },
                {
                    "species": "Blue Tit",
                    "role": "prey",
                    "observed_count": 3400000,
                    "breeding_pairs": 1700000,
                    "territory_km2": 0.01,
                    "year": 2023,
                    "source": "BTO",
                },
                {
                    "species": "House Sparrow",
                    "role": "prey",
                    "observed_count": 5100000,
                    "breeding_pairs": 1800000,
                    "territory_km2": 0.005,
                    "year": 2023,
                    "source": "RSPB",
                },
            ]
        )
        sample.to_csv(output_path, index=False)
