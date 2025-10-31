import ast
from typing import List, Tuple, Dict

class CodeAnalyzer:
    def __init__(self, code_string: str):
        self.code = ast.parse(code_string)

    def get_functions(self) -> List[Tuple[str, str]]:
        functions = []
        for node in ast.walk(self.code):
            if isinstance(node, ast.FunctionDef):
                functions.append((node.name, node.args.argnames))
        return functions

    def get_classes(self) -> List[Tuple[str, Dict[str, Tuple[str]]]]:
        classes = []
        for node in ast.walk(self.code):
            if isinstance(node, ast.ClassDef):
                class_dict = {}
                for body_node in node.body:
                    if isinstance(body_node, ast.FunctionDef):
                        class_dict[body_node.name] = tuple([arg.arg for arg in body_node.args.args])
                classes.append((node.name, class_dict))
        return classes

    def get_imports(self) -> List[Tuple[str, str]]:
        imports = []
        for node in ast.walk(self.code):
            if isinstance(node, ast.Import):
                for alias_node in node.names:
                    imports.append((alias_node.name, alias_node.asname))
        return imports
