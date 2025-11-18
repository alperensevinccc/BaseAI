"""
BaseAI Stratejik Evrim Döngüsü (Evolution Reflector)
NİHAİ SÜRÜM - Tam Otonomi Başlangıcı

Bu modül, BaseAI'nin harici LLM bağımlılığını kırmak için 
gerekli olan içsel modülleri inşa etme sürecini yönetir.
Lokal LLM'i (Ollama) bir araç olarak kullanarak, kendi 
stratejik planlama ve kod analiz yeteneklerini inşa eder.
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
from typing import Dict, List, Any, Set, Optional, Tuple, Union, Callable, Awaitable

# BaseAI Çekirdek Bileşenleri
# Harici bağımlılık kaldırıldı. Lokal köprüye geçiliyor.
from baseai.bridges.local_llm_bridge import local_llm_bridge 
from baseai.log.logger import core_logger as log    # Merkezi Logger

# --- Stabilize Edilmiş Yardımcı Fonksiyonlar ---
# self_heal_loop'tan gerekli olan ve kararlılığı kanıtlanmış 
# tüm yardımcı fonksiyonlar buraya entegre edildi.

PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_AI_CORE_DIR = os.path.join(PROJECT_ROOT_DIR, 'baseai')

# --- NİHAİ DÜZELTME (NameError): EVOLUTION_DATA_FILE global scope'a taşındı. ---
EVOLUTION_DATA_FILE = os.path.join(PROJECT_ROOT_DIR, 'evolution_data.json')

AUTODEV_BOOTSTRAP_FILES: Set[str] = {
    "baseai/autodev/evolution_reflector.py",
    "baseai/autodev/self_heal_loop.py", 
}
CONTEXT_IGNORE_DIRS: Set[str] = {
    ".venv", ".git", "__pycache__", ".idea", ".vscode", 
    "node_modules", "build", "dist", "logs", "tests",
    "autodev" 
}
CONTEXT_MAX_FILES: int = 150 

SUPPORTED_TASK_TYPES: Set[str] = {
    "YENİ_MODÜL", 
    "MEVCUT_MODÜLÜ_GELİŞTİR", 
    "REFAKTÖR", 
    "TEST_YAZ",
}

ENABLE_GIT_SAFETY_CHECK: bool = True 
ENABLE_GIT_AUTO_COMMIT: bool = True 

async def _validate_and_normalize_path(relative_path: str) -> Optional[str]:
    """Göreceli yolu doğrular, normalize eder ve mutlak yolunu döndürür."""
    if not relative_path or not isinstance(relative_path, str):
        log.warning(f"[AutoDev|Path] Geçersiz veya boş dosya yolu: {relative_path}")
        return None
    try:
        abs_path = os.path.normpath(os.path.join(PROJECT_ROOT_DIR, relative_path))
        if not abs_path.startswith(PROJECT_ROOT_DIR):
            log.error(f"[AutoDev|Path|Güvenlik] 🚨 Engellendi! '{relative_path}' proje kökü dışına işaret ediyor.")
            return None
        critical_dirs = {".git", ".venv", ".tmp"} 
        path_parts = set(abs_path.split(os.sep))
        if critical_dirs.intersection(path_parts):
            log.error(f"[AutoDev|Path|Güvenlik] 🚨 Engellendi! '{relative_path}' kritik bir dizine işaret ediyor.")
            return None
        return abs_path
    except Exception as e:
        log.error(f"[AutoDev|Path] '{relative_path}' için yol normalizasyon/doğrulama hatası: {e}", exc_info=True)
        return None

async def _write_files_to_disk(file_bundle: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """Üretilen dosya paketini alır ve diske yazar."""
    written_files: List[str] = []
    failed_files: List[str] = []
    
    if not isinstance(file_bundle, dict) or not file_bundle:
        log.warning("[AutoDev|Disk] Yazılacak dosya içeren boş veya geçersiz bir paket alındı.")
        return written_files, failed_files 

    log.info(f"[AutoDev|Disk] {len(file_bundle)} adet dosya yazılacak...")
    for relative_path, content in file_bundle.items():
        if not content or not isinstance(content, str):
            log.warning(f"[AutoDev|Disk] '{relative_path}' için boş veya geçersiz içerik atlandı.")
            failed_files.append(relative_path)
            continue

        abs_path = await _validate_and_normalize_path(relative_path)
        if not abs_path:
            failed_files.append(relative_path)
            continue 

        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            if os.path.exists(abs_path):
                log.warning(f"[AutoDev|Disk] ⚠️ Mevcut dosyanın üzerine yazılıyor: {relative_path}")
            with open(abs_path, "w", encoding="utf-8") as f: 
                f.write(content)
            log.info(f"[AutoDev|Disk] ✅ Dosya yazıldı/güncellendi: {relative_path}")
            written_files.append(relative_path)
        except Exception as e:
            log.error(f"[AutoDev|Disk] ❌ Yazma hatası ({relative_path}): {e}", exc_info=True)
            failed_files.append(relative_path)
            
    return written_files, failed_files

async def _get_codebase_context(root_dir: str, ignore_dirs: Set[str], max_files: int = CONTEXT_MAX_FILES) -> str:
    """.py dosyalarını tarar ve göreceli yollarını içeren bir metin oluşturur."""
    log.debug(f"[AutoDev|Context] Kod tabanı bağlamı taranıyor (Kök: {root_dir}, Limit: {max_files})...")
    context_files: List[str] = []
    scanned_paths: Set[str] = set()
    try:
        priority_files = ["baseai/main.py", "baseai/core.py"] 
        for pf in priority_files:
            relative_path = pf
            abs_pf_path = os.path.normpath(os.path.join(PROJECT_ROOT_DIR, pf))
            if os.path.exists(abs_pf_path) and relative_path not in scanned_paths:
                context_files.append(relative_path)
                scanned_paths.add(relative_path)
                if len(context_files) >= max_files: break

        if len(context_files) < max_files:
            for current_root, dirs, files in os.walk(root_dir, topdown=True):
                dirs[:] = [d for d in dirs if d not in ignore_dirs and os.path.join(current_root, d) != BASE_AI_CORE_DIR] 
                for file in files:
                     if file.endswith(".py"):
                        full_path = os.path.join(current_root, file)
                        relative_path = os.path.relpath(full_path, PROJECT_ROOT_DIR)
                        if relative_path not in scanned_paths:
                            context_files.append(relative_path)
                            scanned_paths.add(relative_path)
                            if len(context_files) >= max_files: break
                if len(context_files) >= max_files: break 
    except Exception as e:
        log.error(f"[AutoDev|Context] Kod tabanı taranırken hata: {e}", exc_info=True)
        return "[HATA: Kod bağlamı alınamadı]"

    log.info(f"[AutoDev|Context] {len(context_files)} dosya bağlam için bulundu (Limit: {max_files}).")
    return "Mevcut Python Dosyaları (Proje Köküne Göre):\n" + "\n".join(sorted(context_files))

async def _read_file_content(relative_path: str) -> Optional[str]:
    """Verilen göreceli yoldaki dosyanın içeriğini güvenli bir şekilde okur."""
    abs_path = await _validate_and_normalize_path(relative_path)
    if not abs_path: return None
    try:
        if not os.path.exists(abs_path):
            log.warning(f"[AutoDev|Read] Dosya bulunamadı: {relative_path}")
            return None
        file_size_mb = os.path.getsize(abs_path) / (1024 * 1024)
        if file_size_mb > 1:
            log.warning(f"[AutoDev|Read] Dosya çok büyük ({file_size_mb:.2f}MB), içeriği okunmuyor: {relative_path}")
            return f"[HATA: Dosya içeriği çok büyük ({file_size_mb:.2f}MB)]"
        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log.error(f"[AutoDev|Read] Dosya okuma hatası ({relative_path}): {e}", exc_info=True)
        return None

def _parse_task_description(description: str) -> Optional[Dict[str, str]]:
    """LLM'den gelen görev tanımını ayrıştırır."""
    if not description or not isinstance(description, str):
        log.warning("[AutoDev|Parse] Ayrıştırılacak görev tanımı boş veya geçersiz.")
        return None
    task = {"type": "UNKNOWN", "target": "N/A", "description": ""} 
    try:
        type_match = re.search(r"Görev\s*Tipi\s*:\s*(.*)", description, re.IGNORECASE | re.MULTILINE)
        target_match = re.search(r"Hedef\s*Dosya\(lar\)\s*:\s*(.*)", description, re.IGNORECASE | re.MULTILINE)
        desc_match = re.search(r"Açıklama\s*:\s*(.*)", description, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        raw_type = "UNKNOWN"
        if type_match:
            value = type_match.group(1).strip()
            cleaned_value = re.sub(r"^[^\w]+|[^\w]+$", "", value).strip()
            raw_type = cleaned_value.upper().replace(" ", "_")
        if raw_type not in SUPPORTED_TASK_TYPES:
            log.error(f"[AutoDev|Parse] ❌ LLM tarafından desteklenmeyen görev tipi üretildi: '{raw_type}'.")
            return None 
        task["type"] = raw_type
        if target_match: 
            value = target_match.group(1).strip()
            cleaned_value = re.sub(r"^[^\w./\\-]+|[^\w./\\-]+$", "", value).strip()
            task["target"] = re.sub(r'[`\'"]', '', cleaned_value)
        if desc_match: 
            task["description"] = desc_match.group(1).strip()
        if task["target"] == "N/A" and task["type"] != "UNKNOWN":
            log.error(f"[AutoDev|Parse] ❌ Görev tipi '{task['type']}' için Hedef Dosya(lar) gerekli ama bulunamadı.")
            return None 
        if not task["description"] and task["type"] != "UNKNOWN":
            log.error("[AutoDev|Parse] ❌ Görev açıklaması boş veya ayrıştırılamadı.")
            return None
        log.info(f"[AutoDev|Parse] ✅ Görev başarıyla ayrıştırıldı ve doğrulandı: Tip='{task['type']}', Hedef='{task['target']}'")
        return task
    except Exception as e:
        log.error(f"[AutoDev|Parse] Görev tanımı ayrıştırılırken kritik hata: {e}", exc_info=True)
        return None

async def _run_subprocess(command_parts: list[str]) -> tuple[bool, str, str]:
    """Verilen komut parçalarını (liste) 'exec' kullanarak asenkron olarak çalıştırır."""
    try:
        if not command_parts:
            return False, "", "Boş komut."
        program = command_parts[0]
        args = command_parts[1:]
        process = await asyncio.create_subprocess_exec(
            program, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout = stdout_bytes.decode('utf-8').strip()
        stderr = stderr_bytes.decode('utf-8').strip()
        success = process.returncode == 0
        if not success and not stderr and stdout:
            stderr = stdout
        return success, stdout, stderr
    except Exception as e:
        command_str = " ".join(command_parts)
        log.error(f"[AutoDev|Subprocess] Alt süreç çalıştırılamadı ('{command_str}'): {e}", exc_info=True)
        return False, "", f"Subprocess failed to run: {str(e)}"

async def _lint_code(code_content: str) -> tuple[bool, str, str]:
    """
    Üretilen Python kodunu Ruff ile lint eder ve *güvenli* hataları düzeltir.
    Returns: (lint_passed, error_message, corrected_code)
    """
    temp_dir = os.path.join(PROJECT_ROOT_DIR, ".tmp")
    os.makedirs(temp_dir, exist_ok=True) 
    temp_file_name: Optional[str] = None 
    corrected_code_content = code_content # Varsayılan olarak orijinal kod

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding='utf-8', dir=temp_dir) as temp_file:
            temp_file.write(code_content)
            temp_file_name = temp_file.name
            temp_file.flush() 
        
        # --- Adım 1: Ruff Düzeltme Denemesi (inplace) ---
        fix_command = [
            "ruff", "check", "--fix", "--force-exclude", 
            "--select=E,F,W", 
            "--ignore=E501,W291", # W291 (Trailing Whitespace) kalıcı olarak yoksayılıyor
            temp_file_name
        ]
        log.debug(f"[AutoDev|Lint|Fix] Ruff düzeltme denemesi: {' '.join(fix_command)}")
        fix_success, fix_output, fix_stderr = await _run_subprocess(fix_command)

        if not fix_success:
             # Eğer Ruff --fix komutu 0 olmayan bir kodla dönerse (örn: düzeltilemeyen hata kaldıysa),
             # bu bir hata değildir, sadece düzeltmenin tamamlanmadığını gösterir.
             # Ancak, stderr varsa, bu Ruff'un çalışamadığını gösterir (örn: ruff kurulu değil)
             if fix_stderr:
                return False, f"Linting failed (Ruff fix execution error): {fix_stderr}", code_content
             # Sadece çıktı (output) varsa, bu düzeltilemeyen hatalardır.
             log.warning(f"[AutoDev|Lint|Fix] Ruff düzeltilemeyen hatalar buldu, son kontrol yapılacak.")
        
        # --- Adım 2: Düzeltilmiş Kodu Oku ---
        with open(temp_file_name, "r", encoding='utf-8') as f:
            corrected_code_content = f.read()

        # --- Adım 3: Son Onay Kontrolü (Sadece Kritik Hatalar: E, F) ---
        check_command = [
            "ruff", "check", "--output-format=json", "--force-exclude", 
            "--select=E,F", # Sadece E ve F'yi kontrol et
            "--ignore=E501", 
            temp_file_name
        ]
        log.debug(f"[AutoDev|Lint|Check] Son onay kontrolü: {' '.join(check_command)}")
        success, output, stderr = await _run_subprocess(check_command)

        if not success:
             error_msg = stderr or output or "Son onay Ruff komutu başarısız oldu."
             return False, f"Linting failed (Final check execution error): {error_msg}", corrected_code_content
        
        # --- Adım 4: JSON Çıktısını Yorumla ---
        try:
            # Output boşsa (veya sadece whitespace ise), KESİN BAŞARIDIR.
            if not output:
                 return True, "Linting passed (Autofix applied).", corrected_code_content

            lint_errors = json.loads(output)
            
            # JSON parse edildi ve hata listesi boştuysa, BAŞARIDIR.
            if not lint_errors:
                 return True, "Linting passed (JSON output empty/no errors).", corrected_code_content
            
            # Düzeltilemeyen (E/F) hatalar kaldı
            error_summaries = [f"{e.get('code','N/A')} (L{e.get('location',{}).get('row')}): {e.get('message','N/A')}" for e in lint_errors]
            first_summary = error_summaries[0]
            log.error(f"[AutoDev|Evrim] Ruff düzeltme sonrası kritik hatalar buldu ({len(error_summaries)} adet).")
            return False, f"Linting failed after autofix ({len(error_summaries)} remaining): {first_summary}", corrected_code_content

        except json.JSONDecodeError:
            # Ruff RC=0 döndü ama JSON bozuk. 
            error_msg = stderr or output or "Bilinmeyen ruff JSON hatası."
            log.error(f"[AutoDev|Evrim] Ruff başarılı (RC=0) ancak JSON ayrıştırılamadı. Ham çıktı: {error_msg}")
            return False, f"Linting failed (Final check returned unparsable JSON with RC=0): {error_msg}", corrected_code_content

    except Exception as e:
        log.error(f"[AutoDev|Lint] Linting sırasında beklenmedik kritik hata: {e}", exc_info=True)
        return False, f"Unexpected internal linting error: {e}", code_content
    finally:
        if temp_file_name and os.path.exists(temp_file_name):
            try:
                os.remove(temp_file_name)
            except OSError as e:
                log.warning(f"[AutoDev|Lint] Geçici dosya silinemedi: {e}")

async def _check_git_status(abs_filepath: str) -> Tuple[bool, str]:
    """
    Verilen dosyanın Git durumunu kontrol eder.
    """
    if not ENABLE_GIT_SAFETY_CHECK:
        return True, "Git safety check disabled."
        
    # --- YENİ GÜVENLİK KONTROLÜ (YENİ_MODÜL için) ---
    # Eğer dosya henüz mevcut değilse (YENİ_MODÜL durumu), 
    # Git kontrolü yapmaya gerek yoktur, yazmak güvenlidir.
    if not os.path.exists(abs_filepath):
        log.debug(f"[AutoDev|Git] Hedef dosya mevcut değil ({os.path.relpath(abs_filepath, PROJECT_ROOT_DIR)}). Yazma güvenli.")
        return True, "File does not exist (new module)."
    git_dir = os.path.join(PROJECT_ROOT_DIR, ".git")
    if not os.path.exists(git_dir):
        log.warning("[AutoDev|Git] Proje bir Git deposu değil. Güvenlik kontrolü atlanıyor.")
        return True, "Not a Git repository."
    command = ["git", "status", "--porcelain", abs_filepath]
    success, stdout, stderr = await _run_subprocess(command)
    if not success:
        return False, f"Failed to run git status: {stderr}" 
    if not stdout:
        return True, "File is clean or untracked."
    else:
        log.critical(f"[AutoDev|Git|Güvenlik] 🚨 YAZMA ENGELLENDİ! '{os.path.relpath(abs_filepath, PROJECT_ROOT_DIR)}' dosyasında kaydedilmemiş değişiklikler var.")
        return False, f"Uncommitted changes detected: {stdout.strip()}"

async def _git_add_commit(abs_filepaths: List[str], task_description: str) -> bool:
    """Yazılan dosyaları Git'e ekler ve commit atar."""
    if not ENABLE_GIT_AUTO_COMMIT or not abs_filepaths:
        return False
    git_dir = os.path.join(PROJECT_ROOT_DIR, ".git")
    if not os.path.exists(git_dir):
        return False
    valid_paths_to_add = [p for p in abs_filepaths if p and p.startswith(PROJECT_ROOT_DIR)]
    if not valid_paths_to_add:
        return False
    add_command = ["git", "add"] + valid_paths_to_add
    success_add, _, stderr_add = await _run_subprocess(add_command)
    if not success_add:
        log.error(f"[AutoDev|Git] 'git add' başarısız oldu: {stderr_add}"); return False
    commit_subject = f"feat(AutoDev): Apply changes for task - {task_description[:70]}"
    file_list_str = "\n- ".join(os.path.relpath(p, PROJECT_ROOT_DIR) for p in valid_paths_to_add[:3])
    if len(valid_paths_to_add) > 3: file_list_str += "\n- ..."
    commit_message = f"{commit_subject}\n\nFiles changed:\n- {file_list_str}"
    commit_command = ["git", "commit", "-m", commit_message]
    success_commit, stdout_commit, stderr_commit = await _run_subprocess(commit_command)
    if not success_commit and "nothing to commit" in (stdout_commit + stderr_commit):
        return True # Hata yok
    elif not success_commit:
        log.error(f"[AutoDev|Git] 'git commit' başarısız oldu: {stderr_commit}"); return False
    log.info(f"[AutoDev|Git] ✅ Değişiklikler otomatik olarak commit edildi.")
    push_command = ["git", "push", "origin", "main"]
    success_push, stdout_push, stderr_push = await _run_subprocess(push_command)

    if not success_push:
        log.error(f"[AutoDev|Git] 'git push' başarısız oldu: {stderr_push}")
        return False # Push başarısız olursa tüm işlemi başarısız say
    
    log.info("[AutoDev|Git] ✅ Değişiklikler başarıyla GitHub'a yüklendi.")

    return True

# --- Geçmiş Analiz Fonksiyonları ---

def load_evolution_data() -> Dict[str, List]:
    """Tarihsel evrim verilerini JSON dosyasından yükler."""
    if os.path.exists(EVOLUTION_DATA_FILE):
        try:
            with open(EVOLUTION_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data.get('iterations'), list):
                    return data
                else:
                    log.warning(f"'{EVOLUTION_DATA_FILE}' dosyası geçersiz formatta. Sıfırlanıyor.")
                    return {"iterations": []} 
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"'{EVOLUTION_DATA_FILE}' okunamadı: {e}. Sıfırlanıyor.")
            return {"iterations": []}
    return {"iterations": []} 

def save_evolution_data(data: Dict[str, List]):
    """Evrim verilerini JSON dosyasına kaydeder."""
    try:
        with open(EVOLUTION_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        log.error(f"'{EVOLUTION_DATA_FILE}' dosyasına yazılamadı: {e}")
    except Exception as e:
         log.error(f"Evrim verisi kaydedilirken beklenmedik hata: {e}", exc_info=True)

def analyze_past_cycles(data: Dict[str, List]) -> str:
    """Yüklenen verilerden geçmiş geliştirme döngülerini analiz eder."""
    iterations = data.get("iterations", [])
    if not iterations:
        return "Geçmiş veri yok."
    successful_tasks = sum(1 for iter_data in iterations if iter_data.get("success"))
    total_tasks = len(iterations)
    success_rate = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0
    return f"Toplam {total_tasks} görev denendi, başarı oranı: %{success_rate:.1f}"

# --- ANA STRATEJİK EVRİM DÖNGÜSÜ ---

async def run_once() -> Dict[str, Any]:
    """
    BaseAI Stratejik Evrim Döngüsünün tek bir iterasyonunu çalıştırır.
    (Stratejik Görev Manuel Olarak Atanmış Sürüm)
    """
    start_time = time.monotonic()
    log.info("[AutoDev|StratejikEvrim] ▶️ Stratejik Döngü İterasyonu Başlıyor...")
    
    # NİHAİ DÜZELTME (UnboundLocalError): 'evolution_data'yı try bloğunun dışına taşı
    evolution_data = load_evolution_data()
    
    result: Dict[str, Any] = {
        "timestamp": time.time(), 
        "success": False, "task_type": "N/A", "task_target": "N/A",
        "task_description": "N/A", "files_generated": [], "files_lint_failed": [], 
        "files_git_blocked": [], "files_written": [], "files_failed_write": [], 
        "error": None, "duration_s": 0
    }
    
    # --- NİHAİ DÜZELTME (ReadTimeout): Görev Üretme Adımını Atla ve Manuel Görev Ata ---
    # Lokal LLM'in (Ollama) planlama (ReadTimeout) hatasını önlemek için
    # Kendi kendine yeterlilik (Aşama 1) görevini manuel olarak enjekte et.
    task_type: str = "YENİ_MODÜL"
    task_target_str: str = "baseai/core/code_analyzer.py"
    task_description: str = (
        "BaseAI'nin harici LLM'lere olan bağımlılığını azaltmak için ilk adımı at. "
        "Python'un 'ast' (Abstract Syntax Tree) kütüphanesini kullanarak, "
        "verilen bir Python kod dizesini analiz edebilen (parse) "
        "ve içindeki fonksiyonları, sınıfları ve import'ları listeleyebilen "
        "temel bir 'CodeAnalyzer' sınıfı oluştur."
    )
    # --- Manuel Görev Ataması Bitti ---

    target_file_paths = [re.sub(r'[`\'"]', '', p.strip()) for p in task_target_str.split(',') if p.strip()]

    try:
        # Lokal Köprüyü (Ollama) kullan
        bridge = await local_llm_bridge() 
        
        # --- Adım 1 & 2: Analiz ve Bağlam ---
        analysis_summary = analyze_past_cycles(evolution_data)
        log.info(f"[AutoDev|StratejikEvrim] Geçmiş Analizi: {analysis_summary}")
        
        code_context = await _get_codebase_context(BASE_AI_CORE_DIR, CONTEXT_IGNORE_DIRS, max_files=50)
        if "[HATA:" in code_context:
             result["error"] = "Failed to get codebase context."; return result

        # --- Adım 3: Görev Üretimi (ATLANDI) ---
        result.update({
            "task_type": task_type,
            "task_description": task_description,
            "task_target": task_target_str
        })
        log.info(f"[AutoDev|StratejikEvrim] ✅ Görev Manuel Olarak Belirlendi: [{task_type}] {task_target_str}") 

        # --- Adım 4 & 5: Bağlam Hazırlama ve Görev Yürütme ---
        execution_instruction: str = ""; execution_context: str = ""; execution_rules: List[str] = []
        
        if task_type == "YENİ_MODÜL":
             if not target_file_paths or len(target_file_paths) != 1: 
                 result["error"] = "YENİ_MODÜL için tek hedef dosya gerekir."; return result
             
             target_file = target_file_paths[0] 
             execution_context = code_context # Mevcut proje yapısı
             execution_instruction = (
                 f"**GÖREV TİPİ:** {task_type}\n"
                 f"**OLUŞTURULACAK DOSYA:** `{target_file}`\n\n"
                 f"**GÖREV AÇIKLAMASI:** {task_description}\n\n"
                 f"**MEVCUT PROJE YAPISI (Referans için):**\n```\n{execution_context}\n```\n\n"
                 f"**İSTEK:** Lütfen `{target_file}` dosyası için tam Python kodunu oluştur.\n\n"
                 f"**ÇIKTI FORMATI:** JSON (`{{ \"{target_file}\": \"tam_kod\" }}`)."
             )
             execution_rules = [
                 "[KESİN] Çıktı formatı: JSON.",
                 f"[KESİN] JSON anahtarı: `{target_file}`.",
                 "[KALİTE] Python 3.11+ standartlarında, type hinting kullanarak yaz.",
                 "[DOĞRULAMA] Kod `ruff ...` komutundan HATASIZ geçmelidir."
             ]
        else:
            # Bu manuel döngüde diğer görev tipleri beklenmiyor
             log.error(f"Manuel olarak atanmış bu döngüde desteklenmeyen görev tipi: {task_type}")
             result["error"] = f"Unsupported task type in manual override: {task_type}"; return result
        
        log.info(f"[AutoDev|StratejikEvrim] ⚙️ Görev yürütülüyor: {task_description[:100]}...")
        
        # Lokal model (Ollama) aracılığıyla kod üretimi
        file_bundle = await bridge.generate_files(execution_instruction, execution_context, rules=execution_rules)

        # --- Adım 6, 7, 8: Doğrulama, Lint, Yazma ---
        if not file_bundle or not isinstance(file_bundle, dict) or "error" in file_bundle:
            error_msg = file_bundle.get("error", "Lokal köprü hatası") if isinstance(file_bundle, dict) else "Geçersiz veya boş yanıt (Yürütme)"
            result["error"] = f"LLM failed during task execution: {error_msg}"; return result 
            
        result["files_generated"] = list(file_bundle.keys())
        generated_files_set = set(result["files_generated"])
        expected_files_exec = set(target_file_paths) 
        
        if not expected_files_exec.issubset(generated_files_set):
             log.error(f"[AutoDev|StratejikEvrim] ❌ Lokal LLM yürütme sonucu beklenen hedef dosyaları içermiyor! Beklenen: {expected_files_exec}, Dönen: {generated_files_set}")
             result["error"] = "Lokal LLM yürütme sonucu beklenen hedef dosyaları içermiyor!"; return result
             
        log.info(f"[AutoDev|StratejikEvrim] ✅ Lokal LLM'den {len(file_bundle)} dosyalık yürütme sonucu alındı.")

        files_to_write: Dict[str, str] = {}; abs_paths_to_commit: List[str] = [] 
        lint_failed_details: Dict[str, str] = {}
        
        for relative_path, content in file_bundle.items():
            if relative_path not in expected_files_exec: 
                 log.warning(f"[AutoDev|StratejikEvrim] ⚠️ Lokal LLM beklenmeyen dosya döndürdü, yoksayılıyor: {relative_path}"); continue
                 
            lint_passed, lint_message, corrected_code = await _lint_code(content) 
            
            if not lint_passed:
                log.error(f"[AutoDev|StratejikEvrim] ❌ Üretilen kod LINT KONTROLÜNÜ GEÇEMEDİ: {relative_path}. Mesaj: {lint_message}")
                result["files_lint_failed"].append(relative_path); lint_failed_details[relative_path] = lint_message; continue 

            content = corrected_code # Otomatik düzeltilmiş kodu kullan

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
                log.info("[AutoDev|StratejikEvrim] ✅ Görev başarıyla tamamlandı, commit atılıyor...")
                
                # --- Adım 9: Otomatik Commit ve Push ---
                commit_success = False
                if abs_paths_to_commit:
                    # _git_add_commit artık push işlemini de içeriyor ve başarı/başarısızlık döndürüyor
                    commit_success = await _git_add_commit(abs_paths_to_commit, result['task_description'])
                
                if commit_success:
                    result["success"] = True
                    log.info("[AutoDev|StratejikEvrim] ✅ Görev başarıyla GitHub'a kaydedildi.")
                else:
                    # EĞER COMMIT VEYA PUSH BAŞARISIZ OLURSA (örn: Colab Yetki Hatası):
                    result["success"] = False
                    result["error"] = "Task completed but failed to commit or push to GitHub."
                    log.error("[AutoDev|StratejikEvrim] ❌ Görev tamamlandı ancak GitHub'a push edilemedi.")

            else: # Kısmi başarı veya tam başarısızlık (Lint, Git, Yazma)
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
        
        # 'evolution_data' artık burada her zaman tanımlı
        evolution_data.setdefault("iterations", []).append(result)
        save_evolution_data(evolution_data)
        
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