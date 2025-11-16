from __future__ import annotations
import time
import json
import os
import contextlib
from typing import Dict, Any

from baseai.log.logger import bridge_logger as log
import traceback

# Sadece GPTDiagnostics'i dahil etmeye çalış. Eğer GPTBridge içinde bu sınıf yoksa,
# hata vermemek için contextlib.suppress kullanıyoruz ve manuel olarak ekliyoruz.
# Ancak GPTBridge'in kendisini kullanmak daha temiz bir Enterprise mimarisidir.

# Geçici olarak GPTDiagnostics'i GPTBridge modülünden içe aktaralım.
# Eğer GPTBridge içinde Diagnostics sınıfı yoksa, bu import başarısız olur.
with contextlib.suppress(ImportError, AttributeError):
    from .gpt import GPTBridge  # GPTBridge'in kendisini içe aktar
    
# Gerekli importlar
try:
    from .gpt import GPTDiagnostics as GTD
    GPT_DIAGNOSTICS_AVAILABLE = True
except ImportError:
    GPT_DIAGNOSTICS_AVAILABLE = False


HEALTH_ALL = "baseai/logs/bridge_health_all.json"


def collect_all() -> Dict[str, Any]:
    """
    Tüm mevcut ve aktif Bridge Diagnostics raporlarını toplar ve diske kaydeder.
    """
    log.info("[Bridge] Collecting unified health report...")
    
    report_bridges = {}
    
    # --- GPT Bridge Entegrasyonu (Ana Öncelik) ---
    if GPT_DIAGNOSTICS_AVAILABLE:
        try:
            # GPTDiagnostics.run() metodunu kullan
            gpt_report = GTD.run()
            report_bridges["gpt"] = gpt_report
        except Exception as e:
            log.error(f"[Bridge|GPT] Diagnostics raporu alınırken hata: {e}", exc_info=False)
            report_bridges["gpt"] = {"status": "ERROR", "details": str(e)}
    else:
        log.warning("[Bridge] GPT Diagnostics sınıfı (GTD) bulunamadı. Rapor atlanıyor.")
        
    # Gemini artık kaldırıldı, raporlanmayacak.
    
    report = {
        "ts": time.time(),
        "bridges": report_bridges,
    }
    
    # Dizini oluştur ve raporu yaz
    os.makedirs(os.path.dirname(HEALTH_ALL), exist_ok=True)
    try:
        with open(HEALTH_ALL, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        log.info(f"[Bridge] Unified health report successfully saved → {HEALTH_ALL}")
    except Exception as e:
        log.critical(f"[Bridge] Unified health raporu diske yazılamadı: {e}", exc_info=True)

    return report