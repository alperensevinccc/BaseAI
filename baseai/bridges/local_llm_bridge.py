"""
BaseAI Lokal LLM Köprüsü (Ollama Entegrasyonu - Nihai Sürüm).

Bu modül, GPT/Gemini gibi harici, maliyetli API'lere olan bağımlılığı
ortadan kaldırır. BaseAI'nin 'Ollama' (ve Llama 3 gibi modeller) 
üzerinden yerel olarak çalışmasını sağlar.

SÜRÜM: 2.0 (Deterministik JSON Onarım Entegrasyonu)
"""

from __future__ import annotations
import os
import json
import time
import asyncio
import re
import contextlib
from typing import (
    Any, Dict, Optional, List, Callable, Awaitable, AsyncIterable, Union, cast
)

# HTTP istemcisi için (Ollama API'si ile konuşmak)
import httpx

# --- Logging Kurulumu ---
with contextlib.suppress(ImportError, AttributeError):
    from baseai.log.logger import bridge_logger as log
if "log" not in globals() or log is None:
    import logging
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    log = logging.getLogger("LocalLLMBridge_Fallback")
    log.warning("BaseAI bridge_logger bulunamadı. Fallback logger kullanılıyor.")

__all__ = ["LocalLLMBridge", "local_llm_bridge"]

# --- Yapılandırma ---
# Donanım kısıtlamalarını (8GB RAM) aşmak için Llama 3 8B (q5_K_M) kullanıyoruz.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct-q5_K_M") 
# Lokal modelin düşünme süresi (10 dakika)
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SEC", "600")) 
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434/api/generate/") # Yönlendirme için / içerir

# [YENİ] Programatik onarım için maksimum deneme sayısı
MAX_JSON_FIX_ATTEMPTS = 15

# --- JSON İşleme (Geliştirildi) ---
def _clean_json_output(raw_text: Optional[str]) -> str:
    """Lokal modelin ham metin çıktısından JSON bloğunu ayıklar."""
    if not raw_text: return ""
    text = raw_text.strip()
    
    # 1. Ham JSON bloğunu regex ile bul (en esnek yöntem)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        extracted = match.group(0).strip()
        log.debug(f"[LocalBridge|JSON] Regex ile JSON bloğu ayıklandı: {extracted[:100]}...")
        # [KALDIRILDI] Hatalı replace(r'\"', '"') çağrısı kaldırıldı.
        # Bu, geçerli JSON'u bozuyordu.
        return extracted
        
    # 2. Markdown çitlerini (```json ... ```) temizle
    try:
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) > 1:
                content = parts[1].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
                log.debug(f"[LocalBridge|JSON] Markdown çitleri temizlendi: {content[:100]}...")
                # [KALDIRILDI] Hatalı replace çağrısı buradan da kaldırıldı.
                return content
    except Exception:
        pass 

    log.warning("[LocalBridge|JSON] JSON temizlenemedi. Ham çıktı deneniyor.")
    return text

def _safe_parse_json(json_string: str) -> Dict[str, str]:
    """
    [YENİDEN İNŞA EDİLDİ]
    Metni güvenli bir şekilde Dict[str, str]'ye dönüştürür.
    JSONDecodeError hatasını yakalar ve 'proaktif onarım' dener.
    """
    if not json_string: 
        return {}

    current_string = json_string
    attempts = 0

    while attempts < MAX_JSON_FIX_ATTEMPTS:
        try:
            data = json.loads(current_string)
            if isinstance(data, dict):
                # Başarılı onarım veya ilk denemede başarı
                if attempts > 0:
                    log.info(f"[LocalBridge|JSON] ✅ Programmatik JSON onarımı {attempts} denemede BAŞARILI.")
                return {str(k): str(v) for k, v in data.items()}
            else:
                log.error(f"[LocalBridge|JSON] JSON geçerli ancak beklenen format (dict) değil. Tür: {type(data)}")
                return {}
        
        except json.JSONDecodeError as e:
            attempts += 1
            pos = e.pos
            
            # Hata konumu dizenin dışındaysa veya onarılamaz bir hataysa dur.
            if pos >= len(current_string):
                log.error(f"[LocalBridge|JSON] Onarılamaz JSON hatası (pozisyon dışı): {e}")
                log.debug(f"Hatalı JSON Metni:\n{current_string[:500]}")
                return {}

            # KÖK NEDEN: Kod içindeki kaçışsız tırnak işareti (").
            # Hata mesajı genellikle 'Expecting ',' delimiter' olur.
            # Hatanın olduğu pozisyondaki karakteri kontrol et.
            # Eğer bu bir tırnak işaretiyse ve bir kaçış karakteri değilse,
            # önüne bir kaçış karakteri (\) ekle.
            
            log.warning(
                f"[LocalBridge|JSON] Programmatik Düzeltme Denemesi ({attempts}/{MAX_JSON_FIX_ATTEMPTS}): "
                f"JSON hatası algılandı: {e.msg} (Pozisyon: {pos}). Onarım deniyor..."
            )

            # En yaygın hatayı (kaçışsız tırnak) onar
            if current_string[pos] == '"' and (pos == 0 or current_string[pos-1] != '\\'):
                # Hatalı pozisyona kaçış karakteri ekle
                current_string = current_string[:pos] + '\\' + current_string[pos:]
            elif current_string[pos] in ('\n', '\r', '\t'):
                # Kaçışsız kontrol karakterlerini onar
                replacement = {'\n': '\\n', '\r': '\\r', '\t': '\\t'}[current_string[pos]]
                current_string = current_string[:pos] + replacement + current_string[pos+1:]
            else:
                # Başka bir karakterde beklenmedik hata, onarılamıyor.
                log.error(f"[LocalBridge|JSON] Bilinmeyen JSON onarım hatası. Karakter: '{current_string[pos]}' (Pozisyon: {pos}). {e}")
                log.debug(f"Hatalı JSON Metni:\n{current_string[:500]}")
                return {}
        
        except Exception as e:
            # json.loads dışında başka bir kritik hata
            log.critical(f"[LocalBridge|JSON] JSON işlemede bilinmeyen kritik hata: {e}", exc_info=True)
            return {}

    log.error(f"[LocalBridge|JSON] ❌ Programmatik JSON onarımı BAŞARISIZ ({MAX_JSON_FIX_ATTEMPTS} deneme aşıldı).")
    log.debug(f"Onarılamayan JSON Metni (ilk 500 karakter):\n{json_string[:500]}")
    return {}


# --- Sistem Talimatları (Lokal Model Uyumlu) ---
SYSTEM_PROMPT_JSON = (
    "You are a helpful assistant that only returns valid, raw JSON objects. "
    "Do not include any explanations or markdown fences (```json)."
)
SYSTEM_PROMPT_TEXT = (
    "You are a helpful assistant. Provide concise, plain-text answers. "
    "Do not use markdown."
)
SYSTEM_PROMPT_JSON_FIXER = (
    "You are a JSON repair utility. Analyze the following broken text. "
    "Your response MUST be ONLY the valid, raw JSON object extracted or repaired from the text."
)

# --- Ana Köprü Sınıfı ---
class LocalLLMBridge:
    _client: httpx.AsyncClient
    model: str
    
    def __init__(self) -> None:
        try:
            self.model = OLLAMA_MODEL
            self._client = httpx.AsyncClient(
                base_url=OLLAMA_API_URL,
                timeout=OLLAMA_TIMEOUT,
                verify=False, 
                follow_redirects=True # HTTP 307 hatasını çözmek için eklendi
            )
            log.info(f"LocalLLMBridge (Ollama) hazır ✅ (Model={self.model}, URL={OLLAMA_API_URL})")
        except Exception as e:
            log.critical(f"[LocalBridge|FATAL] Başlatma sırasında beklenmedik hata: {e}", exc_info=True)
            raise

    async def _internal_async_generate(
        self, 
        prompt: str, 
        system_prompt: str,
        format_json: bool = False
    ) -> str:
        """Çekirdek asenkron Ollama üretim fonksiyonu."""
        
        request_body = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False 
        }
        if format_json:
            request_body["format"] = "json" 

        log.debug(f"[LocalBridge|API] Ollama isteği gönderiliyor (Model={self.model})...")
        
        try:
            response = await self._client.post(url="", json=request_body)
            response.raise_for_status() 
            response_data = response.json()
            
            if response_data.get("response"):
                log.debug(f"[LocalBridge|API] Ollama yanıtı başarılı.")
                return response_data["response"]
            else:
                log.error(f"[LocalBridge|API] Ollama'dan beklenmedik/boş yanıt: {response_data}")
                return f"[BaseAI Hata: Lokal modelden boş yanıt]"

        except httpx.ConnectError as e:
            log.critical(f"[LocalBridge|FATAL] Ollama sunucusuna bağlanılamadı ({OLLAMA_API_URL}). "
                         "Ollama'nın çalıştığından emin olun. Hata: {e}")
            raise RuntimeError(f"Ollama sunucusuna bağlanılamadı. Ollama çalışıyor mu? Hata: {e}") from e
        except httpx.ReadTimeout as e:
            log.error(f"[LocalBridge|API] Okuma Zaman Aşımı: Lokal model (Ollama) {OLLAMA_TIMEOUT} saniye içinde yanıt veremedi. Donanım yetersiz veya görev çok karmaşık. {e}")
            return f"[BaseAI Hata: Metin üretilemedi - ReadTimeout: {e}]"
        except httpx.HTTPStatusError as e:
            log.error(f"[LocalBridge|API] API Hatası ({e.response.status_code}): {e.response.text}")
            return f"[BaseAI Hata: Lokal API Hatası - {e.response.status_code}]"
        except Exception as e:
            log.error(f"[LocalBridge|API] generate_text başarısız oldu: {e}", exc_info=True)
            return f"[BaseAI Hata: Metin üretilemedi - {type(e).__name__}: {e}]"

    async def generate_text(self, instruction: str, context: str = "") -> str:
        """Lokal olarak düz metin üretir."""
        log.info(f"[LocalBridge] Metin üretimi başlatıldı (Talimat: {instruction[:50]}...).")
        full_prompt = f"BAĞLAM:\n{context or 'Yok'}\n\nTALİMAT:\n{instruction.strip()}"
        return await self._internal_async_generate(
            prompt=full_prompt,
            system_prompt=SYSTEM_PROMPT_TEXT
        )

    async def generate_files(
        self, 
        instruction: str, 
        context: str = "", 
        *, 
        rules: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Lokal olarak dosya içeriği (JSON) üretir."""
        log.info(f"[LocalBridge] Dosya (JSON) üretimi başlatıldı (Talimat: {instruction[:50]}...).")
        rule_block = "Kurallar:\n" + ("\n".join(f"- {r}" for r in rules) if rules else "Yok")
        user_prompt = (
            f"{rule_block}\n\n"
            f"BAĞLAM (Referans Kod/Veri):\n{context or 'Yok'}\n\n"
            f"GÖREV (TASK):\n{instruction.strip()}\n\n"
            "SADECE İSTENEN JSON NESNESİNİ DÖNDÜR."
        )

        try:
            raw_text = await self._internal_async_generate(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT_JSON,
                format_json=True
            )
            
            cleaned_text = _clean_json_output(raw_text) 
            # [GÜNCELLENDİ] _safe_parse_json artık onarım yeteneğine sahip.
            data = _safe_parse_json(cleaned_text)

            if data:
                log.info(f"[LocalBridge] ✅ Başarılı JSON üretimi ({len(data)} dosya).")
                return data

            # Eğer programmatik onarım başarısız olursa, LLM tabanlı onarımı dene.
            log.warning("[LocalBridge] Programmatik JSON onarımı başarısız. LLM tabanlı 'Kendi kendini düzeltme' deneniyor...")
            fixer_prompt = f"Aşağıdaki metinden geçerli JSON nesnesini çıkar/düzelt:\n```\n{raw_text}\n```"
            
            fixed_raw_text = await self._internal_async_generate(
                prompt=fixer_prompt,
                system_prompt=SYSTEM_PROMPT_JSON_FIXER,
                format_json=True
            )
            
            cleaned_fixed_text = _clean_json_output(fixed_raw_text)
            # Programmatik onarımı burada tekrar dene
            fixed_data = _safe_parse_json(cleaned_fixed_text)
            
            if fixed_data:
                log.info("[LocalBridge] ✅ LLM tabanlı kendi kendini düzeltme BAŞARILI.")
                return fixed_data
            else:
                log.error("[LocalBridge] ❌ Kendi kendini düzeltme (hem programmatik hem LLM) BAŞARISIZ.")
                # Orijinal metni de logla
                log.debug(f"Onarılamayan Orijinal Metin:\n{raw_text[:500]}")
                return {"error": "JSON_FIX_PARSE_FAILED", "original_text": raw_text, "fixed_text": fixed_raw_text}

        except Exception as e:
            log.critical(f"[LocalBridge] generate_files sırasında kritik hata: {e}", exc_info=True)
            return {"error": f"CRITICAL_FAILURE ({type(e).__name__}): {e}"}

# --- Singleton (Tekil Örnek) ---
_SINGLETON: Optional[LocalLLMBridge] = None
_singleton_lock = asyncio.Lock()

async def local_llm_bridge() -> LocalLLMBridge:
    """
    LocalLLMBridge'in tekil (singleton) örneğini asenkron olarak döndürür.
    """
    global _SINGLETON
    if _SINGLETON is not None:
        return _SINGLETON
        
    async with _singleton_lock:
        if _SINGLETON is None:
            log.debug("[LocalBridge] Singleton köprü örneği oluşturuluyor...")
            try:
                _SINGLETON = LocalLLMBridge()
            except Exception as e:
                 log.critical(f"[LocalBridge|FATAL] Singleton oluşturulamadı: {e}", exc_info=True)
                 raise RuntimeError(f"Failed to initialize Local LLM Bridge: {e}") from e
                 
    return _SINGLETON