import os
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from tests.factories.v2 import V2Factory


def _local_test_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL is not configured for a disposable local V2 test database")
    parsed = urlparse(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("fixture integration tests refuse non-local PostgreSQL")
    if parsed.path.removeprefix("/") not in {"lifemanager_test", "lifemanager_v2_test"}:
        pytest.skip("fixture integration tests require an allowlisted disposable database")
    return url


def test_canonical_dataset_satisfies_postgresql_constraints() -> None:
    engine = sa.create_engine(_local_test_url())
    try:
        with Session(engine) as db, db.begin():
            dataset = V2Factory(db).build_canonical_dataset()
            assert len(dataset.tasks) == 6
            assert len(dataset.activities) == 4
            db.connection().exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
            db.rollback()
    finally:
        engine.dispose()
