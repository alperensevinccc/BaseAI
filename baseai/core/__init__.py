from typing import Optional


def validate_api_key(api_key: Optional[str]) -> None:
    """Validates that the API key is provided.

    Args:
        api_key: The API key to validate.

    Raises:
        ValueError: If the API key is None or an empty string.
    """
    if not api_key:
        raise ValueError("ERROR: Missing required config: GEMINI_API_KEY")


__all__ = ["validate_api_key"]
