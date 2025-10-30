"""Verifies that the required GEMINI_API_KEY is available."""

import os
import sys
from typing import Optional


def check_required_config(api_key: Optional[str]) -> None:
    """Checks for the presence of the Gemini API key.

    Args:
        api_key: The Gemini API key to check.

    Raises:
        ValueError: If the API key is not provided.
    """
    if not api_key:
        raise ValueError("Missing required config: GEMINI_API_KEY")


def main(api_key: Optional[str] = None) -> None:
    """Main entry point for the application.

    Args:
        api_key: The Gemini API key.
    """
    check_required_config(api_key)
    print("GEMINI_API_KEY is configured successfully.")
    # Additional application logic goes here.


if __name__ == "__main__":
    # Prioritize API key from environment variable, fallback to command-line argument.
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key and len(sys.argv) > 1:
        gemini_api_key = sys.argv[1]

    try:
        main(api_key=gemini_api_key)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
