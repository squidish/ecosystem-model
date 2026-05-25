"""
Service layer for running EcosystemModel.

This is the ONLY interface the frontend and notebooks use to run the model.
It isolates model internals from UI concerns.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from model.config import EcosystemConfig
from model.ecosystem import EcosystemModel


@dataclass
class RunConfig:
    """Parameters for a single simulation run."""

    ecosystem_config: EcosystemConfig
    n_steps: int = 300
    seed: int = 42
    stop_on_extinction: bool = True


@dataclass
class RunResult:
    """Output of a completed simulation run."""

    config: RunConfig
    data: pd.DataFrame          # step-indexed datacollector output
    extinction_events: List[str]
    steps_completed: int
    terminated_early: bool
    # Reference to the final model state (for grid visualisation in notebooks)
    model: Optional[EcosystemModel] = field(default=None, repr=False)


class SimulationRunner:
    """
    Runs EcosystemModel and returns a RunResult.

    Handles extinction, step limits, and error recovery.
    The frontend and notebooks import only this class — never EcosystemModel directly.

    Usage:
        runner = SimulationRunner()
        result = runner.run(RunConfig(EcosystemConfig(), n_steps=200))
        print(result.data.head())
    """

    def run(self, run_config: RunConfig) -> RunResult:
        """Run a single simulation and return a RunResult."""
        model = EcosystemModel(
            config=run_config.ecosystem_config, seed=run_config.seed
        )
        terminated_early = False

        for _ in range(run_config.n_steps):
            model.step()
            if run_config.stop_on_extinction and model.is_extinct():
                terminated_early = True
                break

        return RunResult(
            config=run_config,
            data=model.get_results(),
            extinction_events=list(model.monitor.extinction_events),
            steps_completed=model.steps,
            terminated_early=terminated_early,
            model=model,
        )

    def run_sweep(
        self,
        base_config: EcosystemConfig,
        param_name: str,
        param_values: list,
        n_steps: int = 300,
        seeds: Optional[List[int]] = None,
    ) -> List[RunResult]:
        """
        Run the model once per param_value; return a list of RunResults.

        If seeds is provided, runs len(seeds) replicates per value so callers
        can compute mean ± std across replicates. Results are ordered as:
            [value_0_seed_0, value_0_seed_1, ..., value_1_seed_0, ...]

        Args:
            base_config: Base EcosystemConfig. The swept parameter is overridden
                         per iteration using dataclasses.replace.
            param_name: Name of the EcosystemConfig field to sweep, e.g.
                        "sheep_reproduce".
            param_values: List of values to try.
            n_steps: Steps per run.
            seeds: List of RNG seeds. Defaults to [42] (single replicate).

        Returns:
            List of RunResult, length = len(param_values) * len(seeds).

        Used by notebook 02 for parameter sensitivity analysis.
        """
        import dataclasses

        if seeds is None:
            seeds = [42]

        results: List[RunResult] = []
        for value in param_values:
            sweep_config = dataclasses.replace(base_config, **{param_name: value})
            for seed in seeds:
                rc = RunConfig(
                    ecosystem_config=sweep_config,
                    n_steps=n_steps,
                    seed=seed,
                    stop_on_extinction=True,
                )
                results.append(self.run(rc))
        return results
