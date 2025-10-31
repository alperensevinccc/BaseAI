import ast
class CodeAnalyzer:
    def __init__(self, code):
        self.code = code
    def parse(self):
        tree = ast.parse(self.code)
        return tree
