import unittest
import uuid

from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, User, WorkspaceMember
from app.models.workspace_member import WorkspaceRole
from app.schemas import CategoryCreate, CategoryUpdate
from app.services.category_service import (
    CategoryNameConflictError,
    CategoryNotFoundError,
    CategoryPermissionError,
    activate_category,
    create_category,
    deactivate_category,
    get_category,
    list_categories,
    normalize_category_name,
    update_category,
)


class CategoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock(spec=Session)
        self.workspace_id = uuid.uuid4()
        self.user = User(id=uuid.uuid4())
        self.membership = WorkspaceMember(
            workspace_id=self.workspace_id,
            user_id=self.user.id,
            role=WorkspaceRole.MEMBER,
        )

    def membership_patch(self, membership: WorkspaceMember | None = None):
        return patch(
            "app.services.category_service.get_workspace_membership",
            return_value=self.membership if membership is None else membership,
        )

    def make_category(self, **overrides: object) -> Category:
        values: dict[str, object] = {
            "id": uuid.uuid4(),
            "workspace_id": self.workspace_id,
            "name": "Trabajo",
            "normalized_name": "trabajo",
            "description": None,
            "is_active": True,
        }
        values.update(overrides)
        return Category(**values)

    def test_normalization_cleans_visible_name_and_preserves_accents(self) -> None:
        self.assertEqual(
            normalize_category_name("  Trabajo   Personal "),
            ("Trabajo Personal", "trabajo personal"),
        )
        self.assertEqual(
            normalize_category_name("Tecnología"),
            ("Tecnología", "tecnología"),
        )
        self.assertEqual(
            normalize_category_name("Tecnologi\u0301a"),
            ("Tecnología", "tecnología"),
        )
        self.assertNotEqual(
            normalize_category_name("Tecnología")[1],
            normalize_category_name("Tecnologia")[1],
        )

    def test_create_stores_clean_and_normalized_name_without_committing(self) -> None:
        self.db.scalar.return_value = None
        with self.membership_patch():
            category = create_category(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
                category_in=CategoryCreate(name=" Trabajo   Personal "),
            )

        self.assertEqual(category.name, "Trabajo Personal")
        self.assertEqual(category.normalized_name, "trabajo personal")
        self.assertTrue(category.is_active)
        self.db.add.assert_called_once_with(category)
        self.db.flush.assert_called_once_with()
        self.db.commit.assert_not_called()
        self.db.rollback.assert_not_called()

    def test_duplicate_normalizations_in_same_workspace_are_rejected(self) -> None:
        for name in ("Trabajo", "TRABAJO", "  Trabajo   "):
            self.db.reset_mock()
            self.db.scalar.return_value = uuid.uuid4()
            with (
                self.subTest(name=name),
                self.membership_patch(),
                self.assertRaises(CategoryNameConflictError),
            ):
                create_category(
                    self.db,
                    workspace_id=self.workspace_id,
                    current_user=self.user,
                    category_in=CategoryCreate(name=name),
                )
            self.db.add.assert_not_called()

    def test_same_name_query_is_scoped_to_requested_workspace(self) -> None:
        other_workspace_id = uuid.uuid4()
        self.db.scalar.return_value = None
        membership = WorkspaceMember(
            workspace_id=other_workspace_id,
            user_id=self.user.id,
            role=WorkspaceRole.MEMBER,
        )

        with patch(
            "app.services.category_service.get_workspace_membership",
            return_value=membership,
        ):
            category = create_category(
                self.db,
                workspace_id=other_workspace_id,
                current_user=self.user,
                category_in=CategoryCreate(name="Trabajo"),
            )

        statement = self.db.scalar.call_args.args[0]
        self.assertIn(other_workspace_id, statement.compile().params.values())
        self.assertEqual(category.workspace_id, other_workspace_id)

    def test_integrity_error_race_is_translated(self) -> None:
        self.db.scalar.return_value = None
        original_error = MagicMock()
        original_error.diag.constraint_name = (
            "uq_categories_workspace_id_normalized_name"
        )
        self.db.flush.side_effect = IntegrityError(
            "duplicate",
            params={},
            orig=original_error,
        )

        with self.membership_patch(), self.assertRaisesRegex(
            CategoryNameConflictError,
            "Category name already exists",
        ):
            create_category(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
                category_in=CategoryCreate(name="Trabajo"),
            )

    def test_list_all_active_and_inactive_is_scoped_and_ordered(self) -> None:
        expected = [self.make_category(), self.make_category(name="Familia")]
        self.db.scalars.return_value.all.return_value = expected

        for active in (None, True, False):
            self.db.reset_mock()
            self.db.scalars.return_value.all.return_value = expected
            with self.subTest(active=active), self.membership_patch():
                result = list_categories(
                    self.db,
                    workspace_id=self.workspace_id,
                    current_user=self.user,
                    active=active,
                )

            statement = self.db.scalars.call_args.args[0]
            sql = str(statement)
            self.assertIn(self.workspace_id, statement.compile().params.values())
            self.assertIn(
                "ORDER BY categories.normalized_name, categories.name, categories.id",
                sql,
            )
            if active is None:
                self.assertNotIn("categories.is_active IS", sql)
            else:
                self.assertIn(f"categories.is_active IS {str(active).lower()}", sql)
            self.assertEqual(result, expected)
            self.db.commit.assert_not_called()
            self.db.flush.assert_not_called()

    def test_get_is_scoped_and_inactive_category_remains_readable(self) -> None:
        category = self.make_category(is_active=False)
        self.db.scalar.return_value = category
        with self.membership_patch():
            result = get_category(
                self.db,
                workspace_id=self.workspace_id,
                category_id=category.id,
                current_user=self.user,
            )

        statement = self.db.scalar.call_args.args[0]
        parameters = statement.compile().params.values()
        self.assertIn(self.workspace_id, parameters)
        self.assertIn(category.id, parameters)
        self.assertIs(result, category)

    def test_cross_workspace_or_missing_category_raises_not_found(self) -> None:
        self.db.scalar.return_value = None
        with self.membership_patch(), self.assertRaises(CategoryNotFoundError):
            get_category(
                self.db,
                workspace_id=self.workspace_id,
                category_id=uuid.uuid4(),
                current_user=self.user,
            )

    def test_update_cleans_fields_and_equivalent_self_name_succeeds(self) -> None:
        category = self.make_category()
        self.db.scalar.return_value = category
        with self.membership_patch():
            result = update_category(
                self.db,
                workspace_id=self.workspace_id,
                category_id=category.id,
                current_user=self.user,
                category_in=CategoryUpdate(
                    name="  TRABAJO ",
                    description="Updated",
                ),
            )

        self.assertIs(result, category)
        self.assertEqual(category.name, "TRABAJO")
        self.assertEqual(category.normalized_name, "trabajo")
        self.assertEqual(category.description, "Updated")
        self.db.scalar.assert_called_once()
        self.db.flush.assert_called_once_with()

    def test_update_to_another_category_name_fails(self) -> None:
        category = self.make_category()
        self.db.scalar.side_effect = [category, uuid.uuid4()]
        with self.membership_patch(), self.assertRaises(CategoryNameConflictError):
            update_category(
                self.db,
                workspace_id=self.workspace_id,
                category_id=category.id,
                current_user=self.user,
                category_in=CategoryUpdate(name="Personal"),
            )
        self.db.flush.assert_not_called()

    def test_activation_and_deactivation_are_idempotent(self) -> None:
        category = self.make_category(is_active=True)
        self.db.scalar.return_value = category
        with self.membership_patch():
            deactivate_category(
                self.db,
                workspace_id=self.workspace_id,
                category_id=category.id,
                current_user=self.user,
            )
        self.assertFalse(category.is_active)
        self.db.flush.assert_called_once_with()

        self.db.reset_mock()
        self.db.scalar.return_value = category
        with self.membership_patch():
            deactivate_category(
                self.db,
                workspace_id=self.workspace_id,
                category_id=category.id,
                current_user=self.user,
            )
        self.db.flush.assert_not_called()

        with self.membership_patch():
            activate_category(
                self.db,
                workspace_id=self.workspace_id,
                category_id=category.id,
                current_user=self.user,
            )
        self.assertTrue(category.is_active)
        self.db.flush.assert_called_once_with()

        self.db.reset_mock()
        self.db.scalar.return_value = category
        with self.membership_patch():
            activate_category(
                self.db,
                workspace_id=self.workspace_id,
                category_id=category.id,
                current_user=self.user,
            )
        self.db.flush.assert_not_called()

    def test_nonmember_is_denied_without_writes(self) -> None:
        with (
            patch(
                "app.services.category_service.get_workspace_membership",
                return_value=None,
            ),
            self.assertRaises(CategoryPermissionError),
        ):
            list_categories(
                self.db,
                workspace_id=self.workspace_id,
                current_user=self.user,
            )
        self.db.add.assert_not_called()
        self.db.flush.assert_not_called()
        self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
