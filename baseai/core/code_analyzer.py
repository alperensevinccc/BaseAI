
import ast
import logging

log = logging.getLogger(__name__)

class CodeAnalyzer:
    """
    Kod tabanını (AST kullanarak) analiz eden temel BaseAI modülü.
    Bu dosya, LLM kilitlenmesini aşmak için manuel olarak enjekte edilmiştir.
    """
    def __init__(self, code_string: str):
        self.code_string = code_string
        try:
            self.ast_tree = ast.parse(self.code_string)
        except SyntaxError as e:
            log.error(f"AST Ayrıştırma Hatası: {e}")
            self.ast_tree = None

    def get_functions(self) -> list:
        if not self.ast_tree:
            return []
        return [node.name for node in ast.walk(self.ast_tree) if isinstance(node, ast.FunctionDef)]
