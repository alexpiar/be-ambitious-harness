#!/usr/bin/env bash
# Мутационная проверка: ломаем парсер по-разному и смотрим, ловят ли это тесты
set -u
SRC=$1; WORK=$2
run() {
  local name=$1 expr=$2
  rm -rf "$WORK"; mkdir -p "$WORK"; cp -r "$SRC"/package.json "$SRC"/src "$SRC"/test "$SRC"/devices "$WORK"/
  perl -0pi -e "$expr" "$WORK/src/lib/locale.js"
  if cmp -s "$SRC/src/lib/locale.js" "$WORK/src/lib/locale.js"; then echo "$name: MUTATION NOT APPLIED"; return; fi
  local out; out=$(cd "$WORK" && node --test test/ 2>&1 | grep -E '^# fail')
  echo "$name: $out"
}
run "no script skip"        's/if \(SCRIPT\.test\(next\)\) next = subtags\[2\] \|\| .{2};//'
run "no numeric region"     's/\|\[0-9\]\{3\}//'
run "no uppercase region"   's/next\.toUpperCase\(\)/next/'
run "no lowercase language" 's/subtags\[0\]\.toLowerCase\(\)/subtags[0]/'
run "hyphen only"           's/split\(\/\[-_\]\/\)/split("-")/'
run "region 2-3 letters"    's/\[a-z\]\{2\}\|\[0-9\]/[a-z]{2,3}|[0-9]/'
run "no 5-8 languages"      's/\|\[a-z\]\{5,8\}//'
