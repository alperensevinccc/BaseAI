import ast

class CodeAnalyzer:
    def __init__(self, code: str):
        self.ast_tree = ast.parse(code)

    def get_functions(self) -> list:
        return [node.id for node in ast.walk(self.ast_tree) if isinstance(node, ast.FunctionDef)]

    def get_classes(self) -> list:
        return [node.name for node in ast.walk(self.ast_tree) if isinstance(node, ast.ClassDef)]

    def get_imports(self) -> list:
        imports = set()
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.Import):
                imports.update({imp[0].name for imp in node.names})
            elif isinstance(node, ast.From):
                imports.add(node.module.name)

        return list(imports)
