import ast

class CodeAnalyzer:
    def __init__(self, code_str: str):
        self.code_str = code_str

    def parse_code(self) -> dict:
        try:
            tree = ast.parse(self.code_str)
            return {
                'functions': [node.id for node in tree.body if isinstance(node, ast.FunctionDef)],
                'classes': [node.name for node in tree.body if isinstance(node, ast.ClassDef)],
                'imports': [import_node.names[0].name for import_node in tree.body if isinstance(import_node, ast.Import)]
            }
        except Exception as e:
            return {'error': str(e)}
