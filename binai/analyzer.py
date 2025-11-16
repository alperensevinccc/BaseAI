"""
BaseAI - BinAI v21.1 Mimari Yükseltmesi
"Akıllı Analiz" (Intelligent Analysis) Motoru (Enterprise Core)

v21.1 Yükseltmeleri (Enterprise+++):
- 'db_manager' (v21.0) Entegrasyonu: 'sqlite3.connect' (Tehlikeli) çağrısı 
  kaldırıldı. 'trades' tablosunu okumak için artık 'db_manager.get_db_connection'
  üzerinden "Sadece Okuma" (Read-Only) bağlantısı kullanılıyor.
- Kararlılık (Thread-Safety): Bu, 'Database is locked' (Veritabanı Kilitli)
  hatasını ve 'Yazıcı Thread' (Writer Thread) ile çakışmayı engeller.
- Kararlılık (Path): 'DB_PATH' (Hardcoded Path) kaldırıldı.
  Veritabanı yolunu artık 'db_manager' (Hafıza) merkezi olarak yönetir.
"""

import pandas as pd
import os
import sys

# === BİNAİ MODÜLLERİ ===
try:
    # v21.1: Mutlak (Absolute) içe aktarma
    from binai import config
    from binai.logger import log
    # v21.1 YENİ: DB Bağlantısını 'db_manager'dan (Hafıza) al
    from binai import db_manager 
except ImportError as e:
    print(f"KRİTİK HATA (analyzer.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)


# === v14.0 AYARLARI ===
# (Bu ayarları 'config.py'a taşımak v22.0 için bir hedef olabilir)
RECENT_TRADE_COUNT = 10 
RECENT_WIN_RATE_THRESHOLD = 40.0 # %40


def analyze_performance(is_autonomous_cycle: bool = False):
    """
    'trades' (Ticaretler) tablosunu okur ve performans raporu basar.
    
    v15.0: 'is_autonomous_cycle' True ise, 'Bayatlamış Beyin' (Stale Brain)
    tespiti yapar ve (is_stale) bayrağını döndürür.
    
    v21.1: Artık 'db_manager' (v21.0) 'Sadece Okuma' (Read-Only)
    bağlantısı kullanır.
    """
    
    if not is_autonomous_cycle:
        # 'print' yerine 'log' kullanmak, 'run.py' (v2) tarafından
        # çağrıldığında çıktının kaybolmamasını sağlar.
        log.info("\n--- [BinAI v21.1 Performans Analiz Raporu] ---")
    
    conn = None
    try:
        # v21.1: 'Sadece Okuma' (Read-Only) ve 'Thread-Safe' (Güvenli) bağlantı
        conn = db_manager.get_db_connection(is_writer_thread=False)
        
        if conn is None:
            log.warning("Hafıza (DB) okunamadı (Muhtemelen henüz oluşturulmadı). Analiz atlanıyor.")
            return False

        # 'trades' tablosu var mı diye kontrol et (v21.1 Sağlamlık Kontrolü)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if cursor.fetchone() is None:
            if not is_autonomous_cycle:
                log.warning("Hafıza (DB) bulundu ancak 'trades' tablosunda henüz kayıt yok.")
            conn.close()
            return False

        df = pd.read_sql_query("SELECT * FROM trades", conn)

        
        if df.empty:
            if not is_autonomous_cycle:
                log.info("Hafıza (DB) 'trades' tablosu bulundu ancak henüz kayıtlı işlem (trade) yok.")
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

            log.info("--- Performans (Tüm Zamanlar) ---")
            log.info(f"Toplam İşlem Sayısı   : {total_trades}")
            log.info(f"Toplam Net Kâr/Zarar : {total_pnl:.4f} USDT")
            log.info(f"Kazanma Oranı (Win %)  : {win_rate:.2f}% ({len(wins)} Kazanan / {len(losses)} Kaybeden)")
            log.info(f"Profit Factor          : {profit_factor:.2f}")

        # --- 2. SON PERFORMANS (Recent) (v14.0 "Bayatlamış Beyin" Tespiti) ---
        is_stale = False
        if len(df) >= RECENT_TRADE_COUNT:
            df_recent = df.tail(RECENT_TRADE_COUNT)
            
            recent_pnl = df_recent['pnl_usdt'].sum()
            recent_wins = df_recent[df_recent['pnl_usdt'] > 0]
            recent_losses = df_recent[df_recent['pnl_usdt'] < 0]
            recent_win_rate = (len(recent_wins) / RECENT_TRADE_COUNT) * 100
            
            if not is_autonomous_cycle:
                log.info("\n--- Performans (Son 10 İşlem) ---")
                log.info(f"Net Kâr/Zarar : {recent_pnl:.4f} USDT")
                log.info(f"Kazanma Oranı : {recent_win_rate:.2f}% ({len(recent_wins)} Kazanan / {len(recent_losses)} Kaybeden)")

            if recent_win_rate < RECENT_WIN_RATE_THRESHOLD:
                is_stale = True # v15.0: "Bayatlamış Beyin" TESPİT EDİLDİ
        
        elif not is_autonomous_cycle:
            log.info(f"\n--- Performans (Son {RECENT_TRADE_COUNT} İşlem) ---")
            log.info(f"Otonom analiz için yetersiz işlem (Mevcut: {len(df)}).")

        # --- 3. Sembol Bazlı Performans ---
        if not is_autonomous_cycle:
            symbol_pnl = df.groupby('symbol')['pnl_usdt'].sum().sort_values()
            log.info("\n--- Sembol Bazlı Performans (En Kötü -> En İyi) ---")
            # 'print' kullanıyoruz çünkü 'to_string' (Pandas) çıktısı
            # 'log' formatlamasını (timestamp vb.) bozar.
            print(symbol_pnl.to_string())

        # --- 4. OTONOM TAVSİYE (v14.0) / TETİKLEME (v15.0) ---
        if not is_autonomous_cycle:
            if is_stale:
                log.warning("\n--- [BaseAI v21.1 OTONOM TAVSİYE] ---")
                log.warning(f"DİKKAT: Son {RECENT_TRADE_COUNT} işlemdeki Kazanma Oranı (%{recent_win_rate:.2f})")
                log.warning(f"hedeflenen eşiğin (%{RECENT_WIN_RATE_THRESHOLD:.2f}) altındadır.")
                log.warning("Strateji Hafızası (strategy_params.db) 'Bayatlamış' (Stale) olabilir.")
                log.warning("\nÇÖZÜM: 'optimize binai' komutunu çalıştırın.")
                log.warning("-------------------------------------------------")
            else:
                log.info("\n--- [BaseAI v21.1 OTONOM TAVSİYE] ---")
                log.info("Strateji performansı hedefler dahilinde. Evrim (Optimizasyon) gerekmiyor.")
                log.info("-------------------------------------------------")
        
        # v15.0: "Otonom Evrim" döngüsü için 'is_stale' bayrağını döndür
        return is_stale

    except pd.errors.DatabaseError as e:
        # v21.1: 'Database is locked' hatası normalde burada olmamalı
        # (çünkü 'Sadece Okuma' (Read-Only) moddayız), ancak olursa yakala.
        if "database is locked" in str(e):
            log.error("Analiz hatası: Hafıza (DB) kilitli (Başka bir 'Yazıcı' (Writer) mı var?). Atlanıyor.")
        else:
            log.error(f"Analiz sırasında (Pandas) veritabanı hatası: {e}")
        return False
    except Exception as e:
        if not is_autonomous_cycle:
            log.error(f"Analiz sırasında kritik hata: {e}", exc_info=True)
        return False # Hata durumunda 'Bayatlamış' (Stale) değil
    finally:
        # v21.1: Bağlantıyı (conn) her zaman kapat
        if conn:
            conn.close()


if __name__ == "__main__":
    # Bu dosyanın 'python binai/analyzer.py' olarak 
    # manuel (manuel) çalıştırılabilmesi için
    # 'logger' ve 'db_manager'ın başlatıldığından emin olmalıyız.
    
    # v21.1 Not: 'db_manager'ın 'Yazıcı Thread'i (Writer Thread) 
    # 'initialize_database' ile başlar.
    try:
        db_manager.initialize_database()
        analyze_performance(is_autonomous_cycle=False)
    finally:
        # Manuel çalıştırıyorsak, 'Yazıcı Thread'i (Writer Thread)
        # düzgünce kapatmalıyız.
        db_manager.shutdown_db_writer()