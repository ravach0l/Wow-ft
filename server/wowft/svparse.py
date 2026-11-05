"""Liest SavedVariables-Dateien (Lua-Tabellenliterale) ohne Lua auszuführen.

Unterstützt genau das, was WoW beim Speichern schreibt: Zuweisungen
`Name = <Wert>` auf oberster Ebene, Tabellen mit `[key] = value`,
`key = value` und Positionswerten, Strings, Zahlen, Booleans und nil.
Tabellen mit den Schlüsseln 1..n werden zu Listen, alle anderen zu Dicts.
"""

from __future__ import annotations

import math
import re
from typing import Any

MAX_DEPTH = 32
EOF = "\0"  # Rückgabe von peek() am Dateiende


class ParseError(ValueError):
    pass


_NUMBER = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|inf|nan)")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "\n": "\n",
}


class _Parser:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    # -- Hilfen -----------------------------------------------------------
    def error(self, msg: str) -> ParseError:
        line = self.s.count("\n", 0, self.i) + 1
        return ParseError(f"Zeile {line}: {msg}")

    def skip(self) -> None:
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n;":
                self.i += 1
            elif s.startswith("--", self.i):
                m = re.compile(r"--\[(=*)\[").match(s, self.i)
                if m:
                    end = s.find("]" + m.group(1) + "]", m.end())
                    if end < 0:
                        raise self.error("Kommentar nicht geschlossen")
                    self.i = end + len(m.group(1)) + 2
                else:
                    nl = s.find("\n", self.i)
                    self.i = n if nl < 0 else nl + 1
            else:
                break

    def peek(self) -> str:
        self.skip()
        return self.s[self.i] if self.i < self.n else EOF

    def expect(self, ch: str) -> None:
        if self.peek() != ch:
            raise self.error(f"'{ch}' erwartet")
        self.i += 1

    # -- Werte ------------------------------------------------------------
    def value(self, depth: int) -> Any:
        c = self.peek()
        if c == "{":
            return self.table(depth + 1)
        if c in "\"'":
            return self.string()
        if c == "[" and re.compile(r"\[=*\[").match(self.s, self.i):
            return self.long_string()
        m = _NAME.match(self.s, self.i)
        if m:
            word = m.group(0)
            if word in ("true", "false", "nil"):
                self.i = m.end()
                return {"true": True, "false": False, "nil": None}[word]
        m = _NUMBER.match(self.s, self.i)
        if m:
            self.i = m.end()
            return _to_number(m.group(0))
        raise self.error("Wert erwartet")

    def string(self) -> str:
        quote = self.s[self.i]
        self.i += 1
        out: list[str] = []
        s = self.s
        while True:
            if self.i >= self.n:
                raise self.error("String nicht geschlossen")
            c = s[self.i]
            if c == quote:
                self.i += 1
                return "".join(out)
            if c == "\\":
                self.i += 1
                e = s[self.i] if self.i < self.n else ""
                if e in _ESCAPES:
                    out.append(_ESCAPES[e])
                    self.i += 1
                elif e.isdigit():
                    m = re.compile(r"\d{1,3}").match(s, self.i)
                    raw_bytes = bytearray([int(m.group(0)) & 0xFF])
                    self.i = m.end()
                    # Mehrere Byte-Escapes hintereinander als UTF-8 lesen.
                    while s.startswith("\\", self.i):
                        m2 = re.compile(r"\\(\d{1,3})").match(s, self.i)
                        if not m2:
                            break
                        raw_bytes.append(int(m2.group(1)) & 0xFF)
                        self.i = m2.end()
                    out.append(raw_bytes.decode("utf-8", errors="replace"))
                elif e == "x":
                    try:
                        out.append(chr(int(s[self.i + 1 : self.i + 3], 16)))
                    except ValueError as e:
                        raise self.error("ungültiges \\x-Escape") from e
                    self.i += 3
                else:
                    raise self.error(f"unbekanntes Escape \\{e}")
            elif c == "\n":
                raise self.error("Zeilenumbruch im String")
            else:
                out.append(c)
                self.i += 1

    def long_string(self) -> str:
        m = re.compile(r"\[(=*)\[\n?").match(self.s, self.i)
        close = "]" + m.group(1) + "]"
        end = self.s.find(close, m.end())
        if end < 0:
            raise self.error("langer String nicht geschlossen")
        self.i = end + len(close)
        return self.s[m.end() : end]

    def table(self, depth: int) -> Any:
        if depth > MAX_DEPTH:
            raise self.error("Tabelle zu tief verschachtelt")
        self.expect("{")
        result: dict[Any, Any] = {}
        pos = 1
        while True:
            c = self.peek()
            if c == "}":
                self.i += 1
                break
            if c == "[" and not re.compile(r"\[=*\[").match(self.s, self.i):
                self.i += 1
                key = self.value(depth)
                self.expect("]")
                self.expect("=")
                val = self.value(depth)
            else:
                m = _NAME.match(self.s, self.i)
                after = m and re.compile(r"\s*=(?!=)").match(self.s, m.end())
                if m and after and m.group(0) not in ("true", "false", "nil"):
                    key = m.group(0)
                    self.i = after.end()
                    val = self.value(depth)
                else:
                    key = pos
                    pos += 1
                    val = self.value(depth)
            if isinstance(key, float) and key.is_integer():
                key = int(key)
            if val is not None:
                result[key] = val
            sep = self.peek()
            if sep in ",;":
                self.i += 1
            elif sep != "}":
                raise self.error("',' oder '}' erwartet")
        return _listify(result)

    def document(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        while self.peek() != EOF:
            m = _NAME.match(self.s, self.i)
            if not m:
                raise self.error("Variablenname erwartet")
            self.i = m.end()
            self.expect("=")
            out[m.group(0)] = self.value(0)
        return out


def _to_number(text: str) -> int | float:
    low = text.lower()
    if low.lstrip("-") == "inf":
        return -math.inf if low.startswith("-") else math.inf
    if low.lstrip("-") == "nan":
        return math.nan
    if "x" in low:
        return int(text, 16)
    if any(ch in low for ch in ".e"):
        f = float(text)
        return int(f) if f.is_integer() and abs(f) < 2**53 else f
    return int(text)


def _listify(d: dict[Any, Any]) -> Any:
    if d and all(isinstance(k, int) for k in d) and set(d) == set(range(1, len(d) + 1)):
        return [d[k] for k in range(1, len(d) + 1)]
    if not d:
        return {}
    return {str(k) if not isinstance(k, str) else k: v for k, v in d.items()}


def parse(text: str) -> dict[str, Any]:
    """Gibt alle Variablen der Datei als Dict zurück."""
    if text.startswith("\ufeff"):
        text = text[1:]
    return _Parser(text).document()


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    with open(sys.argv[1], encoding="utf-8") as fh:
        print(json.dumps(parse(fh.read()), indent=2, ensure_ascii=False))
