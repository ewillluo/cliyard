"""SPL 错误消息解释器 — 将 ANTLR 原始错误翻译为人话。

ANTLR 产生的错误信息对普通用户不友好（如「符号【'='】非预期；建议【<EOF>>」），
本模块通过模式匹配识别常见错误场景，产出可读的中文解释。

模式优先级：
  1. 引号包裹的字段名        "field"=value
  2. 算子拼写错误            eva a=1 → eval
  3. 连续管道符              | |
  4. 尾部逗号                fields _raw,<EOF>
  5. eval 聚合函数           eval count()
  6. 聚合函数缺括号          stats count as c
  7. search2 缺少 repo       search2 ... (no repo=)
  8. mstats 多了 repo        mstats repo=...
  9. stats by 后缺字段       stats count() by<EOF>
  10. 未匹配                → 保留原始 ANTLR 消息
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 已知算子白名单（用于拼写检查）
# ---------------------------------------------------------------------------
_KNOWN_COMMANDS = {
    "eval", "where", "stats", "timechart", "movingavg", "eventstats",
    "streamstats", "sort", "fields", "dedup", "rename", "replace", "rex",
    "bin", "lookup", "inputlookup", "outputlookup", "join", "append",
    "convert", "transaction", "mvexpand", "mvcombine", "iplocation",
    "export", "chart", "over", "addtotals", "explain", "noop", "repartition",
    "analyze", "fit", "apply", "score", "split", "top", "rare", "accum",
    "addinfo", "makemv", "makeresults", "jsonpath", "xmlpath", "startswith",
    "endswith", "like", "unnest", "topseries", "mcollect", "compare",
    "trend", "alert", "logcluster", "anomalies", "outliers", "forecast",
    "rate", "search", "search2", "mstats", "msearch", "show", "from",
    "dbquery", "ml", "model", "summary", "against", "inputlookup",
    "outputlookup", "limit", "head", "tail", "regex", "rex", "grok",
    "table", "format", "eval", "search", "search2",
}

# 常见拼写错误 → 正确写法
_COMMON_TYPOS = {
    "serch": "search", "serach": "search", "searc": "search",
    "serch2": "search2",
    "stat": "stats", "statss": "stats", "stas": "stats",
    "evl": "eval", "eva": "eval", "evals": "eval",
    "wher": "where", "whre": "where",
    "fileds": "fields", "feilds": "fields", "fiels": "fields",
    "srot": "sort", "sor": "sort", "sorr": "sort",
    "limt": "limit", "lmit": "limit", "limti": "limit",
    "renmae": "rename", "renam": "rename",
    "dedup": "dedup", "dedupe": "dedup",
    "seach": "search",
}

# 属于合法 SPL 关键字，不做拼写建议
_SKIP_WORDS = {"as", "by", "in", "or", "and", "not", "over", "with",
               "on", "off", "true", "false", "null", "desc", "asc"}


def _edit_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(dp[j], dp[j - 1], prev)
            prev = temp
    return dp[n]


def _suggest_command(word: str) -> str | None:
    """对可能的算子名称做拼写建议。"""
    if word.lower() in _SKIP_WORDS:
        return None
    if word in _COMMON_TYPOS:
        return _COMMON_TYPOS[word]
    word_lower = word.lower()
    if word_lower in _SKIP_WORDS:
        return None
    if word_lower in _COMMON_TYPOS:
        return _COMMON_TYPOS[word_lower]
    # 编辑距离检查
    best, best_dist = None, 3
    for known in _KNOWN_COMMANDS:
        dist = _edit_distance(word_lower, known)
        if dist < best_dist:
            best, best_dist = known, dist
    if best:
        return best
    return None


def _first_word_after_pipe(spl: str, col: int) -> str | None:
    """获取错误位置所在管道段的首个词（可能是算子名）。"""
    before_pipe = spl[:col].rsplit("|", 1)[-1] if "|" in spl[:col] else spl[:col]
    after = spl[col:]
    # 截取从错误位置到管道/结尾之间的第一个词
    segment = (before_pipe + after).strip()
    # 取第一个词
    m = re.match(r'(\w+)', segment)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# 模式匹配函数
# ---------------------------------------------------------------------------


def _quoted_field_name(spl: str, col: int,
                       token_text: str | None, expected: str) -> str | None:
    """检测双引号包裹的字段名：search ... "field"=value"""
    if token_text == "=":
        before = spl[max(0, col - 25):col]
        m = re.search(r'(")([^"]+)("\s*=?\s*)$', before)
        if m:
            field = m.group(2)
            return (f"字段名 `{field}` 不需要用双引号包裹，"
                    f"去掉 `{field}` 两侧的引号即可")


def _typo_command(spl: str, col: int,
                  token_text: str | None, expected: str) -> str | None:
    """检测算子拼写错误：eva a=1 → 建议 eval"""
    if token_text and token_text.isalpha() and len(token_text) >= 2:
        suggestion = _suggest_command(token_text)
        if suggestion and suggestion != token_text.lower():
            return (f"不支持的算子 `{token_text}`，"
                    f"是否想用 `{suggestion}`？")
        # 检查错误位置之前的第一个词（可能是管道后的算子）
        first_word = _first_word_after_pipe(spl, col)
        if first_word and first_word != token_text:
            suggestion2 = _suggest_command(first_word)
            if suggestion2 and suggestion2 != first_word.lower():
                return (f"不支持的算子 `{first_word}`，"
                        f"是否想用 `{suggestion2}`？")
    return None


def _double_pipe(spl: str, col: int,
                 token_text: str | None, expected: str) -> str | None:
    """检测连续管道符：| |"""
    if token_text == "|":
        before = spl[max(0, col - 3):col].strip()
        if before == "|" or before.endswith("|"):
            return "不能连续使用管道符 `|`，每个 `|` 后面应该跟一个算子"


def _trailing_comma(spl: str, col: int,
                    token_text: str | None, expected: str) -> str | None:
    """检测尾部逗号：fields _raw,<EOF>"""
    if "EOF" in expected or not expected:
        before = spl[max(0, col - 10):col]
        if "," in before:
            return "逗号后面缺少字段名，请补全或去掉多余的逗号"


def _eval_aggregation(spl: str, col: int,
                      token_text: str | None, expected: str) -> str | None:
    """检测 eval 中使用聚合函数：eval count() / eval sum(x)"""
    before_pipe = spl[:col].rsplit("|", 1)[-1] if "|" in spl[:col] else spl[:col]
    if "eval" in before_pipe:
        after = spl[col:col + 30]
        agg_funcs = ["count", "sum", "avg", "min", "max", "distinct_count",
                     "values", "list", "percentile", "earliest", "latest",
                     "stdev", "var"]
        for func in agg_funcs:
            ctx = before_pipe.rsplit("eval", 1)[-1] + " " + after
            if re.search(rf'\b{func}\s*\(', ctx):
                return (f"`eval` 不支持聚合函数 `{func}()`。"
                        f"统计类操作请使用 `stats {func}() ...` 或 "
                        f"`eventstats {func}() ...`")


def _agg_missing_paren(spl: str, col: int,
                       token_text: str | None, expected: str) -> str | None:
    """检测聚合函数缺括号：stats count as c → 应为 stats count() as c"""
    if token_text and token_text.lower() in ("as",) and "(" in expected:
        before = spl[max(0, col - 25):col + 10]
        agg_funcs = ["count", "sum", "avg", "min", "max", "distinct_count",
                     "values", "list", "percentile"]
        for func in agg_funcs:
            if re.search(rf'\b{func}\s+as\b', before, re.IGNORECASE):
                return (f"聚合函数 `{func}` 缺少括号，应该写为 `{func}() as`。"
                        f"统计函数必须带括号：`stats {func}(field) as 别名`")
    return None


def _missing_repo(spl: str, col: int,
                  token_text: str | None, expected: str) -> str | None:
    """检测 search2 缺少 repo 参数：search2 start="-1h" "error"

    当 search2 打头且后续没有 repo= 时报错。
    """
    if token_text is None and spl.strip().startswith("search2"):
        if "repo=" not in spl and "repo =" not in spl:
            return "`search2` 需要指定仓库，请添加 `repo=仓库名` 参数，如 `search2 repo=\"logs\"`"


def _mstats_has_repo(spl: str, col: int,
                     token_text: str | None, expected: str) -> str | None:
    """检测 mstats 误用了 repo 参数：mstats repo=..."""
    if spl.strip().startswith("mstats") and "repo=" in spl:
        return "`mstats` 不支持 `repo` 参数，指标查询直接写 `mstats start=\"-1h\" span=\"1m\" avg(...)`"


# ---------------------------------------------------------------------------
# 模式注册表（按优先级排序）
# ---------------------------------------------------------------------------
_PATTERNS = [
    ("quoted_field_name", _quoted_field_name),
    ("typo_command", _typo_command),
    ("double_pipe", _double_pipe),
    ("trailing_comma", _trailing_comma),
    ("eval_aggregation", _eval_aggregation),
    ("agg_missing_paren", _agg_missing_paren),
    ("missing_repo", _missing_repo),
    ("mstats_has_repo", _mstats_has_repo),
]


def humanize(spl: str, line: int, col: int, err_msg: str,
             token_text: str | None = None,
             expected: str = "") -> tuple[str | None, str | None]:
    """将 ANTLR 原始错误翻译为人话。

    Args:
        spl: 原始 SPL 查询
        line: 错误行号（1-based）
        col: 错误列号（0-based）
        err_msg: 原始错误消息
        token_text: 出错的 token 文本
        expected: 建议的 token

    Returns:
        (human_message, original_message)
        human_message 为 None 表示无匹配，只展示 original_message
    """
    for name, fn in _PATTERNS:
        result = fn(spl, col, token_text, expected)
        if result:
            return result, err_msg
    return None, err_msg
