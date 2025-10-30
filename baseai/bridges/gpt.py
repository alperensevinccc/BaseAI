# baseai/bridges/gpt.py
"""
BaseAI için OpenAI GPT Modellerine Erişim Köprüsü (Nihai Sürüm).

Bu modül, `openai>=1.0` kütüphanesini kullanarak BaseAI'nin 
OpenAI'nin Chat Completion API'si (GPT-3.5, GPT-4 vb.) ile etkileşim kurmasını sağlar.
Asenkron işlemler, gelişmiş hata yönetimi, yeniden deneme mekanizmaları,
JSON işleme, token sayımı ve streaming yetenekleri içerir.
"""

from __future__ import annotations
import os
import json
import time
import asyncio
import contextlib
import re
import traceback
from dataclasses import dataclass, field
from typing import (
    Any, Dict, Optional, List, Callable, Awaitable, AsyncIterable, Union, cast
)

# OpenAI Kütüphanesi (v1.0+) - Kurulum kontrolü
try:
    import openai
    from openai import AsyncOpenAI, RateLimitError, APIError, APITimeoutError, \
                   APIConnectionError, AuthenticationError, BadRequestError
    from openai.types.chat import ChatCompletionMessageParam
    from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
    from openai.types.chat.chat_completion import ChatCompletion
except ImportError:
    # Kritik hata: OpenAI kütüphanesi yoksa köprü çalışamaz.
    # Başlatma sırasında loglama henüz aktif olmayabilir, bu yüzden print kullanabiliriz.
    print(
        "FATAL: OpenAI library not found. Please install it using 'pip install openai>=1.0'.\n"
        "Ensure 'openai>=1.0' is in your requirements.txt file."
    )
    raise # Import hatasını tekrar yükselterek programın çökmesini sağla

# Token sayımı için Tiktoken (OpenAI standardı) - Opsiyonel
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    # Loglama henüz tam hazır olmayabilir, uyarıyı print ile de verebiliriz.
    print(
        "WARNING: 'tiktoken' library not found. Token counting will be disabled. "
        "Install it using 'pip install tiktoken'."
    )
    tiktoken = None # type: ignore 
    TIKTOKEN_AVAILABLE = False

# --- Logging Kurulumu ---
# Ana logger'ı bulamazsa basit bir fallback oluşturur.
with contextlib.suppress(ImportError, AttributeError):
    from baseai.log.logger import bridge_logger as log
if "log" not in globals() or log is None:
    import logging
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] (%(name)s:%(lineno)d) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger("GPTBridge_Fallback")
    log.warning("BaseAI bridge_logger bulunamadı. Fallback logger kullanılıyor.")

__all__ = ["GPTBridge", "gpt_bridge", "GPTConfig"]

# --- Yapılandırma ---
@dataclass
class GPTConfig:
    """
    GPTBridge için yapılandırma parametrelerini içeren veri sınıfı.
    Değerler öncelikle ortam değişkenlerinden okunur, yoksa varsayılanlar kullanılır.
    """
    api_key: str = field(repr=False) # Loglarda görünmemesi için repr=False
    model: str = "gpt-4-turbo" # Güçlü ve güncel bir varsayılan
    temperature: float = 0.2
    max_output_tokens: Optional[int] = None # OpenAI'nin model limitini kullan
    request_timeout: int = 300  # 5 dakika
    max_retries: int = 5
    initial_backoff_sec: float = 2.0
    # Tiktoken için model ailesi -> encoding adı eşleştirmesi
    tiktoken_encoding_map: Dict[str, str] = field(default_factory=lambda: {
        "gpt-4": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
    })

    @classmethod
    def load_from_env(cls) -> 'GPTConfig':
        """Ortam değişkenlerinden yapılandırmayı yükler."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("[GPT Bridge|Config] Kritik Hata: OPENAI_API_KEY ortam değişkeni tanımlı değil.")
        
        try:
            return cls(
                api_key=api_key,
                model=os.getenv("OPENAI_MODEL", "gpt-4-turbo"),
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
                max_output_tokens=int(max_tokens) if (max_tokens := os.getenv("OPENAI_MAX_TOKENS")) else None,
                max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "5")),
                initial_backoff_sec=float(os.getenv("OPENAI_BACKOFF_SEC", "2.0")),
                request_timeout=int(os.getenv("OPENAI_TIMEOUT_SEC", "300")),
            )
        except ValueError as e:
            log.error(f"[GPT Bridge|Config] Ortam değişkenleri okunurken değer hatası: {e}. Lütfen .env dosyanızı kontrol edin.")
            raise

# --- JSON İşleme ---

def _clean_json_output(raw_text: Optional[str]) -> str:
    """Modelin ham metin çıktısından JSON bloğunu ayıklar, hatalara karşı dayanıklıdır."""
    if not raw_text: return ""
    text = raw_text.strip()
    
    # 0. Agresif Ön-temizleme (Önceki yama): Bazı bozuk kaçış karakterlerini kaldır
    # Bu adımı sadece belirli hatalar için yapmalı, aksi takdirde geçerli JSON'u bozar.
    # Şimdilik bu adımı atlıyoruz ve sadece tırnaklara odaklanıyoruz.
    
    # 1. En içteki {} bloğunu bulmaya çalış
    # Bu adım genellikle en büyük JSON bloğunu yakalar.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        extracted = match.group(0).strip()
        
        # --- KRİTİK JSON TEMİZLEME MANTIĞI ---
        # 2. Hatalı ardışık tırnakları düzelten regex: 
        #    JSON değerinin başında veya sonunda hatalı biçimde dört tırnak varsa (örn: """), onu çift tırnağa indir.
        #    Bu, özellikle "content": """Python kodu""" gibi bir yapıyı "content": "Python kodu" yapmaya çalışır.
        # Hata kodu: """Processes user intents for the BaseAI application."""nn
        # Bu, dört tırnak (") ile başlar. İlk dört tırnağı atar.
        extracted = re.sub(r'("""|""")', '"', extracted)
        
        log.debug(f"[GPT Bridge|JSON] Regex ile JSON bloğu ayıklandı (Temizlendi): {extracted[:100]}...")
        return extracted
        
    # Regex başarısız olursa markdown çitlerini ara (aynı kalır)

def _safe_parse_json(json_string: str) -> Dict[str, str]:
    """Temizlenmiş metni güvenli bir şekilde Dict[str, str]'ye dönüştürür."""
    if not json_string: return {}
    try:
        data = json.loads(json_string)
        if isinstance(data, dict):
            # Anahtarların ve değerlerin string olduğundan emin ol
            return {str(k): str(v) for k, v in data.items()}
        else:
            log.warning(f"[GPT Bridge|JSON] JSON kökü 'dict' değil, '{type(data).__name__}' tipinde geldi. Boş dict döndürülüyor.")
            return {}
    except json.JSONDecodeError as e:
        log.error(f"[GPT Bridge|JSON] JSON ayrıştırma hatası (JSONDecodeError): {e}")
        log.debug(f"Hatalı JSON Metni (ilk 500 karakter):\n{json_string[:500]}")
        return {}
    except Exception as e:
        log.error(f"[GPT Bridge|JSON] JSON işlemede bilinmeyen kritik hata: {e}", exc_info=True)
        return {}

# --- Sistem Talimatları ---
SYSTEM_PROMPT_JSON = (
    "You are BaseAI's Enterprise+++++ Software Engineer. "
    "Your response MUST be ONLY a single, valid, raw JSON object mapping file paths to their full contents. "
    "Do NOT include explanations, comments, or markdown fences (```json)."
)
SYSTEM_PROMPT_TEXT = (
    "You are BaseAI's internal assistant. Provide concise, plain-text answers. "
    "Do not use markdown formatting, lists, or code blocks."
)
SYSTEM_PROMPT_JSON_FIXER = (
    "You are a JSON repair utility. Analyze the following broken text. "
    "Your response MUST be ONLY the valid, raw JSON object extracted or repaired from the text. "
    "Do not include explanations or markdown."
)

# --- Ana Köprü Sınıfı ---
class GPTBridge:
    """
    BaseAI için OpenAI GPT Modellerine Erişim Köprüsü (Nihai Sürüm).

    `openai>=1.0` kütüphanesini kullanarak asenkron işlemler, gelişmiş hata 
    yönetimi, yeniden deneme, JSON işleme, token sayımı ve streaming sağlar.
    Yapılandırma ortam değişkenlerinden yüklenir. Singleton olarak kullanılır.
    """
    _client: AsyncOpenAI
    config: GPTConfig
    _tokenizer: Optional[tiktoken.Encoding]

    def __init__(self, config: Optional[GPTConfig] = None) -> None:
        """
        GPTBridge örneğini başlatır. 
        Yapılandırmayı yükler ve AsyncOpenAI istemcisini oluşturur.
        """
        try:
            self.config = config or GPTConfig.load_from_env()
            
            # Asenkron OpenAI istemcisini başlat
            # max_retries=0: Kendi özel retry mekanizmamız kullanılacak
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                timeout=self.config.request_timeout,
                max_retries=0 
            )
            
            # Tokenizer'ı yükle (varsa)
            self._tokenizer = self._get_tokenizer() if TIKTOKEN_AVAILABLE else None

            log.info(f"GPTBridge (v1 - OpenAI SDK) hazır ✅ (Model={self.config.model}, Retries={self.config.max_retries})")

        except ValueError as e: # Config yükleme hatası
             log.critical(f"[GPT Bridge|FATAL] Yapılandırma hatası: {e}")
             raise # Yeniden yükselt, başlatmayı durdur
        except Exception as e:
            log.critical(f"[GPT Bridge|FATAL] Başlatma sırasında beklenmedik hata: {e}", exc_info=True)
            raise

    def _get_tokenizer(self) -> Optional[tiktoken.Encoding]:
        """Model adı için en uygun Tiktoken kodlayıcısını bulur ve döndürür."""
        if not tiktoken: return None # Kütüphane yüklenememişse None döndür
        
        # Öncelik sırası: 1) Tam model adı, 2) Model ailesi eşleşmesi, 3) Varsayılan
        try:
            # Doğrudan model adıyla dene (en doğru sonuç)
            log.debug(f"[GPT Bridge|Token] Model adı ile tokenizer aranıyor: {self.config.model}")
            return tiktoken.encoding_for_model(self.config.model)
        except KeyError:
            log.debug(f"Model adı '{self.config.model}' için doğrudan eşleşme bulunamadı, aile adı deneniyor...")
            # Model ailesine göre eşleştirme (örn: gpt-4-turbo -> gpt-4)
            model_key = self.config.model.lower()
            encoding_name = "cl100k_base" # Varsayılan (çoğu modern model için geçerli)
            for family, enc in self.config.tiktoken_encoding_map.items():
                if family in model_key:
                    encoding_name = enc
                    log.debug(f"Model ailesi '{family}' için eşleşme bulundu: '{encoding_name}'")
                    break
            
            try:
                log.info(f"[GPT Bridge|Token] Tokenizer yükleniyor: '{encoding_name}' (Model: {self.config.model})")
                return tiktoken.get_encoding(encoding_name)
            except Exception as e:
                log.error(f"[GPT Bridge|Token] Tiktoken kodlaması ('{encoding_name}') yüklenemedi: {e}. Token sayımı devre dışı.", exc_info=True)
                return None
        except Exception as e:
             log.error(f"[GPT Bridge|Token] Tiktoken yüklenirken beklenmedik hata: {e}. Token sayımı devre dışı.", exc_info=True)
             return None

    async def _async_retry_wrapper(
        self, 
        coro_func: Callable[[], Awaitable[Any]], 
        operation_name: str
    ) -> Any:
        """
        Asenkron OpenAI API çağrıları için hata yönetimi ve yeniden deneme.
        Geçici hatalarda üstel geri çekilme uygular, kalıcı hatalarda hemen çıkar.
        """
        last_exc: Exception = Exception(f"Bilinmeyen {operation_name} hatası")
        
        for attempt in range(self.config.max_retries + 1): # 0'dan max_retries'e kadar
            try:
                # Coroutine'i çalıştır ve sonucu döndür
                return await coro_func() 
            
            # --- Yeniden Denenebilir Hatalar ---
            except (RateLimitError, APITimeoutError, APIConnectionError, APIError) as e:
                # APIError genellikle 5xx sunucu hatalarını kapsar
                last_exc = e
                # Son deneme ise artık bekleme, hatayı yükselt
                if attempt == self.config.max_retries:
                    log.error(f"[GPT Bridge|Retry] {operation_name} {self.config.max_retries} denemeden sonra başarısız oldu (Son Hata: {type(e).__name__}).")
                    break # Döngüden çık ve hatayı aşağıda yükselt
                    
                # Geri çekilme süresini hesapla (jitter ile)
                delay = (self.config.initial_backoff_sec ** attempt) + (os.urandom(1)[0] * 0.1) # 0-0.1s arası jitter
                delay = min(delay, 30.0) # Maksimum 30 saniye bekle
                log.warning(
                    f"[GPT Bridge|Retry] {operation_name} geçici hatası ({type(e).__name__}) "
                    f"(Deneme {attempt + 1}/{self.config.max_retries}). {delay:.2f}s sonra tekrar denenecek."
                )
                await asyncio.sleep(delay)
                
            # --- Kalıcı Hatalar (Yeniden Denenmez) ---
            except (AuthenticationError, BadRequestError) as e:
                log.error(f"[GPT Bridge|API] {operation_name} Kritik/Kalıcı API Hatası ({type(e).__name__}): {e}", exc_info=True)
                raise e # Hatayı hemen yükselt, yeniden deneme anlamsız
                
            # --- Diğer Beklenmedik Hatalar ---
            except Exception as e:
                log.error(f"[GPT Bridge|System] {operation_name} sırasında beklenmeyen sistem hatası: {e}", exc_info=True)
                # Bu tür hatalar genellikle yeniden deneme ile düzelmez, ama bir kez deneyebiliriz?
                # Şimdilik: Kalıcı hata gibi davranıp hemen çıkalım.
                # İleri seviye: Hatanın türüne göre karar verilebilir.
                last_exc = e
                break # Döngüden çık ve hatayı aşağıda yükselt

        # Döngü bittiğinde (ya max_retries aşıldı ya da beklenmedik hata oldu) son hatayı yükselt
        raise last_exc


    async def _internal_async_chat_completion(
        self, 
        messages: List[ChatCompletionMessageParam],
        stream: bool = False,
        **kwargs: Any # Ekstra API parametreleri (örn: response_format) için
    ) -> Union[ChatCompletion, AsyncIterable[ChatCompletionChunk]]:
        """
        Çekirdek asenkron chat tamamlama fonksiyonu. 
        Hata yönetimi ve yeniden deneme sarmalayıcısını kullanır.
        """
        log.debug(f"[GPT Bridge|API] Chat completion isteği gönderiliyor (stream={stream}, model={self.config.model})...")
        
        async def api_call():
            # İstemci örneğini doğrudan kullan
            return await self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_output_tokens,
                stream=stream,
                **kwargs # Ekstra parametreleri ilet
            )

        # Yeniden deneme sarmalayıcısı ile API çağrısını yap
        return await self._async_retry_wrapper(
            api_call, 
            f"chat_completion(stream={stream})"
        )


    # --- Genel API Metotları ---

    async def generate_text(self, instruction: str, context: str = "") -> str:
        """
        Verilen talimat ve bağlama göre asenkron olarak düz metin üretir.
        Yanıtın tamamını bekler ve tek bir string olarak döndürür.
        Hata durumunda bilgilendirici bir string döndürür.
        """
        log.info(f"[GPT Bridge] Metin üretimi başlatıldı (Talimat: {instruction[:50]}...).")
        
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT_TEXT},
            {"role": "user", "content": f"BAĞLAM:\n{context or 'Yok'}\n\nTALİMAT:\n{instruction.strip()}"}
        ]
        
        try:
            # stream=False ile çağrı yap
            response = cast(ChatCompletion, await self._internal_async_chat_completion(messages, stream=False))
            
            # Yanıtı doğrula ve içeriği al
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                log.debug("[GPT Bridge] Metin üretimi başarılı.")
                return response.choices[0].message.content
            else:
                # Yanıt yapısı beklenmedik veya içerik boş
                finish_reason = response.choices[0].finish_reason if response.choices else "unknown"
                log.error(f"[GPT Bridge] generate_text boş veya hatalı yanıt aldı (finish_reason: {finish_reason}). Yanıt: {response.model_dump_json(indent=2)}")
                return f"[BaseAI Hata: Boş veya tamamlanmamış yanıt (Sebep: {finish_reason})]"
                
        except Exception as e:
            log.error(f"[GPT Bridge] generate_text başarısız oldu: {e}", exc_info=True)
            # Kullanıcıya hatayı daha net bildir
            return f"[BaseAI Hata: Metin üretilemedi - {type(e).__name__}: {e}]"

    async def generate_files(
        self, 
        instruction: str, 
        context: str = "", 
        *, 
        rules: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Verilen talimata göre asenkron olarak dosya içeriği (JSON) üretir.
        Hata durumunda 'kendi kendine düzeltme' yapar.
        Başarısızlık durumunda {"error": "..."} içeren bir dict döndürür.
        """
        log.info(f"[GPT Bridge] Dosya (JSON) üretimi başlatıldı (Talimat: {instruction[:50]}...).")
        
        rule_block = "Kurallar:\n" + ("\n".join(f"- {r}" for r in rules) if rules else "Yok")

        user_prompt = (
            f"{rule_block}\n\n"
            f"BAĞLAM (Referans Kod/Veri):\n{context or 'Yok'}\n\n"
            f"GÖREV (TASK):\n{instruction.strip()}"
        )
        messages: List[ChatCompletionMessageParam] = [
             {"role": "system", "content": SYSTEM_PROMPT_JSON},
             {"role": "user", "content": user_prompt}
        ]

        try:
            # JSON modu istemek (destekleyen modeller için)
            # Not: Bu, modelin JSON dışında bir şey döndürme olasılığını azaltır
            # ancak garanti etmez ve tüm modeller desteklemeyebilir.
            response_format = {"type": "json_object"} if "json" in self.config.model else None # Basit kontrol
            kwargs = {"response_format": response_format} if response_format else {}

            response = cast(ChatCompletion, await self._internal_async_chat_completion(messages, stream=False, **kwargs))
            
            if not (response.choices and response.choices[0].message and response.choices[0].message.content):
                finish_reason = response.choices[0].finish_reason if response.choices else "unknown"
                log.error(f"[GPT Bridge] JSON üretimi boş yanıt döndürdü (finish_reason: {finish_reason}).")
                return {"error": f"EMPTY_RESPONSE (finish_reason: {finish_reason})"}

            raw_text = response.choices[0].message.content
            # JSON modunda bile bazen temizleme gerekebilir
            cleaned_text = _clean_json_output(raw_text) 
            data = _safe_parse_json(cleaned_text)

            if data:
                log.info(f"[GPT Bridge] ✅ Başarılı JSON üretimi ({len(data)} dosya).")
                return data

            # --- JSON Ayrıştırma Başarısız: KENDİ KENDİNE DÜZELTME ---
            log.warning("[GPT Bridge] JSON ayrıştırma başarısız. Kendi kendini düzeltme deneniyor...")
            log.debug(f"Düzeltilecek Ham Metin:\n{raw_text}") # Düzeltme öncesi logla
            
            fixer_messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": SYSTEM_PROMPT_JSON_FIXER},
                {"role": "user", "content": f"Aşağıdaki metinden geçerli JSON nesnesini çıkar/düzelt:\n```\n{raw_text}\n```"}
            ]
            
            # Düzeltme için de JSON modu isteyebiliriz
            fix_response = cast(ChatCompletion, await self._internal_async_chat_completion(fixer_messages, stream=False, **kwargs))

            if not (fix_response.choices and fix_response.choices[0].message and fix_response.choices[0].message.content):
                 log.error("[GPT Bridge] JSON düzeltme denemesi boş yanıt döndürdü.")
                 return {"error": "JSON_FIX_EMPTY_RESPONSE", "original_text": raw_text}

            fixed_raw_text = fix_response.choices[0].message.content
            cleaned_fixed_text = _clean_json_output(fixed_raw_text) # Düzeltilmiş metni de temizle
            fixed_data = _safe_parse_json(cleaned_fixed_text)
            
            if fixed_data:
                log.info("[GPT Bridge] ✅ JSON kendi kendini düzeltme BAŞARILI.")
                return fixed_data
            else:
                log.error("[GPT Bridge] ❌ JSON kendi kendini düzeltme BAŞARISIZ.")
                log.debug(f"Başarısız Düzeltme Metni:\n{fixed_raw_text}")
                return {"error": "JSON_FIX_PARSE_FAILED", "original_text": raw_text, "fixed_text": fixed_raw_text}

        except Exception as e:
            log.critical(f"[GPT Bridge] generate_files sırasında kritik hata: {e}", exc_info=True)
            return {"error": f"CRITICAL_FAILURE ({type(e).__name__}): {e}"}

    async def generate_text_stream(
        self, 
        instruction: str, 
        context: str = "",
        system_instruction: str = SYSTEM_PROMPT_TEXT
    ) -> AsyncIterable[str]:
        """
        Metin yanıtını kelime kelime (stream) döndürür.
        Hata durumunda hata mesajını stream'e dahil eder.
        """
        log.info(f"[GPT Bridge] Metin stream başlatıldı (Talimat: {instruction[:50]}...).")
        
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"BAĞLAM:\n{context or 'Yok'}\n\nTALİMAT:\n{instruction.strip()}"}
        ]
        
        try:
            # stream=True ile çağrı yap
            stream = cast(AsyncIterable[ChatCompletionChunk], await self._internal_async_chat_completion(messages, stream=True))
            
            async for chunk in stream:
                # Stream parçasının içeriğini kontrol et
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        # Stream sırasında oluşabilecek hataları yakala
        except Exception as e:
            log.error(f"[GPT Bridge] Stream sırasında hata: {e}", exc_info=True)
            # Hatayı stream'in bir parçası olarak döndür
            yield f"[BaseAI Stream Hatası: {type(e).__name__}: {e}]"


    def count_tokens(
        self, 
        instruction: str, 
        context: str = "", 
        system_instruction: Optional[str] = None 
    ) -> int:
        """
        Verilen talimat, bağlam ve sistem talimatı için OpenAI API'sine 
        gönderilecek **tahmini** token sayısını (Tiktoken kullanarak) hesaplar.

        Returns:
            Hesaplanan token sayısı veya hata durumunda -1.
        """
        if not self._tokenizer:
            log.warning("[GPT Bridge|Token] Tiktoken yüklenemediği için token sayımı yapılamıyor.")
            return -1

        log.debug(f"[GPT Bridge|Token] Token sayımı başlatıldı...")
        
        messages: List[Dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": f"BAĞLAM:\n{context or 'Yok'}\n\nTALİMAT:\n{instruction.strip()}"})

        num_tokens = 0
        try:
            # OpenAI Cookbook'dan önerilen token sayma yöntemi
            # (Model adı hatalıysa KeyError verebilir)
            tokens_per_message = 3 
            tokens_per_name = 1
            
            for message in messages:
                num_tokens += tokens_per_message
                for key, value in message.items():
                    if value: # Sadece içeriği olanları say
                         num_tokens += len(self._tokenizer.encode(value))
                    if key == "name": # Eğer 'name' kullanılırsa (fonksiyon çağırmada vb.)
                        num_tokens += tokens_per_name
            num_tokens += 3 # Yanıt başlangıcı için

            log.info(f"[GPT Bridge|Token] Tahmini token sayımı: {num_tokens} (Model: {self.config.model})")
            return num_tokens
            
        except KeyError:
             log.error(f"[GPT Bridge|Token] Model '{self.config.model}' için Tiktoken kodlaması bulunamadı (KeyError). Sayım yapılamıyor.", exc_info=False) # Traceback gereksiz
             # Bu durumda tokenizer'ı None yapıp tekrar denemeleri engelleyebiliriz.
             # self._tokenizer = None 
             return -1
        except Exception as e:
            log.error(f"[GPT Bridge|Token] Tiktoken ile token sayımı sırasında beklenmedik hata: {e}", exc_info=True)
            return -1


# --- Singleton (Tekil Örnek) ---
_SINGLETON: Optional[GPTBridge] = None
_singleton_lock = asyncio.Lock() # Asenkron ortamda singleton oluştururken kilit kullanmak daha güvenli

async def gpt_bridge() -> GPTBridge:
    """
    GPTBridge'in tekil (singleton) örneğini asenkron olarak döndürür.
    İlk çağrıda örneği oluşturur, sonraki çağrılarda mevcut örneği kullanır.
    Bu, tüm sistemin aynı yapılandırılmış istemciyi kullanmasını sağlar.
    """
    global _SINGLETON
    # Hızlı kontrol (kilit almadan)
    if _SINGLETON is not None:
        return _SINGLETON
        
    # Kilit alarak oluşturma işlemini senkronize et
    async with _singleton_lock:
        # Kilit alındıktan sonra tekrar kontrol et (başka bir görev oluşturmuş olabilir)
        if _SINGLETON is None:
            log.debug("[GPT Bridge] Singleton köprü örneği oluşturuluyor...")
            try:
                _SINGLETON = GPTBridge()
            except Exception as e:
                 # Başlatma sırasında kritik hata olursa logla ve programı durdur
                 log.critical(f"[GPT Bridge|FATAL] Singleton oluşturulamadı: {e}", exc_info=True)
                 # Burada sys.exit kullanmak asenkron ortamda riskli olabilir.
                 # Hatanın yukarıya yayılmasına izin vermek daha iyi olabilir.
                 raise RuntimeError(f"Failed to initialize GPT Bridge: {e}") from e
                 
    # _SINGLETON artık kesinlikle None değil
    return _SINGLETON