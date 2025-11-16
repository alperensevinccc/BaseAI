import logging
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError
import json
import re
import traceback

try:
    from baseai.bridges.gemini import gemini_bridge
except ImportError:
    logging.critical("[IntentProcessor] Gemini köprüsü yüklenemedi. Niyet işlenemez.")
    gemini_bridge = None

logger = logging.getLogger(__name__)

class Blueprint(BaseModel):
    task_description: str = Field(description="Kod üreteci için detaylı ve net görev tanımı.")
    target_path: str = Field(description="Üretilecek veya değiştirilecek dosyanın proje yolu.")
    context_files: List[str] = Field(default_factory=list, description="Okunması gereken yardımcı dosyalar.")
    original_intent: str = Field(description="Partner'dan gelen ham niyet.", exclude=True)

class IntentProcessor:
    def __init__(self):
        if not gemini_bridge:
            logger.error("[IntentProcessor] Modül inaktif. Gemini köprüsü bulunamadı.")
        
        self.system_prompt = """
        [GÖREV]
        Partner'dan gelen ham niyeti (intent) analiz et ve yapısal bir JSON çıktısı üret.
        - 'task_description': Görevin net ve detaylı açıklaması.
        - 'target_path': Kodun yazılacağı dosya yolu.
        - 'context_files': Görevi yapmak için okunması gereken dosyalar (genellikle niyet içinde belirtilir).
        
        [KURALLAR]
        1. SADECE JSON çıktısı ver. Başka hiçbir metin veya açıklama ekleme.
        2. JSON 'task_description', 'target_path' ve 'context_files' alanlarını içermelidir.
        3. 'target_path' daima tam bir yol olmalıdır (örn: 'baseai/utils/new_util.py').
        """

    def _extract_json_from_response(self, response: str) -> Optional[dict]:
        try:
            # Gemini JSON modu, markdown bloğunu (```json ... ```) otomatik olarak temizler.
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                response = match.group(0)
            
            return json.loads(response.strip())
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"[IntentProcessor] LLM yanıtı JSON formatında değil: {e}. Yanıt: {response[:100]}...")
            return None

    async def process_intent(self, raw_intent: str) -> Optional[Blueprint]:
        if not gemini_bridge:
            logger.error("[IntentProcessor] Niyet işlenemiyor. Köprü (Bridge) inaktif.")
            return None
        
        logger.info(f"[IntentProcessor] Niyet analiz ediliyor: '{raw_intent[:50]}...'")
        
        try:
            # Gemini'nin JSON modunu kullan
            response_str = await gemini_bridge.generate_text(
                raw_intent, 
                self.system_prompt, 
                json_mode=True
            )
            if not response_str:
                logger.error("[IntentProcessor] Niyet analizi LLM'den boş yanıt aldı.")
                return None

            json_data = self._extract_json_from_response(response_str)
            if not json_data:
                return None

            blueprint = Blueprint(**json_data, original_intent=raw_intent)
            logger.info(f"[IntentProcessor] Niyet başarıyla plana dönüştürüldü. Hedef: {blueprint.target_path}")
            return blueprint

        except ValidationError as e:
            logger.error(f"[IntentProcessor] Pydantic doğrulama hatası: {e}. LLM Yanıtı: {json_data}")
            return None
        except Exception as e:
            logger.error(f"[IntentProcessor] Niyet analizi sırasında kritik hata: {e}")
            return None
