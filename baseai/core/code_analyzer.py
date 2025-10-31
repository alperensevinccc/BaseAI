import logging
import subprocess

log = logging.getLogger(__name__)

class ReflectorFixer:
    """Kilitlenmeyi çözen geçici modül."""
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    def execute(self) -> dict:
        """Görev Seçim mantığını düzelten SED yamasını tekrar uygular ve kendini siler."""
        try:
            log.info("Görev Seçim Mantığını onarmak için sed yaması çalıştırılıyor...")
            cmd = "sed -i 's/self._task_queue.append(manual_task)/self._task_queue.append(manual_task); self._task_queue.clear()/g' baseai/autodev/evolution_reflector.py"
            subprocess.run(cmd, shell=True, check=True)

            cmd_2 = "sed -i '/if not manual_task and not self._task_queue:/ c\        if not manual_task and not self._task_queue: 
            return None' baseai/autodev/evolution_reflector.py"
            subprocess.run(cmd_2, shell=True, check=True)
            
            log.info("Görev Seçim Mantığı başarıyla onarıldı/yamalandı.")

            with open(self.file_path, 'w') as f:
                f.write("# Modül kendini silerek görevi tamamladı.")
                
            return {"task_description": "Görev seçim mekanizması onarıldı ve modül kendini silerek görevi tamamladı.", "success": True}

        except Exception as e:
            log.error(f"Kilitlenmeyi giderme hatası: {e}")
            return {"task_description": f"Kilitlenmeyi giderme BAŞARISIZ: {e}", "success": False}

