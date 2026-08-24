from dataclasses import dataclass


MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


@dataclass(frozen=True)
class PasswordPolicyViolation:
    code: str
    message: str


class PasswordPolicyError(ValueError):
    def __init__(self, violations: tuple[PasswordPolicyViolation, ...]) -> None:
        self.violations = violations
        super().__init__(violations[0].message)


def validate_password_policy(password: str) -> str:
    """Validate the exact submitted password without normalizing it."""
    violations: list[PasswordPolicyViolation] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        violations.append(
            PasswordPolicyViolation(
                "password_too_short",
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.",
            )
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        violations.append(
            PasswordPolicyViolation(
                "password_too_long",
                f"La contraseña no debe exceder {MAX_PASSWORD_LENGTH} caracteres.",
            )
        )
    if not any(character.isupper() for character in password):
        violations.append(
            PasswordPolicyViolation(
                "password_uppercase_required",
                "La contraseña debe incluir al menos una letra mayúscula.",
            )
        )
    if not any(character.islower() for character in password):
        violations.append(
            PasswordPolicyViolation(
                "password_lowercase_required",
                "La contraseña debe incluir al menos una letra minúscula.",
            )
        )
    if not any(
        not character.isalnum() and not character.isspace()
        for character in password
    ):
        violations.append(
            PasswordPolicyViolation(
                "password_symbol_required",
                "La contraseña debe incluir al menos un símbolo.",
            )
        )
    if violations:
        raise PasswordPolicyError(tuple(violations))
    return password
