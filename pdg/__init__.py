"""pdg — a graph-based product design, prototype and development workflow (Context → … → Iteration)."""

import sys

# The package lives in a shared tree that other runs and commits read (backlog N-12): importing it turns bytecode off, so
# only this file's own cache can appear, and `python -B -m pdg` writes none at all.
sys.dont_write_bytecode = True

__version__ = "1.0.0"
