"""
BaseAI - BinAI v23.0 "Doktor" (The Doctor)
Log İzleme ve Otonom İyileştirme Modülü

Görevi: 'binai_main_runtime.log' ve 'binai_runtime.log' dosyalarını canlı izler.
Hata veya üst üste zarar görürse, 'optimizer.py' üzerinden Gemini'yi çağırır.
"""

import time
import os
import re
from binai.logger import log
from binai import optimizer
from binai import config

# İzlenecek Log Dosyası
LOG_FILE_PATH = config.CORE_LOG_FILE # binai_runtime.log

# Tetikleyici Kurallar
MAX_CONSECUTIVE_LOSSES = 2  # Üst üste 2 zarar
ERROR_PATTERN = r"APIError|KRİTİK HATA|Exception"

def follow(file):
    """Dosyayı canlı olarak (tail -f gibi) okuyan jeneratör."""
    file.seek(0, os.SEEK_END)
    while True:
        line = file.readline()
        if not line:
            time.sleep(0.1)
            continue
        yield line

def start_doctor():
    log.info("--- [v23.0 DOKTOR (Gözetmen)] Göreve Başladı ---")
    log.info(f"İzlenen Dosya: {LOG_FILE_PATH}")
    
    consecutive_losses = {} # {symbol: loss_count}
    error_buffer = []
    
    try:
        with open(LOG_FILE_PATH, "r") as logfile:
            loglines = follow(logfile)
            
            for line in loglines:
                # 1. ZARAR TESPİTİ
                # Log örneği: "KAPANDI: BTCUSDT | PNL: -5.40 USDT..."
                if "PNL:" in line and "KAPANDI:" in line:
                    parts = line.split("|")
                    symbol_part = parts[0].split(":")[-1].strip()
                    pnl_part = parts[1].split(":")[1].strip().replace("USDT", "")
                    
                    try:
                        pnl = float(pnl_part)
                        symbol = symbol_part
                        
                        if pnl < 0:
                            consecutive_losses[symbol] = consecutive_losses.get(symbol, 0) + 1
                            log.warning(f"v23.0 Doktor: {symbol} ZARAR etti ({pnl}). Sayaç: {consecutive_losses[symbol]}")
                            
                            if consecutive_losses[symbol] >= MAX_CONSECUTIVE_LOSSES:
                                log.warning(f"v23.0 Doktor: {symbol} için ACİL MÜDAHALE gerekiyor!")
                                # Optimizer'ı (Doktor Modu) Tetikle
                                error_msg = f"Üst üste {consecutive_losses[symbol]} zarar. Son PnL: {pnl}"
                                optimizer.analyze_logs_and_heal(symbol, error_msg)
                                consecutive_losses[symbol] = 0 # Sayacı sıfırla
                        else:
                            if symbol in consecutive_losses:
                                log.info(f"v23.0 Doktor: {symbol} KÂR etti ({pnl}). Sayaç sıfırlandı.")
                                consecutive_losses[symbol] = 0
                                
                    except Exception:
                        pass

                # 2. TEKNİK HATA TESPİTİ
                if re.search(ERROR_PATTERN, line):
                    log.warning(f"v23.0 Doktor: Teknik Hata Tespit Edildi -> {line.strip()}")
                    # Hata genel ise (sembolsüz), belki config optimizasyonu yapılabilir
                    # Şimdilik sadece logluyoruz.

    except Exception as e:
        log.error(f"v23.0 Doktor çöktü: {e}")

if __name__ == "__main__":
    start_doctor()