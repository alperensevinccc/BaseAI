import ast

class CodeAnalyzer:
    def __init__(self, code_string):
        self.ast = ast.parse(code_string)

    def get_functions(self):
        return [node.id for node in ast.walk(self.ast) if isinstance(node, ast.FunctionDef)]

    def get_classes(self):
        return [node.name for node in ast.walk(self.ast) if isinstance(node, ast.ClassDef)]

    def get_imports(self):
        return {imp[0].name: imp[1][0].asname() for imp in ast.iter_modules(self.ast)}
