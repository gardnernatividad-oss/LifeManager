import unicodedata


class NameValidationError(ValueError):
    pass


def normalize_name(
    value: str,
    *,
    max_length: int,
    field_label: str,
) -> tuple[str, str]:
    visible_name = unicodedata.normalize("NFC", " ".join(value.split()))
    if not visible_name:
        raise NameValidationError(f"{field_label} name cannot be blank")

    normalized_name = unicodedata.normalize("NFC", visible_name.casefold())
    if len(visible_name) > max_length or len(normalized_name) > max_length:
        raise NameValidationError(
            f"{field_label} name must not exceed {max_length} characters"
        )
    return visible_name, normalized_name
