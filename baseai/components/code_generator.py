import logging
from typing import Optional
from .intent_processor import Blueprint
import traceback

try:
    from baseai.bridges.gemini import gemini_bridge
except ImportError:
    logging.critical("[CodeGenerator] Gemini köprüsü yüklenemedi.")
    gemini_bridge = None

logger = logging.getLogger(__name__)

class CodeGenerator:
    def __init__(self):
        if not gemini_bridge:
            logger.error("[CodeGenerator] Modül inaktif. Gemini Köprüsü başlatılamadı.")
        else:
            logger.info("[CodeGenerator] Modül Aktif. Gemini köprüsü bağlı.")

    def _get_system_prompt(self) -> str:
        return """
        [GÖREV]
        Sen BaseAI için kod üreten bir uzmansın.
        Verilen görevi (task) yerine getiren, Enterprise+++ (E3) standartlarında Python kodu üret.

        [KURALLAR]
        1. SADECE Python kodu üret. Açıklamaları kod içinde `#` veya docstring olarak ekle.
        2. Kodu ````python` bloğu içinde döndür.
        3. Asla test kodu, `print()` ifadeleri veya `if __name__ == "__main__":` bloğu ekleme.
        4. Tüm fonksiyonlar ve metotlar 'type hint' (tür ipucu) içermelidir.
        5. Güvenlik, verimlilik ve okunabilirlik en üst önceliktir.
        """

    def _get_user_prompt(self, blueprint: Blueprint) -> str:
        return f"""
        [GÖREV DETAYI]
        Görev: "{blueprint.task_description}"
        Hedef Dosya: "{blueprint.target_path}"
        """

    async def generate_code(self, blueprint: Blueprint, target_model: str = "gemini") -> Optional[str]:
        if not blueprint:
            logger.error("[CodeGenerator] Blueprint (plan) boş. Kod üretimi iptal edildi.")
            return None
        
        if not gemini_bridge:
             logger.error("[CodeGenerator] Gemini köprüsü inaktif. Kod üretilemiyor.")
             return None

        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(blueprint)

        try:
            logger.info(f"[CodeGenerator] Gemini köprüsü ile '{blueprint.target_path}' üretiliyor...")
            
            raw_code = await gemini_bridge.generate_text(user_prompt, system_prompt, json_mode=False)

            if not raw_code or not raw_code.strip():
                 logger.warning("[CodeGenerator] LLM (Gemini) boş yanıt döndürdü.")
                 return None

            logger.info(f"[CodeGenerator] {blueprint.target_path} için ham kod üretildi.")
            return raw_code

        except Exception as e:
            logger.error(f"[CodeGenerator] Kod üretimi sırasında kritik hata: {e}", exc_info=True)
            return None
