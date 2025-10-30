"""Monitors and manages live refactor operations.

This module validates the necessary environment configuration for the live
refactor watchdog service and provides an entry point to start the service.
"""

import logging
import os
import sys
from typing import Optional

# Module-level constant for the environment variable name.
_GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"


def get_gemini_api_key() -> Optional[str]:
    """Retrieves the Gemini API key from environment variables.

    Returns:
        The API key if set, otherwise None.
    """
    return os.getenv(_GEMINI_API_KEY_ENV_VAR)


def validate_environment() -> None:
    """Validates that all required environment variables are set.

    Raises:
        EnvironmentError: If a required environment variable is missing.
    """
    if get_gemini_api_key() is None:
        raise EnvironmentError(f"Missing required config: {_GEMINI_API_KEY_ENV_VAR}")


def main() -> int:
    """Initializes and runs the live refactor watchdog.

    Sets up logging, validates the environment, and starts the monitoring
    service.

    Returns:
        0 on success, 1 on configuration error.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    try:
        validate_environment()
        logging.info("Environment validated successfully.")
        logging.info("Starting the monitoring service...")
        # Placeholder for the main monitoring loop or service initialization.
        return 0
    except EnvironmentError as e:
        logging.error("Failed to start service: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
