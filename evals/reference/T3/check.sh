#!/usr/bin/env bash
# Эталон T3 одной командой, с чистого клона: bash evals/reference/T3/check.sh
# Нужны только bash, git (для git apply) и Node.js 20. Работает во временной копии
# фикстуры и удаляет её; репозиторий не меняет. Код выхода 0 — все ожидания выполнены.
#
# Порядок как в журнале: воспроизведение → новый тест падает на исходном коде →
# фикс → все тесты зелёные → вывод open-screen для devices/ не изменился →
# граничный ввод не бросает → скрытый оракул 9/9 (на исходном коде 5/9).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
FIXTURE="$ROOT/evals/runs/2026-10-21-gate/fixtures/t3-acme-settings"
HIDDEN="$ROOT/evals/runs/2026-10-21-gate/fixtures/hidden/t3-hidden.test.js"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
REPO="$WORK/repo"
cp -r "$FIXTURE" "$REPO"
cd "$REPO" || exit 2

fails=0
expect() {  # expect <название> <ожидаемый код: 0 | nonzero> <фактический код>
  local ok=0
  if [ "$2" = 0 ]; then [ "$3" = 0 ] && ok=1; else [ "$3" != 0 ] && ok=1; fi
  if [ "$ok" = 1 ]; then echo "  OK   $1 (exit $3)"; else echo "  FAIL $1 (exit $3, ожидался $2)"; fails=$((fails + 1)); fi
}
tap() { grep -E '^(ok|not ok|# (tests|pass|fail))|^  error:' | sed "s|$REPO/||g"; }

echo "== 1. Воспроизведение на исходном коде: locale de, pt, fil, по 10 запусков"
for loc in de pt fil; do
  crashed=0
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    node -e "require('./src/app').openScreen('settings', {...require('./devices/galaxy-s21-de-de.json'), locale: '$loc'})" \
      2>"$WORK/err.txt" || crashed=$((crashed + 1))
  done
  echo "  locale=$loc: падений $crashed из 10; $(grep -m1 -o 'TypeError.*' "$WORK/err.txt"); $(grep -m1 -o 'at regionOf ([^)]*)' "$WORK/err.txt" | sed "s|$REPO/||")"
  [ "$crashed" = 10 ] || { echo "  FAIL не воспроизводится детерминированно"; fails=$((fails + 1)); }
done
for f in devices/*.json; do node bin/open-screen.js settings "$f" >"$WORK/before-$(basename "$f")"; done

echo "== 2. Новый тест поверх исходного кода — должен упасть той же TypeError"
cp "$HERE/test/settings-locale-without-region.test.js" test/
npm test >"$WORK/t2.txt" 2>&1; code=$?
tap <"$WORK/t2.txt"
expect "новые тесты падают до фикса" nonzero "$code"
grep -q "reading 'toUpperCase'" "$WORK/t2.txt" || { echo "  FAIL причина падения не та"; fails=$((fails + 1)); }

echo "== 3. Фикс (fix.diff) и полный npm test"
git apply "$HERE/fix.diff"; expect "git apply fix.diff" 0 $?
npm test >"$WORK/t3.txt" 2>&1; code=$?
tap <"$WORK/t3.txt"
expect "npm test после фикса" 0 "$code"

echo "== 4. open-screen settings для devices/*.json до и после фикса"
for f in devices/*.json; do node bin/open-screen.js settings "$f" >"$WORK/after-$(basename "$f")"; done
same=0
for f in devices/*.json; do cmp -s "$WORK/before-$(basename "$f")" "$WORK/after-$(basename "$f")" && same=$((same + 1)); done
echo "  совпадают побайтно: $same из 3"
[ "$same" = 3 ] || fails=$((fails + 1))

echo "== 5. Граничный ввод (раздел 6 промпта T3-A): не бросает исключений"
node -e "
const { openScreen } = require('./src/app');
const g = require('./devices/galaxy-s21-de-de.json');
let bad = 0;
for (const locale of ['pt_BR', 'zh-Hant', 'zh-Hant-TW', 'es-419', 'DE', '']) {
  try { console.log('  ' + JSON.stringify(locale) + ' -> ' + JSON.stringify(openScreen('settings', { ...g, locale }).sections[1].rows.map((r) => r.value))); }
  catch (e) { bad += 1; console.log('  ' + JSON.stringify(locale) + ' THROWS ' + e.message); }
}
process.exit(bad);"
expect "граничный ввод" 0 $?

echo "== 6. Скрытый оракул t3-hidden.test.js (CWD = копия репозитория)"
node --test "$HIDDEN" >"$WORK/h1.txt" 2>&1; code=$?
tap <"$WORK/h1.txt" | grep -E '^# (tests|pass|fail)'
expect "оракул на исправленном коде (ожидается 9/9)" 0 "$code"
grep -q '^# pass 9$' "$WORK/h1.txt" || fails=$((fails + 1))
git apply -R "$HERE/fix.diff"
node --test "$HIDDEN" >"$WORK/h0.txt" 2>&1; code=$?
echo "  на исходном коде (фикс откатан, тест оставлен): $(grep -E '^# pass' "$WORK/h0.txt"), $(grep -E '^# fail' "$WORK/h0.txt")"
expect "оракул на исходном коде падает (ожидается 5/9)" nonzero "$code"

echo
if [ "$fails" = 0 ]; then echo "T3 reference: OK"; else echo "T3 reference: $fails FAIL"; fi
exit $(( fails > 0 ))
