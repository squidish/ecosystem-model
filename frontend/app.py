"""
Panel-based interactive frontend for the ecosystem model.

Run with:
    panel serve frontend/app.py --show

Imports ONLY from simulation.runner and data.loader — no direct model imports.
"""

import io
import datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import panel as pn

from simulation.runner import SimulationRunner, RunConfig, RunResult
from model.config import EcosystemConfig
from data.loader import DataLoader
from data.calibration import build_ecosystem_config_from_birds

pn.extension("plotly", sizing_mode="stretch_width")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_runner = SimulationRunner()
_loader = DataLoader()
_last_result: Optional[RunResult] = None
_bird_configs = []

# ---------------------------------------------------------------------------
# Sidebar widgets — Model Parameters
# ---------------------------------------------------------------------------

sheep_slider = pn.widgets.IntSlider(
    name="Initial Sheep", start=10, end=500, value=100
)
wolves_slider = pn.widgets.IntSlider(
    name="Initial Wolves", start=5, end=200, value=50
)
sheep_reproduce_slider = pn.widgets.FloatSlider(
    name="Sheep Reproduce Rate", start=0.01, end=0.2, step=0.01, value=0.04
)
wolf_reproduce_slider = pn.widgets.FloatSlider(
    name="Wolf Reproduce Rate", start=0.01, end=0.2, step=0.01, value=0.05
)
grass_regrowth_slider = pn.widgets.IntSlider(
    name="Grass Regrowth Time", start=5, end=100, value=30
)
steps_slider = pn.widgets.IntSlider(
    name="Steps to Run", start=50, end=1000, value=300
)
seed_input = pn.widgets.IntInput(name="Random Seed", value=42)

# ---------------------------------------------------------------------------
# Sidebar widgets — Bird Data
# ---------------------------------------------------------------------------

file_input = pn.widgets.FileInput(name="Load Bird CSV", accept=".csv")
load_status = pn.widgets.StaticText(name="", value="No file loaded.")
apply_bird_data_button = pn.widgets.Button(
    name="Apply to Sliders", button_type="success", disabled=True
)

# ---------------------------------------------------------------------------
# Sidebar widgets — Actions
# ---------------------------------------------------------------------------

run_button = pn.widgets.Button(name="Run Simulation", button_type="primary")
export_button = pn.widgets.Button(
    name="Export CSV", button_type="default", disabled=True
)
status_text = pn.widgets.StaticText(name="", value="Ready.")

# ---------------------------------------------------------------------------
# Tab content placeholders
# ---------------------------------------------------------------------------

population_pane = pn.pane.Plotly(
    go.Figure(layout=go.Layout(title="Run a simulation to see results.")),
    sizing_mode="stretch_width",
    height=500,
)
grid_pane = pn.pane.Plotly(
    go.Figure(layout=go.Layout(title="Run a simulation to see grid state.")),
    sizing_mode="stretch_width",
    height=500,
)
summary_pane = pn.widgets.DataFrame(
    pd.DataFrame(columns=["Metric", "Value"]),
    sizing_mode="stretch_width",
)

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def _build_eco_config() -> EcosystemConfig:
    return EcosystemConfig(
        initial_sheep=sheep_slider.value,
        initial_wolves=wolves_slider.value,
        sheep_reproduce=sheep_reproduce_slider.value,
        wolf_reproduce=wolf_reproduce_slider.value,
        grass_regrowth_time=grass_regrowth_slider.value,
        seed=seed_input.value,
    )


def _population_figure(result: RunResult) -> go.Figure:
    df = result.data
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["Wolves"], name="Wolves",
        line=dict(color="red"), hovertemplate="Step %{x}<br>Wolves: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["Sheep"], name="Sheep",
        line=dict(color="steelblue"), hovertemplate="Step %{x}<br>Sheep: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["Grass_Coverage_Pct"], name="Grass Coverage %",
        line=dict(color="green", dash="dash"),
        hovertemplate="Step %{x}<br>Grass: %{y:.1f}%<extra></extra>",
    ))
    for event in result.extinction_events:
        fig.add_vline(
            x=result.steps_completed,
            line_dash="dot", line_color="black",
            annotation_text=f"{event.capitalize()} extinct",
        )
    fig.update_layout(
        title="Population Dynamics",
        xaxis_title="Step",
        yaxis_title="Count / %",
        legend=dict(orientation="h"),
        hovermode="x unified",
    )
    return fig


def _grid_figure(result: RunResult) -> go.Figure:
    if result.model is None:
        return go.Figure(layout=go.Layout(title="Grid state unavailable."))

    model = result.model
    from model.agents import Wolf, Sheep, GrassPatch

    wolves = model.agents.select(agent_type=Wolf)
    sheep = model.agents.select(agent_type=Sheep)
    grass = [a for a in model.agents.select(agent_type=GrassPatch) if a.fully_grown]

    # Sample grass to avoid overplotting
    import random
    sample_size = max(1, len(grass) // 5)
    grass_sample = random.sample(grass, min(sample_size, len(grass)))

    fig = go.Figure()

    if grass_sample:
        gx, gy = zip(*[a.pos for a in grass_sample])
        fig.add_trace(go.Scatter(
            x=gx, y=gy, mode="markers", name="Grass (20% sample)",
            marker=dict(symbol="square", color="lightgreen", size=6, opacity=0.5),
        ))

    if sheep:
        sx, sy = zip(*[a.pos for a in sheep])
        fig.add_trace(go.Scatter(
            x=sx, y=sy, mode="markers", name="Sheep",
            marker=dict(symbol="circle", color="steelblue", size=8),
        ))

    if wolves:
        wx, wy = zip(*[a.pos for a in wolves])
        fig.add_trace(go.Scatter(
            x=wx, y=wy, mode="markers", name="Wolves",
            marker=dict(symbol="triangle-up", color="red", size=10),
        ))

    extinction_str = (
        f" | Extinct: {', '.join(result.extinction_events)}"
        if result.extinction_events else ""
    )
    fig.update_layout(
        title=f"Grid State — Step {result.steps_completed}{extinction_str}",
        xaxis_title="X", yaxis_title="Y",
        xaxis=dict(range=[-1, model.config.width]),
        yaxis=dict(range=[-1, model.config.height]),
    )
    return fig


def _summary_df(result: RunResult, seed: int) -> pd.DataFrame:
    wolf_peak_step = int(result.data["Wolves"].idxmax())
    sheep_peak_step = int(result.data["Sheep"].idxmax())
    rows = [
        ("Steps Completed", result.steps_completed),
        ("Final Wolf Count", int(result.data["Wolves"].iloc[-1])),
        ("Final Sheep Count", int(result.data["Sheep"].iloc[-1])),
        (f"Peak Wolf Count (step {wolf_peak_step})", int(result.data["Wolves"].max())),
        (f"Peak Sheep Count (step {sheep_peak_step})", int(result.data["Sheep"].max())),
        ("Grass Coverage at End (%)", round(float(result.data["Grass_Coverage_Pct"].iloc[-1]), 1)),
        ("Extinction Events", ", ".join(result.extinction_events) or "None"),
        ("Seed Used", seed),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def on_run_clicked(event):
    global _last_result
    status_text.value = "Running…"
    export_button.disabled = True
    try:
        eco_cfg = _build_eco_config()
        rc = RunConfig(
            ecosystem_config=eco_cfg,
            n_steps=steps_slider.value,
            seed=seed_input.value,
            stop_on_extinction=True,
        )
        result = _runner.run(rc)
        _last_result = result

        population_pane.object = _population_figure(result)
        grid_pane.object = _grid_figure(result)
        summary_pane.value = _summary_df(result, seed_input.value)

        ext_msg = (
            f" (extinct: {', '.join(result.extinction_events)})"
            if result.extinction_events else ""
        )
        status_text.value = f"Done — {result.steps_completed} steps{ext_msg}."
        export_button.disabled = False
    except Exception as exc:
        status_text.value = f"Error: {exc}"


def on_export_clicked(event):
    global _last_result
    if _last_result is None:
        return
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"ecosystem_results_{seed_input.value}_{ts}.csv"
    _last_result.data.to_csv(path)
    status_text.value = f"Exported to {path}"


def on_file_loaded(event):
    global _bird_configs
    if file_input.value is None:
        return
    try:
        content = io.BytesIO(file_input.value)
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(content.read())
            tmp_path = tmp.name
        df = _loader.load_csv(tmp_path)
        os.unlink(tmp_path)
        _bird_configs = _loader.to_species_configs(df)
        names = [c.name for c in _bird_configs]
        load_status.value = f"Loaded: {', '.join(names)}"
        apply_bird_data_button.disabled = False
    except Exception as exc:
        load_status.value = f"Error: {exc}"
        apply_bird_data_button.disabled = True


def on_apply_bird_data(event):
    global _bird_configs
    if not _bird_configs:
        return
    try:
        cfg = build_ecosystem_config_from_birds(_bird_configs)
        sheep_slider.value = min(cfg.initial_sheep, sheep_slider.end)
        wolves_slider.value = min(cfg.initial_wolves, wolves_slider.end)
        sheep_reproduce_slider.value = round(
            max(sheep_reproduce_slider.start,
                min(sheep_reproduce_slider.end, cfg.sheep_reproduce)), 2
        )
        wolf_reproduce_slider.value = round(
            max(wolf_reproduce_slider.start,
                min(wolf_reproduce_slider.end, cfg.wolf_reproduce)), 2
        )
        load_status.value = load_status.value + " — applied to sliders."
    except Exception as exc:
        load_status.value = f"Apply error: {exc}"


run_button.on_click(on_run_clicked)
export_button.on_click(on_export_clicked)
file_input.param.watch(on_file_loaded, "value")
apply_bird_data_button.on_click(on_apply_bird_data)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

sidebar = pn.Accordion(
    (
        "Model Parameters",
        pn.Column(
            sheep_slider, wolves_slider,
            sheep_reproduce_slider, wolf_reproduce_slider,
            grass_regrowth_slider, steps_slider, seed_input,
        ),
    ),
    (
        "Bird Data",
        pn.Column(file_input, load_status, apply_bird_data_button),
    ),
    active=[0],
)

tabs = pn.Tabs(
    ("Population", population_pane),
    ("Grid", grid_pane),
    ("Summary", summary_pane),
)

template = pn.template.FastListTemplate(
    title="Ecosystem Model",
    sidebar=[sidebar, pn.layout.Divider(), run_button, export_button, status_text],
    main=[tabs],
)

template.servable()
