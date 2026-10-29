"""Bundle the installed img2table as pure Python so Pyodide can import it.

img2table ships four Cython extensions with no WebAssembly wheel. Their .pyx
sources are included, so this strips the C type annotations to get equivalent
(slower) Python, then zips the package for the browser worker to unpack.

    uv run python web/build_img2table.py [output_dir]
"""

import re
import shutil
import sys
import zipfile
from pathlib import Path

import img2table

HEADER = """import math

M_PI = math.pi
atan = math.atan
ceil = math.ceil


def c_round(value):
    # C round() goes half away from zero; Python's round() goes half to even.
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)
"""
DROP = re.compile(r"^\s*(cimport .*|from \S+ cimport .*|cnp\.import_array\(\)|@cython\.\w+\(.*\))\s*$")
DEF = re.compile(r"^(\s*)(cdef\s+inline\s+[\w.]+\s+|cpdef\s+[\w.]+\s+|def\s+)(\w+)\(")
CDEF = re.compile(r"^(\s*)cdef\s+([\w.]+)(\[[^\]]*\])?\s+(.*)$", re.DOTALL)
ASSIGN = re.compile(r"^(\s*)(\w+(?:\s*,\s*\w+)*)\s*(=|\+=|-=|\*=)(?!=)\s*(.*)$", re.DOTALL)
CAST = re.compile(r"<(int|long|double|cnp\.\w+)>\s*")
# NumPy 2 keeps array scalars in their narrow dtype (uint8 + int stays uint8), while
# C widens them into the declared variable, so values assigned to C scalars are
# converted to Python numbers to keep the original overflow-free arithmetic.
INTS = {"int", "long", "Py_ssize_t", "cnp.intp_t", "cnp.int32_t", "cnp.int64_t", "unsigned"}
FLOATS = {"double", "float", "cnp.float64_t"}


def close(text, start):
    """Index just past the bracket group opening at text[start]."""
    depth = 0
    for i in range(start, len(text)):
        depth += text[i] in "([{"
        depth -= text[i] in ")]}"
        if depth == 0:
            return i + 1
    raise ValueError(f"Unbalanced brackets: {text[start : start + 60]!r}")


def balance(text):
    return sum(ch in "([{" for ch in text) - sum(ch in ")]}" for ch in text)


def split_top(text, sep):
    parts, depth, last = [], 0, 0
    for i, ch in enumerate(text):
        depth += ch in "([{"
        depth -= ch in ")]}"
        if ch == sep and depth == 0:
            parts.append(text[last:i])
            last = i + 1
    return parts + [text[last:]]


def strip_casts(text):
    match = CAST.search(text)
    if not match:
        return text
    rest = text[match.end() :]
    if rest.startswith("("):
        end = close(rest, 0)
    else:
        end = re.match(r"[\w.]+", rest).end()
        if rest[end : end + 1] == "(":
            end = close(rest, end)
    operand = strip_casts(rest[:end])
    # int/long casts truncate; double and fixed-width casts change nothing in Python.
    cast = f"int({operand})" if match[1] in ("int", "long") else operand
    return text[: match.start()] + cast + strip_casts(rest[end:])


def kind(ctype, buffer):
    if buffer:
        return None
    return "int" if ctype in INTS else "float" if ctype in FLOATS else None


def strip_signature(source, match):
    """Return the Python def line, typed scalar parameters and the length consumed."""
    open_at = match.end() - 1
    end = close(source, open_at)
    colon = source.index(":", end)
    args, typed = [], {}
    for arg in split_top(source[open_at + 1 : end - 1], ","):
        arg = " ".join(arg.split())
        if arg:
            left, *default = split_top(arg, "=")
            words = re.match(r"(?:([\w.]+)(\[.*\])?\s+)?(\w+)$", left.strip())
            if words[1] and (k := kind(words[1], words[2])):
                typed[words[3]] = k
            args.append(words[3] + ("=" + default[0].strip() if default else ""))
    return f"{match[1]}def {match[3]}({', '.join(args)}):", typed, colon + 1


def decythonize(source):
    out, pos, scalars = [], 0, {}
    source = "".join(line for line in source.splitlines(keepends=True) if not DROP.match(line))
    while pos < len(source):
        line_end = source.find("\n", pos) + 1 or len(source)
        line = source[pos:line_end]
        if match := DEF.match(line):
            header, scalars, end = strip_signature(source[pos:], match)
            out.append(header)
            pos += end
            if not match[2].startswith("cdef"):  # Hot inline helpers rely on callers' conversion.
                body = source[pos:].lstrip("\n")
                indent = re.match(r"[ \t]*", body)[0]
                out.append("".join(f"\n{indent}{n} = {k}({n})" for n, k in scalars.items()))
            continue
        statement = line
        while balance(statement) > 0:  # Pull in continuation lines of a bracketed expression.
            line_end = source.find("\n", line_end) + 1 or len(source)
            statement = source[pos:line_end]
        pos = line_end
        if match := CDEF.match(statement.rstrip("\n")):
            indent, ctype, buffer, body = match.groups()
            target, *value = split_top(body, "=")
            names = [n.strip() for n in target.split(",")]
            if k := kind(ctype, buffer):
                scalars.update(dict.fromkeys(names, k))
            if value:
                statement = f"{indent}{target.strip()} = {'='.join(value).strip()}\n"
            else:
                continue  # Bare declarations have no Python equivalent.
        statement = strip_casts(statement)
        if match := ASSIGN.match(statement.rstrip("\n")):
            indent, target, op, value = match.groups()
            kinds = {scalars.get(n.strip()) for n in target.split(",")}
            if len(kinds) == 1 and (k := kinds.pop()):
                if "," in target:
                    value = f"map({k}, ({value}))"
                else:
                    value = f"{k}({value})"
                statement = f"{indent}{target} {op} {value}\n"
        out.append(statement)
    return HEADER + "\n" + "".join(out)


def build(output_dir):
    source = Path(img2table.__file__).parent
    staging = output_dir / "staging" / "img2table"
    shutil.rmtree(staging.parent, ignore_errors=True)
    shutil.copytree(source, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyd", "*.so"))
    for pyx in staging.rglob("*.pyx"):
        pyx.with_suffix(".py").write_text(decythonize(pyx.read_text(encoding="utf-8")), encoding="utf-8")
        pyx.unlink()
    archive = output_dir / "img2table.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging.parent).as_posix())
    return staging.parent, archive


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "vendor"
    out.mkdir(parents=True, exist_ok=True)
    staging, archive = build(out)
    print(f"Pure-Python package: {staging}\nArchive: {archive} ({archive.stat().st_size // 1024} KB)")
