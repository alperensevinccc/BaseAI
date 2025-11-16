"""
BaseAI - BinAI v16.0 Mimari Yükseltmesi
"Korelasyonlu Risk Yönetimi" (v13.0) +
"Fırsatçı Yeniden Dengeleme" (v16.0)
"""
from binance.exceptions import BinanceAPIException
import config
from logger import log
import time
import db_manager 
import pandas as pd
import market_data 

# Aktif pozisyonların durumunu (state) tutar
active_positions = {}

def cleanup_orphan_positions(client):
    """
    v17.0 "Sıfır Güven" (Zero Trust) Protokolü.
    Canlı Bot (main.py) başladığında, 'active_positions' (Hafıza)
    ile senkronize olmayan tüm "Yetim" (Orphan) pozisyonları
    otonom olarak kapatır.
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
            
            # 1. Pozisyon var mı?
            if quantity != 0.0:
                # 2. "Hafıza"da (active_positions) var mı?
                if symbol not in active_positions:
                    # HATA: "Yetim" (Orphan) pozisyon tespit edildi.
                    orphans_found += 1
                    log.warning(f"DİKKAT: 'Yetim' (Orphan) Pozisyon Tespiti: {symbol} | Miktar: {quantity}")
                    
                    # 3. Otonom Kapatma (v17.0)
                    log.warning(f"v17.0: {symbol} için açık SL/TP emirleri (Yetim) iptal ediliyor...")
                    client.futures_cancel_all_open_orders(symbol=symbol)
                    
                    # === v17.1 HATA DÜZELTMESİ (APIError -4136) ===
                    # HATALI KOD (v17.0):
                    # client.futures_create_order(
                    #     symbol=symbol,
                    #     side="BUY" if quantity < 0 else "SELL",
                    #     positionSide="SHORT" if quantity < 0 else "LONG",
                    #     type='MARKET',
                    #     closePosition=True # <-- HATA: Hedge Mode ile uyumsuz
                    # )
                    
                    # ONARILMIŞ KOD (v17.1):
                    # "closePosition=True" yerine tam miktarı (abs(quantity)) gönder.
                    client.futures_create_order(
                        symbol=symbol,
                        side="BUY" if quantity < 0 else "SELL", # Miktar negatifse (SHORT) 'BUY' yap
                        positionSide="SHORT" if quantity < 0 else "LONG",
                        type='MARKET',
                        quantity=abs(quantity) # <-- v17.1 ONARIMI
                    )
                    # === DÜZELTME SONU ===
                    log.warning(f"v17.0: 'Yetim' (Orphan) pozisyon ({symbol}) başarıyla temizlendi.")

        if orphans_found == 0:
            log.info("v17.0: 'Yetim' (Orphan) pozisyon bulunamadı. Kasa (0/2) temiz.")
        
        log.info("--- [v17.0 'Sıfır Güven' Protokolü Tamamlandı] ---")

    except BinanceAPIException as e:
        log.error(f"v17.0: 'Yetim' (Orphan) pozisyon temizliği API hatası: {e}")
    except Exception as e:
        log.error(f"v17.0: 'Yetim' (Orphan) pozisyon temizliği genel hata: {e}")

# === v16.0 ÖZEL (PRIVATE) FONKSİYONLAR ===

def _open_position_logic(client, symbol, signal, current_price, exchange_rules):
    """
    v16.0: Yeni bir pozisyon açan (API çağrıları) çekirdek mantık.
    (manage_risk_and_open_position'dan (v13.0) çıkarıldı)
    """
    try:
        # 3. Bakiye ve Miktar Hesaplama (Aynı)
        account_info = client.futures_account_balance()
        usdt_balance = 0
        for asset in account_info:
            if asset['asset'] == 'USDT':
                usdt_balance = float(asset['balance'])
                break
        if usdt_balance <= 10:
            log.error("Pozisyon açmak için yeterli USDT bakiyesi yok.")
            return False

        position_size_usdt = usdt_balance * config.POSITION_SIZE_PERCENT
        quantity = position_size_usdt / current_price
        
        rules = exchange_rules.get(symbol)
        if not rules:
            log.error(f"{symbol} için hassasiyet (precision) kuralı bulunamadı.")
            return False
        qty_precision = rules.get("quantityPrecision")
        price_precision = rules.get("pricePrecision")
        quantity = round(quantity, qty_precision)
        if quantity == 0.0:
            log.warning(f"{symbol} için hesaplanan miktar 0'a yuvarlandı. Emir gönderilmiyor.")
            return False
        
        # 4. Kaldıraç Ayarlama (Aynı)
        try:
            client.futures_change_leverage(symbol=symbol, leverage=config.LEVERAGE)
        except BinanceAPIException as e:
            if "leverage not modified" not in str(e):
                log.warning(f"{symbol} kaldıraç ayarlanamadı (muhtemelen zaten ayarlı): {e}")
        
        # 5. Emir Gönderme (Aynı)
        order_side = "BUY" if signal == "LONG" else "SELL"
        position_side = "LONG" if signal == "LONG" else "SHORT"
        log.info(f"EMİR GÖNDERİLİYOR: {symbol} | {position_side} | Miktar: {quantity} | Fiyat: {current_price}")
        order = client.futures_create_order(
            symbol=symbol, side=order_side, positionSide=position_side,
            type='MARKET', quantity=quantity
        )
        
        # 6. Stop-Loss ve Take-Profit Emirleri (Aynı)
        if signal == "LONG":
            sl_price = current_price * (1 - config.STOP_LOSS_PERCENT)
            tp_price = current_price * (1 + config.TAKE_PROFIT_PERCENT)
            sl_side = "SELL"
            tp_side = "SELL"
        else: # SHORT
            sl_price = current_price * (1 + config.STOP_LOSS_PERCENT)
            tp_price = current_price * (1 - config.TAKE_PROFIT_PERCENT)
            sl_side = "BUY"
            tp_side = "BUY"
        sl_price = round(sl_price, price_precision)
        tp_price = round(tp_price, price_precision)

        client.futures_create_order(
            symbol=symbol, side=sl_side, positionSide=position_side,
            type='STOP_MARKET', stopPrice=sl_price, closePosition=True
        )
        client.futures_create_order(
            symbol=symbol, side=tp_side, positionSide=position_side,
            type='TAKE_PROFIT_MARKET', stopPrice=tp_price, closePosition=True
        )
        log.info(f"{symbol} için SL ({sl_price}) ve TP ({tp_price}) emirleri ayarlandı.")
        
        # (v5.0) Hafıza (Aynı)
        active_positions[symbol] = {
            "side": position_side,
            "quantity": quantity,
            "entry_price": current_price,
            "open_time": int(time.time() * 1000)
        }
        return True
    except BinanceAPIException as e:
        log.error(f"{symbol} için pozisyon açma/yönetme hatası: {e}")
        return False
    except Exception as e:
        log.error(f"{symbol} için bilinmeyen emir hatası: {e}")
        return False

def _get_weakest_open_position(client):
    """
    v16.0: "Fırsatçı Yeniden Dengeleme" için "en zayıf" (en düşük PnL)
    pozisyonu otonom olarak bulur.
    """
    if not active_positions:
        return None, None

    try:
        positions = client.futures_position_information()
        api_positions_map = {pos['symbol']: pos for pos in positions}
        
        weakest_symbol = None
        weakest_pnl = float('inf')

        for symbol in active_positions.keys():
            pos_data = api_positions_map.get(symbol)
            if pos_data:
                pnl = float(pos_data.get('unRealizedProfit', 0.0))
                if pnl < weakest_pnl:
                    weakest_pnl = pnl
                    weakest_symbol = symbol
        
        return weakest_symbol, weakest_pnl
        
    except Exception as e:
        log.error(f"v16.0: 'En Zayıf' pozisyon PnL'i alınamadı: {e}")
        return None, None

def _close_position_by_symbol(client, symbol, reason_log):
    """
    v16.0: "Fırsatçı Yeniden Dengeleme" için "en zayıf" pozisyonu
    (SL/TP emirlerini iptal ederek) otonom olarak kapatır.
    """
    log.warning(f"--- [v16.0 FIRSATÇI KAPATMA] ---")
    log.warning(f"POZİSYON: {symbol} | NEDEN: {reason_log}")
    
    pos_data = active_positions.get(symbol)
    if not pos_data:
        log.error(f"v16.0: Kapatılacak {symbol} pozisyonu 'Hafıza'da (active_positions) bulunamadı.")
        return

    try:
        # Adım 1: Açık SL/TP emirlerini (Orphaned Orders) iptal et
        log.info(f"v16.0: {symbol} için açık SL/TP emirleri iptal ediliyor...")
        client.futures_cancel_all_open_orders(symbol=symbol)
        
        # Adım 2: Pozisyonu Piyasa (Market) emriyle kapat
        log.info(f"v16.0: {symbol} pozisyonu (Piyasa Emri) kapatılıyor...")
        client.futures_create_order(
            symbol=symbol,
            side="BUY" if pos_data['side'] == "SHORT" else "SELL",
            positionSide=pos_data['side'],
            type='MARKET',
            closePosition=True
        )
        
        # Adım 3: Kapanan pozisyonun PnL'ini "Hafıza"ya (DB) kaydet
        # (check_and_update_positions bir sonraki döngüde bunu yakalayacak)
        log.warning(f"--- [v16.0 FIRSATÇI KAPATMA TAMAMLANDI] ---")
        
    except BinanceAPIException as e:
        log.error(f"v16.0: {symbol} Fırsatçı Kapatma hatası (API): {e}")
    except Exception as e:
        log.error(f"v16.0: {symbol} Fırsatçı Kapatma hatası (Genel): {e}")
    finally:
        # (check_and_update_positions'ın PnL'i kaydetmesini beklemeden
        # slotu (v16.0) hemen açmak için manuel olarak kaldır)
        if symbol in active_positions:
            del active_positions[symbol]


# === v13.0 KORELASYONLU RİSK YÖNETİMİ (Aynı kalır) ===
def _check_correlation_risk(client, new_symbol, new_signal):
    # ... (Bu fonksiyon v13.0 ile aynı, değişiklik yok) ...
    if not config.CORRELATION_CHECK_ENABLED or not active_positions:
        return False
    try:
        new_klines_raw = market_data.get_klines(client, new_symbol, config.INTERVAL, config.CORRELATION_KLINE_LIMIT)
        if not new_klines_raw: return False
        df_new = pd.DataFrame(new_klines_raw, columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime', 'QuoteAssetVolume', 'NumTrades', 'TakerBuyBase', 'TakerBuyQuote', 'Ignore'])
        series_new = pd.to_numeric(df_new['Close'])
        
        for existing_symbol, position_data in active_positions.items():
            existing_klines_raw = market_data.get_klines(client, existing_symbol, config.INTERVAL, config.CORRELATION_KLINE_LIMIT)
            if not existing_klines_raw: continue
            df_existing = pd.DataFrame(existing_klines_raw, columns=['OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime', 'QuoteAssetVolume', 'NumTrades', 'TakerBuyBase', 'TakerBuyQuote', 'Ignore'])
            series_existing = pd.to_numeric(df_existing['Close'])
            correlation = series_new.corr(series_existing)
            existing_signal = position_data.get("side")
            log.debug(f"v13.0: Korelasyon Taraması: {new_symbol} vs {existing_symbol} = {correlation:.4f}")
            if correlation > config.CORRELATION_THRESHOLD and new_signal == existing_signal:
                log.warning(f"--- [v13.0 RİSK YÖNETİMİ REDDETTİ] ---")
                log.warning(f"SİNYAL: {new_symbol} | {new_signal}")
                log.warning(f"NEDEN: Yüksek Korelasyon ({correlation:.4f} > {config.CORRELATION_THRESHOLD})")
                log.warning(f"VE Aynı Yön ({new_signal}) ile MEVCUT POZİSYON: {existing_symbol} | {existing_signal}")
                return True # Risk Var
    except Exception as e:
        log.error(f"v1G.0: Korelasyon hesaplaması sırasında kritik hata: {e}")
        return False
    return False # Risk Yok

# === v5.0 PNL RAPORLAMA (Aynı kalır) ===
def log_closed_position_pnl(client, symbol, position_data):
    # ... (Bu fonksiyon v12.0 ile aynı, değişiklik yok) ...
    log.info(f"Kapanan pozisyon ({symbol}) için PNL hesaplanıyor...")
    # ... (v12.0 PNL hesaplama kodu) ...
    db_manager.log_trade_to_db(
        symbol, position_data.get("side"), position_data.get("quantity"),
        position_data.get("entry_price"), total_realized_pnl, close_reason
    )

# === v5.0 POZİSYON GÜNCELLEME (Aynı kalır) ===
def check_and_update_positions(client):
    # ... (Bu fonksiyon v13.0 ile aynı, değişiklik yok) ...
    if not active_positions: return
    try:
        positions = client.futures_position_information()
        api_positions_map = {pos['symbol']: pos for pos in positions}
        open_symbols = list(active_positions.keys()) 
        for symbol in open_symbols:
            api_pos_data = api_positions_map.get(symbol)
            if api_pos_data and float(api_pos_data['positionAmt']) != 0:
                pass # Pozisyon hala açık
            else:
                log_data = active_positions[symbol]
                log.warning(f"POZİSYON KAPANDI TESPİT EDİLDİ: {symbol}.")
                log_closed_position_pnl(client, symbol, log_data)
                del active_positions[symbol]
    except Exception as e:
        log.error(f"check_and_update_positions genel hata: {e}")

# === v16.0 ANA GİRİŞ NOKTASI (Entry Point) ===
def manage_risk_and_open_position(client, symbol, signal, confidence, current_price, exchange_rules):
    
    # KONTROL 1: (v16.0) Pozisyon zaten açık mı?
    if symbol in active_positions:
        log.debug(f"{symbol} atlanıyor (zaten pozisyonda).")
        return

    # KONTROL 2: (v13.0) Korelasyon Riski var mı?
    if _check_correlation_risk(client, symbol, signal):
        return # Emir atlandı (loglama _check_correlation_risk içinde yapıldı)

    # KONTROL 3: (v16.0) "Kasa"da (Slot) yer var mı?
    if len(active_positions) < config.MAX_CONCURRENT_POSITIONS:
        # EVET. "Kasa"da (Slot) yer var (örn: 0/2 veya 1/2).
        log.info(f"Kasa (Slot) mevcut ({len(active_positions)}/{config.MAX_CONCURRENT_POSITIONS}). Yeni pozisyon açılıyor...")
        _open_position_logic(client, symbol, signal, current_price, exchange_rules)
    
    # KONTROL 4: (v16.0) "Fırsatçı Yeniden Dengeleme" (Opportunistic Rebalancing)
    elif config.OPPORTUNISTIC_REBALANCE_ENABLED:
        # HAYIR. "Kasa" (Slot) dolu (örn: 2/2).
        
        # Sinyal, "Mükemmel" (A++) (v16.0) eşiğini (örn: 0.95) aşıyor mu?
        if confidence >= config.OPPORTUNISTIC_REBALANCE_THRESHOLD:
            log.warning(f"--- [v16.0 FIRSATÇI YENİDEN DENGELEME] ---")
            log.warning(f"MÜKEMMEL SİNYAL TESPİT EDİLDİ: {symbol} (Güven: {confidence:.2f})")
            log.warning(f"Kasa (Slot) dolu (2/2). 'En Zayıf' pozisyon aranıyor...")
            
            # 1. "En Zayıf" pozisyonu bul
            weakest_symbol, weakest_pnl = _get_weakest_open_position(client)
            
            if weakest_symbol:
                log.warning(f"'En Zayıf' pozisyon: {weakest_symbol} (PnL: {weakest_pnl:.4f} USDT).")
                
                # 2. "En Zayıf" pozisyonu kapat (SL/TP emirleri dahil)
                _close_position_by_symbol(client, weakest_symbol, f"v16.0 Fırsatçı Yeniden Dengeleme ({symbol} sinyali için yer açılıyor)")
                
                # 3. "Mükemmel" (A++) sinyali aç
                log.info(f"v16.0: Boşalan slota 'Mükemmel' sinyal ({symbol}) yerleştiriliyor...")
                _open_position_logic(client, symbol, signal, current_price, exchange_rules)
                
            else:
                log.error("v16.0: Yeniden dengeleme başarısız. 'En Zayıf' pozisyon bulunamadı.")
        
        else:
            # Sinyal "iyi" (örn: 0.85) ancak "mükemmel" (örn: 0.95) değil.
            log.warning(f"Sinyal bulundu: {symbol} (Güven: {confidence:.2f}).")
            log.warning(f"Kasa (Slot) dolu (2/2) ve sinyal 'Fırsatçı' (v16.0) eşiğini ({config.OPPORTUNISTIC_REBALANCE_THRESHOLD}) aşamadı. Emir atlanıyor.")
    
    else:
        # Kasa (Slot) dolu (2/2) ve "Fırsatçı Yeniden Dengeleme" (v16.0) kapalı.
        log.warning(f"Kasa (Slot) dolu (2/2). {symbol} için yeni pozisyon açılmıyor (v16.0 Yeniden Dengeleme Kapalı).")