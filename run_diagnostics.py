"""
BaseAI Otonom Operasyon ve Tanılama (OOT) Sistemi (v9.1)
Enterprise+++ Seviyesi
- P0 (Dosya Yazıcı) 'os.path.exists()' yol (path) hatası onarıldı.
- P4 (Raporlama) 'AttributeError: 'Row' object has no attribute 'cells'' hatası onarıldı.
- 'rich' kütüphanesi ile yapısal ve renkli raporlama (P4) sağlar.
"""
import asyncio
import logging
import os
import shutil
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

# 'rich' loglamayı etkinleştirmek için 'config' MUTLAKA İLK olarak yüklenmelidir.
try:
    from baseai.config import config
except ImportError as e:
    print(f"[OOT: KRİTİK HATA] Config yüklenemedi. 'config.py' (v8.2) eksik mi? Hata: {e}")
    exit(1)

# 'config' yüklendikten sonra, diğer bileşenleri güvenle yükle
try:
    from baseai.bridges.gemini import gemini_bridge
    from baseai.components.intent_processor import IntentProcessor, Blueprint
    from baseai.components.code_generator import CodeGenerator
    from baseai.components.code_auditor import CodeAuditor
    from baseai.components.file_writer import FileWriter
except ImportError as e:
    logging.critical(f"[OOT: KRİTİK HATA] Çekirdek bileşenler (örn: gemini.py) yüklenemedi: {e}")
    exit(1)

# Tanılama için global ayarlar
console = Console()
DIAG_TEMP_DIR = "temp_diag_do_not_edit"
DIAG_TEST_INTENT = (
    f"Yeni bir dosya oluştur: '{DIAG_TEMP_DIR}/diag_test_module.py'. "
    f"Bu dosyaya, 'calculate_sum' adında, iki integer (a: int, b: int) "
    f"alan ve toplamlarını (a + b) döndüren bir fonksiyon yaz. "
    f"Fonksiyon, Enterprise+++ standartlarına uygun olmalı ve type hints içermelidir."
)

class OOTSystem:
    def __init__(self):
        # Yazıcıyı (P0 Onarımı) projenin ana diziniyle (os.getcwd()) başlat
        self.writer_root = os.getcwd()
        self.writer = FileWriter(root_dir=self.writer_root) 
        
        self.processor = IntentProcessor()
        self.generator = CodeGenerator()
        self.auditor = CodeAuditor()
        self.report_table = self._create_report_table()

    def _create_report_table(self) -> Table:
        """Tanılama raporu için 'rich' tablosunu hazırlar."""
        table = Table(
            title="[bold cyan]BaseAI Otonom Operasyon ve Tanılama (OOT) Raporu (v9.1)[/bold cyan]",
            style="blue",
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("ADIM (BİLEŞEN)", style="cyan", width=25)
        table.add_column("DURUM", style="green", width=12)
        table.add_column("DETAYLAR / SONUÇ", style="white", min_width=50)
        return table

    def _add_row(self, step: str, status: str, details: str):
        """Rapora bir satır ekler."""
        status_emoji = "[bold green]BAŞARILI[/bold green] ✅" if status == "BAŞARILI" else "[bold red]BAŞARISIZ[/bold red] ❌"
        self.report_table.add_row(step, status_emoji, details)

    async def run_diagnostics(self):
        """Tüm BaseAI boru hattını uçtan uca test eder."""
        console.clear()
        
        with Live(self.report_table, refresh_per_second=10, vertical_overflow="visible") as live:
            try:
                # --- Adım 0: Güvenli Alan Hazırlığı ---
                live.update(self.report_table)
                time.sleep(0.5)
                temp_dir_full_path = os.path.join(self.writer_root, DIAG_TEMP_DIR)
                if os.path.exists(temp_dir_full_path):
                    shutil.rmtree(temp_dir_full_path)
                os.makedirs(temp_dir_full_path)
                self._add_row("HAZIRLIK (OOT)", "BAŞARILI", f"Güvenli test dizini '{temp_dir_full_path}/' oluşturuldu.")
                
                # --- Adım 1: Yapılandırma (Config) ---
                live.update(self.report_table)
                time.sleep(0.5)
                if not config or not config.GOOGLE_PROJECT_ID:
                    self._add_row("YAPILANDIRMA (config.py)", "BAŞARISIZ", "Config modülü veya Proje ID'si yüklenemedi.")
                    return
                self._add_row(
                    "YAPILANDIRMA (config.py)", "BAŞARILI", 
                    f"Proje: [bold]{config.GOOGLE_PROJECT_ID}[/bold], Model: [bold]{config.DEFAULT_GEMINI_MODEL}[/bold]"
                )

                # --- Adım 2: Köprü (GeminiBridge) ---
                live.update(self.report_table)
                time.sleep(0.5)
                if not gemini_bridge or not gemini_bridge.model:
                    self._add_row("KÖPRÜ (gemini.py)", "BAŞARISIZ", "Gemini Köprüsü veya Vertex AI Modeli başlatılamadı.")
                    return
                self._add_row("KÖPRÜ (gemini.py)", "BAŞARILI", "Vertex AI SDK'sı (v8.2) aktif ve modele bağlı.")

                # --- Adım 3: Niyet İşleyici (IntentProcessor) ---
                live.update(self.report_table)
                time.sleep(0.5)
                blueprint: Optional[Blueprint] = await self.processor.process_intent(DIAG_TEST_INTENT)
                if not blueprint or blueprint.target_path != f"{DIAG_TEMP_DIR}/diag_test_module.py":
                    self._add_row("NİYET İŞLEYİCİ", "BAŞARISIZ", "Niyet (intent) JSON plana dönüştürülemedi.")
                    return
                self._add_row("NİYET İŞLEYİCİ", "BAŞARILI", f"Niyet başarıyla plana dönüştürüldü. Hedef: {blueprint.target_path}")
                
                # --- Adım 4: Kod Üreteci (CodeGenerator) ---
                live.update(self.report_table)
                time.sleep(0.5)
                raw_code: Optional[str] = await self.generator.generate_code(blueprint, target_model="vertex")
                if not raw_code or "def calculate_sum" not in raw_code:
                    self._add_row("KOD ÜRETECİ", "BAŞARISIZ", "Kod üretilemedi veya 'calculate_sum' fonksiyonu eksik.")
                    return
                self._add_row("KOD ÜRETECİ", "BAŞARILI", f"{len(raw_code)} bayt ham kod üretildi.")

                # --- Adım 5: Kod Denetçisi (CodeAuditor) ---
                live.update(self.report_table)
                time.sleep(0.5)
                is_valid, report, audited_code = await self.auditor.audit_code(raw_code, blueprint)
                if not is_valid:
                    self._add_row("KOD DENETÇİSİ", "BAŞARISIZ", f"Denetçi reddetti: {report}")
                    return
                self._add_row("KOD DENETÇİSİ", "BAŞARILI", f"Denetçi onayladı: {report}")

                # --- Adım 6: Dosya Yazıcı (FileWriter) ---
                live.update(self.report_table)
                time.sleep(0.5)
                
                # [P0 ONARIM] 'write_to_project' göreceli (relative) yol döndürür.
                # 'os.path.exists()' için tam (absolute) yolu (self.writer_root ile birleştirilmiş) kontrol et.
                relative_path = self.writer.write_to_project(audited_code, blueprint)
                full_path = os.path.join(self.writer_root, relative_path) if relative_path else None

                if not full_path or not os.path.exists(full_path):
                    self._add_row("DOSYA YAZICI", "BAŞARISIZ", "Denetlenmiş kod diske yazılamadı.")
                    return
                self._add_row("DOSYA YAZICI", "BAŞARILI", f"Kod başarıyla '{full_path}' dosyasına yazıldı.")

            except Exception as e:
                console.print_exception()
                self._add_row("KRİTİK HATA", "BAŞARISIZ", f"Tanılama sırasında sistem çöktü: {e}")
            
            finally:
                # --- Sonuç Paneli ---
                live.stop()
                
                # [P4 ONARIM] 'AttributeError: 'Row' object has no attribute 'cells'' hatasını çöz.
                # 'self.report_table.rows' yerine 'self.report_table._rows' (internal)
                # veya daha güvenlisi, 'self.report_table.columns' kullanarak kontrol et.
                # En güvenlisi: 'self.report_table.columns[1]' (DURUM sütunu) hücresine bak.
                
                # 'self.report_table.columns[1]._cells' (DURUM sütunundaki hücrelerin listesi)
                has_failure = any("BAŞARISIZ" in str(cell) for cell in self.report_table.columns[1]._cells)

                console.print(self.report_table)
                
                if has_failure:
                    final_status = "[bold red]KRİTİK HATA TESPİT EDİLDİ[/bold red]"
                    final_message = "Bileşenlerden biri veya daha fazlası testi geçemedi. Yukarıdaki raporu inceleyin."
                else:
                    final_status = "[bold green]TÜM SİSTEMLER OPERASYONEL (ENTERPRISE+++)[/bold green]"
                    final_message = (
                        "BaseAI Çekirdeği, yeni Vertex AI SDK'sı (v8.2) üzerinde tam kapasite çalışıyor. "
                        "Tüm bileşenler (P0) ve kozmetik raporlama (P4) testleri başarıyla tamamlandı."
                    )

                console.print(Panel(
                    f"{final_status}\n\n{final_message}",
                    title="[bold]OOT NİHAİ RAPORU (v9.1)[/bold]",
                    border_style="cyan",
                    padding=(1, 2)
                ))
                
                # Güvenli alanı temizle
                if os.path.exists(DIAG_TEMP_DIR):
                    # shutil.rmtree(DIAG_TEMP_DIR)
                    console.print(f"Tanılama tamamlandı. Sonuçlar '{DIAG_TEMP_DIR}' dizininde bırakıldı.")


if __name__ == "__main__":
    if not config:
        logging.critical("Config yüklenemediği için Tanılama (OOT) sistemi başlatılamıyor.")
    else:
        try:
            oot_system = OOTSystem()
            asyncio.run(oot_system.run_diagnostics())
        except KeyboardInterrupt:
            console.print("\n[bold red]Tanılama (OOT) manuel olarak iptal edildi.[/bold red]")