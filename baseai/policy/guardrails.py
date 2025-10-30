"""
Module for handling guardrails policy configuration.

This module provides mechanisms to enforce guardrails through configuration validation.
"""

import os


class GuardrailsConfigError(Exception):
    """Custom exception for guardrails configuration errors."""

    pass


def get_api_key() -> str:
    """
    Retrieve the GEMINI API key from environment variables.

    Raises:
        GuardrailsConfigError: If the GEMINI_API_KEY is not set.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GuardrailsConfigError("Missing required config: GEMINI_API_KEY")
    return api_key


def validate_guardrails_config() -> None:
    """
    Validates if the guardrails configuration is set up correctly.

    Raises:
        GuardrailsConfigError: If required configurations are missing.
    """
    get_api_key()  # validate presence of GEMINI_API_KEY


def main() -> None:
    """
    Main entry point for guardrails validation script.
    """
    try:
        validate_guardrails_config()
        print("Guardrails configuration is valid.")
    except GuardrailsConfigError as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
