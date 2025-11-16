"""
BaseAI - BinAI v21.2 Mimari Yükseltmesi
"Dinamik Risk Yöneticisi" (Dynamic Risk Manager)

v21.2 Yükseltmeleri (Enterprise+++):
- "Süper Özellik #2: Dinamik Pozisyon Boyutu" (Volatilite Tabanlı Risk) eklendi.
- '_open_position_logic' (v21.2) fonksiyonu, 'config.USE_DYNAMIC_POSITION_SIZING'
  ayarını okuyacak şekilde yeniden yazıldı.
- 'Dinamik' (v21.2) modda, 'quantity' (Miktar) artık 'sabit' (static) 
  'POSITION_SIZE_PERCENT' ile değil, 'RISK_PER_TRADE_PERCENT' (örn: Kasanın %2'si)
  ve 'sl_distance' (Volatilite) kullanılarak otonom olarak (otomatik) hesaplanır.
- Bu, 'Milyarder Trader' (Quant) seviyesinde 'Kasa Yönetimi' (Bankroll) sağlar.
"""

from binance.exceptions import BinanceAPIException
from binance.client import Client # v21.0: Tip (Type Hinting) için eklendi
import threading
import time
import pandas as pd
from typing import Dict, Any, Optional, Tuple

# === BİNAİ MODÜLLERİ ===
try:
    from binai import config
    from binai.logger import log
    from binai import db_manager 
    from binai import market_data 
except ImportError as e:
    print(f"KRİTİK HATA (trade_manager.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)


# === v21.0 DURUM (STATE) YÖNETİMİ (ENTERPRISE) ===
# (v21.2'de değişiklik yok)
active_positions: Dict[str, Dict] = {}
_active_positions_lock = threading.Lock()


def cleanup_orphan_positions(client: Client):
    """
    v17.0 "Sıfır Güven" (Zero Trust) Protokolü.
    (v21.2'de değişiklik yok. Bu, 'startup'ta (başlangıçta) çalışır.)
    """
    log.info("--- [v17.0 'Sıfır Güven' Protokolü] ---")
    log.info("Mevcut 'Hafıza' (active_positions) boş.")
    log.info("Binance hesabındaki 'Yetim' (Orphan) pozisyonlar taranıyor...")
    
    try:
        positions = client.futures_position_information()
        
        orphans_found = 0
        for pos in positions:
            symbol = pos['symbol']
            quantity = float(pos.get('positionAmt', 0.0))
            
            if quantity != 0.0:
                if symbol not in active_positions:
                    orphans_found += 1
                    log.warning(f"DİKKAT: 'Yetim' (Orphan) Pozisyon Tespiti: {symbol} | Miktar: {quantity}")
                    
                    log.warning(f"v17.0: {symbol} için açık SL/TP emirleri (Yetim) iptal ediliyor...")
                    client.futures_cancel_all_open_orders(symbol=symbol)
                    
                    log.warning(f"v17.0: 'Yetim' (Orphan) pozisyon ({symbol}) piyasa (market) emriyle kapatılıyor...")
                    client.futures_create_order(
                        symbol=symbol,
                        side="BUY" if quantity < 0 else "SELL",
                        positionSide="SHORT" if quantity < 0 else "LONG",
                        type='MARKET',
                        quantity=abs(quantity) # v17.1 ONARIMI
                    )
                    log.warning(f"v17.0: 'Yetim' (Orphan) pozisyon ({symbol}) başarıyla temizlendi.")

        if orphans_found == 0:
            log.info("v17.0: 'Yetim' (Orphan) pozisyon bulunamadı. Kasa (0/2) temiz.")
        
        log.info("--- [v17.0 'Sıfır Güven' Protokolü Tamamlandı] ---")

    except BinanceAPIException as e:
        log.error(f"v17.0: 'Yetim' (Orphan) pozisyon temizliği API hatası: {e}")
    except Exception as e:
        log.error(f"v17.0: 'Yetim' (Orphan) pozisyon temizliği genel hata: {e}", exc_info=True)


# === v21.2 ÖZEL (PRIVATE) FONKSİYONLAR (SÜPER ÖZELLİK #2) ===

def _open_position_logic(
    client: Client, 
    symbol: str, 
    signal: str, 
    current_price: float, 
    last_atr: float,  # v21.0 YENİ: Volatilite (Oynaklık)
    exchange_rules: Dict
):
    """
    v21.2: Yeni bir pozisyon açan (API çağrıları) çekirdek mantık.
    - Süper Özellik #1: 'Dinamik SL/TP' (v21.1) kullanır.
    - Süper Özellik #2: 'Dinamik Pozisyon Boyutu' (v21.2) kullanır.
    """
    
    # === Adım 1: Bakiye (Balance) Al ===
    try:
        account_info = client.futures_account_balance()
        usdt_balance = 0
        for asset in account_info:
            if asset['asset'] == 'USDT':
                usdt_balance = float(asset['balance'])
                break
        if usdt_balance <= 10: # Minimum bakiye kontrolü
            log.error(f"{symbol} pozisyon açmak için yeterli USDT bakiyesi (10$) yok.")
            return False
    except Exception as e:
        log.error(f"{symbol} bakiye (balance) alınamadı: {e}", exc_info=True)
        return False

    # === Adım 2: Hassasiyet (Precision) Kurallarını Al ===
    rules = exchange_rules.get(symbol)
    if not rules:
        log.error(f"{symbol} için hassasiyet (precision) kuralı bulunamadı.")
        return False
    qty_precision = rules.get("quantityPrecision")
    price_precision = rules.get("pricePrecision")

    # === Adım 3: SL/TP Mesafelerini (Distance) Hesapla (Süper Özellik #1) ===
    # (Bu, 'Miktar' (quantity) hesaplamasından ÖNCE yapılmalıdır)
    
    sl_distance_per_unit = 0.0 # Birim (coin) başına $ cinsinden SL mesafesi
    tp_distance_per_unit = 0.0 # Birim (coin) başına $ cinsinden TP mesafesi
    
    if config.USE_DYNAMIC_SLTP and last_atr > 0:
        # === Dinamik (Volatilite Tabanlı) SL/TP ===
        log.info(f"v21.1: 'Dinamik SL/TP' kullanılıyor (ATR: {last_atr:.4f})")
        sl_distance_per_unit = last_atr * config.ATR_STOP_LOSS_MULTIPLIER
        tp_distance_per_unit = last_atr * config.ATR_TAKE_PROFIT_MULTIPLIER
    else:
        # === Statik (v6.1 Fallback) SL/TP ===
        log.info(f"v21.0: 'Statik SL/TP' kullanılıyor (Dinamik kapalı veya ATR=0)")
        sl_distance_per_unit = current_price * config.STOP_LOSS_PERCENT
        tp_distance_per_unit = current_price * config.TAKE_PROFIT_PERCENT

    if sl_distance_per_unit == 0:
        log.error(f"{symbol} için SL Mesafesi (sl_distance_per_unit) '0' olarak hesaplandı. Risk hesaplanamaz. Emir atlanıyor.")
        return False

    # === Adım 4: Pozisyon Miktarını (Quantity) Hesapla (Süper Özellik #2) ===
    
    quantity = 0.0
    
    if config.USE_DYNAMIC_POSITION_SIZING:
        # === Dinamik (Risk Tabanlı) Miktar ===
        log.info(f"v21.2: 'Dinamik Pozisyon Boyutu' kullanılıyor (Risk: {config.RISK_PER_TRADE_PERCENT*100}%)")
        
        # 1. Kasa (Bankroll) başına ne kadar $ riske atılacak?
        # (örn: 1000$ * %2 = 20$)
        risk_amount_usdt = usdt_balance * config.RISK_PER_TRADE_PERCENT
        
        # 2. Miktarı (Quantity) Hesapla
        # (örn: Miktar = 20$ (Risk) / 0.15$ (SL Mesafesi) = 133.33 adet)
        quantity = risk_amount_usdt / sl_distance_per_unit
        log.info(f"v21.2: Dinamik Miktar Hesabı: {risk_amount_usdt:.2f}$ (Risk) / {sl_distance_per_unit:.4f}$ (SL Mesafesi) = {quantity:.4f} (Miktar)")
        
    else:
        # === Statik (v5.3 Fallback) Miktar ===
        log.info(f"v21.2: 'Statik Pozisyon Boyutu' kullanılıyor (Kasanın {config.POSITION_SIZE_PERCENT*100}%)")
        
        # 1. Kasanın %X'i ile ne kadar $ (Kaldıraçsız) pozisyon açılacak?
        # (örn: 1000$ * %50 = 500$)
        position_size_usdt = usdt_balance * config.POSITION_SIZE_PERCENT
        
        # 2. Kaldıraçlı (Notional) Miktarı (Quantity) Hesapla
        # (örn: Miktar = (500$ * 10x Kaldıraç) / 10$ (Fiyat) = 500 adet)
        quantity = (position_size_usdt * config.LEVERAGE) / current_price
    
    # Miktarı (Quantity) hassasiyete (precision) göre yuvarla
    quantity = round(quantity, qty_precision)
    
    if quantity == 0.0:
        log.warning(f"{symbol} için hesaplanan miktar 0'a yuvarlandı. Emir gönderilmiyor.")
        return False

    # === Adım 5: Kaldıraç, Emir ve SL/TP'yi Ayarla ===
    try:
        # 5.1. Kaldıraç Ayarlama
        try:
            client.futures_change_leverage(symbol=symbol, leverage=config.LEVERAGE)
        except BinanceAPIException as e:
            if "leverage not modified" not in str(e):
                log.warning(f"{symbol} kaldıraç ayarlanamadı (muhtemelen zaten ayarlı): {e}")
        
        # 5.2. Emir Gönderme (Piyasa Emri)
        order_side = "BUY" if signal == "LONG" else "SELL"
        position_side = "LONG" if signal == "LONG" else "SHORT"
        
        log.info(f"--- [EMİR GÖNDERİLİYOR (v21.2)] ---")
        log.info(f"Sembol: {symbol} | Taraf: {position_side}")
        log.info(f"Miktar: {quantity} | Fiyat: {current_price}")
        
        order = client.futures_create_order(
            symbol=symbol, side=order_side, positionSide=position_side,
            type='MARKET', quantity=quantity
        )
        
        # 5.3. SL/TP Fiyatlarını Hesapla (Adım 3'teki mesafelere göre)
        if signal == "LONG":
            sl_price = current_price - sl_distance_per_unit
            tp_price = current_price + tp_distance_per_unit
            sl_side = "SELL"
            tp_side = "SELL"
        else: # SHORT
            sl_price = current_price + sl_distance_per_unit
            tp_price = current_price - tp_distance_per_unit
            sl_side = "BUY"
            tp_side = "BUY"
            
        sl_price = round(sl_price, price_precision)
        tp_price = round(tp_price, price_precision)

        # 5.4. SL/TP Emirlerini Gönderme
        client.futures_create_order(
            symbol=symbol, side=sl_side, positionSide=position_side,
            type='STOP_MARKET', stopPrice=sl_price, closePosition=True
        )
        client.futures_create_order(
            symbol=symbol, side=tp_side, positionSide=position_side,
            type='TAKE_PROFIT_MARKET', stopPrice=tp_price, closePosition=True
        )
        log.info(f"{symbol} için SL ({sl_price}) ve TP ({tp_price}) emirleri ayarlandı.")
        
        # 5.5. "Hafıza"yı (RAM) Güncelle (v21.0: Kilitli)
        with _active_positions_lock:
            active_positions[symbol] = {
                "side": position_side,
                "quantity": quantity,
                "entry_price": current_price,
                "open_time": int(time.time() * 1000),
                "unRealizedProfit": 0.0 # 'check_and_update' tarafından güncellenecek
            }
        return True
    
    except BinanceAPIException as e:
        log.error(f"{symbol} için pozisyon açma/yönetme hatası: {e}")
        return False
    except Exception as e:
        log.error(f"{symbol} için bilinmeyen emir hatası: {e}", exc_info=True)
        return False


def _get_weakest_open_position() -> Tuple[Optional[str], Optional[float]]:
    """
    v21.0: "Fırsatçı Yeniden Dengeleme" (v16.0) için "en zayıf" pozisyonu
    artık 'Hafıza'dan (RAM - active_positions) okur. (API ÇAĞRISI YOK)
    (v21.2'de değişiklik yok)
    """
    with _active_positions_lock: 
        if not active_positions:
            return None, None
        
        weakest_symbol = None
        try:
            first_pos = next(iter(active_positions.values()))
            weakest_pnl = float(first_pos.get('unRealizedProfit', 0.0))
        except Exception:
            weakest_pnl = 0.0 

        for symbol, pos_data in active_positions.items():
            pnl = float(pos_data.get('unRealizedProfit', 0.0))
            if pnl <= weakest_pnl:
                weakest_pnl = pnl
                weakest_symbol = symbol
        
    return weakest_symbol, weakest_pnl

def _close_position_by_symbol(client: Client, symbol: str, reason_log: str):
    """
    v16.0: "Fırsatçı Yeniden Dengeleme" için "en zayıf" pozisyonu
    otonom olarak kapatır.
    (v21.2'de değişiklik yok)
    """
    log.warning(f"--- [v16.0 FIRSATÇI KAPATMA] ---")
    log.warning(f"POZİSYON: {symbol} | NEDEN: {reason_log}")
    
    with _active_positions_lock:
        pos_data = active_positions.get(symbol)
        if not pos_data:
            log.error(f"v16.0: Kapatılacak {symbol} pozisyonu 'Hafıza'da (active_positions) bulunamadı.")
            return

    try:
        log.info(f"v16.0: {symbol} için açık SL/TP emirleri iptal ediliyor...")
        client.futures_cancel_all_open_orders(symbol=symbol)
        
        log.info(f"v16.0: {symbol} pozisyonu (Piyasa Emri) kapatılıyor...")
        client.futures_create_order(
            symbol=symbol,
            side="BUY" if pos_data['side'] == "SHORT" else "SELL",
            positionSide=pos_data['side'],
            type='MARKET',
            quantity=abs(float(pos_data['quantity'])) # v21.0
        )
        
        log.warning(f"--- [v16.0 FIRSATÇI KAPATMA TAMAMLANDI] ---")
        
    except BinanceAPIException as e:
        log.error(f"v16.0: {symbol} Fırsatçı Kapatma hatası (API): {e}")
    except Exception as e:
        log.error(f"v16.0: {symbol} Fırsatçı Kapatma hatası (Genel): {e}", exc_info=True)
    finally:
        with _active_positions_lock:
            if symbol in active_positions:
                del active_positions[symbol]


# === v13.0 KORELASYONLU RİSK YÖNETİMİ ===
# (v21.2'de değişiklik yok)
def _check_correlation_risk(client: Client, new_symbol: str, new_signal: str) -> bool:
    
    with _active_positions_lock:
        if not config.CORRELATION_CHECK_ENABLED or not active_positions:
            return False 
        active_positions_copy = dict(active_positions)
        
    try:
        new_klines_raw = market_data.get_klines(client, new_symbol, config.INTERVAL, config.CORRELATION_KLINE_LIMIT)
        if not new_klines_raw: return False
        df_new = pd.DataFrame(new_klines_raw, columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime', 'QuoteAssetVolume', 'NumTrades', 'TakerBuyBase', 'TakerBuyQuote', 'Ignore'])
        series_new = pd.to_numeric(df_new['Close'])
        
        for existing_symbol, position_data in active_positions_copy.items():
            existing_klines_raw = market_data.get_klines(client, existing_symbol, config.INTERVAL, config.CORRELATION_KLINE_LIMIT)
            if not existing_klines_raw: continue
            df_existing = pd.DataFrame(existing_klines_raw, columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime', 'QuoteAssetVolume', 'NumTrades', 'TakerBuyBase', 'TakerBuyQuote', 'Ignore'])
            series_existing = pd.to_numeric(df_existing['Close'])
            
            aligned_series_new, aligned_series_existing = series_new.align(series_existing, join='inner')
            if aligned_series_new.empty:
                continue

            correlation = aligned_series_new.corr(aligned_series_existing)
            existing_signal = position_data.get("side")
            
            log.debug(f"v13.0: Korelasyon Taraması: {new_symbol} vs {existing_symbol} = {correlation:.4f}")
            
            if correlation > config.CORRELATION_THRESHOLD and new_signal == existing_signal:
                log.warning(f"--- [v13.0 RİSK YÖNETİMİ REDDETTİ] ---")
                log.warning(f"SİNYAL: {new_symbol} | {new_signal}")
                log.warning(f"NEDEN: Yüksek Korelasyon ({correlation:.4f} > {config.CORRELATION_THRESHOLD})")
                log.warning(f"VE Aynı Yön ({new_signal}) ile MEVCUT POZİSYON: {existing_symbol} | {existing_signal}")
                return True # Risk Var
                
    except Exception as e:
        log.error(f"v13.0: Korelasyon hesaplaması sırasında kritik hata: {e}", exc_info=True)
        return False 
        
    return False # Risk Yok

# === v5.0 PNL RAPORLAMA (Aynı kalır, v12.0 DB Entegrasyonu) ===
def log_closed_position_pnl(client: Client, symbol: str, position_data: Dict):
    """
    Kapanan pozisyonun PnL'ini (Kâr/Zarar) hesaplar ve DB'ye (v21.0) kaydeder.
    (v21.2'de değişiklik yok)
    """
    log.info(f"Kapanan pozisyon ({symbol}) için PNL hesaplanıyor...")
    
    try:
        trades = client.futures_account_trade_list(symbol=symbol, startTime=position_data["open_time"])
        
        total_realized_pnl = 0.0
        close_reason = "Bilinmiyor (Muhtemelen SL/TP)"
        
        for trade in trades:
            real_pnl = float(trade['realizedPnl'])
            if real_pnl != 0:
                total_realized_pnl += real_pnl
                # v21.2: Daha sağlam Neden (Reason) tespiti
                if trade['orderId'] == trade['id'] and trade['positionSide'] != "BOTH":
                    close_reason = "TakeProfit" if real_pnl > 0 else "StopLoss"

        log.info(f"KAPANDI: {symbol} | PNL: {total_realized_pnl:.4f} USDT | Neden: {close_reason}")

        # v21.0: "Asenkron Yazıcı Sırası"na (Async Writer Queue) at (HIZLI)
        db_manager.log_trade_to_db(
            symbol=symbol, 
            side=position_data.get("side"), 
            quantity=position_data.get("quantity"),
            entry_price=position_data.get("entry_price"), 
            pnl=total_realized_pnl, 
            close_reason=close_reason
        )
    except Exception as e:
        log.error(f"{symbol} PNL hesaplama/kaydetme hatası: {e}", exc_info=True)

# === v21.0 POZİSYON GÜNCELLEME (Optimize Edildi) ===
def check_and_update_positions(client: Client):
    """
    v21.0: 'Hafıza'yı (RAM - active_positions) Binance ile senkronize eder.
    (v21.2'de değişiklik yok)
    """
    
    with _active_positions_lock:
        if not active_positions: 
            return 
        open_symbols = list(active_positions.keys()) 
    
    try:
        positions = client.futures_position_information(symbols=open_symbols)
        api_positions_map = {pos['symbol']: pos for pos in positions}
        
        for symbol in open_symbols:
            
            log_data = None 
            
            with _active_positions_lock:
                if symbol not in active_positions:
                    continue
                
                api_pos_data = api_positions_map.get(symbol)
                
                if api_pos_data and float(api_pos_data['positionAmt']) != 0:
                    # EVET: Pozisyon hala açık. Anlık PnL'i 'Hafıza'ya (RAM) yaz
                    active_positions[symbol]['unRealizedProfit'] = float(api_pos_data['unRealizedProfit'])
                
                else:
                    # HAYIR: Pozisyon kapanmış.
                    log.warning(f"POZİSYON KAPANDI TESPİT EDİLDİ: {symbol}.")
                    log_data = active_positions.pop(symbol) # 'Hafıza'dan (RAM) sil
            
            if log_data:
                # (Kilidi (lock) bıraktıktan sonra PnL'i hesapla)
                log_closed_position_pnl(client, symbol, log_data)

    except BinanceAPIException as e:
        log.error(f"check_and_update_positions API hatası: {e}")
    except Exception as e:
        log.error(f"check_and_update_positions genel hata: {e}", exc_info=True)


# === v21.2 ANA GİRİŞ NOKTASI (Entry Point) ===
def manage_risk_and_open_position(
    client: Client, 
    symbol: str, 
    signal: str, 
    confidence: float, 
    current_price: float, 
    last_atr: float, # v21.0: Volatilite
    exchange_rules: Dict
):
    
    # KONTROL 1: (v16.0) Pozisyon zaten açık mı?
    with _active_positions_lock:
        if symbol in active_positions:
            log.debug(f"{symbol} atlanıyor (zaten pozisyonda).")
            return

    # KONTROL 2: (v13.0) Korelasyon Riski var mı?
    if _check_correlation_risk(client, symbol, signal):
        return # Emir atlandı

    # KONTROL 3: (v16.0) "Kasa"da (Slot) yer var mı?
    with _active_positions_lock:
        current_pos_count = len(active_positions)
    
    if current_pos_count < config.MAX_CONCURRENT_POSITIONS:
        # EVET. "Kasa"da (Slot) yer var (örn: 0/2 veya 1/2).
        log.info(f"Kasa (Slot) mevcut ({current_pos_count}/{config.MAX_CONCURRENT_POSITIONS}). Yeni pozisyon açılıyor...")
        
        # v21.2: 'Süper Özellik #1' (ATR) ve 'Süper Özellik #2' (Dinamik Miktar)
        # mantığını içeren 'v21.2' fonksiyonunu çağır.
        _open_position_logic(client, symbol, signal, current_price, last_atr, exchange_rules)
    
    # KONTROL 4: (v16.0) "Fırsatçı Yeniden Dengeleme"
    elif config.OPPORTUNISTIC_REBALANCE_ENABLED:
        # HAYIR. "Kasa" (Slot) dolu (örn: 2/2).
        
        if confidence >= config.OPPORTUNISTIC_REBALANCE_THRESHOLD:
            log.warning(f"--- [v16.0 FIRSATÇI YENİDEN DENGELEME] ---")
            log.warning(f"MÜKEMMEL SİNYAL TESPİT EDİLDİ: {symbol} (Güven: {confidence:.2f})")
            log.warning(f"Kasa (Slot) dolu (2/2). 'En Zayıf' pozisyon aranıyor...")
            
            # 1. "En Zayıf" pozisyonu bul (v21.0: Hızlı, RAM'den okur)
            weakest_symbol, weakest_pnl = _get_weakest_open_position()
            
            if weakest_symbol:
                log.warning(f"'En Zayıf' pozisyon: {weakest_symbol} (Anlık PnL: {weakest_pnl:.4f} USDT).")
                
                # 2. "En Zayıf" pozisyonu kapat
                _close_position_by_symbol(client, weakest_symbol, f"v16.0 Fırsatçı Yeniden Dengeleme ({symbol} sinyali için yer açılıyor)")
                
                # 3. "Mükemmel" (A++) sinyali aç
                log.info(f"v16.0: Boşalan slota 'Mükemmel' sinyal ({symbol}) yerleştiriliyor...")
                # v21.2: 'Süper Özellik #1' (ATR) ve 'Süper Özellik #2' (Dinamik Miktar)
                # mantığını içeren 'v21.2' fonksiyonunu çağır.
                _open_position_logic(client, symbol, signal, current_price, last_atr, exchange_rules)
                
            else:
                log.error("v16.0: Yeniden dengeleme başarısız. 'En Zayıf' pozisyon bulunamadı (Hafıza (RAM) boş mu?).")
        
        else:
            log.warning(f"Sinyal bulundu: {symbol} (Güven: {confidence:.2f}).")
            log.warning(f"Kasa (Slot) dolu (2/2) ve sinyal 'Fırsatçı' (v16.0) eşiğini ({config.OPPORTUNISTIC_REBALANCE_THRESHOLD}) aşamadı. Emir atlanıyor.")
    
    else:
        log.warning(f"Kasa (Slot) dolu (2/2). {symbol} için yeni pozisyon açılmıyor (v16.0 Yeniden Dengeleme Kapalı).")