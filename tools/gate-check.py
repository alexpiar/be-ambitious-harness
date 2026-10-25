#!/usr/bin/env python3
"""gate-check: a mechanical check that the gate criterion was not rewritten.

    python3 -I tools/gate-check.py <prompt> <log> [--strict]

<prompt> is the worker prompt (seven sections, core/prompt-template.md);
<log> is the worker's evidence log. Standard library only, Python 3.10+.

Checks (each prints OK / FAIL / SKIP lines; a usage error prints ERROR):

  presence   section 4 of the prompt has a gate  <=>  the log has a GATE
             block (a ``` fence whose first line is GATE, core/gate.md).
             A gate in neither passes: "gate absent from both prompt and
             log". The prompt has no gate when section 4 says so, or when
             there is no section 4 and the scheme in section 1 is baseline
             or ambitious right away (run T3-A of 2026-10-21).
  criterion  the "criterion (as written)" field of every GATE block
             against the "Pass criterion" line of section 4.
  order      the first GATE block stands above the first ambitious-branch
             entry: a heading outside code fences that contains the words
             "ambitious branch" / "амбициозная ветка" (any case, any
             grammatical form, a hyphen allowed between the words).

Exit code: 0 every check passed; 1 a discrepancy (its FAIL line says where);
2 usage error: a file is missing or unreadable, the prompt has no "## N."
sections, the scheme is conditional but there is no section 4, section 4 has
no "Pass criterion" line, or the criterion has no pass condition.

How the criterion is compared, and why not literally
----------------------------------------------------
The v0.2 spec (work 3) says "character by character after whitespace
normalisation" and also requires exit 0 on run L2-A of 2026-10-21. The two
conflict: the L2-A log copies the pass condition verbatim, but retells the
applicability condition ("Если в dev-популяции среза меньше 100
положительных меток, критерий неприменим" -> "при < 100 положительных в
dev-популяции среза — неприменим") and drops the rationale. The default mode
splits the criterion into sentences and ;-clauses, sorts them into three
parts and compares each part as strictly as L2-A allows:

  1. Pass condition: every clause that is neither rationale nor
     applicability. Compared character by character after normalisation:
     Unicode NFC; soft hyphen, ZWSP, ZWNJ, ZWJ, word joiner and BOM removed;
     any run of whitespace (NBSP and other Unicode spaces included) -> one
     space; trailing . ; : , ! ? … dropped. Thresholds, operators and
     metrics live here; any change fails, including a retyped symbol
     (">=" for "≥", "-" for "−"): copy the line, do not retype it.
  2. Applicability condition: a clause that says the criterion is
     inapplicable ("неприменим", "inapplicable") and has a condition word
     (если / при / когда / if / when / unless); "…, otherwise inapplicable"
     without one stays in part 1. Same rule for prompt and log, so a
     verbatim copy always matches. This part may be retold, but (a) the
     ordered sequence of numbers, comparison operators (symbols or words:
     "меньше" = "<", "не менее" = "at least" = "≥"), identifiers (ROC,
     AUC(Б), F1, n_sessions) and logic words (и, или, не, and, or, not)
     must be identical, and (b) the log may not bring in a word that the
     prompt's clause lacks (dropping words is allowed; a few prepositions
     and "criterion" are exempt).
  3. Rationale: the sentence that starts with "Обоснование:" /
     "Rationale:". The log may omit it; if the log has it, it must match
     like part 1.

Not caught in the default mode: a retold applicability condition that only
drops a qualifier ("100 положительных меток" -> "100 меток"). Changing a
word there is caught (rule b), and so is any change to its numbers. --strict
compares the whole criterion character by character after whitespace
normalisation, the letter of the spec; on L2-A it exits 1.

Extending
---------
A check is a function Context -> list[Result], listed in CHECKS; the output
format and the exit code come from the results. Work 5 of v0.2 (timestamps
holdout-sealed < scout-end < gate-criterion-written < gate-run) is meant to
become one more such function.

По-русски
---------
Скрипт сверяет промпт воркера и журнал: (наличие) gate в разделе 4 есть
тогда и только тогда, когда в журнале есть блок GATE; (критерий) поле
«критерий (как записан)» каждого блока GATE совпадает со строкой «Критерий
прохождения» раздела 4; (порядок) первый GATE стоит выше первого заголовка
со словами «амбициозная ветка» в любой форме и любом регистре. Коды: 0 —
совпало, 1 — расхождение (строка FAIL говорит, где), 2 — ошибка
использования.

Отступление от буквы ТЗ: посимвольно (после нормализации пробелов)
сравнивается условие прохождения — все предложения и части через «;»,
кроме обоснования и условия применимости. Условие применимости — часть со
словом «неприменим» и словом условия (если/при/когда); его можно
пересказать, но последовательность чисел, операторов сравнения (знаком или
словом), обозначений и связок и/или/не должна совпасть, а новых слов журнал
вносить не может. Обоснование можно опустить; если оно есть — сравнивается
посимвольно. Иначе L2-A от 21.10 даёт 1, а ТЗ требует 0. Флаг --strict —
буквальное сравнение всего критерия; на L2-A он даёт 1. Не ловится:
пересказ условия применимости, который только выбрасывает уточнение
(«положительных меток» → «меток»).
"""

import argparse
import difflib
import re
import sys
import unicodedata
from dataclasses import dataclass, field

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# --- Сообщения: ключ -> (русский, английский) --------------------------------
# Язык вывода — язык заголовков разделов промпта; до чтения промпта — оба.

MESSAGES = {
    'header': ('gate-check (режим: {mode}): промпт {prompt}; журнал {log}',
               'gate-check (mode: {mode}): prompt {prompt}; log {log}'),
    'mode_default': ('обычный', 'default'),
    'mode_strict': ('строгий', 'strict'),
    'total': ('итог: {code}', 'result: {code}'),
    # ошибки использования (код 2)
    'file_missing': ('файл не найден: {path}', 'file not found: {path}'),
    'file_unreadable': ('не удалось прочитать {path}: {err}', 'cannot read {path}: {err}'),
    'not_utf8': ('файл не в UTF-8: {path}', 'file is not UTF-8: {path}'),
    'no_sections': ('в промпте нет разделов вида «## 1. …» (core/prompt-template.md): {path}',
                    'the prompt has no "## 1. …" sections (core/prompt-template.md): {path}'),
    'no_section4_conditional': ('схема условная (строка {line}), а раздела «## 4. Входная проверка» в промпте нет',
                                'the scheme is conditional (line {line}) but the prompt has no "## 4. Gate check" section'),
    'no_section4': ('раздела 4 в промпте нет, а строки «Схема:» с базовой или амбициозной схемой '
                    'и слов «входной проверки нет» тоже нет — неясно, был ли gate',
                    'the prompt has no section 4, no "Scheme:" line naming a baseline or ambitious scheme, '
                    'and no "no gate" statement — cannot tell whether there was a gate'),
    'no_criterion_line': ('в разделе 4 (строка {line}) нет строки «Критерий прохождения …:» и не сказано, что проверки нет',
                          'section 4 (line {line}) has no "Pass criterion …:" line and does not say there is no gate'),
    'empty_criterion': ('строка «Критерий прохождения» пуста (строка {line})',
                        'the "Pass criterion" line is empty (line {line})'),
    'no_pass_part': ('в критерии раздела 4 (строка {line}) нет условия прохождения — только обоснование или условие применимости',
                     'the section 4 criterion (line {line}) has no pass condition — only a rationale or an applicability condition'),
    # причины, по которым gate в промпте нет
    'why_scheme': ('схема «{value}», строка {line}', 'scheme "{value}", line {line}'),
    'why_section4': ('раздел 4, строка {line}: «{text}»', 'section 4, line {line}: "{text}"'),
    'why_phrase': ('строка {line}: «{text}»', 'line {line}: "{text}"'),
    # наличие
    'presence_both': ('gate есть в промпте (раздел 4, строка {p}) и в журнале (GATE, строка {j})',
                      'gate present in the prompt (section 4, line {p}) and in the log (GATE, line {j})'),
    'presence_none': ('gate отсутствует в промпте и журнале ({why})',
                      'gate absent from both prompt and log ({why})'),
    'presence_no_log': ('в промпте gate есть (раздел 4, строка {p}), а в журнале нет блока GATE (``` с первой строкой GATE){hint}',
                        'the prompt has a gate (section 4, line {p}) but the log has no GATE block (``` whose first line is GATE){hint}'),
    'stray_gate_hint': ('; строка {line} «GATE» стоит вне блока кода', '; line {line} "GATE" is outside a code fence'),
    'presence_no_prompt': ('в журнале есть блок GATE (строка {j}), а в промпте входной проверки нет ({why}) — критерий не записан до запуска',
                           'the log has a GATE block (line {j}) but the prompt has no gate ({why}) — no criterion was written before the run'),
    # критерий
    'crit_skip': ('нечего сверять: gate нет в промпте или в журнале', 'nothing to compare: no gate in the prompt or in the log'),
    'crit_unfilled': ('критерий раздела 4 (строка {p}) содержит незаполненное поле [...] — порог не задан до запуска',
                      'the section 4 criterion (line {p}) has an unfilled [...] field — no threshold was set before the run'),
    'crit_no_field': ('в блоке GATE (строка {j}) нет поля «критерий (как записан):»',
                      'the GATE block (line {j}) has no "criterion (as written):" field'),
    'crit_empty_field': ('поле «критерий» в блоке GATE пустое (строка {j})', 'the "criterion" field of the GATE block is empty (line {j})'),
    'crit_ok': ('критерий GATE (строка {j}) совпадает с разделом 4 (строка {p}): условие прохождения — посимвольно{extra}',
                'the GATE criterion (line {j}) matches section 4 (line {p}): pass condition character by character{extra}'),
    'crit_ok_app': ('; условие применимости — по числам, операторам, обозначениям, связкам и словам',
                    '; applicability condition by numbers, operators, identifiers, logic words and vocabulary'),
    'crit_ok_no_rationale': ('; обоснование в журнале опущено', '; the rationale is omitted in the log'),
    'crit_ok_strict': ('критерий GATE (строка {j}) посимвольно совпадает с разделом 4 (строка {p})',
                       'the GATE criterion (line {j}) matches section 4 (line {p}) character by character'),
    'strict_diff': ('строгий режим: критерий расходится с символа {pos}: раздел 4 (строка {p}) «{a}» ≠ GATE (строка {j}) «{b}»',
                    'strict mode: the criterion differs from character {pos}: section 4 (line {p}) "{a}" ≠ GATE (line {j}) "{b}"'),
    'pass_replace': ('условие прохождения расходится с символа {pos}: раздел 4 (строка {p}) «{a}» ≠ GATE (строка {j}) «{b}»',
                     'the pass condition differs from character {pos}: section 4 (line {p}) "{a}" ≠ GATE (line {j}) "{b}"'),
    'pass_missing': ('в GATE (строка {j}) нет части условия прохождения из раздела 4 (строка {p}): «{a}»',
                     'GATE (line {j}) lacks a part of the pass condition from section 4 (line {p}): "{a}"'),
    'pass_extra': ('в GATE (строка {j}) лишняя часть условия прохождения, которой нет в разделе 4 (строка {p}): «{b}»',
                   'GATE (line {j}) has a pass-condition part that section 4 (line {p}) lacks: "{b}"'),
    'app_tokens': ('условие применимости расходится в числах, операторах, обозначениях или связках: '
                   'раздел 4 (строка {p}) [{a}] ≠ GATE (строка {j}) [{b}]',
                   'the applicability condition differs in numbers, operators, identifiers or logic words: '
                   'section 4 (line {p}) [{a}] ≠ GATE (line {j}) [{b}]'),
    'app_words': ('в условии применимости GATE (строка {j}) есть слова, которых нет в разделе 4 (строка {p}): {words}',
                  'the applicability condition in GATE (line {j}) has words absent from section 4 (line {p}): {words}'),
    'rationale_differs': ('обоснование в GATE (строка {j}) не совпадает с разделом 4 (строка {p}): «{a}» ≠ «{b}»',
                          'the rationale in GATE (line {j}) does not match section 4 (line {p}): "{a}" ≠ "{b}"'),
    # порядок
    'order_skip_prompt': ('gate в промпте нет — порядок не проверяется', 'no gate in the prompt — order not checked'),
    'order_skip_log': ('блока GATE в журнале нет — порядок не проверяется', 'no GATE block in the log — order not checked'),
    'order_none': ('записей амбициозной ветки в журнале нет', 'the log has no ambitious-branch entries'),
    'order_ok': ('GATE (строка {j}) стоит раньше первой записи амбициозной ветки (строка {h}: «{title}»)',
                 'GATE (line {j}) comes before the first ambitious-branch entry (line {h}: "{title}")'),
    'order_fail': ('GATE (строка {j}) стоит после начала амбициозной ветки (строка {h}: «{title}»)',
                   'GATE (line {j}) comes after the ambitious branch started (line {h}: "{title}")'),
    'order_no_gate': ('амбициозная ветка начата (строка {h}: «{title}»), а блока GATE в журнале нет',
                      'the ambitious branch started (line {h}: "{title}") but the log has no GATE block'),
}

CHECK_NAMES = {'presence': ('наличие', 'presence'),
               'criterion': ('критерий', 'criterion'),
               'order': ('порядок', 'order')}


def say(lang, key, **kw):
    ru, en = MESSAGES[key]
    if lang is None:  # язык ещё неизвестен — оба
        return ru.format(**kw) + ' / ' + en.format(**kw)
    return (ru if lang == 'ru' else en).format(**kw)


class UsageError(Exception):
    """Проверку нельзя выполнить: код 2."""

    def __init__(self, key, lang=None, **kw):
        super().__init__(key)
        self.key, self.lang, self.kw = key, lang, kw


# --- Нормализация -------------------------------------------------------------

_INVISIBLE_RE = re.compile('[\u00ad\u200b\u200c\u200d\u2060\ufeff]')  # мягкий перенос, ZWSP, ZWNJ, ZWJ, WJ, BOM
_TRAILING_RE = re.compile(r'[\s.;:,!?…]+$')


def norm_ws(text):
    """NFC, без невидимых символов, любые пробельные серии -> один пробел."""
    text = _INVISIBLE_RE.sub('', unicodedata.normalize('NFC', text))
    return ' '.join(text.split())


def clip(s, width=90):
    return s if len(s) <= width else s[:width - 1] + '…'


def fragment(s, m, width=25):
    """Найденное место строки с окрестностью — для сообщения."""
    lo, hi = max(0, m.start() - width), min(len(s), m.end() + width)
    return ('…' if lo else '') + s[lo:hi].strip() + ('…' if hi < len(s) else '')


def diff_kw(a, b, width=30):
    """Номер первого несовпадающего символа и окрестность с обеих сторон."""
    k = 0
    while k < min(len(a), len(b)) and a[k] == b[k]:
        k += 1
    lo = max(0, k - width)

    def window(s):
        hi = k + width
        return ('…' if lo else '') + s[lo:hi] + ('…' if hi < len(s) else '')

    return {'pos': k + 1, 'a': window(a), 'b': window(b)}


# --- Markdown: блоки кода и заголовки -----------------------------------------

_FENCE_OPEN_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
_FENCE_CLOSE_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})\s*$')
_HEADING_RE = re.compile(r'^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$')


@dataclass
class Fence:
    line: int                                   # строка открывающего забора, с 1
    body: list = field(default_factory=list)    # [(номер строки, текст)]


@dataclass
class Heading:
    line: int
    level: int
    text: str


def scan_markdown(lines, lo=0, hi=None):
    """Блоки кода и заголовки вне блоков в lines[lo:hi]."""
    hi = len(lines) if hi is None else hi
    fences, headings, outside, open_fence = [], [], [], None
    for i in range(lo, hi):
        s = lines[i]
        if open_fence is None:
            m = _FENCE_OPEN_RE.match(s)
            if m and not (m.group(1)[0] == '`' and '`' in m.group(2)):
                open_fence = (m.group(1)[0], len(m.group(1)))
                fences.append(Fence(i + 1))
                continue
            outside.append((i + 1, s))
            m = _HEADING_RE.match(s)
            if m:
                headings.append(Heading(i + 1, len(m.group(1)), m.group(2)))
        else:
            m = _FENCE_CLOSE_RE.match(s)
            if m and m.group(1)[0] == open_fence[0] and len(m.group(1)) >= open_fence[1]:
                open_fence = None
                continue
            fences[-1].body.append((i + 1, s))
    return fences, headings, outside


def read_lines(path):
    try:
        with open(path, encoding='utf-8-sig') as f:
            return f.read().split('\n')
    except FileNotFoundError:
        raise UsageError('file_missing', path=path)
    except UnicodeDecodeError:
        raise UsageError('not_utf8', path=path)
    except OSError as e:
        raise UsageError('file_unreadable', path=path, err=e.strerror or e)


# --- Промпт -------------------------------------------------------------------

_CYRILLIC_RE = re.compile('[а-яё]', re.I)
_PROMPT_OPEN_RE = re.compile(r'^\s*<(промпт|prompt)>\s*$', re.I)
_PROMPT_CLOSE_RE = re.compile(r'^\s*</(промпт|prompt)>\s*$', re.I)
_SECTION_RE = re.compile(r'^(\d+)\.\s*(.*)$')
_LIST_MARK = r'(?:[-—–*•]\s+)?(?:\*\*)?'
_CRITERION_RE = re.compile(r'^\s*' + _LIST_MARK + r'(?:критерий\s+прохождения|pass\s+criterion)(?!\w)[^:\n]*:(.*)$', re.I)
# Поля раздела 4 по шаблону: с них начинается следующая запись, критерий кончается.
_S4_LABELS = ['действие', 'материалы', 'наблюдаемый результат', 'критерий прохождения', 'предел затрат',
              'не пройдена', 'пройдена', 'данных недостаточно', 'работа амбициозной ветки', 'исход',
              'action', 'materials', 'observable result', 'pass criterion', 'cost limit', 'passed',
              'failed', 'insufficient data', 'ambitious-branch work', 'ambitious branch work',
              'the outcome', 'outcome']
_S4_LABEL_RE = re.compile(r'^\s*' + _LIST_MARK + '(?:' + '|'.join(
    re.escape(x).replace(r'\ ', r'\s+') for x in sorted(_S4_LABELS, key=len, reverse=True)) + r')(?!\w)', re.I)
_SCHEME_RE = re.compile(r'^\s*(?:\*\*)?(?:схема|scheme)(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.*)$', re.I)
_NO_GATE_RE = re.compile(
    r'входн\w*\s+проверк\w*\s+нет|нет\s+входн\w*\s+проверк|без\s+входн\w*\s+проверк'
    r'|входн\w*\s+проверк\w*\s+не\s+(?:проводится|нужна|требуется|предусмотрена|выполняется)'
    r'|\bno\s+gate\b|\bthere\s+is\s+no\s+gate\b|\bwithout\s+a\s+gate\b|\bgate\s+check\s*:\s*none\b'
    r'|^\s*(?:нет|none|n/a)\s*(?:[.:;—–-]|$)', re.I)


def scheme_kind(value):
    v = value.strip(' *').lower()
    if v.startswith(('условн', 'conditional')):
        return 'conditional'
    if v.startswith(('базов', 'baseline')):
        return 'baseline'
    if v.startswith(('амбициозн', 'ambitious')):
        return 'ambitious'
    return None


@dataclass
class Prompt:
    path: str
    lines: list
    lang: str
    criterion: str | None = None       # текст критерия; строки через \n
    criterion_line: int | None = None  # строка «Критерий прохождения»
    no_gate_why: str = ''              # почему gate нет — для сообщения


def parse_prompt(path):
    lines = read_lines(path)
    lo, hi = 0, len(lines)
    for i, s in enumerate(lines):  # промпт внутри <промпт>…</промпт> — только он
        if _PROMPT_OPEN_RE.match(s):
            lo = i + 1
            hi = next((k for k in range(lo, len(lines)) if _PROMPT_CLOSE_RE.match(lines[k])), len(lines))
            break
    _, headings, outside = scan_markdown(lines, lo, hi)
    sections = {}  # номер -> (строка заголовка, заголовок, конец раздела — индекс строки)
    numbered = [(h, _SECTION_RE.match(h.text)) for h in headings if h.level == 2]
    numbered = [(h, m) for h, m in numbered if m]
    if not numbered:
        raise UsageError('no_sections', path=path)
    lang = 'ru' if any(_CYRILLIC_RE.search(h.text) for h, _ in numbered) else 'en'
    level2 = [h.line for h in headings if h.level <= 2]
    for h, m in numbered:
        end = next((x - 1 for x in level2 if x > h.line), hi)
        sections.setdefault(int(m.group(1)), (h.line, m.group(2), end))
    prompt = Prompt(path, lines, lang)

    def body(num):  # строки раздела вне блоков кода: [(номер, текст)]
        start, _, end = sections[num]
        return [(n, s) for n, s in outside if start < n <= end]

    if 4 in sections:
        rows = body(4)
        for idx, (n, s) in enumerate(rows):
            m = _CRITERION_RE.match(s)
            if not m:
                continue
            parts = [m.group(1).lstrip('*').strip()]
            for _, t in rows[idx + 1:]:
                if not t.strip() or _S4_LABEL_RE.match(t):
                    break
                parts.append(t.strip())
            text = '\n'.join(p for p in parts if p)
            if not norm_ws(text):
                raise UsageError('empty_criterion', lang, line=n)
            if not split_parts(text).passing:
                raise UsageError('no_pass_part', lang, line=n)
            prompt.criterion, prompt.criterion_line = text, n
            return prompt
        for n, s in rows:
            m = _NO_GATE_RE.search(s)
            if m:
                prompt.no_gate_why = say(lang, 'why_section4', line=n, text=fragment(s, m))
                return prompt
        raise UsageError('no_criterion_line', lang, line=sections[4][0])

    # Раздела 4 нет: шаблон допускает это только при неусловной схеме.
    scheme_rows = body(1) if 1 in sections else []
    scheme = next(((n, m.group(1)) for n, s in scheme_rows for m in [_SCHEME_RE.match(s)] if m), None)
    if scheme is None:
        scheme = next(((n, m.group(1)) for n, s in outside for m in [_SCHEME_RE.match(s)] if m), None)
    kind = scheme_kind(scheme[1]) if scheme else None
    if kind == 'conditional':
        raise UsageError('no_section4_conditional', lang, line=scheme[0])
    if kind in ('baseline', 'ambitious'):
        value = re.split(r'\s+[—–-]\s+|[.;]\s', scheme[1].strip(' *'), maxsplit=1)[0]
        prompt.no_gate_why = say(lang, 'why_scheme', value=value, line=scheme[0])
        return prompt
    for n, s in outside:
        m = _NO_GATE_RE.search(s)
        if m:
            prompt.no_gate_why = say(lang, 'why_phrase', line=n, text=fragment(s, m))
            return prompt
    raise UsageError('no_section4', lang)


# --- Журнал -------------------------------------------------------------------

_GATE_FIELD_RE = re.compile(
    r'^\s*(?P<label>действие|материалы|наблюдаемый\s+результат|критерий(?:\s*\(\s*как\s+записан\s*\))?'
    r'|предел\s+затрат|фактические\s+затраты|исход|следствие|action|materials|observable\s+result'
    r'|criterion(?:\s*\(\s*as\s+written\s*\))?|cost\s+limit|actual\s+cost|outcome|consequence)\s*:(?P<value>.*)$',
    re.I)
AMBITIOUS_RE = re.compile(r'амбициозн[а-яё]*[\s\-]+ветк[а-яё]*|ambitious[\s\-]+branch', re.I)


@dataclass
class GateBlock:
    line: int                                       # строка «GATE»
    criteria: list = field(default_factory=list)    # поля «критерий (как записан)»: [(строка, текст)]


@dataclass
class Journal:
    path: str
    lines: list
    gates: list                        # [GateBlock] в порядке журнала
    ambitious: list                    # [Heading] — записи амбициозной ветки
    stray_gate_lines: list             # строки «GATE» вне блоков кода


def parse_journal(path):
    lines = read_lines(path)
    fences, headings, outside = scan_markdown(lines)
    gates = []
    for f in fences:
        body = [(n, s) for n, s in f.body if s.strip()]
        if not body or body[0][1].strip() != 'GATE':
            continue
        block = GateBlock(body[0][0])
        current = None  # строки поля критерия, которое сейчас набирается
        for n, s in body[1:]:
            m = _GATE_FIELD_RE.match(s)
            if m:  # новое поле закрывает предыдущее
                current = None
                if m.group('label').lower().startswith(('критерий', 'criterion')):
                    current = [m.group('value').strip()]
                    block.criteria.append((n, current))
            elif current is not None:  # строка-продолжение поля
                current.append(s.strip())
        block.criteria = [(n, '\n'.join(x for x in rows if x)) for n, rows in block.criteria]
        gates.append(block)
    ambitious = [h for h in headings if AMBITIOUS_RE.search(h.text)]
    stray = [n for n, s in outside if s.strip() == 'GATE']
    return Journal(path, lines, gates, ambitious, stray)


# --- Сравнение критерия -------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?…])\s+(?=[«"„“(\[]?[A-ZА-ЯЁ])')
_CLAUSE_SPLIT_RE = re.compile(r';\s+')
_RATIONALE_RE = re.compile(r'^(?:обоснование|rationale|justification)\s*(?::|—|–|-)', re.I)
_INAPPLICABLE_RE = re.compile(r'неприменим|не\s+применим|не\s+применяется|inapplicable|not\s+applicable'
                              r'|does\s+not\s+apply|doesn\'t\s+apply', re.I)
_CONDITION_RE = re.compile(r'(?<!\w)(?:если|при|когда|if|when|whenever|unless)(?!\w)', re.I)
_UNFILLED_RE = re.compile(r'\[(?:\.\.\.|…)\]')


@dataclass
class Parts:
    passing: list = field(default_factory=list)        # условие прохождения — посимвольно
    applicability: list = field(default_factory=list)  # «…неприменим» — по токенам и словам
    rationale: list = field(default_factory=list)      # «Обоснование: …»


def split_parts(text):
    """Предложения и части через «;» -> три части критерия.

    Часть — условие применимости, только если в ней есть и «неприменим», и слово условия
    (если/при/if…): смешанная фраза «AUC ≥ 0.65, иначе неприменим» остаётся в посимвольной
    части. Правило одно для промпта и журнала, поэтому дословная копия всегда совпадает.
    """
    parts = Parts()
    for sentence in _SENTENCE_SPLIT_RE.split(norm_ws(text)):
        if _RATIONALE_RE.match(sentence):
            parts.rationale.append(_TRAILING_RE.sub('', sentence))
            continue
        for clause in _CLAUSE_SPLIT_RE.split(sentence):
            clause = _TRAILING_RE.sub('', clause)
            if not clause:
                continue
            if _INAPPLICABLE_RE.search(clause) and _CONDITION_RE.search(clause):
                parts.applicability.append(clause)
            else:
                parts.passing.append(clause)
    return parts


# Операторы сравнения словами -> знак. Длинные фразы раньше коротких.
_OP_WORDS = {
    '≥': ['не менее', 'не меньше', 'не ниже', 'как минимум', 'больше или равно', 'больше либо равно',
          'at least', 'no less than', 'not less than', 'no fewer than', 'not fewer than',
          'greater than or equal to', 'no lower than', 'not below'],
    '≤': ['не более', 'не больше', 'не выше', 'не превышает', 'как максимум', 'меньше или равно',
          'меньше либо равно', 'at most', 'no more than', 'not more than', 'no greater than',
          'not greater than', 'less than or equal to', 'no higher than', 'not above', 'does not exceed'],
    '<': ['меньше', 'менее', 'ниже', 'less than', 'fewer than', 'lower than', 'below'],
    '>': ['больше', 'более', 'выше', 'свыше', 'превышает', 'more than', 'greater than', 'higher than',
          'above', 'exceeds'],
    '=': ['равно', 'равен', 'равна', 'equals', 'equal to'],
    '≠': ['не равно', 'не равен', 'не равна', 'not equal to', 'does not equal'],
}
_OP_WORD_MAP = {p: sym for sym, phrases in _OP_WORDS.items() for p in phrases}
_OP_SYMBOLS = {'>=': '≥', '⩾': '≥', '≧': '≥', '≥': '≥', '<=': '≤', '⩽': '≤', '≦': '≤', '≤': '≤',
               '!=': '≠', '≠': '≠', '==': '=', '=': '=', '<': '<', '>': '>', '≈': '≈'}
_TOKEN_RE = re.compile(
    r'(?P<opw>(?<!\w)(?:' + '|'.join(re.escape(p).replace(r'\ ', r'\s+')
                                     for p in sorted(_OP_WORD_MAP, key=len, reverse=True)) + r')(?!\w))'
    r'|(?P<ops>>=|<=|!=|==|[≥≤≠⩾⩽≧≦≈<>=])'
    r'|(?P<num>(?<![\w.,])-?\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?(?: ?%)?)'
    r'|(?P<word>\w+(?:\(\w+\))?)', re.I)
_CONNECTIVES = {'и', 'или', 'либо', 'не', 'ни', 'нет', 'and', 'or', 'not', 'nor', 'no'}
# Слова, которые пересказ условия применимости может добавить без смены смысла.
_EXEMPT = {'если', 'при', 'когда', 'в', 'во', 'на', 'по', 'для', 'из', 'у', 'с', 'со', 'к', 'о', 'об', 'от',
           'то', 'это', 'чем', 'критерий', 'if', 'when', 'whenever', 'in', 'on', 'at', 'of', 'for', 'the',
           'a', 'an', 'is', 'are', 'be', 'then', 'it', 'by', 'with', 'than', 'criterion'}
_MINUS = str.maketrans({'\u2212': '-', '\u2012': '-', '\u2013': '-', '\u2010': '-'})  # минус, цифровое и короткое тире, дефис


def is_identifier(word):
    """ROC, AUC(Б), ДИ, F1, n_sessions — да; «Если», «dev», «D» — нет."""
    return len(word) >= 2 and ('(' in word or any(c.isupper() or c.isdigit() or c == '_' for c in word[1:]))


def analyse(text):
    """Значимые токены по порядку и прочие слова (для проверки «новых слов нет»)."""
    tokens, words = [], []
    for m in _TOKEN_RE.finditer(text.translate(_MINUS)):
        kind, s = m.lastgroup, m.group()
        if kind == 'opw':
            tokens.append(_OP_WORD_MAP[' '.join(s.lower().split())])
        elif kind == 'ops':
            tokens.append(_OP_SYMBOLS[s])
        elif kind == 'num':
            tokens.append(s.replace(' ', '').replace(',', '.'))
        else:
            low = s.lower().replace('ё', 'е')
            if low in _CONNECTIVES:
                tokens.append(low)
            elif is_identifier(s):
                tokens.append(s)
            else:
                words.append(low)
    return tokens, words


def compare(p_text, j_text, strict):
    """Список расхождений [(ключ сообщения, параметры)]; пустой — совпало."""
    if strict:
        a, b = norm_ws(p_text), norm_ws(j_text)
        return [] if a == b else [('strict_diff', diff_kw(a, b))]
    P, J = split_parts(p_text), split_parts(j_text)
    problems = []
    matcher = difflib.SequenceMatcher(None, P.passing, J.passing, autojunk=False)
    for tag, i1, _, j1, _ in matcher.get_opcodes():
        if tag == 'replace':
            problems.append(('pass_replace', diff_kw(P.passing[i1], J.passing[j1])))
        elif tag == 'delete':
            problems.append(('pass_missing', {'a': clip(P.passing[i1])}))
        elif tag == 'insert':
            problems.append(('pass_extra', {'b': clip(J.passing[j1])}))
        if tag != 'equal':
            break  # первого расхождения в условии прохождения достаточно
    p_tokens, p_words = analyse(' '.join(P.applicability))
    j_tokens, j_words = analyse(' '.join(J.applicability))
    if p_tokens != j_tokens:
        problems.append(('app_tokens', {'a': ' '.join(p_tokens) or '∅', 'b': ' '.join(j_tokens) or '∅'}))
    known = set(p_words) | _EXEMPT
    new = list(dict.fromkeys(w for w in j_words if w not in known))
    if new:
        problems.append(('app_words', {'words': ', '.join(new)}))
    if J.rationale and J.rationale != P.rationale:
        problems.append(('rationale_differs', {'a': clip(' '.join(P.rationale) or '∅'),
                                               'b': clip(' '.join(J.rationale))}))
    return problems


# --- Проверки -----------------------------------------------------------------

@dataclass
class Context:
    prompt: Prompt
    journal: Journal
    strict: bool
    lang: str


@dataclass
class Result:
    check: str    # presence / criterion / order / …
    status: str   # OK / FAIL / SKIP
    text: str


def check_presence(ctx):
    p, j, lang = ctx.prompt, ctx.journal, ctx.lang
    if p.criterion is not None and j.gates:
        return [Result('presence', 'OK', say(lang, 'presence_both', p=p.criterion_line, j=j.gates[0].line))]
    if p.criterion is None and not j.gates:
        return [Result('presence', 'OK', say(lang, 'presence_none', why=p.no_gate_why))]
    if p.criterion is not None:
        hint = say(lang, 'stray_gate_hint', line=j.stray_gate_lines[0]) if j.stray_gate_lines else ''
        return [Result('presence', 'FAIL', say(lang, 'presence_no_log', p=p.criterion_line, hint=hint))]
    return [Result('presence', 'FAIL', say(lang, 'presence_no_prompt', j=j.gates[0].line, why=p.no_gate_why))]


def check_criterion(ctx):
    p, j, lang = ctx.prompt, ctx.journal, ctx.lang
    if p.criterion is None or not j.gates:
        return [Result('criterion', 'SKIP', say(lang, 'crit_skip'))]
    if _UNFILLED_RE.search(p.criterion):
        return [Result('criterion', 'FAIL', say(lang, 'crit_unfilled', p=p.criterion_line))]
    results = []
    for g in j.gates:
        if not g.criteria:
            results.append(Result('criterion', 'FAIL', say(lang, 'crit_no_field', j=g.line)))
        for line, text in g.criteria:  # каждое поле критерия каждого блока GATE
            where = {'p': p.criterion_line, 'j': line}
            if not norm_ws(text):
                results.append(Result('criterion', 'FAIL', say(lang, 'crit_empty_field', **where)))
                continue
            problems = compare(p.criterion, text, ctx.strict)
            results += [Result('criterion', 'FAIL', say(lang, key, **where, **kw)) for key, kw in problems]
            if problems:
                continue
            if ctx.strict:
                results.append(Result('criterion', 'OK', say(lang, 'crit_ok_strict', **where)))
                continue
            P, J = split_parts(p.criterion), split_parts(text)
            extra = (say(lang, 'crit_ok_app') if P.applicability or J.applicability else '') + \
                    (say(lang, 'crit_ok_no_rationale') if P.rationale and not J.rationale else '')
            results.append(Result('criterion', 'OK', say(lang, 'crit_ok', extra=extra, **where)))
    return results


def check_order(ctx):
    p, j, lang = ctx.prompt, ctx.journal, ctx.lang
    if p.criterion is None:
        return [Result('order', 'SKIP', say(lang, 'order_skip_prompt'))]
    first = j.ambitious[0] if j.ambitious else None
    if not j.gates:
        if first:
            return [Result('order', 'FAIL', say(lang, 'order_no_gate', h=first.line, title=clip(first.text, 70)))]
        return [Result('order', 'SKIP', say(lang, 'order_skip_log'))]
    if first is None:
        return [Result('order', 'OK', say(lang, 'order_none'))]
    key = 'order_ok' if j.gates[0].line < first.line else 'order_fail'
    return [Result('order', 'OK' if key == 'order_ok' else 'FAIL',
                   say(lang, key, j=j.gates[0].line, h=first.line, title=clip(first.text, 70)))]


# Новая проверка — функция Context -> [Result], добавленная сюда (работа 5 ТЗ v0.2: метки времени).
CHECKS = (check_presence, check_criterion, check_order)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # кириллица и «≥» не должны падать на чужой локали
        if (getattr(stream, 'encoding', '') or '').lower().replace('-', '') != 'utf8' and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(
        prog='gate-check.py',
        description='Check that the gate criterion in the log matches section 4 of the prompt and that '
                    'GATE precedes the ambitious branch. Exit: 0 match, 1 discrepancy, 2 usage error. '
                    '/ Сверка критерия gate в журнале с разделом 4 промпта и порядка GATE.')
    ap.add_argument('prompt', help='worker prompt / промпт воркера')
    ap.add_argument('log', help='evidence log / журнал воркера')
    ap.add_argument('--strict', action='store_true',
                    help='whole criterion character by character after whitespace normalisation '
                         '/ весь критерий посимвольно')
    args = ap.parse_args(argv)
    lang = None
    try:
        prompt = parse_prompt(args.prompt)
        lang = prompt.lang
        journal = parse_journal(args.log)
    except UsageError as e:
        print('ERROR', say(e.lang or lang, e.key, **e.kw), file=sys.stderr)
        return EXIT_USAGE
    ctx = Context(prompt, journal, args.strict, lang)
    results = [r for check in CHECKS for r in check(ctx)]
    mode = say(lang, 'mode_strict' if args.strict else 'mode_default')
    print(say(lang, 'header', mode=mode, prompt=args.prompt, log=args.log))
    width = max(len(v[0 if lang == 'ru' else 1]) for v in CHECK_NAMES.values())
    for r in results:
        name = CHECK_NAMES.get(r.check, (r.check, r.check))[0 if lang == 'ru' else 1]
        print(f'{r.status:<5} {name:<{width}}  {r.text}')
    code = EXIT_FAIL if any(r.status == 'FAIL' for r in results) else EXIT_OK
    print(say(lang, 'total', code=code))
    return code


if __name__ == '__main__':
    sys.exit(main())
