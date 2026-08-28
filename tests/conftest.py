"""Shared pytest fixtures."""

import gc

import pytest


@pytest.fixture(autouse=True)
def _collect_sqlite_connections() -> None:
    yield
    gc.collect()
