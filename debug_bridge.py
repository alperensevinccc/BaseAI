"""
Debug Script: GeminiBridge Metodlarını Listele
"""
import sys
from baseai.bridges.gemini import GeminiBridge

print("\n--- GeminiBridge İncelemesi ---")
try:
    # Köprüyü başlat
    bridge = GeminiBridge()
    
    # Tüm metodları ve özellikleri listele
    attributes = dir(bridge)
    
    print("Mevcut Metodlar:")
    for attr in attributes:
        # Sadece gizli olmayan (__) metodları göster
        if not attr.startswith("__"):
            print(f" - {attr}")
            
except Exception as e:
    print(f"Hata: {e}")

print("-------------------------------\n")