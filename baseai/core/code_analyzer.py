
import ast

class CodeAnalyzer:
    def __init__(self, code: str):
        self.code = code

    def analyze(self) -> dict:
        try:
            tree = ast.parse(self.code)
            functions = [node.id for node in tree.body if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
            imports = [node.names[0].name for node in tree.body if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom)]

            return {
                'functions': functions,
                'classes': classes,
                'imports': imports,
            }
        except Exception as e:
            print(f'Error analyzing code: {e}')
            return {}
