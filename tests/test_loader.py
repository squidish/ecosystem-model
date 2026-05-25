"""Tests for DataLoader."""

import os
import tempfile

import pandas as pd
import pytest

from data.loader import DataLoader


@pytest.fixture
def loader():
    return DataLoader()


@pytest.fixture
def sample_csv(tmp_path):
    path = str(tmp_path / "birds.csv")
    loader = DataLoader()
    loader.generate_sample_data(path)
    return path


def test_load_valid_csv(loader, sample_csv):
    df = loader.load_csv(sample_csv)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert set(df["role"].unique()).issubset({"predator", "prey"})


def test_load_missing_columns_raises_valueerror_with_message(loader, tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("species,role\nSparrowhawk,predator\n")
    with pytest.raises(ValueError) as exc_info:
        loader.load_csv(str(bad_csv))
    msg = str(exc_info.value)
    assert "Missing required columns" in msg
    # Should list the missing columns
    assert "observed_count" in msg or "breeding_pairs" in msg


def test_load_file_not_found_raises(loader):
    with pytest.raises(FileNotFoundError):
        loader.load_csv("/nonexistent/path/birds.csv")


def test_generate_sample_data_creates_file(loader, tmp_path):
    path = str(tmp_path / "sub" / "sample.csv")
    loader.generate_sample_data(path)
    assert os.path.exists(path)
    df = pd.read_csv(path)
    assert len(df) == 3


def test_to_species_configs_returns_correct_roles(loader, sample_csv):
    df = loader.load_csv(sample_csv)
    configs = loader.to_species_configs(df)
    roles = [c.role for c in configs]
    assert "predator" in roles
    assert "prey" in roles


def test_to_species_configs_predators_first(loader, sample_csv):
    df = loader.load_csv(sample_csv)
    configs = loader.to_species_configs(df)
    # All predators should precede all prey
    seen_prey = False
    for c in configs:
        if c.role == "prey":
            seen_prey = True
        if seen_prey and c.role == "predator":
            pytest.fail("Predator found after prey in ordered list")


def test_load_invalid_role_raises(loader, tmp_path):
    bad_csv = tmp_path / "bad_role.csv"
    bad_csv.write_text(
        "species,role,observed_count,breeding_pairs,territory_km2,year,source\n"
        "Eagle,apex,100,50,10.0,2023,BTO\n"
    )
    with pytest.raises(ValueError, match="Invalid role values"):
        loader.load_csv(str(bad_csv))
