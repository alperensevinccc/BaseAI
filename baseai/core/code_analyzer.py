
import ast

class CodeAnalyzer:
    def __init__(self, code: str):
        self.code = code

    def analyze(self) -> dict:
        tree = ast.parse(self.code)
        modules = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Module):
                module_name = node.name
                if module_name not in modules:
                    modules[module_name] = []
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.ClassDef)):
                        modules[module_name].append(str(child.name))
        return modules
