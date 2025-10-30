"""
BaseAI Stratejik Evrim Döngüsü (Evolution Reflector).

Bu modül, BaseAI'nin genel hedeflerini (TriaportAI, BinAI vb.)
göz önünde bulundurarak üst düzey geliştirme görevleri üretir,
bu görevleri yürütür ve sonuçları analiz ederek gelecekteki
stratejileri optimize eder. self_heal_loop'un yerini alır.
"""

from __future__ import annotations
import os
import time
import asyncio
import traceback
import json
import re
import tempfile
import shlex
from typing import Dict, List, Any, Set, Optional, Tuple

# BaseAI Çekirdek Bileşenleri
from baseai.bridges.gpt import gpt_bridge, GPTConfig # GPT Köprüsü
from baseai.log.logger import core_logger as log    # Merkezi Logger
# Self-heal loop'tan temel yardımcı fonksiyonları import et
# (Kod tekrarını önlemek için idealde bunlar ortak bir 'utils' modülünde olmalı)
from baseai.autodev.self_heal_loop import (
    _validate_and_normalize_path,
    _write_files_to_disk,
    _get_codebase_context,
    _read_file_content,
    _parse_task_description,
    _run_subprocess,
    _lint_code, # Otomatik düzeltme mantığını içeren son sürüm
    _check_git_status,
    _git_add_commit,
    PROJECT_ROOT_DIR,
    BASE_AI_CORE_DIR,
    AUTODEV_BOOTSTRAP_FILES, # Bootstrap kontrolü için
    CONTEXT_IGNORE_DIRS,
    CONTEXT_MAX_FILES,
    SUPPORTED_TASK_TYPES, # Görev tipleri hala geçerli olabilir
    ENABLE_GIT_AUTO_COMMIT # Commit ayarı
)

# --- Stratejik Evrim Sabitleri ---
EVOLUTION_DATA_FILE = os.path.join(PROJECT_ROOT_DIR, 'evolution_data.json')
# Stratejik görev üretimi için farklı bir prompt gerekebilir
STRATEGIC_TASK_PROMPT_TEMPLATE = (
    "**ROL:** BaseAI Üst Düzey Mimar.\n"
    "**AMAÇ:** BaseAI ekosisteminin (TriaportAI, BinAI, DropAI) genel hedeflerine ulaşması için bir sonraki **stratejik** geliştirme adımını belirle.\n"
    "**MEVCUT DURUM:**\n"
    "  - Kod Tabanı Özeti (Ana Modüller):\n```\n{code_context}\n```\n"
    "  - Geçmiş Başarı Oranı (varsa): {success_rate_info}\n"
    "**ANA HEDEFLER:**\n"
    "  1. **TriaportAI:** Lojistik/Forwarder zekasını tamamla.\n"
    "  2. **BinAI:** Futures trading zekasını geliştir.\n"
    "  3. **Entegrasyon:** Bu alt zekaları BaseAI çekirdeği ile tam entegre et.\n"
    "**İSTEK:** Bu bilgilere dayanarak, **bir sonraki en kritik ve mantıklı görevi** aşağıdaki **KESİN FORMATTA** tanımla:\n"
    "```text\n"
    "Görev Tipi: [YENİ_MODÜL, MEVCUT_MODÜLÜ_GELİŞTİR, REFAKTÖR, TEST_YAZ]\n"
    "Hedef Dosya(lar): [İlgili dosya yolu/yolları veya Yeni dosya adı]\n"
    "Açıklama: [Görevin stratejik önemini vurgulayan 1-2 cümlelik özet]\n"
    "```\n"
    "**ÖRNEK STRATEJİK GÖREV:**\n"
    "```text\n"
    "Görev Tipi: YENİ_MODÜL\n"
    "Hedef Dosya(lar): baseai/subai/triaport/core_logic.py\n"
    "Açıklama: TriaportAI için temel yük takip ve rota optimizasyon mantığını içeren çekirdek modülü oluştur.\n"
    "```\n"
    "**SENİN YANITIN (SADECE 3 SATIR):**"
)

# --- Geçmiş Analiz Fonksiyonları ---

def load_evolution_data() -> Dict[str, List]:
    """Loads historical evolution data from the JSON file."""
    if os.path.exists(EVOLUTION_DATA_FILE):
        try:
            with open(EVOLUTION_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Basit doğrulama: Beklenen anahtarlar var mı?
                if isinstance(data.get('iterations'), list):
                    return data
                else:
                    log.warning(f"'{EVOLUTION_DATA_FILE}' dosyası geçersiz formatta. Sıfırlanıyor.")
                    return {"iterations": []} # Geçersizse sıfırla
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"'{EVOLUTION_DATA_FILE}' okunamadı: {e}. Sıfırlanıyor.")
            return {"iterations": []} # Hata durumunda sıfırla
    return {"iterations": []} # Dosya yoksa boş başlat

def save_evolution_data(data: Dict[str, List]):
    """Saves evolution data to the JSON file."""
    try:
        with open(EVOLUTION_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        log.error(f"'{EVOLUTION_DATA_FILE}' dosyasına yazılamadı: {e}")
    except Exception as e:
         log.error(f"Evrim verisi kaydedilirken beklenmedik hata: {e}", exc_info=True)


def analyze_past_cycles(data: Dict[str, List]) -> str:
    """Analyzes past development cycles from loaded data."""
    iterations = data.get("iterations", [])
    if not iterations:
        return "Geçmiş veri yok."
    
    successful_tasks = sum(1 for iter_data in iterations if iter_data.get("success"))
    total_tasks = len(iterations)
    success_rate = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Daha fazla analiz eklenebilir (örn: en çok hata veren görev tipleri)
    
    return f"Toplam {total_tasks} görev denendi, başarı oranı: %{success_rate:.1f}"

# --- ANA STRATEJİK EVRİM DÖNGÜSÜ ---

async def run_once() -> Dict[str, Any]:
    """
    BaseAI Stratejik Evrim Döngüsünün tek bir iterasyonunu çalıştırır.
    Geçmişi analiz eder, stratejik görev üretir, yürütür, doğrular ve sonucu kaydeder.
    """
    start_time = time.monotonic()
    log.info("[AutoDev|StratejikEvrim] ▶️ Stratejik Döngü İterasyonu Başlıyor...")
    
    result: Dict[str, Any] = {
        "timestamp": time.time(), # Zaman damgası ekleyelim
        "success": False, "task_type": "N/A", "task_target": "N/A",
        "task_description": "N/A", "files_generated": [], "files_lint_failed": [], 
        "files_git_blocked": [], "files_written": [], "files_failed_write": [], 
        "error": None, "duration_s": 0 # Süre ekleyelim
    }
    
    task_type: str = "N/A"
    task_description: str = "N/A"
    target_file_paths: List[str] = []
    task_target_str: str = "N/A" 

    try:
        bridge = await gpt_bridge() 
        
        # --- Adım 1: Geçmiş Veriyi Yükle ve Analiz Et ---
        evolution_data = load_evolution_data()
        analysis_summary = analyze_past_cycles(evolution_data)
        log.info(f"[AutoDev|StratejikEvrim] Geçmiş Analizi: {analysis_summary}")
        
        # --- Adım 2: Durum Değerlendirme (Kod Bağlamı) ---
        # Stratejik görevler için daha geniş bir bağlam gerekebilir,
        # Şimdilik core modüllerini kullanmaya devam edelim.
        code_context = await _get_codebase_context(BASE_AI_CORE_DIR, CONTEXT_IGNORE_DIRS, max_files=50) # Daha az dosya ile başla?
        if "[HATA:" in code_context:
             result["error"] = "Failed to get codebase context."; return result

        # --- Adım 3: Stratejik Görev Üretimi ---
        log.info("[AutoDev|StratejikEvrim] 🎯 Bir sonraki stratejik görev LLM'den isteniyor...")
        task_generation_prompt = STRATEGIC_TASK_PROMPT_TEMPLATE.format(
            code_context=code_context,
            success_rate_info=analysis_summary
        )
        try:
             next_task_raw = await bridge.generate_text(task_generation_prompt)
             log.info(f"[AutoDev|StratejikEvrim] 🎯 LLM Görev Önerisi (Ham):\n{next_task_raw}")
             task_details = _parse_task_description(next_task_raw) 
             if not task_details:
                 result["error"] = "LLM desteklenmeyen/ayrıştırılamayan bir görev tanımı üretti."
                 result["success"] = False; return result
                 
             task_type = task_details['type']
             task_description = task_details['description']
             task_target_str = task_details['target'] 
             target_file_paths = [re.sub(r'[`\'"]', '', p.strip()) for p in task_target_str.split(',') if p.strip()]
             
             result.update(task_details) 
             log.info(f"[AutoDev|StratejikEvrim] ✅ Görev Belirlendi: [{task_type}] {task_target_str}") 
        except Exception as e:
             log.error(f"[AutoDev|StratejikEvrim] ❌ Görev üretimi sırasında LLM hatası: {e}", exc_info=True)
             result["error"] = f"Failed to generate/parse next task: {e}"; return result

        # --- Adım 4 & 5: Bağlam Hazırlama ve Görev Yürütme ---
        # Bu adımlar self_heal_loop ile büyük ölçüde aynıdır
        execution_instruction: str = ""; execution_context: str = ""; execution_rules: List[str] = []
        
        if task_type in ["MEVCUT_MODÜLÜ_GELİŞTİR", "REFAKTÖR", "TEST_YAZ", "YENİ_MODÜL"]: # YENİ_MODÜL eklendi
             if not target_file_paths: result["error"] = f"Görev tipi '{task_type}' için hedef dosya gerekli."; return result
             
             # YENİ_MODÜL ise bağlam olarak sadece kod tabanını kullanır
             if task_type == "YENİ_MODÜL":
                 if len(target_file_paths) != 1: result["error"] = "YENİ_MODÜL için tek hedef dosya gerekir."; return result
                 target_file = target_file_paths[0]
                 execution_context = code_context # Mevcut proje yapısı
                 execution_instruction = (f"**ROL:** ...\n**GÖREV TİPİ:** {task_type}\n**OLUŞTURULACAK DOSYA:** `{target_file}`\n\n**GÖREV AÇIKLAMASI:** {task_description}\n\n**MEVCUT PROJE YAPISI:**\n```\n{execution_context}\n```\n\n**İSTEK:** ... `{target_file}` ... oluştur.\n\n**ÇIKTI FORMATI:** ...JSON (`{{ \"{target_file}\": \"tam_kod\" }}`).")
                 execution_rules = [ "[KESİN] Çıktı formatı: JSON...", f"[KESİN] JSON anahtarı: `{target_file}`.", "[KESİN] Mevcut dosyaları değiştirme.", "[KALİTE] Python 3.11+...", "[KALİTE] Enterprise+++...", "[DOĞRULAMA] Kod `ruff ...` komutundan HATASIZ geçmelidir."]
             else: # MEVCUT_MODÜLÜ_GELİŞTİR, REFAKTÖR, TEST_YAZ
                 file_contents = {}; all_content_read = True
                 for file_path in target_file_paths:
                     content = await _read_file_content(file_path);
                     # Eğer dosya yoksa (TEST_YAZ gibi durumlarda) None dönebilir, sorun değil.
                     if content is None and task_type != "TEST_YAZ": 
                         all_content_read = False; log.error(f"[AutoDev|Evrim] ❌ Hedef dosya okunamadı: {file_path}."); break
                     file_contents[file_path] = content or "" # Okunamayan dosya içeriği boş string
                 if not all_content_read: result["error"] = f"Target file(s) not readable for modification"; return result
                 
                 if len(file_contents) == 1: 
                     execution_context = list(file_contents.values())[0]
                 else: 
                     context_parts = [f"# --- START FILE: {fp} ---\n{fc}\n# --- END FILE: {fp} ---" for fp, fc in file_contents.items()]
                     execution_context = "\n\n".join(context_parts)

                 execution_instruction = (f"**ROL:** ...\n**GÖREV TİPİ:** {task_type}\n**HEDEF DOSYA(LAR):** {task_target_str}\n\n**MEVCUT KOD (varsa):**\n```python\n{execution_context}\n```\n\n**İSTENEN DEĞİŞİKLİK/YENİ KOD:** {task_description}\n\n**ÇIKTI FORMATI:** JSON (`{{ \"{task_target_str}\": \"tam_güncel_kod\" }}`).")
                 execution_rules = [ "[KESİN] Çıktı formatı: JSON...", f"[KESİN] JSON anahtar(lar)ı: `{task_target_str}`.", "[KESİN] Mevcut kodu KORU (eğer varsa).", "[KESİN] SADECE isteneni yap.", "[KALİTE] Python 3.11+...", "[KALİTE] Enterprise+++...", "[DOĞRULAMA] Kod `ruff ...` komutundan HATASIZ geçmelidir."]
        
        log.info(f"[AutoDev|StratejikEvrim] ⚙️ Görev yürütülüyor: {task_description[:100]}...")
        file_bundle = await bridge.generate_files(execution_instruction, execution_context, rules=execution_rules)

        # --- Adım 6, 7, 8: Doğrulama, Lint, Yazma ---
        # Bu adımlar self_heal_loop ile tamamen aynıdır
        if not file_bundle or not isinstance(file_bundle, dict) or "error" in file_bundle:
            error_msg = file_bundle.get("error", "Bilinmeyen köprü hatası") if isinstance(file_bundle, dict) else "Geçersiz veya boş yanıt (Yürütme)"
            result["error"] = f"LLM failed during task execution: {error_msg}"; return result 
            
        result["files_generated"] = list(file_bundle.keys())
        generated_files_set = set(result["files_generated"])
        expected_files_exec = set(target_file_paths) 
        
        if not expected_files_exec.issubset(generated_files_set):
             result["error"] = "LLM execution result missing target file(s)"; return result
             
        log.info(f"[AutoDev|StratejikEvrim] ✅ GPT'den {len(file_bundle)} dosyalık yürütme sonucu alındı.")

        files_to_write: Dict[str, str] = {}; abs_paths_to_commit: List[str] = [] 
        lint_failed_details: Dict[str, str] = {}
        
        for relative_path, content in file_bundle.items():
            if relative_path not in expected_files_exec: 
                 log.warning(f"[AutoDev|StratejikEvrim] ⚠️ LLM beklenmeyen dosya döndürdü, yoksayılıyor: {relative_path}"); continue
                 
            lint_passed, lint_message = await _lint_code(content) 
            if not lint_passed:
                log.error(f"[AutoDev|StratejikEvrim] ❌ Üretilen kod LINT KONTROLÜNÜ GEÇEMEDİ: {relative_path}. Mesaj: {lint_message}")
                result["files_lint_failed"].append(relative_path); lint_failed_details[relative_path] = lint_message; continue 

            abs_path = await _validate_and_normalize_path(relative_path)
            if not abs_path: 
                result["files_failed_write"].append(relative_path); continue 
            
            is_safe, git_status_msg = await _check_git_status(abs_path)
            if not is_safe:
                result["files_git_blocked"].append(relative_path); continue 
            
            files_to_write[relative_path] = content
            abs_paths_to_commit.append(abs_path) 

        if not files_to_write:
             error_parts = []
             if result["files_lint_failed"]: error_parts.append(f"{len(result['files_lint_failed'])} file(s) failed lint check")
             if result["files_git_blocked"]: error_parts.append(f"{len(result['files_git_blocked'])} file(s) blocked by Git status")
             result["error"] = "; ".join(error_parts) if error_parts else "No valid files generated or passed checks."
             result["success"] = False
        else:
            written_files, failed_write = await _write_files_to_disk(files_to_write)
            result["files_written"] = written_files
            result["files_failed_write"].extend(failed_write) 

            all_targets_written = expected_files_exec.issubset(set(written_files)) 
            no_failures = not result["files_lint_failed"] and not result["files_git_blocked"] and not result["files_failed_write"]
            
            if all_targets_written and no_failures:
                result["success"] = True
                log.info("[AutoDev|StratejikEvrim] ✅ Görev başarıyla tamamlandı.")
                if abs_paths_to_commit: await _git_add_commit(abs_paths_to_commit, result['task_description'])
            else:
                result["success"] = False
                errors = []
                if result["files_lint_failed"]: errors.append(f"{len(result['files_lint_failed'])} lint errors")
                if result["files_git_blocked"]: errors.append(f"{len(result['files_git_blocked'])} Git blocks")
                if result["files_failed_write"]: errors.append(f"{len(result['files_failed_write'])} write errors")
                if not all_targets_written: errors.append("Not all targets written")
                result["error"] = "; ".join(errors) if errors else "Unknown validation/write failure"
                log.error(f"[AutoDev|StratejikEvrim] ❌ Görev tamamlanamadı. Hatalar: {result['error']}")
                if lint_failed_details:
                     log.error("[AutoDev|StratejikEvrim] Lint Hata Detayları:")
                     for fname, msg in lint_failed_details.items():
                          log.error(f"  File: {fname} -> {msg}")

    except Exception as e:
        detailed_error = traceback.format_exc()
        log.critical(f"[AutoDev|StratejikEvrim] 💥 Döngüde beklenmeyen kritik hata: {e}\n{detailed_error}")
        result["error"] = f"CRITICAL_EVOLUTION_FAILURE: {e}"
        result["success"] = False

    finally:
        end_time = time.monotonic(); duration = end_time - start_time
        result["duration_s"] = round(duration, 2)
        
        # --- Adım 9: Sonucu Kaydet ---
        evolution_data.setdefault("iterations", []).append(result)
        save_evolution_data(evolution_data)
        
        # --- Sonuç Loglama ---
        status = "BAŞARILI" if result.get("success", False) else "BAŞARISIZ"
        log.info(f"--- [AutoDev|StratejikEvrim] İTERASYON SONUCU ---")
        log.info(f" Durum: {status}"); 
        log.info(f" Görev Tipi: {result.get('task_type', 'N/A')}") 
        log.info(f" Hedef(ler): {result.get('task_target', 'N/A')}")
        log.info(f" Açıklama: {result.get('task_description', 'N/A')[:150]}...")
        log.info(f" Üretilen: {len(result.get('files_generated',[]))}, Yazılan: {len(result.get('files_written',[]))}")
        log.info(f" Başarısız (Lint/Git/Yazma): {len(result.get('files_lint_failed',[]))}/{len(result.get('files_git_blocked',[]))}/{len(result.get('files_failed_write',[]))}")
        log.info(f" Süre: {duration:.2f}s")
        if result.get("error"): log.error(f" Hata Detayı: {result.get('error')}")
        log.info(f"--- İTERASYON SONUCU BİTTİ ---")
             
    return result

# --- Refleks Döngüsü Başlatıcısı (Enterprise Loop gibi) ---
async def start_evolution_loop(
    loop_func: Callable[[], Awaitable[Dict[str, Any]]] = run_once,
    success_delay_sec: float = 900.0, # 15 dakika
    error_delay_sec: float = 60.0    # 1 dakika
):
    """Refleks döngüsünü başlatır."""
    log.info(f"🔁 BaseAI Stratejik Evrim Döngüsü Başlatılıyor (Fonksiyon: '{loop_func.__name__}').")
    log.info(f"   Başarı Sonrası Bekleme: {success_delay_sec} saniye")
    log.info(f"   Hata Sonrası Bekleme  : {error_delay_sec} saniye")
    
    loop_count = 0
    while True: # Sonsuz döngü (Ctrl+C ile durdurulur)
        loop_count += 1
        log.info(f"[Loop #{loop_count}] Yeni stratejik evrim iterasyonu başlıyor...")
        
        iteration_result = {}
        try:
            iteration_result = await loop_func()
            status = iteration_result.get("success", False)
            error_detail = iteration_result.get("error", None)
            duration = iteration_result.get("duration_s", 0)
            
            if status:
                log.info(f"[Loop #{loop_count}] İterasyon tamamlandı. Durum: BAŞARILI. Süre: {duration:.2f}s.")
                delay = success_delay_sec
            else:
                log.info(f"[Loop #{loop_count}] İterasyon tamamlandı. Durum: BAŞARISIZ ({error_detail}). Süre: {duration:.2f}s.")
                delay = error_delay_sec
                
            log.info(f"[Loop #{loop_count}] Sonraki iterasyon için {delay} saniye bekleniyor...")
            await asyncio.sleep(delay)

        except asyncio.CancelledError:
            log.warning(f"[Loop #{loop_count}] Döngü iterasyonu iptal edildi (kapatma isteği).")
            break # Döngüden çık
        except Exception as e:
            # Döngü fonksiyonunun kendisinde beklenmedik hata
            log.critical(f"[Loop #{loop_count}|FATAL] Döngü fonksiyonu '{loop_func.__name__}' kritik hata verdi: {e}", exc_info=True)
            log.info(f"[Loop #{loop_count}] Kritik hata sonrası {error_delay_sec} saniye bekleniyor...")
            await asyncio.sleep(error_delay_sec)


if __name__ == '__main__':
    try:
        # Ana asenkron döngüyü başlat
        asyncio.run(start_evolution_loop())
    except KeyboardInterrupt:
        log.info("Kullanıcı tarafından durduruldu.")
    finally:
        log.info("🏁 BaseAI Stratejik Evrim Döngüsü Kapatıldı.")