"""Тесты tools/gate-check.py.

Запуск из корня репозитория:  python3 -I -m unittest discover -s tools/tests

Русские случаи строятся на реальном прогоне 2026-10-21 (evals/runs/2026-10-21-gate,
файлы читаются из репозитория и меняются только во временных копиях), английские —
на синтетических фикстурах tools/tests/fixtures/en, повторяющих L2-A и T3-A.
Каждый сдвиг проверяется и по коду выхода, и по строке расхождения в выводе.
"""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPT = REPO / 'tools' / 'gate-check.py'
RUN = REPO / 'evals' / 'runs' / '2026-10-21-gate'
EN = HERE / 'fixtures' / 'en'

# Для каждого языка: реальные или синтетические файлы и якоря правок (каждый якорь
# встречается в своём файле ровно один раз — replaced() это проверяет).
CASES = {
    'ru': {
        'prompt': RUN / 'L2-A' / 'prompt-to-worker.md',
        'log': RUN / 'L2-A' / 'journal.md',
        'base_prompt': RUN / 'T3-A' / 'prompt-to-worker.md',
        'base_log': RUN / 'T3-A' / 'journal.md',
        'log_threshold': '(как записан): ROC AUC(Б) ≥ 0.65',
        'prompt_threshold': 'подлежит): ROC AUC(Б) ≥ 0.65',
        'second_conjunct': ' и нижняя граница 95% ДИ разности ROC AUC(Б) − ROC AUC(А) > 0;',
        'bound': 'нижняя граница 95% ДИ разности ROC',
        'bound_new': 'верхняя граница 95% ДИ разности ROC',
        'pass_end': 'ROC AUC(А) > 0;',
        'escape': ' или ROC AUC(Б) ≥ 0.60',
        'metric': '(как записан): ROC AUC(Б)',
        'metric_new': '(как записан): PR AUC(Б)',
        'app': 'при < 100 положительных в dev-популяции среза — неприменим',
        'app_number': ('при < 100 положительных', 'при < 50 положительных'),
        'app_operator': ('при < 100 положительных', 'при ≤ 100 положительных'),
        'app_word': ('при < 100 положительных', 'при < 100 отрицательных'),
        'app_dropped_qualifier': ('при < 100 положительных в', 'при < 100 в'),
        'wrap': ('ROC AUC(Б) ≥ 0.65 и нижняя', 'ROC AUC(Б)\u00a0≥ 0.65\n                     и   ниж\u200bняя'),
        'rationale': ('0.65 — нижний уровень', '0.60 — нижний уровень'),
        'criterion_label': 'критерий (как записан):',
        'criterion_label_new': 'порог:',
        'prompt_label': 'Критерий прохождения (зафиксирован, пересмотру не подлежит):',
        'prompt_label_new': 'Порог:',
        'section4_heading': '## 4. Входная проверка\n',
        'section5_heading': '## 5. Подход и этапы',
        'section4_none': '## 4. Входная проверка\nНет: схема базовая.\n\n',
        'gate_heading': '## 01:32–01:33 — этап 1',
        'gate_end': 'Этап 3 не выполняется.\n```\n',
        'ambitious': '## 01:56 — этап 3, амбициозная ветка\n- запуск срезов D ∈ {3, 7, 14, 30}\n\n',
        'ambitious_upper': '## 01:31 — ЭТАП 3, АМБИЦИОЗНАЯ ВЕТКА\n- запуск\n\n',
        'ambitious_inflected': '## 01:31 — этап 3: работа амбициозной ветки\n- запуск\n\n',
        'base_scheme': [('Схема: базовая — планка:', 'Планка:')],
        'base_phrase': [(' (схема базовая, входной проверки нет)', '')],
        'msg_none': 'gate отсутствует в промпте и журнале',
        'msg_crit_ok': 'совпадает с разделом 4',
        'msg_pass': 'условие прохождения расходится',
        'msg_missing': 'нет части условия прохождения',
        'msg_extra': 'лишняя часть условия прохождения',
        'msg_app': 'условие применимости расходится',
        'msg_app_words': 'есть слова, которых нет в разделе 4: ',
        'msg_rationale': 'обоснование в GATE',
        'msg_order_fail': 'стоит после начала амбициозной ветки',
        'msg_order_ok': 'стоит раньше первой записи амбициозной ветки',
        'msg_no_log_gate': 'в журнале нет блока GATE',
        'msg_stray': 'вне блока кода',
        'msg_no_prompt_gate': 'критерий не записан до запуска',
        'msg_no_field': 'нет поля «критерий (как записан):»',
        'msg_unfilled': 'незаполненное поле [...]',
        'msg_strict': 'строгий режим: критерий расходится',
        'msg_conditional': 'схема условная',
        'msg_no_criterion_line': 'нет строки «Критерий прохождения',
        'msg_no_section4': 'неясно, был ли gate',
        'msg_section4_none': 'раздел 4, строка',
        'msg_phrase': 'входной проверки нет',
    },
    'en': {
        'prompt': EN / 'prompt-conditional.md',
        'log': EN / 'log-conditional.md',
        'base_prompt': EN / 'prompt-baseline.md',
        'base_log': EN / 'log-baseline.md',
        'log_threshold': '(as written): ROC AUC(B) ≥ 0.65',
        'prompt_threshold': 'revision): ROC AUC(B) ≥ 0.65',
        'second_conjunct': ' and the lower bound of the 95% CI of the difference ROC AUC(B) − ROC AUC(A) > 0;',
        'bound': 'the lower bound of the 95% CI',
        'bound_new': 'the upper bound of the 95% CI',
        'pass_end': 'ROC AUC(A) > 0;',
        'escape': ' or ROC AUC(B) ≥ 0.60',
        'metric': '(as written): ROC AUC(B)',
        'metric_new': '(as written): PR AUC(B)',
        'app': "inapplicable if < 100 positive labels in the slice's dev population",
        'app_number': ('if < 100 positive', 'if < 50 positive'),
        'app_operator': ('if < 100 positive', 'if ≤ 100 positive'),
        'app_word': ('if < 100 positive labels', 'if < 100 negative labels'),
        'app_dropped_qualifier': ('if < 100 positive labels', 'if < 100 labels'),
        'wrap': ('ROC AUC(B) ≥ 0.65 and the lower', 'ROC AUC(B)\u00a0≥ 0.65\n                        and   the lower'),
        'rationale': ('0.65 is the lowest', '0.60 is the lowest'),
        'criterion_label': 'criterion (as written):',
        'criterion_label_new': 'threshold:',
        'prompt_label': 'Pass criterion (fixed, not subject to revision):',
        'prompt_label_new': 'Threshold:',
        'section4_heading': '## 4. Gate check\n',
        'section5_heading': '## 5. Approach and stages',
        'section4_none': '## 4. Gate check\nNone: the scheme is baseline.\n\n',
        'gate_heading': '## 01:32–01:33 — stage 1',
        'gate_end': 'Stage 3 is not run.\n```\n',
        'ambitious': '## 01:56 — stage 3, ambitious branch\n- slices D ∈ {3, 7, 14, 30}\n\n',
        'ambitious_upper': '## 01:31 — STAGE 3, AMBITIOUS BRANCH\n- run\n\n',
        'ambitious_inflected': '## 01:31 — stage 3: ambitious-branch work\n- run\n\n',
        'base_scheme': [('Scheme: baseline — bar:', 'Bar:')],
        'base_phrase': [(' (baseline scheme, no gate check)', '')],
        'msg_none': 'gate absent from both prompt and log',
        'msg_crit_ok': 'matches section 4',
        'msg_pass': 'the pass condition differs',
        'msg_missing': 'lacks a part of the pass condition',
        'msg_extra': 'has a pass-condition part that section 4',
        'msg_app': 'the applicability condition differs',
        'msg_app_words': 'has words absent from section 4',
        'msg_rationale': 'the rationale in GATE',
        'msg_order_fail': 'comes after the ambitious branch started',
        'msg_order_ok': 'comes before the first ambitious-branch entry',
        'msg_no_log_gate': 'the log has no GATE block',
        'msg_stray': 'outside a code fence',
        'msg_no_prompt_gate': 'no criterion was written before the run',
        'msg_no_field': 'has no "criterion (as written):" field',
        'msg_unfilled': 'unfilled [...] field',
        'msg_strict': 'strict mode: the criterion differs',
        'msg_conditional': 'the scheme is conditional',
        'msg_no_criterion_line': 'has no "Pass criterion',
        'msg_no_section4': 'cannot tell whether there was a gate',
        'msg_section4_none': 'section 4, line',
        'msg_phrase': 'no gate',
    },
}


def run(prompt, log, *flags):
    proc = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), str(prompt), str(log), *flags],
                          capture_output=True, text=True, encoding='utf-8', timeout=60)
    return proc.returncode, proc.stdout + proc.stderr


def replaced(text, pairs):
    for old, new in pairs:
        if text.count(old) != 1:
            raise AssertionError(f'якорь встречается {text.count(old)} раз, нужен 1: {old!r}')
        text = text.replace(old, new)
    return text


def load_module():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('gate_check', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GateCheckCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def write(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding='utf-8')
        return path

    def variant(self, src, pairs, name):
        return self.write(name, replaced(src.read_text(encoding='utf-8'), pairs))

    def expect(self, prompt, log, code, *needles, flags=()):
        got, out = run(prompt, log, *flags)
        where = f'[{getattr(self, "lang", "?")}] {prompt} {log} {" ".join(flags)}\n{out}'
        self.assertEqual(got, code, where)
        for needle in needles:
            self.assertIn(needle, out, where)
        return out

    def each_lang(self):
        # Язык — в сообщении о провале (self.lang), без subTest: тот плохо дружит с генератором.
        for lang, c in CASES.items():
            self.lang = lang
            yield lang, c

    def log_with_criterion(self, c, new_text):
        """Журнал, где поле критерия (строка и её продолжения) заменено на new_text."""
        lines = c['log'].read_text(encoding='utf-8').split('\n')
        i = next(k for k, s in enumerate(lines) if s.startswith(c['criterion_label']))
        j = i + 1
        while lines[j].startswith(' '):
            j += 1
        lines[i:j] = [c['criterion_label'] + ' ' + new_text]
        return self.write('log-verbatim.md', '\n'.join(lines))

    def prompt_criterion(self, c):
        line = next(s for s in c['prompt'].read_text(encoding='utf-8').split('\n') if s.startswith(c['prompt_label']))
        return line[len(c['prompt_label']):].strip()


class RequiredCases(GateCheckCase):
    """Минимум из ТЗ: пункты 1–8."""

    def test_1_matching_prompt_and_log_exit_0(self):
        for _, c in self.each_lang():
            self.expect(c['prompt'], c['log'], 0, 'OK')

    def test_2_threshold_shifted_by_001_exit_1_with_discrepancy_line(self):
        for _, c in self.each_lang():
            old = c['log_threshold']
            log = self.variant(c['log'], [(old, old.replace('0.65', '0.66'))], 'log.md')
            out = self.expect(c['prompt'], log, 1, c['msg_pass'])
            line = next(s for s in out.splitlines() if s.startswith('FAIL'))
            self.assertIn('0.65', line)
            self.assertIn('0.66', line)

    def test_2b_threshold_shifted_in_prompt_exit_1(self):
        for _, c in self.each_lang():
            old = c['prompt_threshold']
            prompt = self.variant(c['prompt'], [(old, old.replace('0.65', '0.64'))], 'prompt.md')
            self.expect(prompt, c['log'], 1, c['msg_pass'], '0.64')

    def test_3a_operator_shifted_exit_1(self):
        for _, c in self.each_lang():
            old = c['log_threshold']
            log = self.variant(c['log'], [(old, old.replace('≥', '>'))], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_pass'])

    def test_3b_second_part_of_condition_removed_exit_1(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['second_conjunct'], ';')], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_pass'])

    def test_4_gate_after_ambitious_heading_exit_1_before_exit_0(self):
        for _, c in self.each_lang():
            text = c['log'].read_text(encoding='utf-8')
            before = self.write('before.md', replaced(text, [(c['gate_heading'], c['ambitious'] + c['gate_heading'])]))
            self.expect(c['prompt'], before, 1, c['msg_order_fail'])
            after = self.write('after.md', text + '\n' + c['ambitious'])
            self.expect(c['prompt'], after, 0, c['msg_order_ok'])

    def test_5_real_l2a_of_2026_10_21_exit_0(self):
        c = CASES['ru']
        self.assertTrue(c['prompt'].is_file() and c['log'].is_file(), 'нет файлов прогона L2-A в репозитории')
        self.expect(c['prompt'], c['log'], 0, 'OK    наличие', 'OK    критерий', 'обоснование в журнале опущено')

    def test_6_real_t3a_without_gate_exit_0(self):
        c = CASES['ru']
        self.expect(c['base_prompt'], c['base_log'], 0, 'gate отсутствует в промпте и журнале')

    def test_7_english_fields_same_outcomes(self):
        # Все остальные тесты прогоняются для обоих языков; здесь — сводно по основным исходам.
        c = CASES['en']
        self.expect(c['prompt'], c['log'], 0)
        self.expect(c['base_prompt'], c['base_log'], 0, 'gate absent from both prompt and log')
        self.expect(c['prompt'], c['log'], 1, 'strict mode', flags=('--strict',))

    def test_8_strict_on_l2a_exit_1(self):
        # Документирует, почему режим по умолчанию не буквальный: на L2-A буква ТЗ даёт 1.
        c = CASES['ru']
        self.expect(c['prompt'], c['log'], 1, 'строгий режим: критерий расходится', '> 0; при < 100',
                    flags=('--strict',))


class CriterionShifts(GateCheckCase):
    """Каждый вид сдвига критерия даёт 1; изменения без смысла — 0."""

    def test_metric_changed(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['metric'], c['metric_new'])], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_pass'])

    def test_lower_bound_changed_to_upper(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['bound'], c['bound_new'])], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_pass'])

    def test_escape_clause_added(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['pass_end'], c['pass_end'][:-1] + c['escape'] + ';')], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_pass'])

    def test_pass_part_dropped_entirely(self):
        for _, c in self.each_lang():
            log = self.log_with_criterion(c, c['app'])
            self.expect(c['prompt'], log, 1, c['msg_missing'])

    def test_extra_pass_part_added(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['pass_end'], c['pass_end'] + c['escape'] + ';')], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_extra'])

    def test_applicability_number_changed(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [c['app_number']], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_app'])

    def test_applicability_operator_changed(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [c['app_operator']], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_app'])

    def test_applicability_removed(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['app'], '')], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_app'], '∅')

    def test_applicability_word_substituted(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [c['app_word']], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_app_words'].split(':')[0])

    def test_known_gap_dropped_qualifier_only_strict_catches(self):
        # Известный предел режима по умолчанию (описан в docstring): пересказ условия
        # применимости, который только выбрасывает уточнение, не ловится; --strict ловит.
        for _, c in self.each_lang():
            log = self.variant(c['log'], [c['app_dropped_qualifier']], 'log.md')
            self.expect(c['prompt'], log, 0)
            self.expect(c['prompt'], log, 1, flags=('--strict',))

    def test_whitespace_and_line_wrap_only_exit_0(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [c['wrap']], 'log.md')
            self.expect(c['prompt'], log, 0)

    def test_verbatim_copy_with_rationale_exit_0_in_both_modes(self):
        for _, c in self.each_lang():
            log = self.log_with_criterion(c, self.prompt_criterion(c))
            self.expect(c['prompt'], log, 0)
            self.expect(c['prompt'], log, 0, flags=('--strict',))

    def test_rationale_present_but_altered_exit_1(self):
        for _, c in self.each_lang():
            old, new = c['rationale']
            log = self.log_with_criterion(c, self.prompt_criterion(c).replace(old, new))
            self.expect(c['prompt'], log, 1, c['msg_rationale'])

    def test_second_gate_block_with_shift_exit_1(self):
        for _, c in self.each_lang():
            text = c['log'].read_text(encoding='utf-8')
            start = text.index('```\nGATE\n')
            end = text.index('```\n', start + 4) + 4
            block = text[start:end].replace(c['log_threshold'], c['log_threshold'].replace('0.65', '0.66'))
            log = self.write('log.md', text + '\n' + block)
            out = self.expect(c['prompt'], log, 1, c['msg_pass'])
            lines = out.splitlines()
            self.assertEqual(sum(s.startswith('OK') and c['msg_crit_ok'] in s for s in lines), 1, out)
            self.assertEqual(sum(s.startswith('FAIL') for s in lines), 1, out)

    def test_unfilled_threshold_exit_1(self):
        for _, c in self.each_lang():
            prompt = self.variant(c['prompt'], [(c['prompt_threshold'], c['prompt_threshold'].replace('0.65', '[...]'))],
                                  'prompt.md')
            log = self.variant(c['log'], [(c['log_threshold'], c['log_threshold'].replace('0.65', '[...]'))], 'log.md')
            self.expect(prompt, log, 1, c['msg_unfilled'])


class CriterionLayout(GateCheckCase):
    """Разбор критерия на части в промптах, собранных в тесте."""

    PROMPT = {'ru': '## 1. Цель и результат\nСхема: условная — планка: …\n\n## 4. Входная проверка\n'
                    'Критерий прохождения (зафиксирован, пересмотру не подлежит): {criterion}\n'
                    'Предел затрат: 10 минут.\n\n## 5. Подход и этапы\n…\n',
              'en': '## 1. Goal and outcome\nScheme: conditional — bar: …\n\n## 4. Gate check\n'
                    'Pass criterion (fixed, not subject to revision): {criterion}\n'
                    'Cost limit: 10 minutes.\n\n## 5. Approach and stages\n…\n'}
    LOG = {'ru': '## 10:00 — этап 1, входная проверка\n\n```\nGATE\nкритерий (как записан): {criterion}\n'
                 'исход:               не пройдена\n```\n',
           'en': '## 10:00 — stage 1, gate check\n\n```\nGATE\ncriterion (as written): {criterion}\n'
                 'outcome:                failed\n```\n'}

    def pair(self, lang, prompt_criterion, log_criterion):
        self.lang = lang
        return (self.write('prompt.md', self.PROMPT[lang].format(criterion=prompt_criterion)),
                self.write('log.md', self.LOG[lang].format(criterion=log_criterion)))

    def test_clause_with_inapplicable_but_no_condition_word_stays_literal(self):
        # «…, иначе критерий неприменим» без «если/при» — часть условия прохождения, пересказ ловится.
        cases = {'ru': ('Доля верных ответов ≥ 0.8 на всех трёх наборах, иначе критерий неприменим.',
                        'Доля верных ответов ≥ 0.8 на одном наборе, иначе критерий неприменим'),
                 'en': ('Accuracy ≥ 0.8 on all three sets, otherwise the criterion is inapplicable.',
                        'Accuracy ≥ 0.8 on one set, otherwise the criterion is inapplicable')}
        for lang, (p_text, j_text) in cases.items():
            prompt, log = self.pair(lang, p_text, j_text)
            self.expect(prompt, log, 1, CASES[lang]['msg_pass'])
            prompt, log = self.pair(lang, p_text, p_text)
            self.expect(prompt, log, 0)

    def test_multiline_prompt_criterion_with_rationale_on_its_own_line(self):
        cases = {'ru': ('F1 ≥ 0.80 на dev.\nОбоснование: ниже — хуже текущего правила.\n'
                        'Если в dev меньше 50 примеров, критерий неприменим.',
                        'F1 ≥ 0.80 на dev; при < 50 примеров в dev — неприменим'),
                 'en': ('F1 ≥ 0.80 on dev.\nRationale: below that, worse than the current rule.\n'
                        'If dev has fewer than 50 examples, the criterion is inapplicable.',
                        'F1 ≥ 0.80 on dev; inapplicable if dev has < 50 examples')}
        for lang, (p_text, j_text) in cases.items():
            prompt, log = self.pair(lang, p_text, j_text)
            self.expect(prompt, log, 0)
            prompt, log = self.pair(lang, p_text, j_text.replace('0.80', '0.79'))
            self.expect(prompt, log, 1, CASES[lang]['msg_pass'])

    def test_criterion_without_pass_condition_is_usage_error(self):
        cases = {'ru': 'Если в dev меньше 50 примеров, критерий неприменим.',
                 'en': 'If dev has fewer than 50 examples, the criterion is inapplicable.'}
        for lang, text in cases.items():
            prompt, log = self.pair(lang, text, text)
            self.expect(prompt, log, 2, 'ERROR')


class PresenceAndOrder(GateCheckCase):
    def test_gate_in_prompt_but_not_in_log_exit_1(self):
        for _, c in self.each_lang():
            self.expect(c['prompt'], c['base_log'], 1, c['msg_no_log_gate'])

    def test_gate_block_without_fence_exit_1_with_hint(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [('```\nGATE\n', 'GATE\n'), (c['gate_end'], c['gate_end'][:-4])], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_no_log_gate'], c['msg_stray'])

    def test_gate_in_log_but_not_in_prompt_exit_1(self):
        for _, c in self.each_lang():
            self.expect(c['base_prompt'], c['log'], 1, c['msg_no_prompt_gate'])

    def test_gate_block_without_criterion_field_exit_1(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['criterion_label'], c['criterion_label_new'])], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_no_field'])

    def test_section4_says_no_gate_exit_0(self):
        for _, c in self.each_lang():
            prompt = self.variant(c['base_prompt'], [(c['section5_heading'], c['section4_none'] + c['section5_heading'])],
                                  'prompt.md')
            self.expect(prompt, c['base_log'], 0, c['msg_none'], c['msg_section4_none'])

    def test_no_scheme_line_but_no_gate_phrase_exit_0(self):
        for _, c in self.each_lang():
            prompt = self.variant(c['base_prompt'], c['base_scheme'], 'prompt.md')
            self.expect(prompt, c['base_log'], 0, c['msg_none'], c['msg_phrase'])

    def test_ambitious_heading_case_insensitive(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['gate_heading'], c['ambitious_upper'] + c['gate_heading'])], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_order_fail'])

    def test_ambitious_heading_other_word_form_counts(self):
        for _, c in self.each_lang():
            log = self.variant(c['log'], [(c['gate_heading'], c['ambitious_inflected'] + c['gate_heading'])], 'log.md')
            self.expect(c['prompt'], log, 1, c['msg_order_fail'])

    def test_ambitious_heading_inside_code_fence_ignored(self):
        for _, c in self.each_lang():
            fenced = '```\n' + c['ambitious'].strip() + '\n```\n\n'
            log = self.variant(c['log'], [(c['gate_heading'], fenced + c['gate_heading'])], 'log.md')
            self.expect(c['prompt'], log, 0)

    def test_ambitious_branch_without_gate_exit_1(self):
        for _, c in self.each_lang():
            log = self.write('log.md', c['base_log'].read_text(encoding='utf-8') + '\n' + c['ambitious'])
            self.expect(c['prompt'], log, 1, c['msg_no_log_gate'])


class UsageErrors(GateCheckCase):
    def test_missing_files_exit_2(self):
        c = CASES['ru']
        self.expect(self.tmp / 'nope.md', c['log'], 2, 'ERROR')
        self.expect(c['prompt'], self.tmp / 'nope.md', 2, 'ERROR', 'nope.md')

    def test_not_a_prompt_exit_2(self):
        c = CASES['ru']
        self.expect(c['log'], c['log'], 2, 'ERROR')

    def test_not_utf8_exit_2(self):
        bad = self.tmp / 'latin1.md'
        bad.write_bytes('## 1. Цель'.encode('cp1251'))
        self.expect(bad, CASES['ru']['log'], 2, 'UTF-8')

    def test_conditional_scheme_without_section4_exit_2(self):
        for _, c in self.each_lang():
            prompt = self.variant(c['prompt'], [(c['section4_heading'], '')], 'prompt.md')
            self.expect(prompt, c['log'], 2, c['msg_conditional'])

    def test_section4_without_criterion_line_exit_2(self):
        for _, c in self.each_lang():
            prompt = self.variant(c['prompt'], [(c['prompt_label'], c['prompt_label_new'])], 'prompt.md')
            self.expect(prompt, c['log'], 2, c['msg_no_criterion_line'])

    def test_no_section4_no_scheme_no_statement_exit_2(self):
        for _, c in self.each_lang():
            prompt = self.variant(c['base_prompt'], c['base_scheme'] + c['base_phrase'], 'prompt.md')
            self.expect(prompt, c['base_log'], 2, c['msg_no_section4'])


class Tokens(unittest.TestCase):
    """Разбор условия применимости: слова-операторы, знаки, числа, обозначения."""

    @classmethod
    def setUpClass(cls):
        cls.gc = load_module()

    def tokens(self, text):
        return self.gc.analyse(text)[0]

    def test_operator_words_equal_symbols(self):
        pairs = [('меньше 100', '< 100'), ('менее 100', '< 100'), ('не менее 0.65', '≥ 0.65'),
                 ('не более 5%', '≤ 5 %'), ('fewer than 100', '< 100'), ('at least 0.65', '>= 0.65'),
                 ('no more than 3', '<= 3'), ('больше 0', '> 0')]
        for words, symbols in pairs:
            with self.subTest(words=words):
                self.assertEqual(self.tokens(words), self.tokens(symbols))

    def test_different_operators_differ(self):
        self.assertNotEqual(self.tokens('меньше 100'), self.tokens('не более 100'))
        self.assertNotEqual(self.tokens('< 100'), self.tokens('≤ 100'))

    def test_signs_numbers_identifiers(self):
        self.assertEqual(self.tokens('разность > −0.01'), ['>', '-0.01'])
        self.assertEqual(self.tokens('AUC(Б) − AUC(А) > 0'), ['AUC(Б)', 'AUC(А)', '>', '0'])
        self.assertEqual(self.tokens('F1 ≥ 0,8 и n_sessions > 3'), ['F1', '≥', '0.8', 'и', 'n_sessions', '>', '3'])
        self.assertEqual(self.tokens('Если в dev-популяции нет данных'), ['нет'])

    def test_words_inside_longer_words_are_not_operators(self):
        self.assertEqual(self.tokens('наиболее вышеуказанный нижняя'), [])


if __name__ == '__main__':
    unittest.main()
