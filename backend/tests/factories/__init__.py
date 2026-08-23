"""Reusable V2 test-data factories.

Factories in this package only use a caller-provided SQLAlchemy session. They
never create an engine and never commit or roll back a transaction.
"""

from tests.factories.v2 import (
    CanonicalV2Dataset,
    PersonalWorkspaceScenario,
    SharedWorkspaceScenario,
    V2Factory,
)

__all__ = [
    "CanonicalV2Dataset",
    "PersonalWorkspaceScenario",
    "SharedWorkspaceScenario",
    "V2Factory",
]
