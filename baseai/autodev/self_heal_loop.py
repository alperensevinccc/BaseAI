"""
BaseAI Otonom Geliştirme, Doğrulama ve Evrim Döngüsü (Nihai, Tam ve Eksiksiz Sürüm).

Bu modül, BaseAI'nin kendi kod tabanını analiz etmesini, 
görevleri tanımlamasını, LLM ile kod üretmesini/güncellemesini,
üretilen kodu 'ruff' ile lint etmesini, Git ile güvenlik kontrolü yapmasını
ve sonuçları diske yazmasını sağlayan ana mantığı içerir. 
Bu dosyanın kendisi BaseAI'nin en yüksek kararlılık standardını temsil eder.
"""

from __future__ import annotations
import os
import time
import asyncio
import traceback
import json
import re
import subprocess
import tempfile
import shlex  # Subprocess komut parçalarını güvenli ayrıştırmak için eklendi
from typing import Dict, List, Any, Set, Optional, Tuple, Union # Union eklendi

# BaseAI Çekirdek Bileşenleri
from baseai.bridges.gpt import gpt_bridge, GPTConfig # GPT Köprüsü
from baseai.log.logger import core_logger as log    # Merkezi Logger

# --- Sabitler ve Yapılandırma ---
PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_AI_CORE_DIR = os.path.join(PROJECT_ROOT_DIR, 'baseai')

AUTODEV_BOOTSTRAP_FILES: Set[str] = {
    "baseai/autodev/evolution_reflector.py",
    "baseai/autodev/auto_refactor.py",
    "baseai/autodev/enterprise_loop.py",
    "baseai/autodev/self_heal_loop.py",
}
CONTEXT_IGNORE_DIRS: Set[str] = {
    ".venv", ".git", "__pycache__", ".idea", ".vscode", 
    "node_modules", "build", "dist", "logs", "tests",
    "autodev" 
}
CONTEXT_MAX_FILES: int = 150 # LLM'e gönderilecek maksimum dosya sayısı

# Desteklenen Görev Tipleri
SUPPORTED_TASK_TYPES: Set[str] = {
    "YENİ_MODÜL", 
    "MEVCUT_MODÜLÜ_GELİŞTİR", 
    "REFAKTÖR", 
    "TEST_YAZ",
}

# Doğrulama ve Güvenlik Ayarları
ENABLE_LINTING_CHECK: bool = True 
# Sadece Hata (E) ve Potansiyel Bug (F) kontrol edilir. W (Uyarılar) atlanır.
RUFF_COMMAND: List[str] = [
    "ruff", "check", "--output-format=json", 
    "--force-exclude", 
    "--select=E,F,W", 
    "--ignore=E501,W291"  # W291 (Trailing Whitespace) kalıcı olarak yoksayılıyor.
]
ENABLE_GIT_SAFETY_CHECK: bool = True 
ENABLE_GIT_AUTO_COMMIT: bool = False # Varsayılan olarak kapalı!

# --- Gelişmiş Yardımcı Fonksiyonlar (Subprocess ve Path Güvenliği) ---

async def _validate_and_normalize_path(relative_path: str) -> Optional[str]:
    """
    Verilen göreceli yolu doğrular, normalize eder ve mutlak yolunu döndürür.
    Proje kökü ve kritik dizin güvenlik kontrollerini içerir.
    """
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
    """
    Üretilen dosya paketini alır ve diske yazar.
    """
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

        except OSError as e:
            log.error(f"[AutoDev|Disk] ❌ İşletim sistemi hatası ({abs_path}): {e}", exc_info=False)
            failed_files.append(relative_path)
        except Exception as e:
            log.error(f"[AutoDev|Disk] ❌ Yazma hatası ({relative_path}): {e}", exc_info=True)
            failed_files.append(relative_path)
            
    return written_files, failed_files

async def _get_codebase_context(root_dir: str, ignore_dirs: Set[str], max_files: int = CONTEXT_MAX_FILES) -> str:
    """
    .py dosyalarını tarar ve göreceli yollarını içeren bir metin oluşturur.
    """
    log.debug(f"[AutoDev|Context] Kod tabanı bağlamı taranıyor (Kök: {root_dir}, Limit: {max_files})...")
    context_files: List[str] = []
    scanned_paths: Set[str] = set()

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
        if file_size_mb > 1: # 1 MB limiti
            log.warning(f"[AutoDev|Read] Dosya çok büyük ({file_size_mb:.2f}MB), içeriği okunmuyor: {relative_path}")
            return f"[HATA: Dosya içeriği çok büyük ({file_size_mb:.2f}MB)]"
             
        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log.error(f"[AutoDev|Read] Dosya okuma hatası ({relative_path}): {e}", exc_info=True)
        return None

def _parse_task_description(description: str) -> Optional[Dict[str, str]]:
    """
    LLM'den gelen görev tanımını (Tip, Hedef, Açıklama formatında) ayrıştırır.
    """
    if not description or not isinstance(description, str):
        log.warning("[AutoDev|Parse] Ayrıştırılacak görev tanımı boş veya geçersiz.")
        return None
    
    task = {"type": "UNKNOWN", "target": "N/A", "description": ""} 
    log.debug(f"[AutoDev|Parse] Ham görev tanımı alınıyor:\n{description}")

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
    """
    Verilen komut parçalarını (liste) 'exec' kullanarak asenkron olarak çalıştırır.
    """
    try:
        if not command_parts:
            log.warning("[AutoDev|Subprocess] Çalıştırmak için boş komut parçaları alındı.")
            return False, "", "Boş komut."
            
        program = command_parts[0]
        args = command_parts[1:]

        # subprocess yerine asyncio.create_subprocess_exec kullanılıyor, bu doğru
        process = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout_bytes, stderr_bytes = await process.communicate()
        
        stdout = stdout_bytes.decode('utf-8').strip()
        stderr = stderr_bytes.decode('utf-8').strip()
        
        success = process.returncode == 0
        
        if not success and not stderr and stdout:
            # Bazı araçlar (Ruff gibi) hataları stdout'a basabilir
            stderr = stdout
            
        return success, stdout, stderr
        
    except Exception as e:
        command_str = " ".join(command_parts)
        log.error(f"[AutoDev|Subprocess] Alt süreç çalıştırılamadı ('{command_str}'): {e}", exc_info=True)
        return False, "", f"Subprocess failed to run: {str(e)}"
    
# baseai/autodev/self_heal_loop.py içindeki _lint_code fonksiyonu

async def _lint_code(code_content: str) -> tuple[bool, str]:
    """
    Üretilen Python kodunu Ruff ile lint eder ve *güvenli* hataları düzeltmeye çalışır.
    """
    success, output, stderr = False, "", ""  
    temp_dir = os.path.join(PROJECT_ROOT_DIR, ".tmp")
    os.makedirs(temp_dir, exist_ok=True) 
    temp_file_name: Optional[str] = None 

    try:
        # 1. Kod içeriğini geçici dosyaya yazma
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding='utf-8', dir=temp_dir) as temp_file:
            temp_file.write(code_content)
            temp_file_name = temp_file.name
            # Dosyayı kapatmadan Ruff'un okuması için flush yap
            temp_file.flush() 
        
        # --- KRİTİK ADIM: 1. Ruff Düzeltme Denemesi (inplace) ---
        # Amaç: W291, W292 ve F541 gibi güvenli ve basit hataları düzeltmek.
        fix_command = [
            "ruff", "check", "--fix", 
            "--force-exclude", 
            "--select=E,F,W", 
            "--ignore=E501,W291",  # W291 Trailing Whitespace'i GÜVENLİ atla
            temp_file_name
        ]
        
        log.debug(f"[AutoDev|Lint|Fix] Ruff düzeltme denemesi: {' '.join(fix_command)}")
        
        # Subprocess yerine doğrudan os.system veya subprocess.run kullanmak async'i bloke eder.
        # Bu nedenle asyncio.create_subprocess_exec kullanmaya devam ediyoruz.
        fix_success, fix_output, fix_stderr = await _run_subprocess(fix_command)

        if not fix_success:
             # Eğer Ruff düzeltme komutu başarısız olursa (örn: Ruff kurulu değil)
             error_msg = fix_stderr or fix_output
             return False, f"Linting failed (Ruff fix execution error): {error_msg}"


        # 4. Düzeltilmiş Kodu Oku
        with open(temp_file_name, "r", encoding='utf-8') as f:
            corrected_code_content = f.read()

        # 5. Son Onay Kontrolü (Düzeltme sonrası kalan kritik hatalar var mı?)
        check_command = [
            "ruff", "check", "--output-format=json", 
            "--force-exclude", 
            "--select=E,F,W", 
            "--ignore=E501,W291",  # W291 Trailing Whitespace'i GÜVENLİ atla
            temp_file_name
        ]
        success, output, stderr = await _run_subprocess(check_command)

        if not success:
             error_msg = stderr or output or "Son onay Ruff komutu başarısız oldu."
             return False, f"Linting failed (Final check execution error): {error_msg}"
        
        # JSON çıktısını kontrol et
        try:
            lint_errors = json.loads(output)
            
            if not lint_errors:
                 # Tüm hatalar düzeltildi, listemiz boş. BAŞARIDIR.
                 return True, "Linting passed (Autofix applied successfully)."

            # Düzeltilemeyen hatalar kaldı (E, F seviyesinde)
            error_summaries = []
            for error in lint_errors:
                 code = error.get('code', 'N/A')
                 line = error.get('location',{}).get('row')
                 message = error.get('message', 'N/A')
                 error_summaries.append(f"{code} (L{line}): {message}")

            first_summary = error_summaries[0]
            # Kodu geri yükle (content'i düzeltilmiş kod ile değiştir)
            code_content = corrected_code_content 
            return False, f"Linting failed after autofix ({len(error_summaries)} remaining): {first_summary}"

        except json.JSONDecodeError:
            error_msg = stderr or output or "Son onay Ruff'tan bozuk JSON geldi."
            return False, f"Linting failed (Final check returned unparsable JSON): {error_msg}"

    except Exception as e:
        log.error(f"[AutoDev|Lint] Linting sırasında beklenmedik kritik hata: {e}", exc_info=True)
        return False, f"Unexpected internal linting error: {e}"

    finally:
        if temp_file_name and os.path.exists(temp_file_name):
            os.remove(temp_file_name)
            log.debug(f"[AutoDev|Lint] Geçici dosya silindi: {temp_file_name}")

async def _check_git_status(abs_filepath: str) -> Tuple[bool, str]:
    """
    Verilen dosyanın Git durumunu kontrol eder.
    """
    if not ENABLE_GIT_SAFETY_CHECK:
        log.debug("[AutoDev|Git] Git güvenlik kontrolü devre dışı.")
        return True, "Git safety check disabled."
        
    git_dir = os.path.join(PROJECT_ROOT_DIR, ".git")
    if not os.path.exists(git_dir) or not os.path.isdir(git_dir):
        log.warning("[AutoDev|Git] Proje bir Git deposu değil. Güvenlik kontrolü atlanıyor.")
        return True, "Not a Git repository."

    if not abs_filepath.startswith(PROJECT_ROOT_DIR):
        log.warning(f"[AutoDev|Git] Dosya yolu ({abs_filepath}) proje kökü dışında. Kontrol atlanıyor.")
        return True, "File outside project root." 

    command = ["git", "status", "--porcelain", abs_filepath]
    success, stdout, stderr = await _run_subprocess(command)
    
    if not success:
        log.error(f"[AutoDev|Git] 'git status' komutu çalıştırılamadı: {stderr}")
        return False, f"Failed to run git status: {stderr}" 

    if not stdout:
        log.debug(f"[AutoDev|Git] Dosya durumu temiz veya takip edilmiyor: {os.path.relpath(abs_filepath, PROJECT_ROOT_DIR)}")
        return True, "File is clean or untracked."
    else:
        log.critical(
            f"[AutoDev|Git|Güvenlik] 🚨 YAZMA ENGELLENDİ! "
            f"'{os.path.relpath(abs_filepath, PROJECT_ROOT_DIR)}' dosyasında kaydedilmemiş değişiklikler var. "
            f"Git Status: '{stdout.strip()}'"
        )
        return False, f"Uncommitted changes detected: {stdout.strip()}"


async def _git_add_commit(abs_filepaths: List[str], task_description: str) -> bool:
    """Yazılan dosyaları Git'e ekler ve commit atar."""
    if not ENABLE_GIT_AUTO_COMMIT:
        log.debug("[AutoDev|Git] Otomatik commit devre dışı.")
        return False 
        
    if not abs_filepaths:
        log.warning("[AutoDev|Git] Commit atılacak dosya bulunamadı.")
        return False

    git_dir = os.path.join(PROJECT_ROOT_DIR, ".git")
    if not os.path.exists(git_dir) or not os.path.isdir(git_dir):
        log.warning("[AutoDev|Git] Proje bir Git deposu değil. Otomatik commit atlanıyor.")
        return False

    valid_paths_to_add = [p for p in abs_filepaths if p and p.startswith(PROJECT_ROOT_DIR)]
    if not valid_paths_to_add:
        log.warning("[AutoDev|Git] Eklenecek geçerli dosya yolu bulunamadı.")
        return False

    log.info(f"[AutoDev|Git] {len(valid_paths_to_add)} dosya Git'e ekleniyor...")
    add_command = ["git", "add"] + valid_paths_to_add
    success_add, _, stderr_add = await _run_subprocess(add_command)
    if not success_add:
        log.error(f"[AutoDev|Git] 'git add' başarısız oldu: {stderr_add}")
        return False

    log.info("[AutoDev|Git] Değişiklikler commit ediliyor...")
    commit_subject = f"feat(AutoDev): Apply changes for task - {task_description[:70]}"
    if len(task_description) > 70: commit_subject += "..."
    
    file_list_str = "\n- ".join(os.path.relpath(p, PROJECT_ROOT_DIR) for p in valid_paths_to_add[:3])
    if len(valid_paths_to_add) > 3: file_list_str += "\n- ..."
    
    commit_message = f"{commit_subject}\n\nFiles changed:\n- {file_list_str}"

    commit_command = ["git", "commit", "-m", commit_message]
    success_commit, stdout_commit, stderr_commit = await _run_subprocess(commit_command)
    
    if not success_commit and "nothing to commit" in (stdout_commit + stderr_commit):
        log.warning("[AutoDev|Git] Commit atılacak yeni değişiklik bulunamadı (belki sadece formatlama?).")
        return True 
    elif not success_commit:
        log.error(f"[AutoDev|Git] 'git commit' başarısız oldu: {stderr_commit}")
        log.warning("[AutoDev|Git] Dosyalar 'git add' yapıldı ancak commit edilemedi. Manuel kontrol gerekebilir.")
        return False
        
    log.info(f"[AutoDev|Git] ✅ Değişiklikler otomatik olarak commit edildi.")
    return True

# --- ANA EVRİMSEL DÖNGÜ FONKSİYONU ---

async def run_once() -> Dict[str, Any]:
    """
    BaseAI Otonom Evrim Döngüsünün tek bir iterasyonunu çalıştırır.
    """
    start_time = time.monotonic()
    log.info("[AutoDev|Evrim] ▶️ Evrimsel Döngü İterasyonu Başlıyor (Nihai Sürüm)...")
    
    result: Dict[str, Any] = {
        "success": False, "task_type": "N/A", "task_target": "N/A",
        "task_description": "N/A", "files_generated": [], "files_lint_failed": [], 
        "files_git_blocked": [], "files_written": [], "files_failed_write": [], 
        "error": None
    }
    
    task_type: str = "N/A"
    task_description: str = "N/A"
    target_file_paths: List[str] = []
    task_target_str: str = "N/A" 

    try:
        bridge = await gpt_bridge() 
        
        # --- Adım 1: Bootstrap Kontrolü ---
        # Bu dosya dahil tüm kritik dosyaların varlığını kontrol et
        for file_rel_path in AUTODEV_BOOTSTRAP_FILES:
             abs_path = await _validate_and_normalize_path(file_rel_path)
             if not abs_path or not os.path.exists(abs_path):
                 log.critical(f"[AutoDev|Evrim|FATAL] Temel AutoDev dosyası eksik: {file_rel_path}.")
                 result["error"] = f"Missing bootstrap file: {file_rel_path}"; return result 

        # --- Adım 2: Durum Değerlendirme (Kod Bağlamı) ---
        code_context = await _get_codebase_context(BASE_AI_CORE_DIR, CONTEXT_IGNORE_DIRS)
        if "[HATA:" in code_context:
             log.error("[AutoDev|Evrim] Kod tabanı bağlamı alınamadı.")
             result["error"] = "Failed to get codebase context."; return result

        # --- Adım 3: Dinamik Görev Üretimi ---
        log.info("[AutoDev|Evrim] 🎯 Bir sonraki geliştirme görevi LLM'den isteniyor...")
        task_generation_prompt = (
            f"**Amaç:** BaseAI'nin otonom evrimi için bir sonraki adımı belirle.\n"
            f"**Mevcut Dosyalar:**\n```\n{code_context}\n```\n"
            f"**İzin Verilen Görev Tipleri:** {', '.join(SUPPORTED_TASK_TYPES)}\n\n"
            "**İstek:** Bu bilgilere göre, BaseAI için **bir sonraki en mantıklı geliştirme görevini** aşağıdaki **KESİN FORMATTA** tanımla. Sadece bu 3 satırı yaz, başka hiçbir şey ekleme:\n"
            "```text\n"
            "Görev Tipi: [Seçtiğin görev tipi]\n"
            "Hedef Dosya(lar): [İlgili dosya yolu/yolları]\n"
            "Açıklama: [Görevin 1 cümlelik özeti]\n"
            "```\n"
            "**ÖRNEK YANIT 1:**\n"
            "```text\n"
            "Görev Tipi: YENİ_MODÜL\n"
            "Hedef Dosya(lar): baseai/core/memory_manager.py\n"
            "Açıklama: Uzun süreli hafıza yönetimi için yeni bir modül oluştur.\n"
            "```\n"
            "**SENİN YANITIN (SADECE 3 SATIR):**"
        )
        try:
             next_task_raw = await bridge.generate_text(task_generation_prompt)
             log.info(f"[AutoDev|Evrim] 🎯 LLM Görev Önerisi (Ham):\n{next_task_raw}")
             task_details = _parse_task_description(next_task_raw) 
             if not task_details:
                 result["error"] = "LLM desteklenmeyen/ayrıştırılamayan bir görev tanımı üretti."
                 log.error(f"[AutoDev|Evrim] ❌ Görev ayrıştırılamadı veya desteklenmiyor. Yanıt:\n{next_task_raw}")
                 result["success"] = False; return result
                 
             task_type = task_details['type']
             task_description = task_details['description']
             task_target_str = task_details['target'] 
             target_file_paths = [re.sub(r'[`\'"]', '', p.strip()) for p in task_target_str.split(',') if p.strip()]
             
             result.update(task_details) 
             log.info(f"[AutoDev|Evrim] ✅ Görev Belirlendi ve Doğrulandı: [{task_type}] {task_target_str}") 
        except Exception as e:
             log.error(f"[AutoDev|Evrim] ❌ Görev üretimi sırasında LLM hatası: {e}", exc_info=True)
             result["error"] = f"Failed to generate/parse next task: {e}"; return result

        # --- Adım 4: Görev Yürütme İçin Talimat/Bağlam Hazırlama --- 
        execution_instruction: str = ""; execution_context: str = ""; execution_rules: List[str] = []
        
        if task_type in ["MEVCUT_MODÜLÜ_GELİŞTİR", "REFAKTÖR", "TEST_YAZ"]:
             if not target_file_paths: result["error"] = f"Görev tipi '{task_type}' için hedef dosya gerekli."; return result
             file_contents = {}; all_content_read = True
             for file_path in target_file_paths:
                 content = await _read_file_content(file_path);
                 if content is None: all_content_read = False; log.error(f"[AutoDev|Evrim] ❌ Hedef dosya okunamadı: {file_path}."); break
                 file_contents[file_path] = content
             if not all_content_read: result["error"] = f"Target file(s) not readable for modification"; return result
             
             if len(file_contents) == 1: 
                 execution_context = list(file_contents.values())[0]
             else: 
                 context_parts = [f"# --- START FILE: {fp} ---\n{fc}\n# --- END FILE: {fp} ---" for fp, fc in file_contents.items()]
                 execution_context = "\n\n".join(context_parts)

             execution_instruction = (f"**ROL:** ...\n**GÖREV TİPİ:** {task_type}\n**HEDEF DOSYA(LAR):** {task_target_str}\n\n**MEVCUT KOD:**\n```python\n{execution_context}\n```\n\n**İSTENEN DEĞİŞİKLİK:** {task_description}\n\n**ÇIKTI FORMATI:** JSON (`{{ \"{task_target_str}\": \"tam_güncel_kod\" }}`).")
             execution_rules = [ "[KESİN] Çıktı formatı: JSON...", f"[KESİN] JSON anahtar(lar)ı: `{task_target_str}`.", "[KESİN] Mevcut kodu KORU.", "[KESİN] SADECE isteneni değiştir.", "[KALİTE] Python 3.11+...", "[KALİTE] Google Docstring...", "[KALİTE] Type Hinting...", "[KALİTE] PEP8...", "[KALİTE] Hata Yönetimi...", "[KALİTE] Modülerlik...", "[KALİTE] Loglama...", "[KALİTE] BaseAI entegrasyonu...", "[KALİTE] Okunabilirlik...", "[DOĞRULAMA] Kod `ruff ...` komutundan HATASIZ geçmelidir."]

        elif task_type == "YENİ_MODÜL":
             if not target_file_paths or len(target_file_paths) != 1: result["error"] = "YENİ_MODÜL için tek hedef dosya gerekir."; return result
             target_file = target_file_paths[0] 
             execution_context = code_context 
             execution_instruction = (f"**ROL:** ...\n**GÖREV TİPİ:** {task_type}\n**OLUŞTURULACAK DOSYA:** `{target_file}`\n\n**GÖREV AÇIKLAMASI:** {task_description}\n\n**MEVCUT PROJE YAPISI:**\n```\n{execution_context}\n```\n\n**İSTEK:** ... `{target_file}` ... oluştur.\n\n**ÇIKTI FORMATI:** ...JSON (`{{ \"{target_file}\": \"tam_kod\" }}`).")
             execution_rules = [ "[KESİN] Çıktı formatı: JSON...", f"[KESİN] JSON anahtarı: `{target_file}`.", "[KESİN] Mevcut dosyaları değiştirme.", "[KALİTE] Python 3.11+...", "[KALİTE] Google Docstring...", "[KALİTE] Type Hinting...", "[KALİTE] PEP8...", "[KALİTE] Hata Yönetimi...", "[KALİTE] Modülerlik...", "[KALİTE] Loglama...", "[KALİTE] BaseAI entegrasyonu...", "[KALİTE] Okunabilirlik...", "[DOĞRULAMA] Kod `ruff ...` komutundan HATASIZ geçmelidir."]
        
        # --- Adım 5: Görev Yürütme (Kod Üretimi/Güncelleme) ---      
        log.info(f"[AutoDev|Evrim] ⚙️ Görev yürütülüyor: {task_description[:100]}...")
        file_bundle = await bridge.generate_files(execution_instruction, execution_context, rules=execution_rules)

        # --- Adım 6: Yanıtı Doğrula (Format) ---    
        if not file_bundle or not isinstance(file_bundle, dict) or "error" in file_bundle:
            error_msg = file_bundle.get("error", "Bilinmeyen köprü hatası") if isinstance(file_bundle, dict) else "Geçersiz veya boş yanıt (Yürütme)"
            log.error(f"[AutoDev|Evrim] ❌ Görev yürütme sırasında GPT'den dosya paketi alınamadı: {error_msg}")
            result["error"] = f"LLM failed during task execution: {error_msg}"; return result 
            
        result["files_generated"] = list(file_bundle.keys())
        generated_files_set = set(result["files_generated"])
        expected_files_exec = set(target_file_paths) 
        
        if not expected_files_exec.issubset(generated_files_set):
             log.error(f"[AutoDev|Evrim] ❌ GPT yürütme sonucu beklenen hedef dosyaları içermiyor! Beklenen: {expected_files_exec}, Dönen: {generated_files_set}")
             result["error"] = "LLM execution result missing target file(s)"; return result
             
        log.info(f"[AutoDev|Evrim] ✅ GPT'den {len(file_bundle)} dosyalık yürütme sonucu alındı.")

        # --- Adım 7: Linting ve Güvenlik Kontrolleri ---     
        files_to_write: Dict[str, str] = {}; abs_paths_to_commit: List[str] = [] 
        lint_failed_details: Dict[str, str] = {}
        
        for relative_path, content in file_bundle.items():
            if relative_path not in expected_files_exec: 
                 log.warning(f"[AutoDev|Evrim] ⚠️ LLM beklenmeyen dosya döndürdü, yoksayılıyor: {relative_path}"); continue
                 
            # Linting kontrolü
            lint_passed, lint_message = await _lint_code(content) 
            if not lint_passed:
                log.error(f"[AutoDev|Evrim] ❌ Üretilen kod LINT KONTROLÜNÜ GEÇEMEDİ: {relative_path}. Mesaj: {lint_message}")
                result["files_lint_failed"].append(relative_path); lint_failed_details[relative_path] = lint_message; continue 

            # Yol ve Güvenlik kontrolü
            abs_path = await _validate_and_normalize_path(relative_path)
            if not abs_path: 
                log.error(f"[AutoDev|Evrim] ❌ Lint geçmiş dosyanın yolu geçersiz: {relative_path}. Yazılmayacak.")
                result["files_failed_write"].append(relative_path); continue 
            
            # Git Kontrolü
            is_safe, git_status_msg = await _check_git_status(abs_path)
            if not is_safe:
                log.critical(f"[AutoDev|Evrim] 🚨 YAZMA GÜVENLİK ENGELİ: {relative_path}. Sebep: {git_status_msg}")
                result["files_git_blocked"].append(relative_path); continue 
            
            files_to_write[relative_path] = content
            abs_paths_to_commit.append(abs_path) 

        # --- Adım 8: Dosyaları Diske Yaz ---    
        if not files_to_write:
             error_parts = []
             if result["files_lint_failed"]: error_parts.append(f"{len(result['files_lint_failed'])} file(s) failed lint check")
             if result["files_git_blocked"]: error_parts.append(f"{len(result['files_git_blocked'])} file(s) blocked by Git status")
             error_detail = "; ".join(error_parts) if error_parts else "No valid files generated or passed checks."
             log.warning(f"[AutoDev|Evrim] ⚠️ Yazılacak geçerli dosya yok ({error_detail}). Görev tamamlanamadı.")
             result["error"] = error_detail
             result["success"] = False
        else:
            written_files, failed_write = await _write_files_to_disk(files_to_write)
            result["files_written"] = written_files
            result["files_failed_write"].extend(failed_write) 

            # Sonuç Durumunu Belirle
            all_targets_written = expected_files_exec.issubset(set(written_files)) 
            no_failures = not result["files_lint_failed"] and not result["files_git_blocked"] and not result["files_failed_write"]
            
            if all_targets_written and no_failures:
                result["success"] = True
                log.info("[AutoDev|Evrim] ✅ Görev başarıyla tamamlandı ve tüm hedefler yazıldı.")
                # --- Adım 9: Otomatik Commit ---
                if abs_paths_to_commit: await _git_add_commit(abs_paths_to_commit, result['task_description'])
            else: # Kısmi başarı veya tam başarısızlık
                result["success"] = False
                errors = []
                if result["files_lint_failed"]: errors.append(f"{len(result['files_lint_failed'])} lint errors")
                if result["files_git_blocked"]: errors.append(f"{len(result['files_git_blocked'])} Git blocks")
                if result["files_failed_write"]: errors.append(f"{len(result['files_failed_write'])} write errors")
                if not all_targets_written: errors.append("Not all targets written")
                result["error"] = "; ".join(errors) if errors else "Unknown validation/write failure"
                log.error(f"[AutoDev|Evrim] ❌ Görev tamamlanamadı veya kısmen tamamlandı. Hatalar: {result['error']}")
                if lint_failed_details: # Lint hatalarını logla
                     log.error("[AutoDev|Evrim] Lint Hata Detayları:")
                     for fname, msg in lint_failed_details.items():
                          log.error(f"  File: {fname} -> {msg}")

    except Exception as e:
        detailed_error = traceback.format_exc()
        log.critical(f"[AutoDev|Evrim] 💥 Döngüde beklenmeyen kritik hata: {e}\n{detailed_error}")
        result["error"] = f"CRITICAL_EVOLUTION_FAILURE: {e}"
        result["success"] = False

    finally:
        # Detaylı Sonuç Loglama (result sözlüğünü kullan)
        end_time = time.monotonic(); duration = end_time - start_time
        status = "BAŞARILI" if result.get("success", False) else "BAŞARISIZ"
        log.info(f"--- [AutoDev|Evrim] İTERASYON SONUCU ---")
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