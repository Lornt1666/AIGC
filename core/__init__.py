"""Shared AIGC core package spanning runtime and src-layout modules.

The runtime coordinator lives in this directory while the existing kernel modules
live under src/core. Extend the package search path so both sets are importable
without ambiguous namespace-package resolution during pytest and deployment.
"""
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
