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

    class SplErrorStrategy(DefaultErrorStrategy):
        """Custom error strategy producing Chinese error messages."""

        def recover(self, recognizer: Any, e: RecognitionException) -> None:
            token = getattr(e, 'offendingToken', None)
            if token is None:
                msg = "没有识别出有效的SPL语句"
            elif isinstance(e, InputMismatchException):
                expected = e.getExpectedTokens().toString(
                    recognizer.literalNames, recognizer.symbolicNames
                )
                msg = (
                    f"在第【{token.line}】行，"
                    f"下标为【{token.column}】的字符处，"
                    f"符号【{self._token_display(token.text)}】非预期；"
                    f"建议【{expected}】"
                )
            elif isinstance(e, NoViableAltException):
                if getattr(token, 'type', None) == SplParser.EOF:
                    msg = "非预期的结束符"
                else:
                    msg = (
                        f"在第【{token.line}】行，"
                        f"下标为【{token.column}】的字符处，"
                        f"符号【{self._token_display(token.text)}】非预期"
                    )
            else:
                msg = (
                    f"在第【{token.line}】行，"
                    f"下标为【{token.column}】的字符处，"
                    f"符号【{self._token_display(token.text)}】非预期"
                )
            raise ValueError(msg)

        def recoverInline(self, recognizer: Any) -> None:
            token = recognizer.getCurrentToken()
            expected = recognizer.getExpectedTokens().toString(
                recognizer.literalNames, recognizer.symbolicNames
            )
            msg = (
                f"在第【{token.line}】行，"
                f"下标为【{token.column}】的字符处，"
                f"符号【{self._token_display(token.text)}】非预期；"
                f"建议【{expected}】"
            )
            raise ValueError(msg)

        def sync(self, recognizer: Any) -> None:
            pass

        @staticmethod
        def _token_display(text: str | None) -> str:
            if text is None:
                return "<EOF>"
            return repr(text)


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

    input_stream = InputStream(spl)
    lexer = SplLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = SplParser(token_stream)

    parser._errHandler = SplErrorStrategy()

    try:
        parser.main()
    except ValueError as e:
        msg = str(e)
        line, column = 1, 0
        m = re.search(r"在第【(\d+)】行，下标为【(\d+)】", msg)
        if m:
            line = int(m.group(1))
            column = int(m.group(2))
        errors.append({"line": line, "column": column, "message": msg})
    except Exception as e:
        errors.append({"line": 1, "column": 0, "message": f"SPL 语法错误: {e}"})

    return errors


def check_spl(spl: str) -> str | None:
    """Quick validation: returns error message or None if valid."""
    errors = validate_spl(spl)
    if errors:
        return errors[0]["message"]
    return None
