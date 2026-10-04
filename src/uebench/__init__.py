"""Unit-product energy benchmarking application."""

from __future__ import annotations

from ._version import __version__

#: Version of the rule/calculator engine semantics, independent of the product
#: version.  Bumped only when rule evaluation semantics change.
RULE_ENGINE_VERSION = "1.0"

__all__ = ["__version__", "RULE_ENGINE_VERSION"]
