import ast
class CodeAnalyzer:
    def __init__(self, code_string: str):
        self.ast_tree = ast.parse(code_string)

    def get_functions(self) -> list[ast.FunctionDef]:
        return [node for node in self.ast_tree.body if isinstance(node, ast.FunctionDef)]

    def get_classes(self) -> list[ast.ClassDef]:
        return [node for node in self.ast_tree.body if isinstance(node, ast.ClassDef)]

    def get_imports(self) -> list[str]:
        imports = set()
        for node in self.ast_tree.body:
            if isinstance(node, ast.Import):
                imports.update({alias.name for alias in node.names})
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        return list(imports)
