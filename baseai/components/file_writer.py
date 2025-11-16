"""
BaseAI Enterprise+++ FileWriter (v9.3)
--------------------------------------
- Tam tip güvenliği (Path → str dönüş standardı)
- AI kaynaklı içeriklerin güvenli dosya yazımı
- Vertex uyumlu yol çözümleme
- Traceback tabanlı hata yakalama
- Circular import güvenliği
"""

import os
import re
import logging
import traceback
from pathlib import Path
from typing import Optional, Union

try:
    from baseai.components.intent_processor import Blueprint
except ImportError:
    # Döngüsel yükleme durumlarında, yalnızca tip ipucu için 'Blueprint' adını bırak
    Blueprint = None  # type: ignore

PROJECT_ROOT = Path(".").resolve()
logger = logging.getLogger(__name__)

class FileWriter:
    """
    BaseAI Otonom Kod Yazıcısı (Enterprise+++)
    ------------------------------------------
    Onaylanmış kodu alır, temizler ve proje dizinine güvenli şekilde yazar.
    Yazım işlemi sırasında güvenlik, bütünlük ve standartlara uygunluk kontrolleri yapar.
    """

    def __init__(self, root_dir: Union[str, Path] = PROJECT_ROOT):
        self.root_dir = Path(root_dir).resolve()

        try:
            os.makedirs(self.root_dir, exist_ok=True)
        except Exception as e:
            logger.critical(f"[FileWriter: KRİTİK] Proje kökü oluşturulamadı: {e}")
            raise

        logger.info(f"[FileWriter] Modül Aktif. Proje Kökü: {self.root_dir}")

    # ---------------------------------------------------------------------
    # Yardımcı Fonksiyonlar
    # ---------------------------------------------------------------------

    def _extract_code(self, raw_content: str) -> str:
        """LLM çıktısından (Markdown veya düz metin) Python kodunu ayıklar."""
        try:
            pattern = r"```(?:python)?\n([\s\S]*?)```"
            match = re.search(pattern, raw_content, re.DOTALL)
            if match:
                code = match.group(1).strip()
                logger.debug("[FileWriter] Markdown kod bloğu ayıklandı.")
                return code
            return raw_content.strip()
        except Exception as e:
            logger.error(f"[FileWriter: Kod Ayıklama Hatası] {e}")
            return raw_content

    def _is_safe_path(self, target_path: Path) -> bool:
        """Yazılacak dosyanın proje kökü içinde olduğundan emin olur."""
        try:
            resolved_path = target_path.resolve()
            return resolved_path.is_relative_to(self.root_dir)
        except AttributeError:
            # Python 3.8 uyumluluğu
            return self.root_dir in resolved_path.parents or self.root_dir == resolved_path
        except Exception as e:
            logger.warning(f"[FileWriter] Güvenlik kontrolü başarısız: {e}")
            return False

    # ---------------------------------------------------------------------
    # Ana İşlev
    # ---------------------------------------------------------------------

    def write_to_project(self, approved_code: str, blueprint: "Blueprint") -> Optional[str]:
        """
        Denetlenmiş (approved) kodu dosyaya yazar.

        Args:
            approved_code: Denetimden geçmiş nihai kod içeriği.
            blueprint: Hedef dosya yolunu içeren plan nesnesi.

        Returns:
            relative_path (str): Yazılan dosyanın proje köküne göre göreceli yolu.
            None: Hata oluşursa.
        """
        try:
            # --- Blueprint kontrolü ---
            if not blueprint or not getattr(blueprint, "target_path", None):
                logger.error("[FileWriter: HATA] Blueprint geçersiz veya hedef yolu eksik.")
                return None

            clean_code = self._extract_code(approved_code)
            if not clean_code:
                logger.error("[FileWriter: HATA] Kod ayıklanamadı (boş içerik).")
                return None

            target_path = (self.root_dir / blueprint.target_path).resolve()

            # --- Güvenlik kontrolü ---
            if not self._is_safe_path(target_path):
                logger.critical(f"[FileWriter: GÜVENLİK İHLALİ] {target_path} proje dizini dışında!")
                return None

            # --- Dosya oluşturma ve yazma ---
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(clean_code)

            relative_path = str(target_path.relative_to(self.root_dir))
            logger.info(f"[FileWriter: BAŞARILI] {len(clean_code)} bayt '{relative_path}' dosyasına yazıldı.")
            return relative_path

        except Exception as e:
            logger.error(
                f"[FileWriter: KRİTİK YAZMA HATASI] {e}\n{traceback.format_exc()}"
            )
            return None
