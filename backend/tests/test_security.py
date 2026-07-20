import unittest

from app.core.security import hash_password, verify_password


class PasswordSecurityTests(unittest.TestCase):
    def test_hash_differs_from_plain_password(self) -> None:
        password = "correct horse battery staple"

        self.assertNotEqual(hash_password(password), password)

    def test_same_password_produces_different_hashes(self) -> None:
        password = "correct horse battery staple"

        self.assertNotEqual(hash_password(password), hash_password(password))

    def test_verify_succeeds_for_matching_password(self) -> None:
        password = "correct horse battery staple"

        self.assertTrue(verify_password(password, hash_password(password)))

    def test_verify_fails_for_incorrect_password(self) -> None:
        hashed_password = hash_password("correct password")

        self.assertFalse(verify_password("incorrect password", hashed_password))

    def test_empty_password_is_supported(self) -> None:
        hashed_password = hash_password("")

        self.assertNotEqual(hashed_password, "")
        self.assertTrue(verify_password("", hashed_password))

    def test_invalid_hash_returns_false(self) -> None:
        self.assertFalse(verify_password("password", "not-a-valid-password-hash"))


if __name__ == "__main__":
    unittest.main()
