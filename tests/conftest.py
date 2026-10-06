from __future__ import annotations

# Isolated test contexts intentionally bypass product-package readiness unless
# an integration test opts in explicitly. Production create_context stays strict.
import uebench.bootstrap as _bootstrap

_production_create_context = _bootstrap.create_context

def _create_isolated_test_context(*args, **kwargs):
    kwargs.setdefault("enforce_standard_library_readiness", False)
    return _production_create_context(*args, **kwargs)

_bootstrap.create_context = _create_isolated_test_context
