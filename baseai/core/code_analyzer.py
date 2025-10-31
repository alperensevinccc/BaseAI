import ast

class CodeAnalyzer:
    def __init__(self, code_string: str):
        self.code_string = code_string

    def analyze(self) -> dict:
        tree = ast.parse(self.code_string)
        functions = [node.id for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]

        return {
            'functions': functions,
            'classes': classes,
            'imports': imports
        }
