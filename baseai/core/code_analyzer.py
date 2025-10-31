import ast
class CodeAnalyzer:
    def __init__(self, code_str):
        self.tree = ast.parse(code_str)
    def get_functions(self):
        return [node.id for node in self.tree.body if isinstance(node, ast.FunctionDef)]
    def get_classes(self):
        return [node.name for node in self.tree.body if isinstance(node, ast.ClassDef)]
    def get_imports(self):
        imports = set()
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                imports.update({alias.name for alias in node.names})
        return list(imports)
