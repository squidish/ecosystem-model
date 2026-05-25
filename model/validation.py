from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

from .config import EcosystemConfig

if TYPE_CHECKING:
    from .agents import Wolf, Sheep


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    warnings: List[str]


class ConfigValidator:
    """Validates EcosystemConfig before a run starts."""

    def validate(self, config: EcosystemConfig) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        # Hard errors
        total_agents = config.initial_sheep + config.initial_wolves
        total_cells = config.width * config.height
        if total_agents > total_cells:
            errors.append(
                f"Too many agents ({total_agents}) for grid size ({total_cells} cells). "
                f"Reduce initial populations or increase grid size."
            )
        if not 0 < config.sheep_reproduce <= 1:
            errors.append("sheep_reproduce must be between 0 and 1 exclusive.")
        if not 0 < config.wolf_reproduce <= 1:
            errors.append("wolf_reproduce must be between 0 and 1 exclusive.")
        if config.width < 5 or config.height < 5:
            errors.append("Grid must be at least 5x5.")

        # Warnings (non-fatal)
        if config.initial_wolves == 0:
            warnings.append("No wolves: predator-prey dynamics will not occur.")
        if config.initial_sheep == 0:
            warnings.append("No sheep: wolves will immediately starve.")
        if config.wolf_gain_from_food < config.sheep_gain_from_food:
            warnings.append(
                "Wolf gain_from_food is less than sheep gain_from_food — "
                "wolves will likely go extinct quickly."
            )
        if config.grass_regrowth_time > 100:
            warnings.append(
                "Very long grass regrowth time may cause sheep starvation cascades."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


class RuntimeMonitor:
    """
    Checks for extinction events and other runtime conditions during a model run.
    Call check() after each model step.
    """

    def __init__(self, model: "EcosystemModel") -> None:  # noqa: F821
        self.model = model
        self.extinction_events: List[str] = []

    def check(self) -> dict:
        from .agents import Wolf, Sheep

        status = {
            "wolves_alive": True,
            "sheep_alive": True,
            "step": self.model.steps,
        }
        if len(self.model.agents.select(agent_type=Wolf)) == 0:
            if "wolves" not in self.extinction_events:
                self.extinction_events.append("wolves")
            status["wolves_alive"] = False
        if len(self.model.agents.select(agent_type=Sheep)) == 0:
            if "sheep" not in self.extinction_events:
                self.extinction_events.append("sheep")
            status["sheep_alive"] = False
        return status

    @property
    def any_extinct(self) -> bool:
        return len(self.extinction_events) > 0
