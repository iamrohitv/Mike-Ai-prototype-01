import ast
import operator
import re

from policies.engine import Level
from tools.base import Tool


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_CHARS = re.compile(r"^[\d\s\+\-\*\/\%\(\)\.\^]+$")

_PREFIXES = [
    "calculate ",
    "compute ",
    "solve ",
    "what is ",
    "what's ",
    "how much is ",
]

_MAX_LENGTH = 200
_MAX_POWER = 10 ** 6


class CalculatorTool(Tool):
    name = "calculator"
    description = "evaluate arithmetic expressions like 12 * 8 + 4"
    level = Level.GREEN

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        return self._extract(request) is not None

    def run(self, request):
        expression = self._extract(request)
        if expression is None:
            return "Give me something to calculate, like 12 * (8 + 4) / 3."
        try:
            tree = ast.parse(self._normalize(expression), mode="eval")
            result = self._evaluate(tree.body)
        except ZeroDivisionError:
            return "Division by zero is undefined."
        except (ValueError, TypeError, OverflowError, SyntaxError):
            return f"I couldn't evaluate '{expression}'."
        return f"{expression.strip()} = {self._format(result)}"

    def verify(self, result):
        if "=" in result or "undefined" in result:
            return "verified: calculation complete"
        return "failed"

    def _extract(self, request):
        lowered = request.lower().strip()
        candidate = None
        for prefix in _PREFIXES:
            if lowered.startswith(prefix):
                candidate = request[len(prefix):].strip()
                break
        if candidate is None:
            if any(word in lowered for word in ["calculate", "compute"]):
                for prefix in _PREFIXES:
                    idx = lowered.find(prefix)
                    if idx != -1:
                        candidate = request[idx + len(prefix):].strip()
                        break
            else:
                candidate = request.strip()
        if not candidate or len(candidate) > _MAX_LENGTH:
            return None
        candidate = candidate.rstrip("?.!:,;")
        if not _ALLOWED_CHARS.match(candidate):
            return None
        if not re.search(r"\d", candidate):
            return None
        if not re.search(r"[\+\-\*\/\%\^]", candidate):
            return None
        return candidate

    def _normalize(self, expression):
        return expression.replace("^", "**").replace("x", "*")

    def _evaluate(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            value = node.value
            if isinstance(value, int) and abs(value) > _MAX_POWER:
                raise ValueError("number too large")
            return value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            if isinstance(node.op, ast.Pow):
                if abs(left) > 1000 or abs(right) > 1000:
                    raise ValueError("exponent too large")
            return _OPERATORS[type(node.op)](left, right)
        raise ValueError("unsupported expression")

    def _format(self, value):
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return f"{value:.6f}".rstrip("0").rstrip(".")
        return str(value)
