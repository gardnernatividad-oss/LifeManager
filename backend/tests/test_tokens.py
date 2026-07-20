import unittest

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt

from app.core.config import settings
from app.core.tokens import create_access_token, decode_access_token


class AccessTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings_patch = patch.multiple(
            settings,
            SECRET_KEY="test-secret-key-that-is-at-least-32-bytes",
            ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=30,
        )
        self.settings_patch.start()

    def tearDown(self) -> None:
        self.settings_patch.stop()

    def decode_claims_without_expiration_check(self, token: str) -> dict[str, object]:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )

    def encode_claims(self, claims: dict[str, object], *, key: str | None = None) -> str:
        return jwt.encode(
            claims,
            key or settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

    def test_token_creation_returns_string(self) -> None:
        self.assertIsInstance(create_access_token(subject="user-id"), str)

    def test_valid_token_returns_subject(self) -> None:
        token = create_access_token(subject="user-id")

        self.assertEqual(decode_access_token(token), "user-id")

    def test_custom_expiration_is_honored(self) -> None:
        before = datetime.now(timezone.utc)
        token = create_access_token(
            subject="user-id",
            expires_delta=timedelta(minutes=5),
        )
        after = datetime.now(timezone.utc)
        expiration = datetime.fromtimestamp(
            self.decode_claims_without_expiration_check(token)["exp"],
            timezone.utc,
        )

        self.assertGreaterEqual(
            expiration,
            before + timedelta(minutes=5, seconds=-1),
        )
        self.assertLessEqual(expiration, after + timedelta(minutes=5))

    def test_default_expiration_uses_configured_minutes(self) -> None:
        settings.ACCESS_TOKEN_EXPIRE_MINUTES = 12
        before = datetime.now(timezone.utc)
        token = create_access_token(subject="user-id")
        after = datetime.now(timezone.utc)
        expiration = datetime.fromtimestamp(
            self.decode_claims_without_expiration_check(token)["exp"],
            timezone.utc,
        )

        self.assertGreaterEqual(
            expiration,
            before + timedelta(minutes=12, seconds=-1),
        )
        self.assertLessEqual(expiration, after + timedelta(minutes=12))

    def test_expired_token_returns_none(self) -> None:
        token = create_access_token(
            subject="user-id",
            expires_delta=timedelta(seconds=-1),
        )

        self.assertIsNone(decode_access_token(token))

    def test_malformed_token_returns_none(self) -> None:
        self.assertIsNone(decode_access_token("not-a-jwt"))

    def test_token_signed_with_another_key_returns_none(self) -> None:
        token = self.encode_claims(
            {
                "sub": "user-id",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "type": "access",
            },
            key="another-secret-key-that-is-at-least-32-bytes",
        )

        self.assertIsNone(decode_access_token(token))

    def test_missing_subject_returns_none(self) -> None:
        token = self.encode_claims(
            {
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "type": "access",
            }
        )

        self.assertIsNone(decode_access_token(token))

    def test_empty_subject_returns_none(self) -> None:
        token = self.encode_claims(
            {
                "sub": "",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "type": "access",
            }
        )

        self.assertIsNone(decode_access_token(token))

    def test_wrong_token_type_returns_none(self) -> None:
        token = self.encode_claims(
            {
                "sub": "user-id",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "type": "refresh",
            }
        )

        self.assertIsNone(decode_access_token(token))


if __name__ == "__main__":
    unittest.main()
