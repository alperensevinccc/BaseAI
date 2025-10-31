import ast

class CodeAnalyzer:
    def __init__(self, code: str):
        self.code = code

    def parse_code(self) -> dict:
        tree = ast.parse(self.code)
        functions = {
            node.id if isinstance(node, ast.FunctionDef) else None for node in ast.walk(tree)
        }
        classes = {
            node.name if isinstance(node, ast.ClassDef) else None for node in ast.walk(tree)
        }
        imports = {
            node.names[0].name for node in tree.body
            if isinstance(node, ast.Import)
        }
        return {
            'functions': functions,
            'classes': classes,
            'imports': imports
        }
