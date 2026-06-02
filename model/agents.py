"""
Agent definitions for the Wolf-Sheep predator-prey ecosystem model.

Step order (enforced by EcosystemModel.step):
  1. Sheep shuffle_do("step")   — move, eat grass, lose energy, die, reproduce
  2. Wolf  shuffle_do("step")   — move, eat sheep, lose energy, die, reproduce
  3. GrassPatch do("step")      — countdown, regrow (deterministic, order irrelevant)
  4. DataCollector.collect()

This ordering matters ecologically: sheep graze before wolves hunt, which
prevents wolves from always intercepting freshly-moved sheep.
"""

from mesa import Agent


class GrassPatch(Agent):
    """
    Represents a single grid cell's vegetation.

    Ecological role: primary producer. Provides energy to Sheep when fully grown.
    Regrows deterministically after grass_regrowth_time steps — no stochastic
    element, so model.random is not needed here.

    Attributes:
        fully_grown: Whether the patch currently has grass available to eat.
        countdown: Steps remaining before the patch regrows (0 when fully grown).
    """

    def __init__(self, model, fully_grown: bool, countdown: int) -> None:
        super().__init__(model)
        self.fully_grown = fully_grown
        self.countdown = countdown

    def step(self) -> None:
        if not self.fully_grown:
            if self.countdown <= 0:
                self.fully_grown = True
                self.countdown = 0
            else:
                self.countdown -= 1


class Sheep(Agent):
    """
    Prey agent. Ecological role: primary consumer.

    Behaviour per step:
      1. Move to a random adjacent cell (Moore neighbourhood, torus grid).
      2. Eat grass on the current cell if fully grown
         (gain sheep_gain_from_food energy; grass begins regrowing).
      3. Lose 1 energy (metabolic cost of existing).
      4. Die if energy <= 0.
      5. Reproduce with probability sheep_reproduce: offspring placed on the
         same cell, parent energy split equally (conservation of energy).

    Always uses self.random (bound to model.random) for all stochastic decisions.

    Attributes:
        energy: Current energy level. Agent dies when this reaches 0 or below.
    """

    def __init__(self, model, energy: int) -> None:
        super().__init__(model)
        self.energy = energy

    def remove(self) -> None:
        self.model.grid.remove_agent(self)
        super().remove()

    def step(self) -> None:
        self._move()
        self._eat_grass()
        self.energy -= 1
        if self.energy <= 0:
            self.remove()
            return
        self._reproduce()

    def _move(self) -> None:
        possible = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=False
        )
        new_pos = self.random.choice(possible)
        self.model.grid.move_agent(self, new_pos)

    def _eat_grass(self) -> None:
        cell_contents = self.model.grid.get_cell_list_contents([self.pos])
        grass_patches = [obj for obj in cell_contents if isinstance(obj, GrassPatch)]
        if grass_patches:
            patch = grass_patches[0]
            if patch.fully_grown:
                self.energy += self.model.config.sheep_gain_from_food
                patch.fully_grown = False
                patch.countdown = self.model.config.grass_regrowth_time

    def _reproduce(self) -> None:
        if self.random.random() < self.model.config.sheep_reproduce:
            self.energy = self.energy // 2
            offspring = Sheep(self.model, energy=self.energy)
            self.model.grid.place_agent(offspring, self.pos)


class Wolf(Agent):
    """
    Predator agent. Ecological role: secondary consumer.

    Behaviour per step:
      1. Move to a random adjacent cell (Moore neighbourhood, torus grid).
      2. Eat a randomly selected Sheep on the current cell if any are present
         (gain wolf_gain_from_food energy; the eaten Sheep is removed).
      3. Lose 1 energy (metabolic cost).
      4. Die if energy <= 0.
      5. Reproduce with probability wolf_reproduce: offspring placed on the
         same cell, parent energy split equally (conservation of energy).

    Always uses self.random (bound to model.random) for all stochastic decisions.

    Attributes:
        energy: Current energy level. Agent dies when this reaches 0 or below.
    """

    def __init__(self, model, energy: int) -> None:
        super().__init__(model)
        self.energy = energy

    def remove(self) -> None:
        self.model.grid.remove_agent(self)
        super().remove()

    def step(self) -> None:
        self._move()
        self._eat_sheep()
        self.energy -= 1
        if self.energy <= 0:
            self.remove()
            return
        self._reproduce()

    def _move(self) -> None:
        possible = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=False
        )
        new_pos = self.random.choice(possible)
        self.model.grid.move_agent(self, new_pos)

    def _eat_sheep(self) -> None:
        cell_contents = self.model.grid.get_cell_list_contents([self.pos])
        sheep_here = [obj for obj in cell_contents if isinstance(obj, Sheep)]
        if sheep_here:
            target = self.random.choice(sheep_here)
            self.energy += self.model.config.wolf_gain_from_food
            target.remove()

    def _reproduce(self) -> None:
        if self.random.random() < self.model.config.wolf_reproduce:
            self.energy = self.energy // 2
            offspring = Wolf(self.model, energy=self.energy)
            self.model.grid.place_agent(offspring, self.pos)
