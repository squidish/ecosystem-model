# Design & Technical Notes

## What this is

An agent-based predator-prey model built on [Mesa 3.1.0](https://mesa.readthedocs.io/), designed as a scientific prototype for exploring ecosystem dynamics. The immediate subject is a classic Wolf-Sheep-Grass system; the longer-term goal is to run it against real UK bird population data (BTO/RSPB/GBIF) so the parameters mean something ecologically.

---

## Architecture overview

```
frontend/app.py          ← Panel UI (sliders, charts, CSV upload)
        │
        ▼
simulation/runner.py     ← service layer (the only public interface to the model)
        │
        ▼
model/ecosystem.py       ← Mesa Model class
model/agents.py          ← GrassPatch, Sheep, Wolf
model/config.py          ← EcosystemConfig dataclass
model/validation.py      ← ConfigValidator, RuntimeMonitor
        │
data/loader.py           ← CSV ingestion and validation
data/calibration.py      ← observation data → model parameters
data/sample/             ← sample UK bird CSV (Sparrowhawk, Blue Tit, House Sparrow)
```

The rule is: **nothing above the runner layer imports from `model/` directly.** The frontend and notebooks talk to `SimulationRunner`; only the runner touches the model internals. This keeps the UI decoupled from Mesa's API so either side can change without breaking the other.

---

## Model mechanics

### Agents

Three agent types on a toroidal `MultiGrid`:

**GrassPatch** — one per cell, always. Flips between `fully_grown=True` (edible) and a countdown state. Regrowth is deterministic: once eaten, the patch counts down from `grass_regrowth_time` to zero then regrows. No randomness here — the stochasticity in grass coverage comes entirely from which cells sheep happen to move to.

**Sheep** (primary consumer) — per step: move to a random Moore-neighbourhood cell, eat grass if present (gaining `sheep_gain_from_food` energy), pay 1 energy metabolic cost, die if energy ≤ 0, reproduce with probability `sheep_reproduce` (parent energy splits equally with offspring — conservation of energy).

**Wolf** (secondary consumer) — identical structure, but hunts a randomly chosen Sheep on the current cell rather than grazing, gaining `wolf_gain_from_food` energy per kill.

### Step order

```
1. Sheep  shuffle_do("step")     — graze before being hunted
2. Wolves shuffle_do("step")     — hunt after sheep have moved
3. GrassPatch  do("step")        — deterministic, order irrelevant
4. DataCollector.collect()
5. RuntimeMonitor.check()
```

Sheep move and eat *before* wolves hunt. This is an explicit ecological choice: it prevents wolves from always intercepting freshly-repositioned sheep, which would artificially inflate predation rates. The shuffle (randomised activation order within each species) prevents any one agent from systematically getting first-mover advantage.

### RNG discipline

All randomness goes through `self.random` (Mesa's seeded RNG, bound per-agent as `self.random = model.random`). `numpy` operations use a separate `model.np_random = np.random.default_rng(seed)` seeded from the same value. Python's built-in `random` module is never used. This makes runs fully reproducible from a single integer seed.

---

## Design choices

### Dataclass config with upfront validation

`EcosystemConfig` is a plain `@dataclass` — no hidden state, trivially serialisable, easy to `dataclasses.replace()` for sweeps. `ConfigValidator` runs before the model touches the grid, so you get a clear `ValueError` with a human-readable message rather than a cryptic Mesa error mid-run.

Hard errors (too many agents for the grid, invalid probability values) raise and abort. Warnings (no wolves, wolf gain < sheep gain) print but allow the run — sometimes you *want* a degenerate configuration to study collapse dynamics.

### Service layer pattern

`SimulationRunner` exists so that callers never need to know about Mesa's internal API. The frontend and notebooks import `RunConfig` and `RunResult` — plain dataclasses — and call `runner.run()`. This means:
- The UI can be rewritten without touching the model
- The model can be swapped for a different Mesa version without touching the UI
- `RunResult` carries a reference to the final model object (for grid visualisation in notebooks) but callers can ignore it

### Calibration is explicit, not automatic

`data/calibration.py` contains the mapping from real field data (observed counts, breeding pairs, territory sizes) to model parameters. Every function documents the ecological assumption it encodes. The design intention is that a biologist should be able to read those docstrings, disagree with an assumption, and override a single value — rather than having magic numbers buried in the code.

The calibration chain:
```
observed_count   → scale_initial_count()   → initial_wolves / initial_sheep
breeding_pairs   → scale_reproduce_rate()  → wolf_reproduce / sheep_reproduce
territory_km2    → scale_gain_from_food()  → wolf_gain_from_food / sheep_gain_from_food
gain_from_food   → ×3                      → initial_wolf_energy / initial_sheep_energy
```

Log-scaling is used for counts and territory sizes because ecological data spans many orders of magnitude (35,000 Sparrowhawks vs 5,100,000 House Sparrows). Linear scaling would either starve the grid with tiny predator counts or overflow it with prey.

### MultiGrid over SingleGrid

`MultiGrid` allows multiple agents to occupy the same cell. This is ecologically correct — a wolf and a sheep can be on the same patch, and predation happens within the cell. `SingleGrid` would force artificial spatial separation and distort predation rates.

The grid is toroidal (`torus=True`) to eliminate boundary effects. Agents that reach an edge wrap around rather than being reflected or stopped, which keeps the spatial statistics uniform across the grid.

### Extinction detection

`RuntimeMonitor` runs after every step and appends to `extinction_events` the first time a species count hits zero. The runner checks `model.is_extinct()` and can terminate early (`stop_on_extinction=True`). This is separate from the model itself deliberately — the model doesn't know about simulation policies, only the runner does.

---

## What the Mesa 3.1.0 API looks like

Mesa 3.x replaced the old scheduler system. Key differences from older examples you'll find online:

| Old (Mesa 2.x) | New (Mesa 3.1.0) |
|---|---|
| `self.schedule = RandomActivationByType(self)` | No scheduler object |
| `self.schedule.step()` | `self.agents.select(agent_type=X).shuffle_do("step")` |
| `self.schedule.agents_by_type[Wolf]` | `self.agents.select(agent_type=Wolf)` |
| `self.schedule.time` | `self.steps` (built-in) |

`coord_iter()` in Mesa 3.x returns `(cell_contents, (x, y))` not `(x, y)` — a common gotcha when porting examples. This project iterates coordinates as `range(width) × range(height)` to avoid the ambiguity entirely.

---

## Testing approach

45 tests across four modules, targeting 80%+ coverage:

- **test_model.py** — black-box tests: does the model initialise with the right counts, is it reproducible, do populations stay non-negative?
- **test_agents.py** — white-box tests: call `_eat_grass()`, `_eat_sheep()`, `_reproduce()` directly to verify energy arithmetic without running a full model step
- **test_runner.py** — service layer tests: does the runner terminate on extinction, does `run_sweep` return the right number of results?
- **test_calibration.py** — boundary tests: do scaling functions clamp correctly, does `build_ecosystem_config_from_birds` raise on missing species?
- **test_loader.py** — validation tests: missing columns, bad role values, file-not-found

Fixtures create small grids (10×10, 15×15) to keep tests fast. The extinction test forces collapse by setting `wolf_gain_from_food=0` rather than waiting for a stochastic extinction event, making it deterministic.

---

## Extending the model

**Third species (apex predator):** Add an `ApexPredator` class in `agents.py` following the Wolf pattern. Add a fourth `shuffle_do` phase in `ecosystem.step()` after wolves. Add fields to `EcosystemConfig` and a new `DataCollector` reporter.

**Seasonal grass regrowth:** In `GrassPatch.step()`, multiply `countdown` by a factor derived from `model.steps % 52` (treating each step as one week). Add a `season_factors: list[float]` field to `EcosystemConfig`.

**Spatial heterogeneity:** Replace the uniform grid initialisation in `_place_agents()` with a habitat map (numpy array loaded from file). Some cells could be permanently bare, permanently fertile, or have different regrowth rates.

**Live GBIF data:** The `DataLoader.load_csv()` interface is format-stable. A `DataLoader.load_gbif(taxon_key, country)` method could hit `https://api.gbif.org/v1/occurrence/search`, aggregate by species and return the same DataFrame format that `to_species_configs()` expects.

**Agent trait variation / evolution:** Give each `Sheep` a `speed` attribute (1 or 2 cells per move) drawn at birth. Track mean speed in `DataCollector`. Wolves that eat fast sheep gain a bonus. Over generations this produces observable selection pressure — a simple evolutionary experiment without changing the model architecture.

---

## Data sources for real runs

| Source | What it provides |
|---|---|
| [BTO BirdFacts](https://www.bto.org/our-science/data) | Breeding population estimates, survival rates, territory sizes |
| [RSPB Species Explorer](https://www.rspb.org.uk/birds-and-wildlife/wildlife-guides/bird-a-z/) | Diet, habitat, population trends |
| [GBIF Occurrence API](https://www.gbif.org/developer/summary) | Georeferenced occurrence records for density mapping |
| [BirdTrack](https://www.bto.org/our-science/projects/birdtrack) | Seasonal migration and count data |
