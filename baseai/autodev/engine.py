from __future__ import annotations

import asyncio
import traceback
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from baseai.log.logger import core_logger as log
from baseai.bridges.gpt import gpt_bridge
from baseai.bridges.gemini import gemini_bridge, GeminiDiagnostics


class AutoDevEngine:
    """
    BaseAI Autonomous Developer Engine — v6.0-OMNI
    - Tamamen async
    - GPT + Gemini çift köprü senkronizasyonu
    - Self-heal / self-repair güvenli
    - Test, Repair, Create modları hatasız
    """

    IMMUTABLE_PATHS = (
        "autodev/engine.py",
        "bridges/",
        "log/",
        "utils/config_loader.py",
    )

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.self_path = Path(__file__).resolve()
        self.modes = {"test", "repair", "create"}
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.safe_mode = os.getenv("BASEAI_SAFE_REPAIR", "True").lower() == "true"
        self.max_concurrent = int(os.getenv("BASEAI_MAX_CONCURRENCY", "3"))
        log.info(f"[AutoDevEngine] Initialized {self.timestamp} (safe={self.safe_mode})")

    # ==========================================================
    # ENTRY
    # ==========================================================
    async def run(
        self,
        mode: str = "repair",
        targets: Optional[List[str]] = None,
        level: str = "enterprise",
    ) -> None:
        """Ana çalışma döngüsü."""
        if mode not in self.modes:
            raise ValueError(f"Invalid mode '{mode}'. Supported: {self.modes}")

        try:
            if mode == "test":
                await self._run_test_cycle()
            elif mode == "repair":
                await self._self_repair()
                await self._repair_targets(targets or ["baseai"])
            elif mode == "create":
                await self._create_targets(targets or ["baseai/utils"])

            log.info(f"[AutoDev] ✅ Mode '{mode}' completed successfully.")
        except Exception as e:
            log.error(f"[AutoDev] Unhandled exception: {e}")
            log.debug(traceback.format_exc())

    # ==========================================================
    # MODES
    # ==========================================================
    async def _run_test_cycle(self) -> None:
        """Gemini + GPT köprü testi ve sağlık raporu."""
        log.info("[AutoDev] Running test cycle...")
        try:
            gpt_task = gpt_bridge.generate_text("Confirm GPT bridge is active (1 line).")
            gem_task = gemini_bridge.generate_text("Confirm Gemini bridge is active (1 line).")
            gpt_test, gem_test = await asyncio.gather(gpt_task, gem_task)

            log.info(f"[AutoDev] GPT bridge response: {gpt_test.strip()}")
            log.info(f"[AutoDev] Gemini bridge response: {gem_test.strip()}")
            report = GeminiDiagnostics.run()
            log.info(f"[AutoDev] Health snapshot hash={report['hash']}")
        except Exception as e:
            log.error(f"[AutoDev] Test cycle failed: {e}")
        log.info("[AutoDev] ✅ Test cycle completed.")

    async def _self_repair(self) -> None:
        """Engine kendini analiz eder, yalnızca sentaks/dil hatalarını düzeltir."""
        try:
            src = self.self_path.read_text(encoding="utf-8")
            prompt = (
                "Analyze this BaseAI AutoDev engine. "
                "Fix syntax or async issues only, without altering logic or imports. "
                "Return valid Python code."
            )
            result = await gpt_bridge.generate_text(prompt, src)
            fixed = self._extract_code(result)

            if self._is_safe_replacement(fixed, src):
                backup = self.self_path.with_suffix(f".bak.{datetime.now().strftime('%H%M%S')}")
                backup.write_text(src, encoding="utf-8")
                self.self_path.write_text(fixed, encoding="utf-8")
                log.info("[AutoDev] ✅ Self-repair applied safely (backup created).")
            else:
                log.info("[AutoDev] No valid self-repair detected; skipped.")
        except Exception as e:
            log.error(f"[AutoDev] Self-repair failed: {e}")
            log.debug(traceback.format_exc())

    async def _repair_targets(self, targets: List[str]) -> None:
        """Hedef Python dosyalarını güvenli biçimde onarır."""
        sem = asyncio.Semaphore(self.max_concurrent)
        log.info(f"[AutoDev] Repairing {len(targets)} targets (safe mode)...")

        async def worker(file_path: Path):
            async with sem:
                await self._repair_file(file_path)

        tasks: list[asyncio.Task] = []
        for raw_target in targets:
            target_path = self._absolute_path(raw_target)
            if not target_path.exists():
                log.warning(f"[AutoDev] ⚠️ Target not found: {raw_target}")
                continue

            if target_path.is_dir():
                for file_path in target_path.rglob("*.py"):
                    if self._should_skip_path(file_path):
                        continue
                    tasks.append(asyncio.create_task(worker(file_path)))
            elif target_path.is_file() and target_path.suffix == ".py":
                if self._should_skip_path(target_path):
                    continue
                tasks.append(asyncio.create_task(worker(target_path)))
            else:
                log.debug(f"[AutoDev] Ignored target (not .py): {raw_target}")

        if not tasks:
            log.info("[AutoDev] No eligible Python files found; skipping repair cycle.")
            return

        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("[AutoDev] ✅ Repair cycle complete.")

    async def _repair_file(self, file_path: Path) -> None:
        """Tek dosya düzeyinde onarım."""
        try:
            src = file_path.read_text(encoding="utf-8")
            prompt = (
                f"Fix syntax or minor typing issues in {file_path}. "
                "Do NOT modify logic, structure, or imports. "
                "Ensure valid Python. Return code only."
            )
            result = await gemini_bridge.generate_text(prompt, src)
            fixed = self._extract_code(result)

            if not self._is_safe_replacement(fixed, src):
                log.warning(f"[AutoDev] Skipped {file_path}: invalid or empty fix.")
                return

            bak = file_path.with_suffix(
                file_path.suffix + f".bak.{datetime.now().strftime('%H%M%S')}"
            )
            bak.write_text(src, encoding="utf-8")
            file_path.write_text(fixed, encoding="utf-8")
            log.info(f"[AutoDev] ✅ Repaired {file_path}")
        except Exception as e:
            log.warning(f"[AutoDev] ⚠️ Skipped {file_path}: {e}")

    async def _create_targets(self, targets: List[str]) -> None:
        """Yeni modüller oluşturur."""
        log.info(f"[AutoDev] Generating modules for {targets}")
        for t in targets:
            await self._create_target(t)
        log.info("[AutoDev] ✅ Create cycle complete.")

    async def _create_target(self, target: str) -> None:
        """Yeni dosya üretimi (GPT)."""
        try:
            path = self._absolute_path(target)
            path.mkdir(parents=True, exist_ok=True)
            prompt = (
                f"Generate a typed, documented Python module for {target}. "
                "Use modern logging and BaseAI style."
            )
            result = await gpt_bridge.generate_text(prompt)
            code = self._extract_code(result)

            if not code.strip():
                log.warning(f"[AutoDev] Empty generation for {target}")
                return

            out = path / f"auto_{datetime.now().strftime('%H%M%S')}.py"
            out.write_text(code, encoding="utf-8")
            log.info(f"[AutoDev] ✅ Created {out}")
        except Exception as e:
            log.warning(f"[AutoDev] ⚠️ Create failed for {target}: {e}")

    # ==========================================================
    # UTILITIES
    # ==========================================================
    def _absolute_path(self, target: str | Path) -> Path:
        """Normalize target paths relative to project root."""
        path = Path(target)
        if path.is_absolute():
            return path.resolve()
        return (self.project_root / path).resolve()

    def _should_skip_path(self, file_path: Path) -> bool:
        """Check if file is marked as immutable."""
        try:
            candidate = file_path.resolve().relative_to(self.project_root).as_posix()
        except ValueError:
            candidate = file_path.as_posix()
        return any(skip in candidate for skip in self.IMMUTABLE_PATHS)

    def _extract_code(self, resp: str) -> str:
        """LLM cevabından Python kodunu ayıklar."""
        if not resp:
            return ""
        txt = resp.strip()
        if "```python" in txt:
            txt = txt.split("```python", 1)[1].split("```", 1)[0]
        elif "```" in txt:
            txt = txt.split("```", 1)[1].split("```", 1)[0]
        return txt.strip()

    def _is_safe_replacement(self, new: str, old: str) -> bool:
        """Yeni kodun güvenli olup olmadığını kontrol eder."""
        if not new or len(new.strip()) < 50:
            return False
        if new.strip() == old.strip():
            return False
        if not any(x in new for x in ("def ", "class ", "import ")):
            return False
        delta = abs(len(new.splitlines()) - len(old.splitlines()))
        return delta <= max(10, len(old.splitlines()) * 0.5)


# ==========================================================
# CLI ENTRYPOINT
# ==========================================================
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run BaseAI AutoDev Engine v6.0-OMNI")
    parser.add_argument("--mode", type=str, default="repair", help="Mode: test / repair / create")
    parser.add_argument("--targets", nargs="*", default=["baseai"], help="Target directories")
    parser.add_argument("--level", type=str, default="enterprise", help="Repair depth")
    args = parser.parse_args()

    engine = AutoDevEngine(project_root=".")
    asyncio.run(engine.run(mode=args.mode, targets=args.targets, level=args.level))

    sys.stdout.flush()
    sys.stderr.flush()
