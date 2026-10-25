#!/usr/bin/env python3
"""Lint the markdown files of the Be-Ambitious Harness.

Run from anywhere (paths are resolved from this file's location):

    python3 -I tools/lint-harness.py          check; exit 0 if clean, 1 on violations
    python3 -I tools/lint-harness.py --fix    also rewrite what is mechanical (the evals badge)
    python3 -I tools/lint-harness.py -v       also list skipped template paths on stderr

Output: one line per violation, `path:line: rule: message`.
Standard library only, Python 3.10+. Rules are listed in RULES at the bottom:
one function per rule; add a function and a line there to add a rule.
"""

# Комментарии — по-русски, сообщения линтера — по-английски: их читают авторы PR.

import argparse
import math
import re
import sys
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------- настройки

ROOT = Path(__file__).resolve().parent.parent

# Корни языков относительно корня репозитория: "" — английский перевод, "ru" — оригинал.
LANG_ROOTS = ("ru", "")
RU = "ru"

# Что считается файлом харнесса в корне каждого языка (плюс всё *.md внутри ru/).
HARNESS_TOP = ("SKILL.md",)
HARNESS_DIRS = ("agents", "core", "scenarios", "checklists", "evals")
NOT_HARNESS = ("evals/runs/", "evals/fixtures/")  # записанные прогоны и генераторы данных — не харнесс

BUDGETS_FILE = "tools/word-budgets.tsv"

# Пути, упоминания которых проверяет правило link.
PATH_PREFIXES = ("agents", "core", "scenarios", "checklists", "evals", "tools")
# Эти папки есть только в корне репозитория и общие для обоих языков:
# из ru/ на них ссылаются от корня, а не от ru/.
SHARED_PATHS = ("evals/runs", "tools")
# Признаки шаблона вместо реального пути: <…>, *, …, [...].
TEMPLATE_MARKS = ("<", ">", "*", "…", "...", "[", "]")

PROMPT_TEMPLATE = "core/prompt-template.md"
PROMPT_SECTIONS = 7

TASKS_FILE = "evals/tasks.md"
RUNS_DIR = "evals/runs"
# README → (подпись бейджа, шаблон текста). Бейдж ищется по подписи.
EVALS_BADGES = {
    "README.md": ("eval runs", "{done} of {total} tasks"),
    "README.ru.md": ("прогоны", "{done} из {total} задач"),
    "README.es.md": ("evaluaciones", "{done} de {total} tareas"),
    "README.zh-CN.md": ("评测运行", "{done}/{total} 项任务"),
}

# ---------------------------------------------------------------- разбор markdown

FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)")
CODE_SPAN = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)")
INLINE_LINK = re.compile(
    r"!?\[(?:[^\]\\]|\\.)*\]\(\s*(<[^>]*>|[^)\s]+)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
REF_DEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
PATH_TOKEN = re.compile(
    r"(?<![\w./~\\@-])(?:" + "|".join(PATH_PREFIXES) + r")/[^\s`'\"«»“”„(),;|—–]*"
)


def iter_lines(text):
    """(номер строки, строка, внутри ли блока кода) без front matter и строк-ограждений."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                start = i + 1
                break
    fence = None  # (символ, длина) открытого ограждения
    for i in range(start, len(lines)):
        line = lines[i]
        if fence:
            stripped = line.strip()
            if (
                len(line) - len(line.lstrip(" ")) <= 3
                and stripped
                and set(stripped) == {fence[0]}
                and len(stripped) >= fence[1]
            ):
                fence = None
                continue
            yield i + 1, line, True
            continue
        m = FENCE_OPEN.match(line)
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence = (m.group(1)[0], len(m.group(1)))
            continue
        yield i + 1, line, False


def headings(text):
    """ATX-заголовки вне блоков кода: [(строка, уровень)]."""
    out = []
    for n, line, in_code in iter_lines(text):
        if not in_code:
            m = ATX_HEADING.match(line)
            if m:
                out.append((n, len(m.group(1))))
    return out


def clean_token(tok):
    """Срезает хвостовую пунктуацию и непарные закрывающие скобки: `scenarios/]` → `scenarios/`."""
    tok = tok.rstrip(",:;!?")
    changed = True
    while changed:
        changed = False
        for opener, closer in ("[]", "()", "<>", "{}"):
            if tok.endswith(closer) and tok.count(closer) > tok.count(opener):
                tok = tok[:-1].rstrip(",:;!?")
                changed = True
    return tok


def path_mentions(text):
    """Упоминания путей с нужными префиксами: в `коде`, в блоках кода и в ссылках markdown."""
    for n, line, in_code in iter_lines(text):
        if in_code:
            for m in PATH_TOKEN.finditer(line):
                yield n, clean_token(m.group(0))
            continue
        for m in CODE_SPAN.finditer(line):
            for t in PATH_TOKEN.finditer(m.group(2)):
                yield n, clean_token(t.group(0))
        prose = CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)
        targets = [m.group(1) for m in INLINE_LINK.finditer(prose)]
        ref = REF_DEF.match(prose)
        if ref:
            targets.append(ref.group(1))
        for target in targets:
            target = target.strip("<>").split("#", 1)[0].split("?", 1)[0]
            target = urllib.parse.unquote(target)
            while target.startswith("./"):
                target = target[2:]
            if target.split("/", 1)[0] in PATH_PREFIXES and "/" in target:
                yield n, target


def is_template(tok):
    return any(mark in tok for mark in TEMPLATE_MARKS)


def word_count(text):
    # То же, что `wc -w` в UTF-8-локали: куски без пробельных символов.
    return len(text.split())


def ceil50(n):
    return max(50, math.ceil(n / 50) * 50)


# ---------------------------------------------------------------- контекст


@dataclass
class Finding:
    path: str
    line: int
    message: str
    fixed: bool = False


class Repo:
    def __init__(self, root, fix=False, verbose=False):
        self.root = root
        self.fix = fix
        self.verbose = verbose
        self._text = {}
        self._files = None

    def exists(self, rel):
        return (self.root / rel).exists()

    def text(self, rel):
        if rel not in self._text:
            with open(self.root / rel, encoding="utf-8", newline="") as f:
                self._text[rel] = f.read()
        return self._text[rel]

    def write(self, rel, text):
        with open(self.root / rel, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        self._text[rel] = text

    def info(self, message):
        if self.verbose:
            print(message, file=sys.stderr)

    def rel(self, path):
        return path.relative_to(self.root).as_posix()

    def harness_files(self):
        """Все markdown-файлы харнесса обоих языков, пути от корня репозитория."""
        if self._files is not None:
            return list(self._files)
        found = set()
        for lang in LANG_ROOTS:
            base = self.root / lang if lang else self.root
            for name in HARNESS_TOP:
                if (base / name).is_file():
                    found.add(self.rel(base / name))
            for d in HARNESS_DIRS:
                if (base / d).is_dir():
                    found.update(self.rel(p) for p in (base / d).rglob("*.md") if p.is_file())
        if (self.root / RU).is_dir():
            found.update(self.rel(p) for p in (self.root / RU).rglob("*.md") if p.is_file())
        # Английская пара любого русского файла — тоже харнесс.
        found.update(f[len(RU) + 1:] for f in list(found)
                     if f.startswith(RU + "/") and self.exists(f[len(RU) + 1:]))
        self._files = sorted(f for f in found if not lang_rel(f).startswith(NOT_HARNESS))
        return list(self._files)

    def readmes(self):
        return sorted(self.rel(p) for p in self.root.glob("README*.md") if p.is_file())


def lang_root(rel):
    return RU if rel.startswith(RU + "/") else ""


def lang_rel(rel):
    """Путь от корня своего языка: ru/core/gate.md → core/gate.md."""
    return rel[len(RU) + 1:] if rel.startswith(RU + "/") else rel


def join(*parts):
    return "/".join(p for p in parts if p)


# ---------------------------------------------------------------- правила


def check_word_budgets(repo):
    """Каждый файл харнесса есть в таблице бюджетов и не длиннее своего лимита."""
    if not repo.exists(BUDGETS_FILE):
        yield Finding(BUDGETS_FILE, 1, "budget table is missing")
        return
    limits = {}  # путь → (лимит, строка таблицы)
    for n, raw in enumerate(repo.text(BUDGETS_FILE).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) != 2 or not parts[1].strip().isdigit() or int(parts[1]) <= 0:
            yield Finding(BUDGETS_FILE, n, f"expected `<path><TAB><positive limit>`, got `{raw}`")
            continue
        path, limit = parts[0].strip(), int(parts[1])
        if path in limits:
            yield Finding(BUDGETS_FILE, n, f"duplicate row for {path} (first at line {limits[path][1]})")
            continue
        limits[path] = (limit, n)

    files = repo.harness_files()
    for rel in files:
        words = word_count(repo.text(rel))
        if rel not in limits:
            yield Finding(rel, 1, f"no row in {BUDGETS_FILE} ({words} words now; "
                                  f"rounded up to 50 that is {ceil50(words)})")
        elif words > limits[rel][0]:
            limit, n = limits[rel]
            yield Finding(rel, 1, f"{words} words, over the limit of {limit} ({BUDGETS_FILE}:{n})")
    for path, (_, n) in limits.items():
        if path not in files:
            what = "not a harness file" if repo.exists(path) else "file does not exist"
            yield Finding(BUDGETS_FILE, n, f"row for {path}: {what}")


def check_links(repo):
    """Пути agents/ core/ scenarios/ checklists/ evals/ tools/ ведут на существующие файлы.

    Проверяются файлы харнесса и README*.md в корне; путь считается от корня своего языка
    (ru/ для русских файлов), кроме SHARED_PATHS — они от корня репозитория.
    """
    for rel in repo.harness_files() + repo.readmes():
        base = lang_root(rel)
        for n, tok in path_mentions(repo.text(rel)):
            if is_template(tok):
                repo.info(f"{rel}:{n}: link: skipped template `{tok}`")
                continue
            tok = tok.rstrip(".")
            shared = any(tok == p or tok.startswith(p + "/") for p in SHARED_PATHS)
            target = tok if shared else join(base, tok)
            path = repo.root / target
            ok = path.is_dir() if tok.endswith("/") else path.exists()
            if not ok:
                where = "" if target == tok else f" (resolved to {target})"
                yield Finding(rel, n, f"`{tok}` does not exist{where}")


def check_prompt_sections(repo):
    """В шаблоне промпта ровно семь разделов: список «N. **Название** —» и скелет «## N. Название»."""
    expected = list(range(1, PROMPT_SECTIONS + 1))
    for lang in LANG_ROOTS:
        rel = join(lang, PROMPT_TEMPLATE)
        if not repo.exists(rel):
            yield Finding(rel, 1, "prompt template is missing")
            continue
        listed, skeleton = [], []  # (строка, номер, название)
        for n, line, in_code in iter_lines(repo.text(rel)):
            if in_code:
                m = re.match(r"^##\s+(\d+)\.\s+(.+?)\s*$", line)
                if m:
                    # «## 4. Gate check   (conditional scheme only)» → «Gate check»
                    title = re.sub(r"\s*\([^)]*\)$", "", m.group(2))
                    skeleton.append((n, int(m.group(1)), title))
            else:
                m = re.match(r"^(\d+)\.\s+(.*)$", line)
                if m:
                    bold = re.match(r"\*\*(.+?)\*\*", m.group(2))
                    if not bold:
                        yield Finding(rel, n, f"section {m.group(1)} in the list has no **title**")
                    listed.append((n, int(m.group(1)), bold.group(1) if bold else ""))
        ok = True
        for where, items in (("list `N. **Title** —`", listed),
                             ("skeleton `## N. Title`", skeleton)):
            numbers = [num for _, num, _ in items]
            if numbers != expected:
                ok = False
                bad = next((i for i, (a, b) in enumerate(zip(numbers, expected)) if a != b),
                           min(len(numbers), len(expected)))
                line = items[bad][0] if bad < len(items) else (items[-1][0] if items else 1)
                yield Finding(rel, line, f"{where} has sections {numbers or 'none'}, "
                                         f"expected {expected}")
        if ok:
            for (_, num, a), (n, _, b) in zip(listed, skeleton):
                if a != b:
                    yield Finding(rel, n, f"section {num} is `{a}` in the list but `{b}` in the skeleton")


def check_heading_counts(repo):
    """У каждой пары ru/X и X одинаковое число заголовков, в том числе по уровням.

    Считаются ATX-заголовки (#…######) вне блоков кода и front matter; setext-заголовков
    (подчёркивание === / ---) в харнессе нет, они не считаются.
    """
    files = repo.harness_files()
    ru = {lang_rel(f) for f in files if f.startswith(RU + "/")}
    en = {f for f in files if not f.startswith(RU + "/")}
    for x in sorted(ru | en):
        ru_x = join(RU, x)
        if x not in en:
            yield Finding(ru_x, 1, f"no English counterpart {x}")
            continue
        if x not in ru:
            yield Finding(x, 1, f"no Russian original {ru_x}")
            continue
        h_ru, h_en = headings(repo.text(ru_x)), headings(repo.text(x))
        c_ru, c_en = Counter(lv for _, lv in h_ru), Counter(lv for _, lv in h_en)
        if c_ru == c_en:
            continue
        levels_ru, levels_en = [lv for _, lv in h_ru], [lv for _, lv in h_en]
        k = next((i for i, (a, b) in enumerate(zip(levels_ru, levels_en)) if a != b),
                 min(len(h_ru), len(h_en)))
        line = h_en[k][0] if k < len(h_en) else (h_en[-1][0] if h_en else 1)

        def fmt(c):
            return ", ".join(f"h{lv}: {c[lv]}" for lv in sorted(c)) or "none"

        yield Finding(x, line, f"{len(h_en)} headings ({fmt(c_en)}), but {ru_x} has "
                               f"{len(h_ru)} ({fmt(c_ru)}); first difference at heading #{k + 1}")


def task_ids(text):
    """ID задач из заголовков «## T1 · …» … «## L2 · …»."""
    return [m.group(1) for _, line, in_code in iter_lines(text)
            if not in_code and (m := re.match(r"^##\s+([A-Z][0-9]+)\s+·", line))]


def split_badge(path):
    """Путь shields `label-message-color` → части; `--` — это дефис внутри текста."""
    parts, cur, i = [], "", 0
    while i < len(path):
        if path.startswith("--", i):
            cur += "--"
            i += 2
        elif path[i] == "-":
            parts.append(cur)
            cur = ""
            i += 1
        else:
            cur += path[i]
            i += 1
    parts.append(cur)
    return parts


def badge_decode(raw):
    text = urllib.parse.unquote(raw).replace("--", "-")
    return re.sub(r"__|_", lambda m: "_" if m.group(0) == "__" else " ", text)


def badge_encode(text):
    return urllib.parse.quote(text.replace("-", "--").replace("_", "__"), safe="")


def check_evals_badge(repo):
    """Бейдж «прогоны N из M задач» в README совпадает с папками evals/runs/*/<ID>-<плечо>/."""
    ids = {}
    for lang in LANG_ROOTS:
        rel = join(lang, TASKS_FILE)
        if repo.exists(rel):
            ids[rel] = task_ids(repo.text(rel))
            dupes = sorted(i for i, c in Counter(ids[rel]).items() if c > 1)
            if dupes:
                yield Finding(rel, 1, f"duplicate task IDs: {', '.join(dupes)}")
    if not ids:
        yield Finding(TASKS_FILE, 1, "no tasks file to count tasks from")
        return
    source = join(RU, TASKS_FILE) if join(RU, TASKS_FILE) in ids else TASKS_FILE
    known = ids[source]
    for rel, found in ids.items():
        if rel != source and found != known:
            yield Finding(rel, 1, f"task IDs {found} differ from {source} {known}")
    if not known:
        yield Finding(source, 1, "no task headings `## <ID> · …` found")
        return

    done = set()
    runs = repo.root / RUNS_DIR
    arms = sorted(arm for run in runs.iterdir() if run.is_dir()
                  for arm in run.iterdir() if arm.is_dir()) if runs.is_dir() else []
    for arm in arms:
        # T3-A, L2-B, T2-pass-A: ID — до первого дефиса; пустые папки не считаются.
        m = re.match(r"^([A-Z][0-9]+)-.+$", arm.name)
        if not m or not any(p.is_file() for p in arm.rglob("*")):
            continue
        if m.group(1) in known:
            done.add(m.group(1))
        else:
            yield Finding(repo.rel(arm) + "/", 1, f"run folder for task {m.group(1)}, "
                                                  f"which is not in {source}")
    total = len(set(known))
    order = {t: i for i, t in enumerate(known)}
    done_list = ", ".join(sorted(done, key=order.get)) or "none"

    for readme, (label, template) in EVALS_BADGES.items():
        if not repo.exists(readme):
            yield Finding(readme, 1, "README listed in EVALS_BADGES is missing")
            continue
        expected = template.format(done=len(done), total=total)
        text = repo.text(readme)
        lines = text.splitlines(keepends=True)
        seen = False
        for n, line in enumerate(lines, 1):
            for m in re.finditer(r"https://img\.shields\.io/badge/([^)\s\"'>?]+)", line):
                parts = split_badge(m.group(1))
                if len(parts) != 3 or badge_decode(parts[0]) != label:
                    continue
                seen = True
                actual = badge_decode(parts[1])
                if actual == expected:
                    continue
                if repo.fix:
                    new = "-".join([parts[0], badge_encode(expected), parts[2]])
                    lines[n - 1] = line = line.replace(m.group(1), new, 1)
                    yield Finding(readme, n, f"fixed: `{actual}` → `{expected}`", fixed=True)
                else:
                    yield Finding(readme, n, f"badge `{label}` says `{actual}`, runs are recorded "
                                             f"for {len(done)} of {total} tasks ({done_list}): "
                                             f"expected `{expected}` (fix: --fix)")
        if not seen:
            yield Finding(readme, 1, f"no shields badge labelled `{label}`")
        if repo.fix and "".join(lines) != text:
            repo.write(readme, "".join(lines))


# Все правила — здесь. Порядок — порядок вывода.
RULES = (
    ("word-budget", check_word_budgets),
    ("link", check_links),
    ("prompt-sections", check_prompt_sections),
    ("heading-count", check_heading_counts),
    ("evals-badge", check_evals_badge),
)

# ---------------------------------------------------------------- запуск


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        epilog="Rules: " + ", ".join(name for name, _ in RULES),
    )
    ap.add_argument("--fix", action="store_true",
                    help="rewrite the evals badge in the READMEs; everything else is only reported")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="list skipped template paths on stderr")
    args = ap.parse_args(argv)

    repo = Repo(ROOT, fix=args.fix, verbose=args.verbose)
    failures = 0
    for name, rule in RULES:
        for f in rule(repo):
            print(f"{f.path}:{f.line}: {name}: {f.message}")
            failures += not f.fixed
    sys.stdout.flush()  # итог — после строк нарушений, даже когда вывод склеен в CI
    if failures:
        print(f"lint-harness: {failures} violation(s)", file=sys.stderr)
        return 1
    print(f"lint-harness: OK ({len(RULES)} rules, {len(repo.harness_files())} harness files)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
