from __future__ import annotations
import os
import sys
from baseai.log.logger import core_logger as log


class ConfigAuditor:
    """Audit BaseAI runtime environment and configuration."""

    REQUIRED_ENV_VARS = [
        "OPENAI_API_KEY",
    ]

    OPTIONAL_ENV_VARS = [
        "GEMINI_API_KEY",
        "BASEAI_DISABLE_GEMINI",
    ]

    @classmethod
    def audit(cls) -> None:
        """Validate environment configuration and raise if invalid."""
        missing = [v for v in cls.REQUIRED_ENV_VARS if not os.getenv(v)]
        if missing:
            log.error(f"❌ Missing critical environment variables: {missing}")
            raise EnvironmentError(f"Missing required config(s): {missing}")

        if os.getenv("BASEAI_DISABLE_GEMINI") == "1":
            log.info("🧩 Gemini bridge disabled via BASEAI_DISABLE_GEMINI.")
        elif not os.getenv("GEMINI_API_KEY"):
            log.warning("⚠️ GEMINI_API_KEY not set — Gemini bridge may be unavailable.")
        else:
            log.info("✅ Gemini API key validated successfully.")

        log.info("✅ Environment configuration audit passed.")


def run_audit() -> None:
    """Entry point for auditor CLI or module execution."""
    try:
        ConfigAuditor.audit()
    except Exception as exc:
        log.exception(f"Configuration audit failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    run_audit()
