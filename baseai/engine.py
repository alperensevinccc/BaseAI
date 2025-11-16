"""
BaseAI Enterprise+++ Otonom Çekirdek Motoru (v9.0 / Sistem Mimarı)
------------------------------------------------------------------
- [YÜKSELTME] Artık 'Architect' ve 'Planner' bileşenlerini içerir.
- [YÜKSELTME] Karmaşık, çoklu dosya (multi-file) mimari niyetlerini 
  otonom olarak tasarlayabilir ve inşa edebilir (Otonom İnşa Yöneticisi).
- Tamamen asenkron (asyncio) ve Vertex AI (v8.2) SDK'sı ile uyumludur.
"""
import logging
import traceback
from typing import Optional, List

# [P4 ONARIM] 'rich' loglamayı etkinleştirmek için 'config' MUTLAKA İLK olarak yüklenmelidir.
# Bu, 17:34'te (veya sonrasında) sağlanan v8.2 'config.py' sürümünü gerektirir.
try:
    from baseai.config import config
except ImportError as e:
    print(f"[BaseAI Engine: KRİTİK HATA] Config (v8.2) yüklenemedi: {e}")
    config = None

# Çekirdek Bileşenleri Yükle
try:
    from baseai.components.intent_processor import IntentProcessor, Blueprint
    from baseai.components.code_generator import CodeGenerator
    from baseai.components.code_auditor import CodeAuditor
    from baseai.components.file_writer import FileWriter
    # [YÜKSELTME v9.0] Yeni Mimari Bileşenleri
    from baseai.components.architect import SystemArchitect, BuildPlan
    from baseai.components.planner import SequentialPlanner
except ImportError as e:
    logging.critical(f"[BaseAI Engine: KRİTİK HATA] Çekirdek bileşenler yüklenemedi: {e}")
    # Sistem bu noktada durdurulmalı, ancak config'in yüklenmesine izin ver
    if config: 
        raise
    else:
        print("Lütfen 'baseai/components/' altındaki tüm dosyaların (architect, planner vb.) mevcut olduğundan emin olun.")
        exit(1)

logger = logging.getLogger("baseai.engine")

# [YÜKSELTME v9.0] Niyetin karmaşıklığını belirlemek için anahtar kelimeler
COMPLEX_TASK_KEYWORDS = [
    "tasarla", "design", "mimari", "architect", "platform", "sistem", "system",
    "uygulama", "app", "proje", "project", "çoklu dosya", "multi-file", "api",
    "veritabanı", "database", "dockerfile", "docker", "k8s", "kubernetes"
]

class BaseAIEngine:
    """
    BaseAI Otonom İnşa Yöneticisi (v9.0).
    Partner'dan gelen niyeti (intent) analiz eder.
    - Basit niyetleri doğrudan yürütür (v7.1 davranışı).
    - Karmaşık niyetleri Mimar (Architect) ve Planlayıcı (Planner) kullanarak
      çok adımlı bir inşa planına dönüştürür ve yürütür.
    """
    def __init__(self):
        if not config:
            raise SystemExit("[BaseAI Engine] KRİTİK HATA: Config modülü başlatılamadı.")

        self.config = config
        
        # v7.1 Çekirdek Boru Hattı Bileşenleri
        self.processor = IntentProcessor()
        self.generator = CodeGenerator()
        self.auditor = CodeAuditor()
        self.writer = FileWriter()
        
        # v9.0 Mimari Boru Hattı Bileşenleri
        self.architect = SystemArchitect()
        self.planner = SequentialPlanner()
        
        logger.info("--- [BaseAI Enterprise+++ Çekirdeği Başlatıldı (v9.0 - Sistem Mimarı)] ---")
        logger.info(f"Durum: Aktif. Model (Vertex AI): {config.DEFAULT_GEMINI_MODEL}")
        logger.info("Tüm bileşenler (Mimar, Planlayıcı, Niyet, Üretici, Denetçi, Yazıcı) devrede.")

    def _is_complex_task(self, raw_intent: str) -> bool:
        """Niyetin basit (tek dosya) mı yoksa karmaşık (mimari) mı olduğunu belirler."""
        intent_lower = raw_intent.lower()
        for keyword in COMPLEX_TASK_KEYWORDS:
            if keyword in intent_lower:
                logger.info("[BaseAI Engine] Karmaşık (Mimari) niyet tespit edildi.")
                return True
        logger.info("[BaseAI Engine] Basit (Tekil Görev) niyet tespit edildi.")
        return False

    async def execute_pipeline(self, raw_intent: str) -> bool:
        """
        BaseAI'nin tam asenkron üretim boru hattını çalıştırır.
        Niyeti analiz eder ve uygun boru hattını (Basit veya Mimari) seçer.
        """
        logger.info("-" * 30)
        
        try:
            if self._is_complex_task(raw_intent):
                # [YÜKSELTME v9.0] Yeni Mimari Boru Hattı
                return await self._execute_architecture_pipeline(raw_intent)
            else:
                # [GERİYE UYUMLULUK v7.1] Eski Basit Görev Boru Hattı
                return await self._execute_simple_pipeline(raw_intent)
        
        except Exception as e:
            logger.critical(f"[BaseAI Pipeline: KRİTİK ÇÖKME] Ana boru hattı çöktü: {e}", exc_info=True)
            return False

    async def _execute_simple_pipeline(self, raw_intent: str) -> bool:
        """
        [v7.1] Basit, tekil dosya görevlerini yürütür.
        Niyet -> Plan -> Ham Kod -> Denetim -> Diske Yazma
        """
        logger.info("[BaseAI Pipeline (Basit Görev): Adım 1/4] Niyet işleniyor...")
        blueprint: Optional[Blueprint] = await self.processor.process_intent(raw_intent)
        if not blueprint:
            logger.error("[BaseAI Pipeline (Basit Görev): BAŞARISIZ] Niyet işlenemedi.")
            return False

        logger.info("[BaseAI Pipeline (Basit Görev): Adım 2/4] Kod üretimi başlatıldı...")
        raw_code: Optional[str] = await self.generator.generate_code(blueprint, target_model="vertex")
        if not raw_code:
            logger.error("[BaseAI Pipeline (Basit Görev): BAŞARISIZ] Kod üreteci yanıt vermedi.")
            return False

        logger.info("[BaseAI Pipeline (Basit Görev): Adım 3/4] Kod denetleniyor...")
        is_valid, report, audited_code = await self.auditor.audit_code(raw_code, blueprint)
        if not is_valid:
            logger.error(f"[BaseAI Pipeline (Basit Görev): BAŞARISIZ] Denetçi reddetti: {report}")
            return False
        logger.info(f"[BaseAI Pipeline] Denetçi Raporu: {report}")

        logger.info("[BaseAI Pipeline (Basit Görev): Adım 4/4] Kod diske yazılıyor...")
        output_path = self.writer.write_to_project(audited_code, blueprint)
        if not output_path:
             logger.error(f"[BaseAI Pipeline (Basit Görev): BAŞARISIZ] Kod dosyaya yazılamadı.")
             return False

        print(f"\n--- [OTONOM ÜRETİM TAMAMLANDI] ---")
        print(f"Sonuç: {output_path}")
        print("---------------------------------")
        return True

    async def _execute_architecture_pipeline(self, raw_intent: str) -> bool:
        """
        [v9.0] Karmaşık, çoklu dosya mimarilerini tasarlar ve inşa eder.
        Niyet -> Mimari -> Planlama -> (Yürütme Döngüsü)
        """
        
        # 1. MİMARİ (ARCHITECT)
        logger.info("[BaseAI Pipeline (MİMARİ): Adım 1/3] Mimari tasarlanıyor...")
        build_plan: Optional[BuildPlan] = await self.architect.design_architecture(raw_intent)
        if not build_plan or not build_plan.file_components:
            logger.error("[BaseAI Pipeline (MİMARİ): BAŞARISIZ] Mimar, 'BuildPlan' üretemedi.")
            return False
        
        # 2. PLANLAMA (PLANNER)
        logger.info("[BaseAI Pipeline (MİMARİ): Adım 2/3] Görev planı (bağımlılıklar) oluşturuluyor...")
        execution_plan: Optional[List[Blueprint]] = await self.planner.create_execution_plan(build_plan)
        if not execution_plan:
            logger.error("[BaseAI Pipeline (MİMARİ): BAŞARISIZ] Planlayıcı, 'ExecutionPlan' üretemedi.")
            return False

        # 3. YÜRÜTME (EXECUTION)
        total_steps = len(execution_plan)
        logger.info(f"[BaseAI Pipeline (MİMARİ): Adım 3/3] {total_steps} adımlık inşa planı yürütülüyor...")
        
        completed_files: List[str] = []
        for i, blueprint in enumerate(execution_plan):
            step_num = i + 1
            logger.info(f"--- [İnşa Adımı {step_num}/{total_steps}] BAŞLATILIYOR: {blueprint.target_path} ---")

            # A. KOD ÜRETİMİ (GENERATE)
            logger.info(f"[İnşa Adımı {step_num}A] Kod üretiliyor...")
            raw_code: Optional[str] = await self.generator.generate_code(blueprint, target_model="vertex")
            if not raw_code:
                logger.critical(f"[İnşa BAŞARISIZ] Adım {step_num} ({blueprint.target_path}) için kod üretilemedi.")
                return False

            # B. DENETİM (AUDIT)
            logger.info(f"[İnşa Adımı {step_num}B] Kod denetleniyor...")
            is_valid, report, audited_code = await self.auditor.audit_code(raw_code, blueprint)
            if not is_valid:
                logger.critical(f"[İnşa BAŞARISIZ] Adım {step_num} ({blueprint.target_path}) denetçi tarafından reddedildi: {report}")
                return False
            logger.info(f"[İnşa Adımı {step_num}B] Denetçi Onayladı: {report}")

            # C. YAZMA (WRITE)
            logger.info(f"[İnşa Adımı {step_num}C] Kod diske yazılıyor...")
            output_path = self.writer.write_to_project(audited_code, blueprint)
            if not output_path:
                 logger.critical(f"[İnşa BAŞARISIZ] Adım {step_num} ({blueprint.target_path}) diske yazılamadı.")
                 return False
            
            logger.info(f"--- [İnşa Adımı {step_num}/{total_steps}] TAMAMLANDI: {output_path} ---")
            completed_files.append(output_path)

        # NİHAİ RAPOR
        print(f"\n--- [OTONOM MİMARİ TAMAMLANDI] ---")
        print(f"Toplam {len(completed_files)} dosya başarıyla üretildi:")
        for file_path in completed_files:
            print(f"  ✅ {file_path}")
        print("---------------------------------------")
        return True