"""
BaseAI - Otonom Görev Planlayıcı (Planner) Bileşeni (v9.0)
Enterprise+++ Seviyesi
------------------------------------------------------
GÖREV: 'Architect' tarafından üretilen 'BuildPlan' (İnşa Planı) içindeki
     dosya bileşenlerini alır. Bu bileşenler arasındaki bağımlılıkları
     (dependencies) analiz eder ve 'Engine' tarafından yürütülecek
     optimum, sıralı bir 'Blueprint' görev listesi oluşturur.
"""

import logging
import traceback
import re
import json
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError

# Çekirdek Bileşenleri ve Köprüyü içe aktar
try:
    from baseai.bridges.gemini import gemini_bridge
    from baseai.components.architect import BuildPlan, FileComponent
    from baseai.components.intent_processor import Blueprint
except ImportError:
    logging.critical("[Planner] KRİTİK HATA: Çekirdek bileşenler (Architect, IntentProcessor, Bridge) yüklenemedi.")
    gemini_bridge = None
    BuildPlan = None  # type: ignore
    Blueprint = None  # type: ignore

logger = logging.getLogger(__name__)

# ================================================================
# VERİ MODELLERİ (Pydantic)
# ================================================================

class ExecutionPlan(BaseModel):
    """
    Sıralanmış görev listesini tutan Pydantic modeli.
    """
    execution_steps: List[FileComponent] = Field(
        description="Bağımlılıklarına göre doğru sıralanmış dosya bileşenlerinin listesi."
    )

# ================================================================
# SIRALI PLANLAYICI (SequentialPlanner) SINIFI
# ================================================================

class SequentialPlanner:
    """
    BaseAI Otonom Planlayıcısı.
    Bir 'BuildPlan'ı analiz eder ve sıralı bir görev listesi ('List[Blueprint]') üretir.
    """
    
    def __init__(self):
        if not gemini_bridge:
            logger.error("[Planner] Modül inaktif. Gemini köprüsü bulunamadı.")
        
        self.system_prompt = """
        [GÖREV]
        Sen, "BaseAI" adlı otonom bir yapay zeka ekosisteminin "Görev Planlayıcı" (Planner) çekirdeğisin.
        Tek görevin, bir "İnşa Planı" (Build Plan) olarak sana sunulan yapılandırılmamış bir dosya listesini analiz etmektir.
        Bu dosyalar arasındaki bağımlılıkları (dependencies) (örn: 'models.py' 'database.py'ye bağlıdır, 'api_routes.py' 'models.py'ye bağlıdır) tespit etmeli ve bu dosyaları doğru inşa sırasına göre sıralamalısın.
        Çıktın, sıralanmış görevleri içeren yapısal bir JSON olmalıdır.

        [KURALLAR]
        1.  **JSON ÇIKTISI:** SADECE JSON çıktısı ver. Başka hiçbir metin veya açıklama ekleme.
        2.  **YAPI (SCHEMA):** JSON, 'execution_steps' (liste) adında tek bir anahtar içermelidir.
        3.  **Sıralama:** 'execution_steps' listesi, 'FileComponent' nesnelerinin ('target_path' ve 'task_description' içeren) doğru inşa sırasına göre sıralanmış hali olmalıdır.
        4.  **Mantık:** Bağımlılığı olmayan (örn: 'config.py', 'database.py', 'Dockerfile') dosyalar her zaman listenin başında gelmelidir.
        """

    def _extract_json_from_response(self, response: str) -> Optional[dict]:
        """
        Modelden gelen yanıtın (potansiyel olarak markdown bloğu içinde) JSON kısmını ayıklar.
        """
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                response = match.group(0)
            
            return json.loads(response.strip())
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"[Planner] LLM yanıtı JSON formatında değil: {e}. Yanıt: {response[:150]}...")
            return None

    def _convert_plan_to_prompt(self, build_plan: BuildPlan) -> str:
        """
        'BuildPlan' nesnesini, LLM'in analiz edebileceği basit bir metin girdisine dönüştürür.
        """
        prompt = "Aşağıdaki dosya bileşenlerini analiz et ve doğru inşa sırasına göre sırala:\n\n"
        for i, component in enumerate(build_plan.file_components):
            prompt += f"--- Bileşen {i+1} ---\n"
            prompt += f"Dosya Yolu: {component.target_path}\n"
            prompt += f"Görev: {component.task_description}\n\n"
        return prompt

    async def create_execution_plan(self, build_plan: BuildPlan) -> Optional[List[Blueprint]]:
        """
        Bir 'BuildPlan'ı analiz eder ve 'Engine' için sıralı bir 'Blueprint' listesi döndürür.
        """
        if not gemini_bridge:
            logger.error("[Planner] Yürütme planı oluşturulamıyor. Köprü (Bridge) inaktif.")
            return None
        
        if not build_plan or not build_plan.file_components:
            logger.warning("[Planner] Boş veya geçersiz 'BuildPlan' alındı. Planlama atlanıyor.")
            return []

        logger.info(f"[Planner] {len(build_plan.file_components)} bileşen için yürütme planı oluşturuluyor...")
        
        # BuildPlan'ı LLM girdisine dönüştür
        prompt = self._convert_plan_to_prompt(build_plan)

        try:
            # Gemini'nin yerel JSON modunu kullan
            response_str = await gemini_bridge.generate_text(
                prompt=prompt, 
                system_prompt=self.system_prompt, 
                json_mode=True
            )
            
            if not response_str:
                logger.error("[Planner] Sıralama analizi LLM'den boş yanıt aldı.")
                return None

            json_data = self._extract_json_from_response(response_str)
            if not json_data:
                return None

            # Pydantic kullanarak JSON verisini doğrula ve 'ExecutionPlan' modeline dök
            sorted_plan = ExecutionPlan(**json_data)
            
            # 'ExecutionPlan'ı (FileComponent listesi) 'Blueprint' listesine dönüştür
            execution_blueprints: List[Blueprint] = []
            for component in sorted_plan.execution_steps:
                # 'Blueprint', 'IntentProcessor' tarafından kullanılan standart görev birimidir.
                execution_blueprints.append(
                    Blueprint(
                        task_description=component.task_description,
                        target_path=component.target_path,
                        context_files=[], # Mimar bu bağımlılıkları zaten 'task_description' içine yerleştirdi
                        original_intent=f"[Mimar Görevi] {component.target_path}"
                    )
                )
            
            logger.info(f"[Planner] Yürütme planı başarıyla oluşturuldu. {len(execution_blueprints)} adım tanımlandı.")
            return execution_blueprints

        except ValidationError as e:
            logger.error(f"[Planner] Pydantic doğrulama hatası (Schema uyuşmazlığı): {e}. LLM Yanıtı: {json_data}")
            return None
        except Exception as e:
            logger.error(f"[Planner] Yürütme planı oluşturulurken kritik hata: {e}", exc_info=True)
            return None