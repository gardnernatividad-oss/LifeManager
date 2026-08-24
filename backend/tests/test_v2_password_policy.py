import pytest

from app.core.password_policy import (
    MAX_PASSWORD_LENGTH,
    PasswordPolicyError,
    validate_password_policy,
)


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("Short1!", "password_too_short"),
        ("lowercase!", "password_uppercase_required"),
        ("UPPERCASE!", "password_lowercase_required"),
        ("NoSymbols1", "password_symbol_required"),
        ("Valid1!" + "a" * MAX_PASSWORD_LENGTH, "password_too_long"),
    ],
)
def test_password_policy_rejects_each_missing_requirement(
    password: str,
    code: str,
) -> None:
    with pytest.raises(PasswordPolicyError) as rejected:
        validate_password_policy(password)
    assert code in {violation.code for violation in rejected.value.violations}
    assert password not in str(rejected.value)


@pytest.mark.parametrize(
    "password",
    [
        "ValidPwd!",
        "NoDigitRequired!",
        "ÁrbolSeguro!",
        " SecurePwd! ",
    ],
)
def test_password_policy_accepts_unicode_no_digit_and_exact_whitespace(
    password: str,
) -> None:
    assert validate_password_policy(password) == password


def test_spaces_do_not_count_as_symbols() -> None:
    with pytest.raises(PasswordPolicyError) as rejected:
        validate_password_policy("Password 1")
    assert "password_symbol_required" in {
        violation.code for violation in rejected.value.violations
    }
