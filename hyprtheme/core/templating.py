"""A tiny, dependency-free template engine used for config generation.

Syntax (deliberately a small subset of Jinja so templates stay readable):

* ``{{ colors.primary }}``                      -> ``#00E5FF``
* ``{{ colors.primary | hypr(0.8) }}``          -> ``rgba(00e5ffcc)``
* ``{{ colors.surface | rgba(effects.opacity) }}`` -> ``rgba(17, 21, 29, 0.85)``
* ``{{ effects.radius | mul(0.5) | int }}``     -> ``7``
* ``{% if effects.glass %} ... {% elif x > 1 %} ... {% else %} ... {% endif %}``
* ``{% for stop in gradient.stops %} {{ stop | hypr }} {% endfor %}``
* ``{# comment #}``

Filter arguments may be number / string literals, ``true``/``false`` or context
paths.  Unknown variables and filters raise :class:`TemplateError` so a typo in
a template is caught by the test-suite instead of producing a broken config.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .colors import Color, ColorError


class TemplateError(ValueError):
    """Raised on syntax errors or unresolved names."""


_TOKEN_RE = re.compile(r"({%.*?%}|{{.*?}}|{#.*?#})", re.DOTALL)
# A block tag or comment that sits alone on its line is removed together with the line
# (Jinja's trim_blocks + lstrip_blocks), so templates can be indented freely.
_STANDALONE_TAG_RE = re.compile(r"^[ \t]*({%.*?%}|{#.*?#})[ \t]*\n", re.MULTILINE | re.DOTALL)
_FILTER_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*)\))?\s*$", re.DOTALL)
_NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _to_color(value: Any) -> Color:
    if isinstance(value, Color):
        return value
    if isinstance(value, str):
        try:
            return Color.parse(value)
        except ColorError as exc:
            raise TemplateError(str(exc)) from exc
    raise TemplateError(f"expected a color, got {value!r}")


def _num(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and _NUMBER_RE.match(value.strip()):
        return float(value)
    raise TemplateError(f"expected a number, got {value!r}")


def _fmt_num(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4g}"


# --- built-in filters --------------------------------------------------------------

FILTERS: dict[str, Callable[..., Any]] = {
    # colors
    "hex": lambda v: _to_color(v).hex,
    "hexlower": lambda v: _to_color(v).hex_lower,
    "hexa": lambda v, a=None: _to_color(v).hexa(None if a is None else _num(a)),
    "strip": lambda v, a=None: _to_color(v).strip(None if a is None else _num(a)),
    "hypr": lambda v, a=None: _to_color(v).hypr(None if a is None else _num(a)),
    "hyprrgb": lambda v: _to_color(v).hypr_rgb(),
    "rgba": lambda v, a=None: _to_color(v).css_rgba(None if a is None else _num(a)),
    "hyprlock": lambda v, a=None: _to_color(v).hyprlock(None if a is None else _num(a)),
    "rgb": lambda v: _to_color(v).css_rgb(),
    "rgbtuple": lambda v: _to_color(v).rgb_tuple(),
    "lighten": lambda v, x: _to_color(v).lighten(_num(x)),
    "darken": lambda v, x: _to_color(v).darken(_num(x)),
    "saturate": lambda v, x: _to_color(v).saturate(_num(x)),
    "alpha": lambda v, a: _to_color(v).with_alpha(_num(a)),
    "mix": lambda v, other, w=0.5: _to_color(v).mix(_to_color(other), _num(w)),
    "rotate": lambda v, deg: _to_color(v).rotate(_num(deg)),
    "readable": lambda v: _to_color(v).readable_text(),
    "noalpha": lambda v: _to_color(v).hex,
    # numbers
    "int": lambda v: round(_num(v)),
    "round": lambda v, n=0: round(_num(v), int(_num(n))) if int(_num(n)) > 0 else round(_num(v)),
    "mul": lambda v, x: _num(v) * _num(x),
    "div": lambda v, x: _num(v) / _num(x) if _num(x) else 0,
    "add": lambda v, x: _num(v) + _num(x),
    "sub": lambda v, x: _num(v) - _num(x),
    "max": lambda v, x: max(_num(v), _num(x)),
    "min": lambda v, x: min(_num(v), _num(x)),
    "pct": lambda v: round(_num(v) * 100),
    "clamp": lambda v, lo, hi: max(_num(lo), min(_num(hi), _num(v))),
    # booleans
    "yesno": lambda v: "yes" if v else "no",
    "truefalse": lambda v: "true" if v else "false",
    "onoff": lambda v: "on" if v else "off",
    "onezero": lambda v: "1" if v else "0",
    # strings
    "default": lambda v, d: d if v in (None, "", False) else v,
    "lower": lambda v: str(v).lower(),
    "upper": lambda v: str(v).upper(),
    "json": lambda v: __import__("json").dumps(v),
    "join": lambda v, sep=", ": sep.join(str(x) for x in v),
    "length": lambda v: len(v),
}


# --- expression evaluation ----------------------------------------------------------


def _split_args(text: str) -> list[str]:
    """Split filter arguments on commas, respecting quotes and parentheses."""
    args: list[str] = []
    depth = 0
    quote: str | None = None
    current = ""
    for ch in text:
        if quote:
            current += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            current += ch
        elif ch == "(":
            depth += 1
            current += ch
        elif ch == ")":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        args.append(current.strip())
    return args


def _split_pipes(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    current = ""
    for ch in text:
        if quote:
            current += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            current += ch
        elif ch == "(":
            depth += 1
            current += ch
        elif ch == ")":
            depth -= 1
            current += ch
        elif ch == "|" and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    parts.append(current.strip())
    return parts


class Context:
    def __init__(self, data: dict[str, Any]):
        self.scopes: list[dict[str, Any]] = [data]

    def push(self, scope: dict[str, Any]) -> None:
        self.scopes.append(scope)

    def pop(self) -> None:
        self.scopes.pop()

    def lookup(self, path: str) -> Any:
        parts = path.split(".")
        head = parts[0]
        for scope in reversed(self.scopes):
            if head in scope:
                value: Any = scope[head]
                break
        else:
            raise TemplateError(f"unknown variable '{path}'")
        for part in parts[1:]:
            if isinstance(value, dict):
                if part not in value:
                    raise TemplateError(f"unknown variable '{path}' (missing '{part}')")
                value = value[part]
            elif isinstance(value, (list, tuple)) and part.isdigit():
                value = value[int(part)]
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                raise TemplateError(f"unknown variable '{path}' (missing '{part}')")
        return value


def _literal(text: str, ctx: Context) -> Any:
    t = text.strip()
    if not t:
        raise TemplateError("empty expression")
    if (t[0] == t[-1]) and t[0] in "\"'" and len(t) >= 2:
        return t[1:-1]
    if t == "true":
        return True
    if t == "false":
        return False
    if t in ("none", "null", "None"):
        return None
    if _NUMBER_RE.match(t):
        return float(t) if "." in t else int(t)
    return ctx.lookup(t)


def _eval_value(expr: str, ctx: Context) -> Any:
    """Evaluate ``value | filter(args) | filter`` chains."""
    parts = _split_pipes(expr)
    value = _literal(parts[0], ctx)
    for raw in parts[1:]:
        m = _FILTER_RE.match(raw)
        if not m:
            raise TemplateError(f"bad filter syntax: {raw!r}")
        name, argtext = m.group(1), m.group(2)
        fn = FILTERS.get(name)
        if fn is None:
            raise TemplateError(f"unknown filter '{name}'")
        args = [_literal(a, ctx) for a in _split_args(argtext)] if argtext else []
        try:
            value = fn(value, *args)
        except TypeError as exc:
            raise TemplateError(f"filter '{name}': {exc}") from exc
    return value


_CMP_RE = re.compile(r"^(.*?)\s*(==|!=|>=|<=|>|<)\s*(.*)$", re.DOTALL)


def _truthy(value: Any) -> bool:
    if isinstance(value, Color):
        return True
    return bool(value)


def _eval_condition(expr: str, ctx: Context) -> bool:
    text = expr.strip()
    # 'or' has the lowest precedence, then 'and', then 'not'
    for op, fn in ((" or ", any), (" and ", all)):
        if op in f" {text} ":
            pieces = re.split(rf"\s+{op.strip()}\s+", text)
            if len(pieces) > 1:
                return fn(_eval_condition(p, ctx) for p in pieces)
    if text.startswith("not "):
        return not _eval_condition(text[4:], ctx)
    m = _CMP_RE.match(text)
    if m and m.group(1).strip():
        left = _eval_value(m.group(1), ctx)
        right = _eval_value(m.group(3), ctx)
        op = m.group(2)
        if op in ("==", "!="):
            eq = left == right
            if not eq and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                eq = float(left) == float(right)
            return eq if op == "==" else not eq
        lf, rf = _num(left), _num(right)
        return {">": lf > rf, "<": lf < rf, ">=": lf >= rf, "<=": lf <= rf}[op]
    return _truthy(_eval_value(text, ctx))


# --- parsing ------------------------------------------------------------------------


@dataclass
class _Node:
    kind: str  # text | var | if | for
    text: str = ""
    branches: list[tuple[str | None, list[_Node]]] | None = None  # for if
    var: str = ""
    iterable: str = ""
    body: list[_Node] | None = None


class Template:
    def __init__(self, source: str, name: str = "<template>"):
        self.name = name
        self.source = source
        cleaned = _STANDALONE_TAG_RE.sub(lambda m: m.group(1), source)
        self.nodes = self._parse(_TOKEN_RE.split(cleaned))

    def _parse(self, tokens: list[str]) -> list[_Node]:
        pos = 0

        def parse_block(terminators: tuple[str, ...]) -> tuple[list[_Node], str | None]:
            nonlocal pos
            nodes: list[_Node] = []
            while pos < len(tokens):
                tok = tokens[pos]
                pos += 1
                if not tok:
                    continue
                if tok.startswith("{#"):
                    continue
                if tok.startswith("{{"):
                    nodes.append(_Node("var", tok[2:-2].strip()))
                    continue
                if tok.startswith("{%"):
                    stmt = tok[2:-2].strip()
                    keyword = stmt.split(None, 1)[0] if stmt else ""
                    if keyword in terminators:
                        return nodes, stmt
                    if keyword == "if":
                        branches: list[tuple[str | None, list[_Node]]] = []
                        cond: str | None = stmt[2:].strip()
                        while True:
                            body, ending = parse_block(("elif", "else", "endif"))
                            branches.append((cond, body))
                            if ending is None:
                                raise TemplateError(f"{self.name}: unterminated {{% if %}}")
                            if ending.startswith("elif"):
                                cond = ending[4:].strip()
                                continue
                            if ending.startswith("else"):
                                body, ending = parse_block(("endif",))
                                branches.append((None, body))
                                if ending is None:
                                    raise TemplateError(f"{self.name}: unterminated {{% else %}}")
                            break
                        nodes.append(_Node("if", branches=branches))
                        continue
                    if keyword == "for":
                        m = re.match(r"for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)$", stmt, re.DOTALL)
                        if not m:
                            raise TemplateError(f"{self.name}: bad for statement {stmt!r}")
                        body, ending = parse_block(("endfor",))
                        if ending is None:
                            raise TemplateError(f"{self.name}: unterminated {{% for %}}")
                        nodes.append(_Node("for", var=m.group(1), iterable=m.group(2).strip(), body=body))
                        continue
                    raise TemplateError(f"{self.name}: unknown statement {stmt!r}")
                nodes.append(_Node("text", tok))
            return nodes, None

        nodes, ending = parse_block(())
        if ending is not None:
            raise TemplateError(f"{self.name}: unexpected {{% {ending} %}}")
        return nodes

    def render(self, data: dict[str, Any]) -> str:
        ctx = Context(data)
        out: list[str] = []
        self._render_nodes(self.nodes, ctx, out)
        return "".join(out)

    def _render_nodes(self, nodes: list[_Node], ctx: Context, out: list[str]) -> None:
        for node in nodes:
            if node.kind == "text":
                out.append(node.text)
            elif node.kind == "var":
                out.append(self._stringify(_eval_value(node.text, ctx)))
            elif node.kind == "if":
                assert node.branches is not None
                for cond, body in node.branches:
                    if cond is None or _eval_condition(cond, ctx):
                        self._render_nodes(body, ctx, out)
                        break
            elif node.kind == "for":
                assert node.body is not None
                items = _eval_value(node.iterable, ctx)
                if isinstance(items, dict):
                    items = list(items.items())
                for index, item in enumerate(items):
                    ctx.push({node.var: item, "loop": {"index": index, "first": index == 0, "last": index == len(items) - 1}})
                    try:
                        self._render_nodes(node.body, ctx, out)
                    finally:
                        ctx.pop()

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, Color):
            return value.hex
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float):
            return _fmt_num(value)
        if value is None:
            return ""
        return str(value)


def render(source: str, data: dict[str, Any], name: str = "<template>") -> str:
    return Template(source, name).render(data)
