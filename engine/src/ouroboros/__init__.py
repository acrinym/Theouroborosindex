"""Ouroboros repository-composition analyzer."""

from importlib.metadata import PackageNotFoundError, version

from .analyze import analyze_repository

__all__ = ["analyze_repository"]

try:
    __version__ = version("repo-ouroboros")
except PackageNotFoundError:
    __version__ = "0.5.0.dev0"
