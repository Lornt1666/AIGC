"""Core kernel utilities for the AIGC local runtime.

The repository contains runtime modules in the root ``core`` package and kernel
modules under ``src/core``. Extend this package path as well as the root package
so test collection order cannot hide runtime modules when ``src/core`` is imported
first. This only affects module discovery; it does not import or execute agents.
"""
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
