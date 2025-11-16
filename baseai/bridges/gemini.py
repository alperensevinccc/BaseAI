"""
BaseAI - Gemini Köprüsü (v8.3 / Vertex AI SDK / Döngü Onarımı)
Enterprise++++ standartlarına uygun, 'async' ve 'gcloud' kimlik doğrulamasını kullanır.
Döngüsel içe aktarma (Circular Import) hatası, 'vertexai.init()'
çağrısının modül seviyesinden __init__ seviyesine taşınmasıyla çözülmüştür.
"""
import logging
import traceback
from typing import Optional

try:
    import vertexai
    from vertexai.preview.generative_models import (
        GenerativeModel,
        GenerationConfig,
        HarmCategory,
        HarmBlockThreshold,
    )
except ImportError:
    logging.critical("[GeminiBridge] KRİTİK HATA: 'google-cloud-aiplatform' SDK'sı bulunamadı.")
    vertexai = None

# 'config' modülünü içe aktar. (Artık döngüsel içe aktarma riski yok.)
try:
    from baseai.config import config
except ImportError as e:
    logging.critical(f"[GeminiBridge] Merkezi 'config' yüklenemedi (Döngüsel Hata?): {e}")
    config = None

logger = logging.getLogger(__name__)

# Vertex AI yalnızca bir kez başlatılsın (global flag)
_VERTEX_AI_INITIALIZED = False


class GeminiBridge:
    """
    Yeni 'google-cloud-aiplatform' (Vertex AI) SDK'sını kullanan modern, asenkron köprü.
    Gemini 2.x SDK ile tam uyumludur.
    """

    def __init__(self):
        global _VERTEX_AI_INITIALIZED
        self.model = None
        self.model_name = "gemini-pro"  # Acil durum varsayılanı

        if not config or not vertexai:
            logger.error("[GeminiBridge] Başlatılamadı: Config veya VertexAI SDK eksik.")
            return

        # Vertex AI başlat
        if not _VERTEX_AI_INITIALIZED:
            try:
                logger.debug("[GeminiBridge] Vertex AI SDK başlatılıyor...")
                vertexai.init(
                    project=config.GOOGLE_PROJECT_ID,
                    location=config.GOOGLE_REGION,
                )
                _VERTEX_AI_INITIALIZED = True
                logger.debug("[GeminiBridge] Vertex AI SDK başarıyla başlatıldı.")
            except Exception as e:
                logger.critical(f"[GeminiBridge] Google Vertex AI SDK yapılandırması başarısız oldu: {e}")
                return

        # Model ayarları
        self.model_name = config.DEFAULT_GEMINI_MODEL
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        try:
            self.model = GenerativeModel(
                self.model_name,
                safety_settings=self.safety_settings,
            )
            logger.info(f"Gemini Köprüsü Aktif. Model: {self.model_name} (Vertex AI SDK)")
        except Exception as e:
            logger.critical(f"NİHAİ ÇÖKME: Model ({self.model_name}) başlatılamadı. SDK Hatası: {e}")
            self.model = None

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Gemini modelinden metin üretir (asenkron)."""
        if not self.model:
            logger.error("Kod üretilemiyor: Model başlatılmamış.")
            return None

        try:
            mime_type = "application/json" if json_mode else "text/plain"
            generation_config = GenerationConfig(
                temperature=0.7,
                response_mime_type=mime_type,
            )

            model_instance = GenerativeModel(
                self.model_name,
                system_instruction=system_prompt,
                safety_settings=self.safety_settings,
                generation_config=generation_config,
            )

            response = await model_instance.generate_content_async(contents=[prompt])

            # --- ✅ Gemini 2.x SDK formatına uyum ---
            text_output = getattr(response, "text", None)

            # Eski format (Gemini 1.x) fallback
            if not text_output and hasattr(response, "candidates"):
                try:
                    text_output = (
                        response.candidates[0]
                        .content.parts[0]
                        .text
                    )
                except Exception:
                    text_output = None

            if not text_output:
                logger.error("[Gemini Bridge] Yanıt boş veya geçersiz formatta döndü.")
                return None

            logger.debug(f"[Gemini Bridge] Başarılı: {len(text_output)} karakter üretildi.")
            return text_output.strip()

        except Exception as e:
            logger.error(f"API isteği sırasında kritik hata: {e}")
            logger.debug(traceback.format_exc())
            return None


# --- Singleton başlatma ---
try:
    gemini_bridge = GeminiBridge()
except Exception as e:
    logger.critical(f"Başlatma sırasında global çökme: {e}")
    gemini_bridge = None
