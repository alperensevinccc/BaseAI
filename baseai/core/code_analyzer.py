import ast

class CodeAnalyzer:
    def __init__(self, code_string):
        self.code_string = code_string

    def parse_code(self):
        tree = ast.parse(self.code_string)
        return tree
