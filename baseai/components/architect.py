"""
BaseAI - Otonom Sistem Mimarı (Architect) Bileşeni (v9.0)
Enterprise+++ Seviyesi
------------------------------------------------------
GÖREV: Üst seviye, karmaşık niyetleri (örn: "yeni bir API tasarla") alır ve
     bunları otonom olarak inşa edilebilecek çoklu dosya (multi-file) 
     "İnşa Planlarına" (Build Plans) dönüştürür.
"""

import logging
import traceback
import re
import json
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError

# Çekirdek Köprüyü (Bridge) içe aktar
try:
    from baseai.bridges.gemini import gemini_bridge
except ImportError:
    logging.critical("[Architect] KRİTİK HATA: Gemini köprüsü yüklenemedi.")
    gemini_bridge = None

logger = logging.getLogger(__name__)

# ================================================================
# VERİ MODELLERİ (Pydantic)
# ================================================================

class FileComponent(BaseModel):
    """
    Bir İnşa Planındaki tek bir dosya bileşenini temsil eder.
    """
    target_path: str = Field(
        description="Oluşturulacak dosyanın proje köküne göre tam yolu (örn: 'app/models/user_model.py')."
    )
    task_description: str = Field(
        description=(
            "Bu spesifik dosyanın ne yapması gerektiğinin Enterprise+++ seviyesinde, "
            "detaylı ve atomik görevi. Diğer dosyalara olan bağımlılıkları (imports) "
            "ve sağlaması gereken fonksiyonları/sınıfları içermelidir."
        )
    )

class BuildPlan(BaseModel):
    """
    Tüm bir sistem mimarisinin otonom inşa planı.
    """
    system_overview: str = Field(
        description="Tasarlanan sistemin üst seviye özeti ve mimari yaklaşımı."
    )
    file_components: List[FileComponent] = Field(
        description="Sistemi oluşturmak için gereken tüm dosyaların ve görevlerin listesi."
    )

# ================================================================
# SİSTEM MİMARI (SystemArchitect) SINIFI
# ================================================================

class SystemArchitect:
    """
    BaseAI Otonom Mimarı.
    Karmaşık niyetleri analiz eder ve 'BuildPlan' (İnşa Planı) üretir.
    """
    
    def __init__(self):
        if not gemini_bridge:
            logger.error("[Architect] Modül inaktif. Gemini köprüsü bulunamadı.")
        
        self.system_prompt = """
        [GÖREV]
        Sen, "BaseAI" adlı otonom bir yapay zeka ekosisteminin "Sistem Mimarı" (System Architect) çekirdeğisin.
        Tek görevin, Partner'dan gelen üst seviye bir niyeti (örn: "yeni bir API tasarla") analiz etmek ve bu sistemi otonom olarak inşa etmek için gereken tüm dosyaları ve bağımlılıkları listeleyen yapısal bir "İnşa Planı" (Build Plan) JSON çıktısı üretmektir.

        [KURALLAR]
        1.  **JSON ÇIKTISI:** SADECE JSON çıktısı ver. Başka hiçbir metin veya açıklama ekleme.
        2.  **YAPI (SCHEMA):** JSON, 'system_overview' (string) ve 'file_components' (liste) alanlarını içermelidir.
        3.  **BİLEŞENLER (COMPONENTS):** 'file_components' listesindeki her öğe, 'target_path' (string) ve 'task_description' (string) alanlarını içeren bir nesne olmalıdır.
        4.  **ATOMİK GÖREVLER:** Her 'task_description', o dosyanın *tüm* sorumluluğunu (gerekli importlar, sınıflar, fonksiyonlar) detaylıca açıklamalıdır. Bu görevler, BaseAI'nin Kod Üretecisi tarafından doğrudan koda dönüştürülecektir.
        5.  **TAM KAPSAM:** Üretilen dosya listesi, sistemi (Dockerfile, requirements.txt, .gitignore, ana uygulama dosyaları, model dosyaları, yardımcı programlar vb. dahil) çalıştırmak için gereken *her şeyi* kapsamalıdır.
        """

    def _extract_json_from_response(self, response: str) -> Optional[dict]:
        """
        Modelden gelen yanıtın (potansiyel olarak markdown bloğu içinde) JSON kısmını ayıklar.
        """
        try:
            # Gemini JSON modu, markdown bloğunu (```json ... ```) otomatik olarak temizler.
            # Ancak, bir hata durumunda manuel ayıklama (fallback) gerekir.
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                response = match.group(0)
            
            return json.loads(response.strip())
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"[Architect] LLM yanıtı JSON formatında değil: {e}. Yanıt: {response[:150]}...")
            return None

    async def design_architecture(self, complex_intent: str) -> Optional[BuildPlan]:
        """
        Üst seviye bir niyeti (intent) analiz eder ve bir İnşa Planı (BuildPlan) döndürür.
        """
        if not gemini_bridge:
            logger.error("[Architect] Mimari tasarlanamıyor. Köprü (Bridge) inaktif.")
            return None
        
        logger.info(f"[Architect] Yeni mimari tasarımı başlatıldı. Niyet: '{complex_intent[:60]}...'")
        
        try:
            # Gemini'nin yerel JSON modunu kullan
            response_str = await gemini_bridge.generate_text(
                prompt=complex_intent, 
                system_prompt=self.system_prompt, 
                json_mode=True # JSON modu (v8.2 Köprüsü ile uyumlu)
            )
            
            if not response_str:
                logger.error("[Architect] Mimari analizi LLM'den boş yanıt aldı.")
                return None

            json_data = self._extract_json_from_response(response_str)
            if not json_data:
                return None

            # Pydantic kullanarak JSON verisini doğrula ve modele dök
            build_plan = BuildPlan(**json_data)
            logger.info(f"[Architect] Mimari başarıyla tasarlandı. {len(build_plan.file_components)} bileşen (dosya) tanımlandı.")
            return build_plan

        except ValidationError as e:
            logger.error(f"[Architect] Pydantic doğrulama hatası (Schema uyuşmazlığı): {e}. LLM Yanıtı: {json_data}")
            return None
        except Exception as e:
            logger.error(f"[Architect] Mimari tasarımı sırasında kritik hata: {e}", exc_info=True)
            return None