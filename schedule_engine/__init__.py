"""CSUB freshman block-schedule engine.

Pipeline: extract (E3E4 -> section catalog) -> generate (5-10 cohort blocks
as a JSON artifact) -> validate (deterministic checks) -> chat (Claude edits
the artifact under counselor constraints, validator keeps it honest).
"""

__version__ = "0.1.0"
