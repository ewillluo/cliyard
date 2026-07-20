"""SPL syntax validator using ANTLR4 parser.

Wraps the generated ANTLR parser to validate SPL query strings
and provide human-readable error messages in Chinese.

Install antlr4-python3-runtime to enable validation:
  pip install antlr4-python3-runtime
"""

from __future__ import annotations

import re
from typing import Any

try:
    from antlr4 import CommonTokenStream, InputStream
    from antlr4.error.ErrorStrategy import DefaultErrorStrategy
    from antlr4.error.Errors import (
        InputMismatchException,
        NoViableAltException,
        RecognitionException,
    )

    HAVE_ANTLR = True
except ImportError:
    HAVE_ANTLR = False

from .SplLexer import SplLexer
from .SplParser import SplParser

if HAVE_ANTLR:

    class SplError(ValueError):
        """Structured SPL error with position and token context."""

        def __init__(self, message: str, line: int, column: int,
                     token_text: str | None = None,
                     expected: str = ""):
            super().__init__(message)
            self.spl_line = line
            self.spl_column = column
            self.token_text = token_text
            self.expected = expected

    class SplErrorStrategy(DefaultErrorStrategy):
        """Custom error strategy producing Chinese error messages."""

        def __init__(self, spl_input: str = "") -> None:
            super().__init__()
            self._spl_input = spl_input

        def _fmt(self, token: Any, msg: str) -> str:
            line = getattr(token, 'line', 1)
            col = getattr(token, 'column', 0)
            token_type = getattr(token, 'type', None)

            # Build visual indicator: show surrounding chars with ^ at error
            indicator = ""
            if self._spl_input:
                lines = self._spl_input.split("\n")
                if 0 < line <= len(lines):
                    err_line = lines[line - 1]
                    start = max(0, col - 15)
                    end = min(len(err_line), col + 15)
                    snippet = err_line[start:end]
                    prefix = "..." if start > 0 else ""
                    suffix = "..." if end < len(err_line) else ""
                    arrow_col = (col - start) + len(prefix)
                    indicator = f"\n  {prefix}{snippet}{suffix}\n  {' ' * arrow_col}^"

            if token_type == SplParser.EOF or token_type == -1:
                return (
                    f"在第【{line}】行，下标为【{col}】的字符处，"
                    f"语句不完整，缺少必要的参数或关键字"
                    f"{indicator}"
                )
            display = self._token_display(getattr(token, 'text', None))
            return (
                f"在第【{line}】行，"
                f"下标为【{col}】的字符处，"
                f"符号【{display}】{msg}"
                f"{indicator}"
            )

        def recover(self, recognizer: Any, e: RecognitionException) -> None:
            token = getattr(e, 'offendingToken', None)
            if token is None:
                raise SplError("没有识别出有效的SPL语句", 1, 0)
            if isinstance(e, InputMismatchException):
                expected = e.getExpectedTokens().toString(
                    recognizer.literalNames, recognizer.symbolicNames
                )
                raise SplError(
                    self._fmt(token, f"非预期；建议【{expected}】"),
                    token.line, token.column,
                    token_text=token.text,
                    expected=expected,
                )
            raise SplError(
                self._fmt(token, "非预期"),
                token.line, token.column,
                token_text=token.text,
            )

        def recoverInline(self, recognizer: Any) -> None:
            token = recognizer.getCurrentToken()
            expected = recognizer.getExpectedTokens().toString(
                recognizer.literalNames, recognizer.symbolicNames
            )
            raise SplError(
                self._fmt(token, f"非预期；建议【{expected}】"),
                token.line, token.column,
                token_text=token.text,
                expected=expected,
            )

        def sync(self, recognizer: Any) -> None:
            pass

        @staticmethod
        def _token_display(text: str | None) -> str:
            return repr(text) if text is not None else "<EOF>"


def validate_spl(spl: str) -> list[dict]:
    """Validate an SPL query string using the ANTLR4 parser.

    Args:
        spl: The SPL query string to validate.

    Returns:
        List of error dicts, each with ``line``, ``column``, and ``message`` keys.
        Empty list means the query is syntactically valid.
    """
    if not HAVE_ANTLR:
        return [{
            "line": 1,
            "column": 0,
            "message": (
                "SPL 语法验证需要 antlr4-python3-runtime 库。"
                "请执行: pip install antlr4-python3-runtime"
            ),
        }]

    if not spl or not spl.strip():
        return [{"line": 1, "column": 0, "message": "SPL 查询不能为空"}]

    errors: list[dict] = []

    # Pre-check: unknown command names in pipe segments
    for m in re.finditer(r'\|\s*(\w+)', spl):
        cmd = m.group(1)
        from .humanizer import _suggest_command
        suggestion = _suggest_command(cmd)
        if suggestion and suggestion != cmd.lower():
            errors.append({
                "line": 1,
                "column": m.start(1),
                "message": f"不支持的算子 `{cmd}`，是否想用 `{suggestion}`？",
                "human_message": f"不支持的算子 `{cmd}`，是否想用 `{suggestion}`？",
                "original_message": "",
                "token_text": cmd,
                "expected": "",
            })

    # If pre-check found errors, skip ANTLR (to avoid secondary noise)
    if errors:
        return errors

    input_stream = InputStream(spl)
    lexer = SplLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = SplParser(token_stream)

    # Remove default error listeners to suppress ANTLR stderr output
    parser.removeErrorListeners()
    parser._errHandler = SplErrorStrategy(spl_input=spl)

    try:
        parser.main()
    except SplError as e:
        from .humanizer import humanize
        human_msg, orig_msg = humanize(spl, e.spl_line, e.spl_column,
                                       str(e), token_text=e.token_text,
                                       expected=e.expected)
        msg = human_msg if human_msg else orig_msg
        errors.append({
            "line": e.spl_line,
            "column": e.spl_column,
            "message": msg,
            "human_message": human_msg,
            "original_message": orig_msg,
            "token_text": e.token_text,
            "expected": e.expected,
        })
    except ValueError as e:
        errors.append({"line": 1, "column": 0, "message": str(e)})
    except Exception as e:
        errors.append({"line": 1, "column": 0, "message": f"SPL 语法错误: {str(e)}"})

    return errors


def check_spl(spl: str) -> str | None:
    """Quick validation: returns error message or None if valid."""
    errors = validate_spl(spl)
    if errors:
        return errors[0]["message"]
    return None
