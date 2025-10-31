
import ast
import os
import logging

log = logging.getLogger(__name__)

class CodeAnalyzer:
    """Kod tabanını (AST kullanarak) analiz eden temel BaseAI modülü."""
    def __init__(self, file_path: str):
        self.file_path = file_path

    def analyze(self) -> dict:
        """Basit fonksiyon ve sınıf adlarını çıkarır."""
        if not os.path.exists(self.file_path):
            log.warning(f"Dosya bulunamadı: {self.file_path}")
            return {}

        with open(self.file_path, r, encoding=utf-8) as f:
            code = f.read()
        
        tree = ast.parse(code)
        
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

        return {
            "functions": functions,
            "classes": classes
        }

if __name__ == __main__:
    # Basit test
    print("CodeAnalyzer temel sınıfı başarıyla enjekte edildi.")

