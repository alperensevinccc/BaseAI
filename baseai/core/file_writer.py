import os
import re
from pathlib import Path
from typing import Any, Optional

# Güvenlik: Proje kök dizini dışına yazmayı engelle.
# Colab/GitHub ortamında bu genellikle mevcut çalışma dizinidir.
PROJECT_ROOT = Path(".").resolve()


class FileWriter:
    """
    BaseAI Otonom Kod Yazıcısı.
    LLM tarafından üretilen ham kod çıktılarını alır, temizler
    ve proje dizinine güvenli bir şekilde yazar.
    Enterprise+++ standartlarına uygun olarak hata yönetimi ve
    dizin oluşturma yeteneklerine sahiptir.
    """

    def __init__(self, root_dir: Path = PROJECT_ROOT):
        self.root_dir = root_dir
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir, exist_ok=True)
        print(f"[FileWriter] Modül Aktif. Proje Kökü: {self.root_dir}")

    def _extract_code(self, raw_content: str) -> str:
        """
        LLM çıktısından (genellikle Markdown içinde) kod bloğunu ayıklar.

        ```python
        print("Hello")
        ```
        veya
        ```
        print("Hello")
        ```
        formatlarını arar.
        """
        # Regex: ```python ... ``` veya ``` ... ``` bloklarını arar
        pattern = r"```(?:python\n)?([\s\S]*?)```"
        match = re.search(pattern, raw_content, re.DOTALL)

        if match:
            # Sadece kod bloğunun içini al
            return match.group(1).strip()
        else:
            # Kod bloğu bulunamazsa, çıktının tamamını kod olarak kabul et
            # (Denetçi zaten temizlemiş olabilir)
            return raw_content.strip()

    def _is_safe_path(self, target_path: Path) -> bool:
        """
        Yazılacak yolun proje kök dizini içinde olup olmadığını kontrol eder.
        Path Traversal (Dizin Aşma) saldırılarını engeller.
        """
        resolved_path = target_path.resolve()
        # 'commonpath' kullanarak yolun kök dizin altında olduğunu doğrula
        return (
            os.path.commonpath([self.root_dir, resolved_path])
            == str(self.root_dir)
        )

    def write_to_project(self, approved_code: str, blueprint: Any) -> Optional[Path]:
        """
        Onaylanmış kodu ve planı alır, kodu temizler ve dosyaya yazar.

        Args:
            approved_code (str): Denetçiden geçen, muhtemelen markdown içeren kod.
            blueprint (Any): IntentProcessor'dan gelen plan.
                             'target_path' özelliğini içermesi beklenir.

        Returns:
            Optional[Path]: Yazılan dosyanın yolu (başarılıysa) veya None.
        """
        try:
            # 1. Hedef Yolu Al
            target_file = getattr(blueprint, "target_path", None)
            if not target_file:
                print(
                    "[FileWriter: HATA] Blueprint 'target_path' bilgisi içermiyor. Yazma işlemi iptal edildi."
                )
                return None

            # 2. Kodu Ayıkla
            clean_code = self._extract_code(approved_code)
            if not clean_code:
                print(
                    "[FileWriter: HATA] LLM çıktısından ayıklanacak geçerli kod bulunamadı."
                )
                return None

            # 3. Güvenlik Kontrolü ve Yol Oluşturma
            target_path = self.root_dir / target_file
            if not self._is_safe_path(target_path):
                print(
                    f"[FileWriter: GÜVENLİK İHLALİ] {target_path} proje dizini dışında. Yazma reddedildi."
                )
                return None

            # 4. Dizinleri Oluştur
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 5. Dosyaya Yaz
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(clean_code)

            print(f"[FileWriter: BAŞARILI] {len(clean_code)} bayt {target_path} dosyasına yazıldı.")
            return target_path

        except (IOError, OSError) as e:
            print(f"[FileWriter: KRİTİK YAZMA HATASI] Dosya yazılırken hata oluştu: {e}")
            return None
        except Exception as e:
            print(f"[FileWriter: BEKLENMEDİK HATA] {e}")
            return None
