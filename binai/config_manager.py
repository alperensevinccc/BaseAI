"""
BaseAI - BinAI Evrim Motoru (v10.0)
Otonom Konfigürasyon Yöneticisi
Bu modül, config.py dosyasını otonom olarak okur ve günceller.
"""
import re
import os
from logger import log

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.py")

def update_config_parameters(params_to_update):
    """
    config.py dosyasını okur ve params_to_update sözlüğündeki
    değerleri (örn: {'FAST_MA_PERIOD': 20}) otonom olarak günceller.
    """
    log.info("--- [Evrim Motoru v10.0] Otonom Konfigürasyon Güncellemesi ---")
    
    if not os.path.exists(CONFIG_PATH):
        log.error(f"Kritik Hata: config.py bulunamadı. {CONFIG_PATH}")
        return False

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        for key, value in params_to_update.items():
            pattern = rf"^(\s*{key}\s*=\s*)(\S+)(\s*#.*|)$"
            
            # === v10.3 HATA DÜZELTMESİ (Nihai Regex) ===
            # HATALI KOD (v10.2):
            # replacement = r"\1" + str(value) + r"\3"
            
            # ONARILMIŞ KOD (Grup Referans Hatasını Çözer):
            # \g<1> -> 1. Grubu (key = ) al
            # {value} -> 0.015 değerini yaz
            # \g<3> -> 3. Grubu ( # yorum) al
            replacement = rf"\g<1>{value}\g<3>"
            # === DÜZELTME SONU ===
            
            content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
            
            if count == 0:
                log.warning(f"config.py içinde '{key}' parametresi bulunamadı (veya desen eşleşmedi).")
            else:
                log.info(f"config.py güncellendi: {key} = {value}")

        if content != original_content:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                f.write(content)
            log.info("config.py başarıyla otonom olarak güncellendi.")
            return True
        else:
            log.info("Konfigürasyon zaten günceldi. Değişiklik yapılmadı.")
            return True
            
    except Exception as e:
        log.error(f"config.py otonom güncellenirken kritik hata: {e}")
        return False