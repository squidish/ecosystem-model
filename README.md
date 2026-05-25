# ecosystem-model

An agent-based predator-prey ecosystem model built on [Mesa 3.1.0](https://mesa.readthedocs.io/), designed as a scientific prototype for exploring ecosystem dynamics. The model is extensible toward real ecological data — specifically UK bird population data from BTO and RSPB.

## 1. Overview and Goals

The model implements a classic Lotka-Volterra style simulation on a toroidal grid:

- **GrassPatch** agents (primary producers) regrow deterministically
- **Sheep** agents (primary consumers) graze grass and are hunted by wolves
- **Wolf** agents (secondary consumers) hunt sheep and reproduce stochastically

The data layer maps real bird observation CSV data (species counts, breeding pairs, territory sizes) to model parameters via documented calibration functions, so the model can be initialised from field data rather than arbitrary defaults.

---

## 2. Install

```bash
pip install -r requirements.txt
```

All dependency versions are pinned. Python 3.10+ recommended.

---

## 3. Run Tests

```bash
pytest tests/ --cov=model --cov=simulation --cov=data -v
```

Target: 80%+ coverage across model, simulation, and data layers.

---

## 4. Run Notebooks

```bash
jupyter notebook
```

Open notebooks in order:

| Notebook | Content |
|---|---|
| `01_baseline_model.ipynb` | Default run, phase plane, grid visualisation, extinction experiment |
| `02_parameter_sweep.ipynb` | Single-parameter sweep with error bands; 2D stability heatmap |
| `03_bird_data.ipynb` | Load CSV, calibrate parameters, compare baseline vs bird-derived run |

---

## 5. Run Frontend

```bash
panel serve frontend/app.py --show
```

Opens a browser with:
- **Sidebar**: parameter sliders, bird CSV loader, Run/Export buttons
- **Population tab**: interactive Plotly line chart
- **Grid tab**: final agent positions (Plotly scatter)
- **Summary tab**: key statistics table

---

## 6. Bird Data Format

The loader expects a CSV with these exact columns:

```
species,role,observed_count,breeding_pairs,territory_km2,year,source
```

| Column | Type | Description |
|---|---|---|
| `species` | str | Common name, e.g. "Sparrowhawk" |
| `role` | str | `"predator"` or `"prey"` |
| `observed_count` | int | Total individuals in survey |
| `breeding_pairs` | int | Confirmed breeding pairs |
| `territory_km2` | float | Mean territory size in km² |
| `year` | int | Survey year |
| `source` | str | Data source (BTO, RSPB, GBIF…) |

Example rows:

```csv
Sparrowhawk,predator,35000,35000,6.0,2023,BTO
Blue Tit,prey,3400000,1700000,0.01,2023,BTO
House Sparrow,prey,5100000,1800000,0.005,2023,RSPB
```

Generate a sample file:

```python
from data.loader import DataLoader
DataLoader().generate_sample_data("data/sample/sample_bird_data.csv")
```

---

## 7. Extending the Model

### a. Adding a third species (apex predator)

Create an `ApexPredator` class in `model/agents.py` following the `Wolf` pattern. In `ecosystem.py`, add a third shuffle-step phase after wolves. Add `initial_apex_predators` to `EcosystemConfig`. Update `DataCollector` reporters.

### b. Adding seasonal grass regrowth

In `GrassPatch.step()`, read `model.steps % 52` to determine season. Multiply `countdown` by a seasonal factor (e.g. 3× in winter). Add a `season_factor` list to `EcosystemConfig`.

### c. Spatial habitat heterogeneity

Replace the uniform `GrassPatch` initialisation in `EcosystemModel._place_agents()` with a heterogeneity map (e.g. loaded from a numpy array or GeoTIFF). Cells marked "rock" or "water" never grow grass and agents cannot enter them.

### d. Connecting to GBIF API for live occurrence data

```python
import requests
url = "https://api.gbif.org/v1/occurrence/search"
params = {"scientificName": "Accipiter nisus", "country": "GB", "limit": 300}
r = requests.get(url, params=params)
records = r.json()["results"]
```

Map occurrence lat/lon to grid cells using a bounding box transform. See [GBIF API docs](https://www.gbif.org/developer/summary).

### e. Agent trait variation for simple evolution experiments

Give each `Sheep` a `speed` trait (1 or 2 cells per step) drawn from `model.random`. Wolves that eat fast sheep gain more energy. Over generations, track mean speed via `DataCollector`. This implements a rudimentary predator-driven selection pressure.

---

## 8. Data Sources

| Source | URL | Content |
|---|---|---|
| BTO BirdFacts | https://www.bto.org/our-science/data | Breeding population estimates, survival rates, territory sizes |
| RSPB Species Explorer | https://www.rspb.org.uk/birds-and-wildlife/wildlife-guides/bird-a-z/ | Species profiles, habitat, diet |
| GBIF Occurrence API | https://www.gbif.org/developer/summary | Georeferenced occurrence records |
| BirdTrack | https://www.bto.org/our-science/projects/birdtrack | Seasonal migration and count data |
