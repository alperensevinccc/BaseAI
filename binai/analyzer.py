"""
BaseAI - BinAI v15.0 Mimari Yükseltmesi
"Akıllı Analiz" (Intelligent Analysis) Motoru
(v15.0: "Bayatlamış Beyin" Tespiti ve Otonom Tetikleme)
"""
import sqlite3
import pandas as pd
import os
import config # v15.0: Eşik (Threshold) değerlerini okumak için eklendi
from logger import log

# v14.0: Otonom Tavsiye (Recommendation) için performans eşiği
RECENT_TRADE_COUNT = 10 
RECENT_WIN_RATE_THRESHOLD = 40.0 

# Veritabanı dosyasının tam yolunu bul
DB_NAME = "binai_tradelog.db"
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

def analyze_performance(is_autonomous_cycle=False):
    """
    binai_tradelog.db dosyasını okur ve "Tüm Zamanlar" (All-Time)
    ve "Son Performans" (Recent) raporlarını basar.
    
    v15.0: Eğer 'is_autonomous_cycle' True ise,
    'Bayatlamış Beyin' (Stale Brain) tespiti yapar ve (is_stale) bayrağını döndürür.
    """
    
    if not is_autonomous_cycle:
        print("\n--- [BinAI v14.0 Performans Analiz Raporu] ---")
    
    if not os.path.exists(DB_PATH):
        if not is_autonomous_cycle:
            print(f"HATA: Hafıza (binai_tradelog.db) bulunamadı.")
        return False # v15.0: Hata durumunda 'Bayatlamış' (Stale) değil

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM trades", conn)
        conn.close()
        
        if df.empty:
            if not is_autonomous_cycle:
                print("Hafıza (DB) bulundu ancak henüz kayıtlı işlem (trade) yok.")
            return False # v15.0: Boşsa 'Bayatlamış' (Stale) değil

        # --- 1. TÜM ZAMANLAR (All-Time) Performansı ---
        if not is_autonomous_cycle:
            total_trades = len(df)
            total_pnl = df['pnl_usdt'].sum()
            wins = df[df['pnl_usdt'] > 0]
            losses = df[df['pnl_usdt'] < 0]
            win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
            total_profit = wins['pnl_usdt'].sum()
            total_loss = abs(losses['pnl_usdt'].sum())
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

            print("--- Performans (Tüm Zamanlar) ---")
            print(f"Toplam İşlem Sayısı   : {total_trades}")
            print(f"Toplam Net Kâr/Zarar : {total_pnl:.4f} USDT")
            print(f"Kazanma Oranı (Win %)  : {win_rate:.2f}% ({len(wins)} Kazanan / {len(losses)} Kaybeden)")
            print(f"Profit Factor          : {profit_factor:.2f}")

        # --- 2. SON PERFORMANS (Recent) (v14.0 "Bayatlamış Beyin" Tespiti) ---
        is_stale = False
        if len(df) >= RECENT_TRADE_COUNT:
            df_recent = df.tail(RECENT_TRADE_COUNT)
            
            recent_pnl = df_recent['pnl_usdt'].sum()
            recent_wins = df_recent[df_recent['pnl_usdt'] > 0]
            recent_losses = df_recent[df_recent['pnl_usdt'] < 0]
            recent_win_rate = (len(recent_wins) / RECENT_TRADE_COUNT) * 100
            
            if not is_autonomous_cycle:
                print("\n--- Performans (Son 10 İşlem) ---")
                print(f"Net Kâr/Zarar : {recent_pnl:.4f} USDT")
                print(f"Kazanma Oranı : {recent_win_rate:.2f}% ({len(recent_wins)} Kazanan / {len(recent_losses)} Kaybeden)")

            if recent_win_rate < RECENT_WIN_RATE_THRESHOLD:
                is_stale = True # v15.0: "Bayatlamış Beyin" TESPİT EDİLDİ
        
        elif not is_autonomous_cycle:
            print(f"\n--- Performans (Son {RECENT_TRADE_COUNT} İşlem) ---")
            print(f"Otonom analiz için yetersiz işlem (Mevcut: {len(df)}).")

        # --- 3. Sembol Bazlı Performans (Aynı) ---
        if not is_autonomous_cycle:
            symbol_pnl = df.groupby('symbol')['pnl_usdt'].sum().sort_values()
            print("\n--- Sembol Bazlı Performans (En Kötü -> En İyi) ---")
            print(symbol_pnl.to_string())

        # --- 4. OTONOM TAVSİYE (v14.0) / TETİKLEME (v15.0) ---
        if not is_autonomous_cycle:
            if is_stale:
                print("\n--- [BaseAI v14.0 OTONOM TAVSİYE] ---")
                print(f"DİKKAT: Son {RECENT_TRADE_COUNT} işlemdeki Kazanma Oranı (%{recent_win_rate:.2f})")
                print(f"hedeflenen eşiğin (%{RECENT_WIN_RATE_THRESHOLD:.2f}) altındadır.")
                print("Strateji Hafızası (strategy_params.db) 'Bayatlamış' (Stale) olabilir.")
                print("\nÇÖZÜM: 'optimize binai' komutunu çalıştırın.")
                print("-------------------------------------------------")
            else:
                print("\n--- [BaseAI v14.0 OTONOM TAVSİYE] ---")
                print("Strateji performansı hedefler dahilinde. Evrim (Optimizasyon) gerekmiyor.")
                print("-------------------------------------------------")
        
        # v15.0: "Otonom Evrim" döngüsü için 'is_stale' bayrağını döndür
        return is_stale

    except Exception as e:
        if not is_autonomous_cycle:
            print(f"Analiz sırasında kritik hata: {e}")
        return False # Hata durumunda 'Bayatlamış' (Stale) değil

if __name__ == "__main__":
    analyze_performance(is_autonomous_cycle=False)