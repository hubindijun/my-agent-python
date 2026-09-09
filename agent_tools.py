import ast
import operator as op

from langchain_core.tools import BaseTool
from langchain_core.tools import tool

_ALLOWED_BIN_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
}

_ALLOWED_UNARY_OPS = {
    ast.UAdd: op.pos,
    ast.USub: op.neg,
}


def _safe_eval(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("只允许数字常量")
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARY_OPS:
            raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
        return _ALLOWED_UNARY_OPS[op_type](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_BIN_OPS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if op_type is ast.Div and right == 0:
            raise ZeroDivisionError("除数不能为零")
        return _ALLOWED_BIN_OPS[op_type](left, right)
    raise ValueError(f"表达式中包含不支持的内容: {type(node).__name__}")


def make_calculator_tool() -> BaseTool:
    """计算器工具：安全计算加减乘除数学表达式，支持括号和嵌套。

    计算失败时抛出 ValueError / ZeroDivisionError，LangChain ToolNode 会自动
    捕获并转为 ToolMessage（tool_call_id 对应，内容为错误信息）。
    """

    @tool
    def calculator(expression: str) -> float | int:
        """计算数学表达式的值，支持加、减、乘、除和括号。当用户需要计算数学问题时使用此工具。

        Args:
            expression: 要计算的数学表达式，例如 "2 + 3"、"10 * 5"、"(15 + 25) * 4 - 10 / 2"

        Returns:
            计算结果（整数或浮点数）。

        Raises:
            ValueError: 表达式语法错误或包含不支持的内容
            ZeroDivisionError: 除数为零
        """
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)
        if isinstance(result, float) and result.is_integer():
            return int(result)
        return result

    return calculator
