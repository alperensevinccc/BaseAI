import logging
from typing import Tuple, Optional
import json
import re
from pydantic import BaseModel, ValidationError
from .intent_processor import Blueprint
import traceback

try:
    from baseai.bridges.gemini import gemini_bridge # Artık denetim için Gemini kullanılıyor
except ImportError:
    logging.critical("[CodeAuditor] Gemini köprüsü yüklenemedi. Kod denetimi yapılamaz.")
    gemini_bridge = None

logger = logging.getLogger(__name__)

class AuditReport(BaseModel):
    is_valid: bool
    report: str
    audited_code: str

class CodeAuditor:
    def __init__(self):
        if not gemini_bridge:
            logger.error("[CodeAuditor] Modül inaktif. Gemini köprüsü bulunamadı.")
        else:
            logger.info("[CodeAuditor] Modül Aktif. Denetim için Gemini kullanılıyor.")
        
        self.system_prompt = """
        [GÖREV]
        Sen BaseAI'nin Kod Denetçisisin.
        Sana gönderilen kodu, verilen 'GÖREV TANIMI'na ve 'E3 STANDARTLARI'na göre denetle.
        
        [E3 STANDARTLARI]
        1. Güvenlik: Kod 'os.system', 'eval()', 'exec()' gibi tehlikeli fonksiyonlar içeriyor mu?
        2. Tamlık: Kod tam mı, yoksa '... # your code here' gibi yarım bırakılmış mı?
        3. Standartlar: Kod, 'type hint' (tür ipuçları) içeriyor mu?
        4. Odak: Kod, test kodu veya `if __name__ == "__main__":` bloğu içeriyor mu? (İçermemeli!)

        [ÇIKTI FORMATI]
        Denetim sonucunu SADECE JSON formatında döndür.
        - 'is_valid' (bool): Kod standartlara ve göreve uygunsa 'true', değilse 'false'.
        - 'report' (str): 1-2 cümlelik net denetim raporu.
        - 'audited_code' (str): Koddaki `print()` gibi küçük hataları temizlediysen temizlenmiş kod. Eğer kod tamamsa veya reddedildiyse, orijinal kodu döndür.
        """

    def _get_user_prompt(self, raw_code: str, blueprint: Blueprint) -> str:
        return f"""
        [GÖREV TANIMI]
        {blueprint.task_description}

        [DENETLENECEK KOD]
        ```python
        {raw_code}
        ```
        """

    def _extract_json_from_response(self, response: str) -> Optional[dict]:
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                response = match.group(0)
            
            return json.loads(response.strip())
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"[CodeAuditor] LLM yanıtı JSON formatında değil: {e}. Yanıt: {response[:100]}...")
            return None

    async def audit_code(self, raw_code: str, blueprint: Blueprint) -> Tuple[bool, str, str]:
        if not gemini_bridge:
            logger.error("[CodeAuditor] Denetim yapılamıyor. Gemini Köprüsü inaktif.")
            return False, "Denetçi modülü inaktif.", raw_code
        
        if not raw_code or not raw_code.strip():
             return False, "Üretilen kod boş.", ""

        user_prompt = self._get_user_prompt(raw_code, blueprint)

        try:
            logger.info(f"[CodeAuditor] Kod denetimi başlatıldı (Hedef: {blueprint.target_path})...")
            
            # Gemini'nin JSON modunu kullan
            response_str = await gemini_bridge.generate_text(
                user_prompt, 
                self.system_prompt, 
                json_mode=True
            )

            if not response_str:
                logger.error("[CodeAuditor] Denetim LLM'den boş yanıt aldı.")
                return False, "Denetçi (Auditor) LLM'den boş yanıt aldı.", raw_code

            json_data = self._extract_json_from_response(response_str)
            if not json_data:
                 return False, "Denetçi yanıtı (JSON) ayrıştırılamadı.", raw_code

            report = AuditReport(**json_data)
            
            logger.info(f"[CodeAuditor] Denetim Raporu: {report.report}")
            return report.is_valid, report.report, report.audited_code

        except ValidationError as e:
             logger.error(f"[CodeAuditor] Denetçi Pydantic doğrulama hatası: {e}. LLM Yanıtı: {json_data}")
             return False, f"Denetçi yanıtı (Pydantic) ayrıştırılamadı.", raw_code
        except Exception as e:
            logger.error(f"[CodeAuditor] Kod denetimi sırasında kritik hata: {e}")
            return False, f"Denetim sırasında kritik hata: {e}", raw_code
