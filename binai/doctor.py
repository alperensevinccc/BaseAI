"""
BaseAI - BinAI v23.1 "Akıllı Doktor" (Smart Doctor)
Log İzleme ve Otonom İyileştirme Modülü

v23.1 Yükseltmeleri (Enterprise+++):
- "Öz Farkındalık" (Self-Awareness): Doktor artık kendi ürettiği veya 
  Optimizer'dan kaynaklanan hataları (loop'a girmemek için) görmezden gelir.
- "Soğuma Süresi" (Cooldown): Doktor bir müdahale (Heal) yaptıktan sonra 
  tekrar müdahale etmek için 5 dakika (300sn) bekler. Bu, sistemi kilitlenmekten korur.
- Hedefli Analiz: Sadece gerçek 'Ticaret' ve 'API' hatalarına odaklanır.
"""

import time
import os
import re
import threading
from binai.logger import log
from binai import optimizer
from binai import config

# İzlenecek Log Dosyası
LOG_FILE_PATH = config.CORE_LOG_FILE 

# Tetikleyici Kurallar
MAX_CONSECUTIVE_LOSSES = 2  # Üst üste 2 zarar
# Sadece Kritik ve API hatalarını yakala, Uyarıları (Warning) değil.
ERROR_PATTERN = r"APIError|KRİTİK HATA|Genel istemci|Signature for this request is not valid"

# Müdahale Ayarları
HEAL_COOLDOWN_SECONDS = 300 # 5 Dakika bekleme süresi
last_heal_time = 0

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
    global last_heal_time
    log.info("--- [v23.1 AKILLI DOKTOR (Gözetmen)] Göreve Başladı ---")
    log.info(f"İzlenen Dosya: {LOG_FILE_PATH}")
    
    consecutive_losses = {} # {symbol: loss_count}
    
    try:
        with open(LOG_FILE_PATH, "r") as logfile:
            loglines = follow(logfile)
            
            for line in loglines:
                current_time = time.time()
                
                # === FİLTRE 1: KENDİ KUYRUĞUNU ISIRMA (Self-Awareness) ===
                # Doktor veya Optimizer loglarını görmezden gel
                if "Doktor" in line or "Optimizer" in line or "Yaratıcı Zeka" in line:
                    continue

                # === SENARYO 1: ZARAR TESPİTİ ===
                if "PNL:" in line and "KAPANDI:" in line:
                    try:
                        parts = line.split("|")
                        symbol_part = parts[0].split(":")[-1].strip()
                        pnl_part = parts[1].split(":")[1].strip().replace("USDT", "")
                        pnl = float(pnl_part)
                        symbol = symbol_part
                        
                        if pnl < 0:
                            consecutive_losses[symbol] = consecutive_losses.get(symbol, 0) + 1
                            log.warning(f"v23.1 Doktor: {symbol} ZARAR etti ({pnl}). Sayaç: {consecutive_losses[symbol]}")
                            
                            if consecutive_losses[symbol] >= MAX_CONSECUTIVE_LOSSES:
                                # SOĞUMA SÜRESİ KONTROLÜ
                                if (current_time - last_heal_time) > HEAL_COOLDOWN_SECONDS:
                                    log.warning(f"v23.1 Doktor: {symbol} için ACİL MÜDAHALE (Heal) başlatılıyor!")
                                    
                                    error_msg = f"Üst üste {consecutive_losses[symbol]} zarar. Son PnL: {pnl}. Acil strateji değişimi gerekli."
                                    # Optimizer'ı Tetikle
                                    threading.Thread(target=optimizer.analyze_logs_and_heal, args=(symbol, error_msg)).start()
                                    
                                    last_heal_time = current_time
                                    consecutive_losses[symbol] = 0 
                                else:
                                    log.info(f"v23.1 Doktor: {symbol} için müdahale gerekli ama Soğuma Süresi (Cooldown) aktif.")
                        else:
                            if symbol in consecutive_losses:
                                # Kâr edince sayacı sıfırla
                                consecutive_losses[symbol] = 0
                                
                    except Exception:
                        pass

                # === SENARYO 2: KRİTİK TEKNİK HATA TESPİTİ ===
                if re.search(ERROR_PATTERN, line):
                    # SOĞUMA SÜRESİ KONTROLÜ
                    if (current_time - last_heal_time) > HEAL_COOLDOWN_SECONDS:
                        log.warning(f"v23.1 Doktor: KRİTİK TEKNİK HATA TESPİT EDİLDİ -> {line.strip()}")
                        log.warning("v23.1 Doktor: İyileştirme (Heal) süreci başlatılıyor...")
                        
                        # Genel bir sembol seç (örn: BTCUSDT) veya hatadan sembolü çıkar
                        target_symbol = "BTCUSDT" 
                        error_msg = f"KRİTİK SİSTEM HATASI: {line.strip()}"
                        
                        threading.Thread(target=optimizer.analyze_logs_and_heal, args=(target_symbol, error_msg)).start()
                        
                        last_heal_time = current_time
                    else:
                         # Çok sık hata geliyorsa logu kirletme
                         pass

    except Exception as e:
        log.error(f"v23.1 Doktor ana döngüsü çöktü: {e}")

if __name__ == "__main__":
    start_doctor()