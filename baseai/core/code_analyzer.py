import ast
from typing import List, Dict

class CodeAnalyzer:
    def __init__(self, code_string: str):
        self.code_tree = ast.parse(code_string)

    def get_functions(self) -> List[str]:
        return [node.id for node in ast.walk(self.code_tree) if isinstance(node, ast.FunctionDef)]

    def get_classes(self) -> List[str]:
        return [node.name for node in ast.walk(self.code_tree) if isinstance(node, ast.ClassDef)]

    def get_imports(self) -> Dict[str, str]:
        imports = {}
        for node in ast.walk(self.code_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.name] = alias.asname or alias.name
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module
                imports[module_name] = node.alias.asname or node.module
        return imports
