import unittest

from pydantic import ValidationError
from sqlalchemy import CheckConstraint

from app.models import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceTimezoneTests(unittest.TestCase):
    def test_model_default_server_default_and_nonblank_constraint(self) -> None:
        column = Workspace.__table__.c.timezone
        self.assertEqual(column.type.length, 100); self.assertFalse(column.nullable)
        self.assertEqual(column.default.arg, "America/Lima")
        self.assertIn("America/Lima", str(column.server_default.arg))
        self.assertIn("ck_workspaces_timezone_not_blank", {item.name for item in Workspace.__table__.constraints if isinstance(item, CheckConstraint)})

    def test_schema_defaults_and_validates_iana_timezone(self) -> None:
        self.assertEqual(WorkspaceCreate(name="Home").timezone, "America/Lima")
        self.assertEqual(WorkspaceCreate(name="Home", timezone="America/New_York").timezone, "America/New_York")
        self.assertEqual(WorkspaceUpdate(timezone="Europe/Madrid").timezone, "Europe/Madrid")
        for schema, payload in ((WorkspaceCreate, {"name": "Home", "timezone": ""}), (WorkspaceUpdate, {"timezone": None}), (WorkspaceUpdate, {"timezone": "Bad/Zone"})):
            with self.subTest(payload=payload), self.assertRaises(ValidationError): schema.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
