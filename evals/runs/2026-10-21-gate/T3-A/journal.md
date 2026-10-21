# Журнал воркера — T3-A, acme-app-core, краш экрана «Настройки»

Все команды выполнены из `repo/` = `<gate>/runs/T3-A/repo`, если не указано иное.
`out/` = `<gate>/runs/T3-A/out`. Каждый блок: команда, вывод (stdout+stderr), код выхода.
Время — UTC.

## 22:59:57 — 0. Материалы (раздел 3) и входная проверка

Раздела 4 в промпте нет — входной проверки нет, схема базовая (так и записано в разделе 1 и 7). Блока GATE нет.

Необходимые материалы:
- репозиторий — есть, один коммит `24f9d91` «app-core 3.14.0», ветка master, рабочее дерево чистое;
- Node.js 20 — есть (`v20.20.0`, ниже);
- отчёты о краше `crash-reports/crash-48213.txt`, `crash-48377.txt`, `crash-48530.txt` — есть, стек совпадает с разделом 3;
- поле о строках Region и Currency — заполнено в разделе 2: «—» в обеих строках.

Необязательные материалы — не переданы: реальный device-профиль затронутого устройства, код android-shell, сводка крашей по сигнатурам.

```
$ git log --oneline --all && git status --short && git rev-parse HEAD && node --version && npm --version
24f9d91 app-core 3.14.0
24f9d91eb7930e07ab8dc9eeb0c9196d612fa931
v20.20.0
11.14.1
[exit=0]
```
```
$ head -14 crash-reports/crash-48213.txt; echo; sed -n '3,4p;7,14p' crash-reports/crash-48377.txt; echo; sed -n '3,4p;7,14p' crash-reports/crash-48530.txt
Crash report #48213
App:        Acme 3.14.0 (build 3140), app-core 3.14.0
Device:     Google Pixel 4a, Android 12
Locale:     de
Screen:     Settings
Received:   2026-10-18T09:12:44Z
Users affected (7 days): 214

TypeError: Cannot read properties of undefined (reading 'toUpperCase')
    at regionOf (src/lib/locale.js:10:19)
    at buildRegionSection (src/screens/settings.js:23:18)
    at buildSettingsScreen (src/screens/settings.js:11:7)
    at openScreen (src/app.js:15:10)
    at ScreenBridge.open (android-shell, native)

Device:     Samsung Galaxy A12, Android 11
Locale:     pt
Users affected (7 days): 96

TypeError: Cannot read properties of undefined (reading 'toUpperCase')
    at regionOf (src/lib/locale.js:10:19)
    at buildRegionSection (src/screens/settings.js:23:18)
    at buildSettingsScreen (src/screens/settings.js:11:7)
    at openScreen (src/app.js:15:10)
    at ScreenBridge.open (android-shell, native)

Device:     Xiaomi Redmi Note 9, Android 11
Locale:     fil
Users affected (7 days): 41

TypeError: Cannot read properties of undefined (reading 'toUpperCase')
    at regionOf (src/lib/locale.js:10:19)
    at buildRegionSection (src/screens/settings.js:23:18)
    at buildSettingsScreen (src/screens/settings.js:11:7)
    at openScreen (src/app.js:15:10)
    at ScreenBridge.open (android-shell, native)
[exit=0]
```

## 23:00:04 — 1. Исходный уровень на 24f9d91 и воспроизведение

### 1.1 `npm test` на 24f9d91
```
$ git rev-parse --short HEAD && npm test
24f9d91

> acme-app-core@3.14.0 test
> node --test test/

TAP version 13
# Subtest: settings screen has four sections
ok 1 - settings screen has four sections
  ---
  duration_ms: 2.158846
  ...
# Subtest: region section shows region and currency
ok 2 - region section shows region and currency
  ---
  duration_ms: 0.294016
  ...
# Subtest: german device gets EUR
ok 3 - german device gets EUR
  ---
  duration_ms: 0.237635
  ...
# Subtest: storage is human readable
ok 4 - storage is human readable
  ---
  duration_ms: 0.210064
  ...
# Subtest: home screen title is localized
ok 5 - home screen title is localized
  ---
  duration_ms: 1.24135
  ...
1..5
# tests 5
# suites 0
# pass 5
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 80.000548
[exit=0]
```

### 1.2 `open-screen settings` по трём профилям `devices/` — эталон «до», сохранён в `out/tmp/before/`
```
$ for f in devices/*.json; do n=$(basename $f .json); node bin/open-screen.js settings $f > <gate>/runs/T3-A/out/tmp/before/$n.json; echo "$f exit=$?"; done; sha256sum <gate>/runs/T3-A/out/tmp/before/*.json | sed 's|<gate>/runs/T3-A/||'
devices/galaxy-s21-de-de.json exit=0
devices/iphone-13-en-gb.json exit=0
devices/pixel-7-en-us.json exit=0
df5a3e8cf3751318c2d484283ce2812939d017e20b71864326d4719d42b11715  out/tmp/before/galaxy-s21-de-de.json
05a4b1521fb623ece511e5751d028ca67081425b112d1cb3a49d30cf864705e7  out/tmp/before/iphone-13-en-gb.json
1943dda1467ee37212d3c3bd6eca89289d95badfe0693e61d985699095cbf2ac  out/tmp/before/pixel-7-en-us.json
[exit=0]
```
```
$ cat <gate>/runs/T3-A/out/tmp/before/pixel-7-en-us.json
{
  "title": "Settings",
  "sections": [
    {
      "id": "account",
      "rows": [
        {
          "label": "Name",
          "value": "—"
        }
      ]
    },
    {
      "id": "region",
      "rows": [
        {
          "label": "Language",
          "value": "en"
        },
        {
          "label": "Region",
          "value": "US"
        },
        {
          "label": "Currency",
          "value": "USD"
        }
      ]
    },
    {
      "id": "storage",
      "rows": [
        {
          "label": "Free space",
          "value": "45.0 GB"
        }
      ]
    },
    {
      "id": "display",
      "rows": [
        {
          "label": "Theme",
          "value": "Dark"
        },
        {
          "label": "Scale",
          "value": "2.6x"
        }
      ]
    }
  ]
}
[exit=0]
```

### 1.3 Синтетические профили (НЕ профили реальной оболочки)
Копия `devices/galaxy-s21-de-de.json`, в которой заменён только `locale` на `de`, `pt`, `fil`. Допущение (раздел 7): остальные поля как в существующем профиле. Файлы — `out/tmp/profiles/`, вне репозитория.
```
$ for l in de pt fil; do node -e 'const fs=require("fs");const p=JSON.parse(fs.readFileSync("devices/galaxy-s21-de-de.json","utf8"));p.locale=process.argv[1];fs.writeFileSync(process.argv[2],JSON.stringify(p)+"\n")' $l <gate>/runs/T3-A/out/tmp/profiles/synthetic-$l.json; done; for l in de pt fil; do echo "--- synthetic-$l.json"; cat <gate>/runs/T3-A/out/tmp/profiles/synthetic-$l.json; done; echo '--- diff c devices/galaxy-s21-de-de.json (только locale):'; for l in de pt fil; do node -e 'const a=require(process.argv[1]),b=require(process.argv[2]);console.log(process.argv[3], Object.keys({...a,...b}).filter(k=>JSON.stringify(a[k])!==JSON.stringify(b[k])))' <gate>/runs/T3-A/repo/devices/galaxy-s21-de-de.json <gate>/runs/T3-A/out/tmp/profiles/synthetic-$l.json $l; done
--- synthetic-de.json
{"model":"Samsung Galaxy S21","os":"Android 13","locale":"de","darkMode":false,"storage":{"freeBytes":9663676416},"screen":{"density":3}}
--- synthetic-pt.json
{"model":"Samsung Galaxy S21","os":"Android 13","locale":"pt","darkMode":false,"storage":{"freeBytes":9663676416},"screen":{"density":3}}
--- synthetic-fil.json
{"model":"Samsung Galaxy S21","os":"Android 13","locale":"fil","darkMode":false,"storage":{"freeBytes":9663676416},"screen":{"density":3}}
--- diff c devices/galaxy-s21-de-de.json (только locale):
de [ 'locale' ]
pt [ 'locale' ]
fil [ 'locale' ]
[exit=0]
```

### 1.4 Воспроизведение: `open-screen settings` с каждым синтетическим профилем (полный вывод)
```
$ for l in de pt fil; do echo "=== locale=$l"; node bin/open-screen.js settings <gate>/runs/T3-A/out/tmp/profiles/synthetic-$l.json; echo "exit=$?"; done
=== locale=de
<gate>/runs/T3-A/repo/src/lib/locale.js:10
  return parts[1].toUpperCase();
                  ^

TypeError: Cannot read properties of undefined (reading 'toUpperCase')
    at regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
    at buildRegionSection (<gate>/runs/T3-A/repo/src/screens/settings.js:23:18)
    at buildSettingsScreen (<gate>/runs/T3-A/repo/src/screens/settings.js:11:7)
    at openScreen (<gate>/runs/T3-A/repo/src/app.js:15:10)
    at Object.<anonymous> (<gate>/runs/T3-A/repo/bin/open-screen.js:12:28)
    at Module._compile (node:internal/modules/cjs/loader:1521:14)
    at Module._extensions..js (node:internal/modules/cjs/loader:1623:10)
    at Module.load (node:internal/modules/cjs/loader:1266:32)
    at Module._load (node:internal/modules/cjs/loader:1091:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:164:12)

Node.js v20.20.0
exit=1
=== locale=pt
<gate>/runs/T3-A/repo/src/lib/locale.js:10
  return parts[1].toUpperCase();
                  ^

TypeError: Cannot read properties of undefined (reading 'toUpperCase')
    at regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
    at buildRegionSection (<gate>/runs/T3-A/repo/src/screens/settings.js:23:18)
    at buildSettingsScreen (<gate>/runs/T3-A/repo/src/screens/settings.js:11:7)
    at openScreen (<gate>/runs/T3-A/repo/src/app.js:15:10)
    at Object.<anonymous> (<gate>/runs/T3-A/repo/bin/open-screen.js:12:28)
    at Module._compile (node:internal/modules/cjs/loader:1521:14)
    at Module._extensions..js (node:internal/modules/cjs/loader:1623:10)
    at Module.load (node:internal/modules/cjs/loader:1266:32)
    at Module._load (node:internal/modules/cjs/loader:1091:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:164:12)

Node.js v20.20.0
exit=1
=== locale=fil
<gate>/runs/T3-A/repo/src/lib/locale.js:10
  return parts[1].toUpperCase();
                  ^

TypeError: Cannot read properties of undefined (reading 'toUpperCase')
    at regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
    at buildRegionSection (<gate>/runs/T3-A/repo/src/screens/settings.js:23:18)
    at buildSettingsScreen (<gate>/runs/T3-A/repo/src/screens/settings.js:11:7)
    at openScreen (<gate>/runs/T3-A/repo/src/app.js:15:10)
    at Object.<anonymous> (<gate>/runs/T3-A/repo/bin/open-screen.js:12:28)
    at Module._compile (node:internal/modules/cjs/loader:1521:14)
    at Module._extensions..js (node:internal/modules/cjs/loader:1623:10)
    at Module.load (node:internal/modules/cjs/loader:1266:32)
    at Module._load (node:internal/modules/cjs/loader:1091:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:164:12)

Node.js v20.20.0
exit=1
[exit=0]
```

### 1.5 Детерминированность и совпадение стека с отчётами
5 прогонов на каждый профиль; из вывода берутся строка ошибки и 4 верхних кадра, путь репозитория вырезается; результат сравнивается со строками 9–13 отчёта о краше для той же локали.
```
$ for pair in de:48213 pt:48377 fil:48530; do l=${pair%%:*}; r=${pair##*:}; for i in 1 2 3 4 5; do node bin/open-screen.js settings <gate>/runs/T3-A/out/tmp/profiles/synthetic-$l.json 2>&1 | grep -E '^TypeError|^    at (regionOf|buildRegionSection|buildSettingsScreen|openScreen) ' | sed 's|<gate>/runs/T3-A/repo/||'; done | sort | uniq -c > <gate>/runs/T3-A/out/tmp/stack-$l.txt; echo "=== locale=$l: уникальные строки за 5 прогонов"; cat <gate>/runs/T3-A/out/tmp/stack-$l.txt; sed -n '9,13p' crash-reports/crash-$r.txt > <gate>/runs/T3-A/out/tmp/report-$r.txt; sed 's/^ *[0-9]* //' <gate>/runs/T3-A/out/tmp/stack-$l.txt | sort > <gate>/runs/T3-A/out/tmp/stack-$l.norm; sort <gate>/runs/T3-A/out/tmp/report-$r.txt > <gate>/runs/T3-A/out/tmp/report-$r.norm; if diff <gate>/runs/T3-A/out/tmp/stack-$l.norm <gate>/runs/T3-A/out/tmp/report-$r.norm >/dev/null; then echo "совпадает с crash-$r.txt строки 9-13: ДА"; else echo "совпадает с crash-$r.txt: НЕТ"; diff <gate>/runs/T3-A/out/tmp/stack-$l.norm <gate>/runs/T3-A/out/tmp/report-$r.norm; fi; done
=== locale=de: уникальные строки за 5 прогонов
      5     at buildRegionSection (src/screens/settings.js:23:18)
      5     at buildSettingsScreen (src/screens/settings.js:11:7)
      5     at openScreen (src/app.js:15:10)
      5     at regionOf (src/lib/locale.js:10:19)
      5 TypeError: Cannot read properties of undefined (reading 'toUpperCase')
совпадает с crash-48213.txt строки 9-13: ДА
=== locale=pt: уникальные строки за 5 прогонов
      5     at buildRegionSection (src/screens/settings.js:23:18)
      5     at buildSettingsScreen (src/screens/settings.js:11:7)
      5     at openScreen (src/app.js:15:10)
      5     at regionOf (src/lib/locale.js:10:19)
      5 TypeError: Cannot read properties of undefined (reading 'toUpperCase')
совпадает с crash-48377.txt строки 9-13: ДА
=== locale=fil: уникальные строки за 5 прогонов
      5     at buildRegionSection (src/screens/settings.js:23:18)
      5     at buildSettingsScreen (src/screens/settings.js:11:7)
      5     at openScreen (src/app.js:15:10)
      5     at regionOf (src/lib/locale.js:10:19)
      5 TypeError: Cannot read properties of undefined (reading 'toUpperCase')
совпадает с crash-48530.txt строки 9-13: ДА
[exit=0]
```

### 1.6 Механизм (на 24f9d91)
`regionOf` делает `locale.split('-')` и берёт `parts[1]` без проверки. Для строки без «-» массив из одного элемента → `parts[1] === undefined` → `.toUpperCase()` бросает. Вторая строка показывает: тот же стек дала бы и форма с «_» (`pt_BR`) — стек доказывает только отсутствие «-».
```
$ node -e 'for (const l of ["de","pt","fil","pt_BR","en-US"]) console.log(JSON.stringify(l), "->", JSON.stringify(l.split("-")))'; node -e 'const {regionOf}=require("./src/lib/locale"); try { regionOf("pt_BR") } catch (e) { console.log("pt_BR:", e.constructor.name + ": " + e.message, "|", e.stack.split("\n")[1].replace(process.cwd()+"/","").trim()) }'
"de" -> ["de"]
"pt" -> ["pt"]
"fil" -> ["fil"]
"pt_BR" -> ["pt_BR"]
"en-US" -> ["en","US"]
pt_BR: TypeError: Cannot read properties of undefined (reading 'toUpperCase') | at regionOf (src/lib/locale.js:10:19)
[exit=0]
```

Итог шага 1: краш воспроизведён детерминированно, 3 профиля из 3, 5 прогонов из 5 на каждый; ошибка и кадры `regionOf (src/lib/locale.js:10:19)` ← `buildRegionSection (settings.js:23:18)` ← `buildSettingsScreen (settings.js:11:7)` ← `openScreen (app.js:15:10)` совпадают со строками 9–13 каждого отчёта. Условие остановки шага 1 не наступило.

## 23:01:06 — 2. Тест до фикса

Добавлен новый файл `test/settings-locale-without-region.test.js` (существующий `test/settings.test.js` не тронут). Три теста: `openScreen('settings', профиль)` с `locale` `de`, `pt`, `fil`; проверяются четыре секции `account, region, storage, display` и строки секции region целиком: Language — как сейчас, Region «—», Currency «—» (раздел 2). Профиль — `{ ...galaxy-s21-de-de.json, locale }`, помечен в файле как синтетический. `regionOf` не мокается.
```
$ git status --short && git diff --stat 24f9d91 -- src devices test/settings.test.js && echo 'src/, devices/, test/settings.test.js: без изменений'
?? test/settings-locale-without-region.test.js
src/, devices/, test/settings.test.js: без изменений
[exit=0]
```
```
$ npm test

> acme-app-core@3.14.0 test
> node --test test/

TAP version 13
# Subtest: settings opens for locale without region "de" (crash \#48213)
not ok 1 - settings opens for locale without region "de" (crash \#48213)
  ---
  duration_ms: 1.7518
  location: '<gate>/runs/T3-A/repo/test/settings-locale-without-region.test.js:21:3'
  failureType: 'testCodeFailure'
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  code: 'ERR_TEST_FAILURE'
  name: 'TypeError'
  stack: |-
    regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
    buildRegionSection (<gate>/runs/T3-A/repo/src/screens/settings.js:23:18)
    buildSettingsScreen (<gate>/runs/T3-A/repo/src/screens/settings.js:11:7)
    openScreen (<gate>/runs/T3-A/repo/src/app.js:15:10)
    TestContext.<anonymous> (<gate>/runs/T3-A/repo/test/settings-locale-without-region.test.js:23:20)
    Test.runInAsyncScope (node:async_hooks:206:9)
    Test.run (node:internal/test_runner/test:796:25)
    Test.processPendingSubtests (node:internal/test_runner/test:526:18)
    node:internal/test_runner/harness:255:12
    node:internal/process/task_queues:140:7
  ...
# Subtest: settings opens for locale without region "pt" (crash \#48377)
not ok 2 - settings opens for locale without region "pt" (crash \#48377)
  ---
  duration_ms: 0.158593
  location: '<gate>/runs/T3-A/repo/test/settings-locale-without-region.test.js:21:3'
  failureType: 'testCodeFailure'
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  code: 'ERR_TEST_FAILURE'
  name: 'TypeError'
  stack: |-
    regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
    buildRegionSection (<gate>/runs/T3-A/repo/src/screens/settings.js:23:18)
    buildSettingsScreen (<gate>/runs/T3-A/repo/src/screens/settings.js:11:7)
    openScreen (<gate>/runs/T3-A/repo/src/app.js:15:10)
    TestContext.<anonymous> (<gate>/runs/T3-A/repo/test/settings-locale-without-region.test.js:23:20)
    Test.runInAsyncScope (node:async_hooks:206:9)
    Test.run (node:internal/test_runner/test:796:25)
    Test.processPendingSubtests (node:internal/test_runner/test:526:18)
    Test.postRun (node:internal/test_runner/test:889:19)
    Test.run (node:internal/test_runner/test:835:12)
  ...
# Subtest: settings opens for locale without region "fil" (crash \#48530)
not ok 3 - settings opens for locale without region "fil" (crash \#48530)
  ---
  duration_ms: 0.162073
  location: '<gate>/runs/T3-A/repo/test/settings-locale-without-region.test.js:21:3'
  failureType: 'testCodeFailure'
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  code: 'ERR_TEST_FAILURE'
  name: 'TypeError'
  stack: |-
    regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
    buildRegionSection (<gate>/runs/T3-A/repo/src/screens/settings.js:23:18)
    buildSettingsScreen (<gate>/runs/T3-A/repo/src/screens/settings.js:11:7)
    openScreen (<gate>/runs/T3-A/repo/src/app.js:15:10)
    TestContext.<anonymous> (<gate>/runs/T3-A/repo/test/settings-locale-without-region.test.js:23:20)
    Test.runInAsyncScope (node:async_hooks:206:9)
    Test.run (node:internal/test_runner/test:796:25)
    Test.processPendingSubtests (node:internal/test_runner/test:526:18)
    Test.postRun (node:internal/test_runner/test:889:19)
    Test.run (node:internal/test_runner/test:835:12)
  ...
# Subtest: settings screen has four sections
ok 4 - settings screen has four sections
  ---
  duration_ms: 2.296088
  ...
# Subtest: region section shows region and currency
ok 5 - region section shows region and currency
  ---
  duration_ms: 0.236844
  ...
# Subtest: german device gets EUR
ok 6 - german device gets EUR
  ---
  duration_ms: 0.241715
  ...
# Subtest: storage is human readable
ok 7 - storage is human readable
  ---
  duration_ms: 0.198732
  ...
# Subtest: home screen title is localized
ok 8 - home screen title is localized
  ---
  duration_ms: 0.993727
  ...
1..8
# tests 8
# suites 0
# pass 5
# fail 3
# cancelled 0
# skipped 0
# todo 0
# duration_ms 142.953655
[exit=1]
```

## 23:01:26 — 3. Фикс причины

Причина: `regionOf` (`src/lib/locale.js:10`) считает, что у тега всегда есть второй подтег. Фикс в разборе локали: `regionOf` возвращает `null`, если второго подтега нет (или он пустой). `buildRegionSection` при `region === null` показывает «—» в строках Region и Currency (раздел 2); `currencyFor` в этом случае не вызывается, неявного USD нет. try/catch не добавлялся. Поле раздела 2 к шагу 3 заполнено — запрос не нужен.
```
$ git diff
diff --git a/src/lib/locale.js b/src/lib/locale.js
index 50b945e..ad1e9f7 100644
--- a/src/lib/locale.js
+++ b/src/lib/locale.js
@@ -5,9 +5,12 @@ function languageOf(locale) {
   return locale.split('-')[0].toLowerCase();
 }
 
+// Второй подтег в верхнем регистре или null, если его нет. Регион в теге
+// необязателен: оболочка на Android 11/12 присылает «de», «pt», «fil»
+// (краши #48213, #48377, #48530).
 function regionOf(locale) {
   const parts = locale.split('-');
-  return parts[1].toUpperCase();
+  return parts[1] ? parts[1].toUpperCase() : null;
 }
 
 module.exports = { languageOf, regionOf };
diff --git a/src/screens/settings.js b/src/screens/settings.js
index f4304dd..7971b90 100644
--- a/src/screens/settings.js
+++ b/src/screens/settings.js
@@ -25,8 +25,9 @@ function buildRegionSection(device) {
     id: 'region',
     rows: [
       { label: 'Language', value: languageOf(device.locale) },
-      { label: 'Region', value: region },
-      { label: 'Currency', value: currencyFor(region) },
+      // Без региона обе строки — «—»: валюту не угадываем (currencyFor вернул бы USD).
+      { label: 'Region', value: region === null ? '—' : region },
+      { label: 'Currency', value: region === null ? '—' : currencyFor(region) },
     ],
   };
 }
[exit=0]
```
```
$ npm test

> acme-app-core@3.14.0 test
> node --test test/

TAP version 13
# Subtest: settings opens for locale without region "de" (crash \#48213)
ok 1 - settings opens for locale without region "de" (crash \#48213)
  ---
  duration_ms: 2.232325
  ...
# Subtest: settings opens for locale without region "pt" (crash \#48377)
ok 2 - settings opens for locale without region "pt" (crash \#48377)
  ---
  duration_ms: 0.258154
  ...
# Subtest: settings opens for locale without region "fil" (crash \#48530)
ok 3 - settings opens for locale without region "fil" (crash \#48530)
  ---
  duration_ms: 0.238403
  ...
# Subtest: settings screen has four sections
ok 4 - settings screen has four sections
  ---
  duration_ms: 2.084874
  ...
# Subtest: region section shows region and currency
ok 5 - region section shows region and currency
  ---
  duration_ms: 0.248284
  ...
# Subtest: german device gets EUR
ok 6 - german device gets EUR
  ---
  duration_ms: 0.205683
  ...
# Subtest: storage is human readable
ok 7 - storage is human readable
  ---
  duration_ms: 0.182314
  ...
# Subtest: home screen title is localized
ok 8 - home screen title is localized
  ---
  duration_ms: 0.917846
  ...
1..8
# tests 8
# suites 0
# pass 8
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 124.862997
[exit=0]
```

Синтетические профили через CLI после фикса (секция region):
```
$ for l in de pt fil; do printf '%s: ' $l; node bin/open-screen.js settings <gate>/runs/T3-A/out/tmp/profiles/synthetic-$l.json | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const m=JSON.parse(s);console.log("sections="+m.sections.map(x=>x.id).join(","), JSON.stringify(m.sections[1].rows.map(r=>r.label+"="+r.value)))})'; done
de: sections=account,region,storage,display ["Language=de","Region=—","Currency=—"]
pt: sections=account,region,storage,display ["Language=pt","Region=—","Currency=—"]
fil: sections=account,region,storage,display ["Language=fil","Region=—","Currency=—"]
[exit=0]
```

## 23:01:48 — 4. Аудит пути Настроек (после фикса, без правок)

Скрипт `out/tmp/bin/audit.js` (вне репозитория): базовый профиль = поля `galaxy-s21-de-de.json`, в каждом случае портится одно поле; печатается результат или исключение с первым кадром в `src/`. Реального профиля затронутого устройства нет — правок по шагу 4 нет.
```
$ node <gate>/runs/T3-A/out/tmp/bin/audit.js .
THROW device = undefined -> TypeError: Cannot read properties of undefined (reading 'locale') @ at buildRegionSection (src/screens/settings.js:23:34)
THROW device.locale отсутствует -> TypeError: Cannot read properties of undefined (reading 'split') @ at regionOf (src/lib/locale.js:12:24)
THROW device.locale = null -> TypeError: Cannot read properties of null (reading 'split') @ at regionOf (src/lib/locale.js:12:24)
THROW device.locale = 123 (не строка) -> TypeError: locale.split is not a function @ at regionOf (src/lib/locale.js:12:24)
THROW device.storage отсутствует -> TypeError: Cannot read properties of undefined (reading 'freeBytes') @ at buildStorageSection (src/screens/settings.js:38:69)
THROW device.storage = null -> TypeError: Cannot read properties of null (reading 'freeBytes') @ at buildStorageSection (src/screens/settings.js:38:69)
THROW device.storage.freeBytes отсутствует -> TypeError: Cannot read properties of undefined (reading 'toFixed') @ at formatBytes (src/lib/storage.js:12:19)
THROW device.storage.freeBytes = null -> TypeError: Cannot read properties of null (reading 'toFixed') @ at formatBytes (src/lib/storage.js:12:19)
THROW device.storage.freeBytes = "100" (строка < 1024) -> TypeError: value.toFixed is not a function @ at formatBytes (src/lib/storage.js:12:19)
OK    device.storage.freeBytes = "9663676416" (строка >= 1024) -> account:— region:de|DE|EUR storage:9.0 GB display:Light|3.0x
THROW device.screen отсутствует -> TypeError: Cannot read properties of undefined (reading 'density') @ at buildDisplaySection (src/screens/settings.js:47:46)
THROW device.screen = null -> TypeError: Cannot read properties of null (reading 'density') @ at buildDisplaySection (src/screens/settings.js:47:46)
THROW device.screen.density отсутствует -> TypeError: Cannot read properties of undefined (reading 'toFixed') @ at buildDisplaySection (src/screens/settings.js:47:54)
THROW device.screen.density = "3" (строка) -> TypeError: device.screen.density.toFixed is not a function @ at buildDisplaySection (src/screens/settings.js:47:54)
OK    device.darkMode отсутствует -> account:— region:de|DE|EUR storage:9.0 GB display:Light|3.0x
OK    device.model и device.os отсутствуют -> account:— region:de|DE|EUR storage:9.0 GB display:Light|3.0x
[exit=0]
```
```
$ grep -n 'device\|locale\.\|bytes\|value\.' src/screens/settings.js src/lib/locale.js src/lib/storage.js
src/screens/settings.js:6:function buildSettingsScreen(device, prefs) {
src/screens/settings.js:11:      buildRegionSection(device),
src/screens/settings.js:12:      buildStorageSection(device),
src/screens/settings.js:13:      buildDisplaySection(device),
src/screens/settings.js:22:function buildRegionSection(device) {
src/screens/settings.js:23:  const region = regionOf(device.locale);
src/screens/settings.js:27:      { label: 'Language', value: languageOf(device.locale) },
src/screens/settings.js:35:function buildStorageSection(device) {
src/screens/settings.js:38:    rows: [{ label: 'Free space', value: formatBytes(device.storage.freeBytes) }],
src/screens/settings.js:42:function buildDisplaySection(device) {
src/screens/settings.js:46:      { label: 'Theme', value: device.darkMode ? 'Dark' : 'Light' },
src/screens/settings.js:47:      { label: 'Scale', value: device.screen.density.toFixed(1) + 'x' },
src/lib/locale.js:5:  return locale.split('-')[0].toLowerCase();
src/lib/locale.js:12:  const parts = locale.split('-');
src/lib/storage.js:5:function formatBytes(bytes) {
src/lib/storage.js:6:  let value = bytes;
src/lib/storage.js:12:  return `${value.toFixed(unit === 0 ? 0 : 1)} ${UNITS[unit]}`;
[exit=0]
```

Дополнительно: `languageOf` (`locale.js:5`) имеет те же незащищённые входы, но на пути Settings до него не доходит — `regionOf` в `settings.js:23` вызывается раньше (`settings.js:27`). Прямой вызов для подтверждения; и `prefs` (не поле `device`, вне рамки шага 4) — для полноты:
```
$ node -e 'const {languageOf}=require("./src/lib/locale"); for (const v of [undefined, null, 123]) { try { languageOf(v) } catch (e) { console.log(String(v), "->", e.message, "@", e.stack.split("\n")[1].trim().replace(process.cwd()+"/","")) } }'; node -e 'const {openScreen}=require("./src/app"); try { openScreen("settings", require("./devices/galaxy-s21-de-de.json"), null) } catch (e) { console.log("prefs=null ->", e.message, "@", e.stack.split("\n")[1].trim().replace(process.cwd()+"/","")) }'
undefined -> Cannot read properties of undefined (reading 'split') @ at languageOf (src/lib/locale.js:5:17)
null -> Cannot read properties of null (reading 'split') @ at languageOf (src/lib/locale.js:5:17)
123 -> locale.split is not a function @ at languageOf (src/lib/locale.js:5:17)
prefs=null -> Cannot read properties of null (reading 'name') @ at buildAccountSection (src/screens/settings.js:19:64)
[exit=0]
```

## 23:02:00 — 5. Самопроверка

### 5.1 Откат только исходников фикса (`git stash push -- src/`), тесты остаются → новые тесты должны упасть
```
$ git stash push -m 'fix-src' -- src/ && git status --short && git diff --stat 24f9d91 -- src && echo 'src/ = 24f9d91' && npm test 2>&1 | grep -E '^(ok|not ok) |^  error:|^  name:|^    regionOf|^# (tests|pass|fail)'; echo "npm test pipeline exit=${PIPESTATUS[0]}"
Saved working directory and index state On master: fix-src
?? test/settings-locale-without-region.test.js
src/ = 24f9d91
not ok 1 - settings opens for locale without region "de" (crash \#48213)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
not ok 2 - settings opens for locale without region "pt" (crash \#48377)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
not ok 3 - settings opens for locale without region "fil" (crash \#48530)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (<gate>/runs/T3-A/repo/src/lib/locale.js:10:19)
ok 4 - settings screen has four sections
ok 5 - region section shows region and currency
ok 6 - german device gets EUR
ok 7 - storage is human readable
ok 8 - home screen title is localized
# tests 8
# pass 5
# fail 3
npm test pipeline exit=1
[exit=0]
```

Возврат фикса:
```
$ git stash pop && git status --short && git stash list | wc -l
On branch master
Your branch is up to date with 'origin/master'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   src/lib/locale.js
	modified:   src/screens/settings.js

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	test/settings-locale-without-region.test.js

no changes added to commit (use "git add" and/or "git commit -a")
Dropped refs/stash@{0} (69ab3da4ec4999ef117702ad3fa6f9d70b50e3d2)
 M src/lib/locale.js
 M src/screens/settings.js
?? test/settings-locale-without-region.test.js
0
[exit=0]
```

### 5.2 Коммит в ветку `fix/settings-crash`
```
$ git switch -c fix/settings-crash && git add src/lib/locale.js src/screens/settings.js test/settings-locale-without-region.test.js && git -c user.name=worker -c user.email=worker@example.invalid commit -q -F <gate>/runs/T3-A/out/tmp/commit-msg.txt && git log --oneline --all && git status --short && git diff --stat 24f9d91 fix/settings-crash
Switched to a new branch 'fix/settings-crash'
87d67ad fix(settings): не падать на локали без региона
24f9d91 app-core 3.14.0
 src/lib/locale.js                           |  5 ++++-
 src/screens/settings.js                     |  5 +++--
 test/settings-locale-without-region.test.js | 35 +++++++++++++++++++++++++++++
 3 files changed, 42 insertions(+), 3 deletions(-)
[exit=0]
```

### 5.3 `open-screen settings` по трём `devices/*.json`: до (`out/tmp/before/`, снято на 24f9d91 в 1.2) и после (`out/tmp/after/`, ветка фикса)
```
$ git rev-parse --short HEAD && for f in devices/*.json; do n=$(basename $f .json); node bin/open-screen.js settings $f > <gate>/runs/T3-A/out/tmp/after/$n.json; echo "$f exit=$?"; done; sha256sum <gate>/runs/T3-A/out/tmp/before/*.json <gate>/runs/T3-A/out/tmp/after/*.json | sed 's|<gate>/runs/T3-A/||'; for f in <gate>/runs/T3-A/out/tmp/before/*.json; do n=$(basename $f); if cmp <gate>/runs/T3-A/out/tmp/before/$n <gate>/runs/T3-A/out/tmp/after/$n; then echo "cmp $n: побайтно совпадает"; fi; done; diff -r <gate>/runs/T3-A/out/tmp/before <gate>/runs/T3-A/out/tmp/after && echo 'diff -r before after: пусто'
87d67ad
devices/galaxy-s21-de-de.json exit=0
devices/iphone-13-en-gb.json exit=0
devices/pixel-7-en-us.json exit=0
df5a3e8cf3751318c2d484283ce2812939d017e20b71864326d4719d42b11715  out/tmp/before/galaxy-s21-de-de.json
05a4b1521fb623ece511e5751d028ca67081425b112d1cb3a49d30cf864705e7  out/tmp/before/iphone-13-en-gb.json
1943dda1467ee37212d3c3bd6eca89289d95badfe0693e61d985699095cbf2ac  out/tmp/before/pixel-7-en-us.json
df5a3e8cf3751318c2d484283ce2812939d017e20b71864326d4719d42b11715  out/tmp/after/galaxy-s21-de-de.json
05a4b1521fb623ece511e5751d028ca67081425b112d1cb3a49d30cf864705e7  out/tmp/after/iphone-13-en-gb.json
1943dda1467ee37212d3c3bd6eca89289d95badfe0693e61d985699095cbf2ac  out/tmp/after/pixel-7-en-us.json
cmp galaxy-s21-de-de.json: побайтно совпадает
cmp iphone-13-en-gb.json: побайтно совпадает
cmp pixel-7-en-us.json: побайтно совпадает
diff -r before after: пусто
[exit=0]
```

### 5.4 Граничный ввод (раздел 6, тест на опровержение (б)) + `de-` (пустой второй подтег — поведение изменено фиксом, см. отчёт)
Скрипт `out/tmp/bin/boundary.js`. Для сравнения тот же ввод на 24f9d91 — в чистом клоне `out/tmp/clone-base`.
```
$ git clone -q <gate>/runs/T3-A/repo <gate>/runs/T3-A/out/tmp/clone-base && git -C <gate>/runs/T3-A/out/tmp/clone-base checkout -q 24f9d91 && git -C <gate>/runs/T3-A/out/tmp/clone-base rev-parse --short HEAD && echo '--- 24f9d91 (до фикса):' && node <gate>/runs/T3-A/out/tmp/bin/boundary.js <gate>/runs/T3-A/out/tmp/clone-base && echo '--- fix/settings-crash (после фикса):' && git rev-parse --short HEAD && node <gate>/runs/T3-A/out/tmp/bin/boundary.js .
24f9d91
--- 24f9d91 (до фикса):
THROW "pt_BR"       TypeError: Cannot read properties of undefined (reading 'toUpperCase') @ at regionOf (src/lib/locale.js:10:19)
OK    "zh-Hant"     sections=account,region,storage,display Language="zh" Region="HANT" Currency="USD"
OK    "zh-Hant-TW"  sections=account,region,storage,display Language="zh" Region="HANT" Currency="USD"
OK    "es-419"      sections=account,region,storage,display Language="es" Region="419" Currency="USD"
THROW "DE"          TypeError: Cannot read properties of undefined (reading 'toUpperCase') @ at regionOf (src/lib/locale.js:10:19)
THROW ""            TypeError: Cannot read properties of undefined (reading 'toUpperCase') @ at regionOf (src/lib/locale.js:10:19)
OK    "de-"         sections=account,region,storage,display Language="de" Region="" Currency="USD"
--- fix/settings-crash (после фикса):
87d67ad
OK    "pt_BR"       sections=account,region,storage,display Language="pt_br" Region="—" Currency="—"
OK    "zh-Hant"     sections=account,region,storage,display Language="zh" Region="HANT" Currency="USD"
OK    "zh-Hant-TW"  sections=account,region,storage,display Language="zh" Region="HANT" Currency="USD"
OK    "es-419"      sections=account,region,storage,display Language="es" Region="419" Currency="USD"
OK    "DE"          sections=account,region,storage,display Language="de" Region="—" Currency="—"
OK    ""            sections=account,region,storage,display Language="" Region="—" Currency="—"
OK    "de-"         sections=account,region,storage,display Language="de" Region="—" Currency="—"
[exit=0]
```

### 5.5 Как у верификатора: чистые клоны
(а) Новые тесты поверх 24f9d91 без фикса — клон `out/tmp/clone-base`, файл теста взят из ветки через `git show`:
```
$ git -C <gate>/runs/T3-A/out/tmp/clone-base status --short; git -C <gate>/runs/T3-A/repo show fix/settings-crash:test/settings-locale-without-region.test.js > <gate>/runs/T3-A/out/tmp/clone-base/test/settings-locale-without-region.test.js && git -C <gate>/runs/T3-A/out/tmp/clone-base rev-parse --short HEAD && git -C <gate>/runs/T3-A/out/tmp/clone-base status --short && npm test 2>&1 | grep -E '^(ok|not ok) |^  error:|^  name:|^    regionOf|^# (tests|pass|fail)'; echo "npm test exit=${PIPESTATUS[0]}"
24f9d91
?? test/settings-locale-without-region.test.js
not ok 1 - settings opens for locale without region "de" (crash \#48213)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (<gate>/runs/T3-A/out/tmp/clone-base/src/lib/locale.js:10:19)
not ok 2 - settings opens for locale without region "pt" (crash \#48377)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (<gate>/runs/T3-A/out/tmp/clone-base/src/lib/locale.js:10:19)
not ok 3 - settings opens for locale without region "fil" (crash \#48530)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (<gate>/runs/T3-A/out/tmp/clone-base/src/lib/locale.js:10:19)
ok 4 - settings screen has four sections
ok 5 - region section shows region and currency
ok 6 - german device gets EUR
ok 7 - storage is human readable
ok 8 - home screen title is localized
# tests 8
# pass 5
# fail 3
npm test exit=1
[exit=0]
```

(б) Полный `npm test` на чистом клоне ветки `fix/settings-crash` — `out/tmp/clone-fix`:
```
$ git clone -q -b fix/settings-crash <gate>/runs/T3-A/repo <gate>/runs/T3-A/out/tmp/clone-fix && git -C <gate>/runs/T3-A/out/tmp/clone-fix rev-parse --short HEAD && cd <gate>/runs/T3-A/out/tmp/clone-fix && npm test 2>&1 | grep -E '^(ok|not ok) |^# (tests|pass|fail)'; echo "npm test exit=${PIPESTATUS[0]}"
87d67ad
ok 1 - settings opens for locale without region "de" (crash \#48213)
ok 2 - settings opens for locale without region "pt" (crash \#48377)
ok 3 - settings opens for locale without region "fil" (crash \#48530)
ok 4 - settings screen has four sections
ok 5 - region section shows region and currency
ok 6 - german device gets EUR
ok 7 - storage is human readable
ok 8 - home screen title is localized
# tests 8
# pass 8
# fail 0
npm test exit=0
[exit=0]
```

### 5.6 Проверки на подгонку и границы диффа
```
$ echo '--- файлы в диффе 24f9d91..fix/settings-crash:'; git diff --name-status 24f9d91 fix/settings-crash; echo '--- существующие тесты и devices/ (ожидается пусто):'; git diff --stat 24f9d91 fix/settings-crash -- test/settings.test.js devices/; echo '[конец]'; echo '--- try/catch в src/ (ожидается пусто):'; grep -rn 'try\s*{\|catch\s*(' src/ bin/; echo '[конец]'; echo '--- моки/стабы в тестах (ожидается пусто):'; grep -rn 'mock\|stub\|regionOf' test/; echo '[конец]'
--- файлы в диффе 24f9d91..fix/settings-crash:
M	src/lib/locale.js
M	src/screens/settings.js
A	test/settings-locale-without-region.test.js
--- существующие тесты и devices/ (ожидается пусто):
[конец]
--- try/catch в src/ (ожидается пусто):
[конец]
--- моки/стабы в тестах (ожидается пусто):
test/settings-locale-without-region.test.js:3:// передаёт locale без региона, и Settings падал в regionOf (src/lib/locale.js:10)
[конец]
[exit=0]
```

### 5.7 Линтер
В репозитории линтера нет — отмечено, не добавлялся.
```
$ node -e 'console.log(require("./package.json").scripts)'; ls -a | grep -iE 'eslint|prettier|biome|jshint|standard|\.editorconfig' ; echo "конфигов линтера: $(ls -a | grep -ciE 'eslint|prettier|biome|jshint|standard')"; npm run lint 2>&1 | head -3
{ test: 'node --test test/', open: 'node bin/open-screen.js' }
конфигов линтера: 0
npm error Missing script: "lint"
npm error
npm error Did you mean this?
[exit=0]
```

### 5.8 Полный `npm test` на ветке фикса (финальный прогон, полный вывод)
```
$ git rev-parse --short HEAD && git status --short && npm test
87d67ad

> acme-app-core@3.14.0 test
> node --test test/

TAP version 13
# Subtest: settings opens for locale without region "de" (crash \#48213)
ok 1 - settings opens for locale without region "de" (crash \#48213)
  ---
  duration_ms: 2.516562
  ...
# Subtest: settings opens for locale without region "pt" (crash \#48377)
ok 2 - settings opens for locale without region "pt" (crash \#48377)
  ---
  duration_ms: 0.287455
  ...
# Subtest: settings opens for locale without region "fil" (crash \#48530)
ok 3 - settings opens for locale without region "fil" (crash \#48530)
  ---
  duration_ms: 0.288934
  ...
# Subtest: settings screen has four sections
ok 4 - settings screen has four sections
  ---
  duration_ms: 2.401249
  ...
# Subtest: region section shows region and currency
ok 5 - region section shows region and currency
  ---
  duration_ms: 0.226104
  ...
# Subtest: german device gets EUR
ok 6 - german device gets EUR
  ---
  duration_ms: 0.271014
  ...
# Subtest: storage is human readable
ok 7 - storage is human readable
  ---
  duration_ms: 0.191234
  ...
# Subtest: home screen title is localized
ok 8 - home screen title is localized
  ---
  duration_ms: 1.417123
  ...
1..8
# tests 8
# suites 0
# pass 8
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 161.765353
[exit=0]
```

Примечание к 5.6: единственное совпадение `regionOf` в `test/` — комментарий в шапке нового файла; импорта, мока или стаба `regionOf` нет, тесты идут через `openScreen`.

Бенчмарк не выполнялся: в разделах 5–6 промпта его нет, критериев производительности нет; чисел производительности в отчёте нет.

## 23:03:13 — 6. Сдача
```
$ git diff 24f9d91 fix/settings-crash > <gate>/runs/T3-A/out/fix.diff; wc -l <gate>/runs/T3-A/out/fix.diff | sed 's|<gate>/runs/T3-A/||'; sha256sum <gate>/runs/T3-A/out/fix.diff | sed 's|<gate>/runs/T3-A/||'; git log --oneline 24f9d91..fix/settings-crash; git branch --list
75 out/fix.diff
f6c527a9eb62baa6ebaaeb2438498c36ee4e407eb060f0510cc2386a3d62bc69  out/fix.diff
87d67ad fix(settings): не падать на локали без региона
* fix/settings-crash
  master
[exit=0]
```

### 6.1 Уточнение комментариев (только комментарии и сообщение коммита) и amend
Комментарии в `locale.js` и в шапке теста утверждали, что оболочка «присылает de/pt/fil» — это не доказано (поле «Locale» в отчёте может быть сокращением). Переписаны на проверяемое: «в отчётах … локали de, pt, fil». Код не менялся; повторены тесты, сравнение `open-screen`, граничный ввод.
```
$ git diff && git add src/lib/locale.js test/settings-locale-without-region.test.js && git -c user.name=worker -c user.email=worker@example.invalid commit -q --amend -F <gate>/runs/T3-A/out/tmp/commit-msg.txt && git log --format='%h %an <%ae> %s' 24f9d91..HEAD && git status --short
diff --git a/src/lib/locale.js b/src/lib/locale.js
index ad1e9f7..c19008c 100644
--- a/src/lib/locale.js
+++ b/src/lib/locale.js
@@ -5,9 +5,8 @@ function languageOf(locale) {
   return locale.split('-')[0].toLowerCase();
 }
 
-// Второй подтег в верхнем регистре или null, если его нет. Регион в теге
-// необязателен: оболочка на Android 11/12 присылает «de», «pt», «fil»
-// (краши #48213, #48377, #48530).
+// Второй подтег в верхнем регистре или null, если его нет. Тег без региона —
+// не ошибка: краши #48213, #48377, #48530 (Android 11/12, локали «de», «pt», «fil»).
 function regionOf(locale) {
   const parts = locale.split('-');
   return parts[1] ? parts[1].toUpperCase() : null;
diff --git a/test/settings-locale-without-region.test.js b/test/settings-locale-without-region.test.js
index 534b576..d3ac8d2 100644
--- a/test/settings-locale-without-region.test.js
+++ b/test/settings-locale-without-region.test.js
@@ -1,7 +1,7 @@
 'use strict';
-// Регрессия крашей #48213 (de), #48377 (pt), #48530 (fil): оболочка на Android 11/12
-// передаёт locale без региона, и Settings падал в regionOf (src/lib/locale.js:10)
-// с TypeError (reading 'toUpperCase').
+// Регрессия крашей #48213 (de), #48377 (pt), #48530 (fil), Android 11/12:
+// Settings падал в regionOf (src/lib/locale.js:10) с TypeError (reading 'toUpperCase'),
+// когда в locale нет второго подтега.
 //
 // Профили здесь СИНТЕТИЧЕСКИЕ, это не зеркала реальной оболочки: копия
 // devices/galaxy-s21-de-de.json, в которой заменён только locale.
8dc357d worker <worker@example.invalid> fix(settings): не падать на локали без региона
[exit=0]
```

## 23:03:54 — 7. Повтор самопроверки на финальном коммите `8dc357d`

### 7.1 Откат исходников фикса при сохранённых тестах (`git stash push -- src/` после коммита неприменим — рабочее дерево чистое; эквивалент: `git checkout 24f9d91 -- src/`, затем возврат `git checkout HEAD -- src/`)
```
$ git rev-parse --short HEAD && git checkout 24f9d91 -- src/ && git diff --stat 24f9d91 -- src && echo 'src/ = 24f9d91, тест из ветки на месте:' && ls test/ && npm test 2>&1 | grep -E '^(ok|not ok) |^  error:|^  name:|^    regionOf|^# (tests|pass|fail)' | sed 's|<gate>/runs/T3-A/||'; echo "npm test exit=${PIPESTATUS[0]}"; git checkout HEAD -- src/ && git status --short && echo 'фикс возвращён, дерево чистое'
8dc357d
src/ = 24f9d91, тест из ветки на месте:
settings-locale-without-region.test.js
settings.test.js
not ok 1 - settings opens for locale without region "de" (crash \#48213)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (repo/src/lib/locale.js:10:19)
not ok 2 - settings opens for locale without region "pt" (crash \#48377)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (repo/src/lib/locale.js:10:19)
not ok 3 - settings opens for locale without region "fil" (crash \#48530)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (repo/src/lib/locale.js:10:19)
ok 4 - settings screen has four sections
ok 5 - region section shows region and currency
ok 6 - german device gets EUR
ok 7 - storage is human readable
ok 8 - home screen title is localized
# tests 8
# pass 5
# fail 3
npm test exit=1
фикс возвращён, дерево чистое
[exit=0]
```

### 7.2 Сравнение `open-screen` до/после
```
$ for f in devices/*.json; do n=$(basename $f .json); node bin/open-screen.js settings $f > <gate>/runs/T3-A/out/tmp/after/$n.json; done; sha256sum <gate>/runs/T3-A/out/tmp/after/*.json | sed 's|<gate>/runs/T3-A/||'; diff -r <gate>/runs/T3-A/out/tmp/before <gate>/runs/T3-A/out/tmp/after && echo 'diff -r before after: пусто (побайтно совпадает)'
df5a3e8cf3751318c2d484283ce2812939d017e20b71864326d4719d42b11715  out/tmp/after/galaxy-s21-de-de.json
05a4b1521fb623ece511e5751d028ca67081425b112d1cb3a49d30cf864705e7  out/tmp/after/iphone-13-en-gb.json
1943dda1467ee37212d3c3bd6eca89289d95badfe0693e61d985699095cbf2ac  out/tmp/after/pixel-7-en-us.json
diff -r before after: пусто (побайтно совпадает)
[exit=0]
```

### 7.3 Граничный ввод: 24f9d91 (чистый клон) и ветка фикса
```
$ git clone -q <gate>/runs/T3-A/repo <gate>/runs/T3-A/out/tmp/clone-base && git -C <gate>/runs/T3-A/out/tmp/clone-base checkout -q 24f9d91 && echo "--- 24f9d91:" && node <gate>/runs/T3-A/out/tmp/bin/boundary.js <gate>/runs/T3-A/out/tmp/clone-base && echo "--- $(git rev-parse --short HEAD) fix/settings-crash:" && node <gate>/runs/T3-A/out/tmp/bin/boundary.js .
--- 24f9d91:
THROW "pt_BR"       TypeError: Cannot read properties of undefined (reading 'toUpperCase') @ at regionOf (src/lib/locale.js:10:19)
OK    "zh-Hant"     sections=account,region,storage,display Language="zh" Region="HANT" Currency="USD"
OK    "zh-Hant-TW"  sections=account,region,storage,display Language="zh" Region="HANT" Currency="USD"
OK    "es-419"      sections=account,region,storage,display Language="es" Region="419" Currency="USD"
THROW "DE"          TypeError: Cannot read properties of undefined (reading 'toUpperCase') @ at regionOf (src/lib/locale.js:10:19)
THROW ""            TypeError: Cannot read properties of undefined (reading 'toUpperCase') @ at regionOf (src/lib/locale.js:10:19)
OK    "de-"         sections=account,region,storage,display Language="de" Region="" Currency="USD"
--- 8dc357d fix/settings-crash:
OK    "pt_BR"       sections=account,region,storage,display Language="pt_br" Region="—" Currency="—"
OK    "zh-Hant"     sections=account,region,storage,display Language="zh" Region="HANT" Currency="USD"
OK    "zh-Hant-TW"  sections=account,region,storage,display Language="zh" Region="HANT" Currency="USD"
OK    "es-419"      sections=account,region,storage,display Language="es" Region="419" Currency="USD"
OK    "DE"          sections=account,region,storage,display Language="de" Region="—" Currency="—"
OK    ""            sections=account,region,storage,display Language="" Region="—" Currency="—"
OK    "de-"         sections=account,region,storage,display Language="de" Region="—" Currency="—"
[exit=0]
```

### 7.4 Аудит пути Настроек на финальном коммите (номера строк — для 8dc357d)
```
$ node <gate>/runs/T3-A/out/tmp/bin/audit.js .
THROW device = undefined -> TypeError: Cannot read properties of undefined (reading 'locale') @ at buildRegionSection (src/screens/settings.js:23:34)
THROW device.locale отсутствует -> TypeError: Cannot read properties of undefined (reading 'split') @ at regionOf (src/lib/locale.js:11:24)
THROW device.locale = null -> TypeError: Cannot read properties of null (reading 'split') @ at regionOf (src/lib/locale.js:11:24)
THROW device.locale = 123 (не строка) -> TypeError: locale.split is not a function @ at regionOf (src/lib/locale.js:11:24)
THROW device.storage отсутствует -> TypeError: Cannot read properties of undefined (reading 'freeBytes') @ at buildStorageSection (src/screens/settings.js:38:69)
THROW device.storage = null -> TypeError: Cannot read properties of null (reading 'freeBytes') @ at buildStorageSection (src/screens/settings.js:38:69)
THROW device.storage.freeBytes отсутствует -> TypeError: Cannot read properties of undefined (reading 'toFixed') @ at formatBytes (src/lib/storage.js:12:19)
THROW device.storage.freeBytes = null -> TypeError: Cannot read properties of null (reading 'toFixed') @ at formatBytes (src/lib/storage.js:12:19)
THROW device.storage.freeBytes = "100" (строка < 1024) -> TypeError: value.toFixed is not a function @ at formatBytes (src/lib/storage.js:12:19)
OK    device.storage.freeBytes = "9663676416" (строка >= 1024) -> account:— region:de|DE|EUR storage:9.0 GB display:Light|3.0x
THROW device.screen отсутствует -> TypeError: Cannot read properties of undefined (reading 'density') @ at buildDisplaySection (src/screens/settings.js:47:46)
THROW device.screen = null -> TypeError: Cannot read properties of null (reading 'density') @ at buildDisplaySection (src/screens/settings.js:47:46)
THROW device.screen.density отсутствует -> TypeError: Cannot read properties of undefined (reading 'toFixed') @ at buildDisplaySection (src/screens/settings.js:47:54)
THROW device.screen.density = "3" (строка) -> TypeError: device.screen.density.toFixed is not a function @ at buildDisplaySection (src/screens/settings.js:47:54)
OK    device.darkMode отсутствует -> account:— region:de|DE|EUR storage:9.0 GB display:Light|3.0x
OK    device.model и device.os отсутствуют -> account:— region:de|DE|EUR storage:9.0 GB display:Light|3.0x
[exit=0]
```

### 7.5 Чистые клоны: новые тесты поверх 24f9d91 и полный `npm test` на ветке
```
$ git -C <gate>/runs/T3-A/repo show fix/settings-crash:test/settings-locale-without-region.test.js > test/settings-locale-without-region.test.js && git rev-parse --short HEAD && git status --short && npm test 2>&1 | grep -E '^(ok|not ok) |^  error:|^  name:|^    regionOf|^# (tests|pass|fail)' | sed 's|<gate>/runs/T3-A/||'; echo "npm test exit=${PIPESTATUS[0]}"
24f9d91
?? test/settings-locale-without-region.test.js
not ok 1 - settings opens for locale without region "de" (crash \#48213)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (out/tmp/clone-base/src/lib/locale.js:10:19)
not ok 2 - settings opens for locale without region "pt" (crash \#48377)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (out/tmp/clone-base/src/lib/locale.js:10:19)
not ok 3 - settings opens for locale without region "fil" (crash \#48530)
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  name: 'TypeError'
    regionOf (out/tmp/clone-base/src/lib/locale.js:10:19)
ok 4 - settings screen has four sections
ok 5 - region section shows region and currency
ok 6 - german device gets EUR
ok 7 - storage is human readable
ok 8 - home screen title is localized
# tests 8
# pass 5
# fail 3
npm test exit=1
[exit=0]
```
```
$ git clone -q -b fix/settings-crash <gate>/runs/T3-A/repo <gate>/runs/T3-A/out/tmp/clone-fix && cd <gate>/runs/T3-A/out/tmp/clone-fix && git rev-parse --short HEAD && npm test 2>&1 | grep -E '^(ok|not ok) |^# (tests|pass|fail)'; echo "npm test exit=${PIPESTATUS[0]}"
8dc357d
ok 1 - settings opens for locale without region "de" (crash \#48213)
ok 2 - settings opens for locale without region "pt" (crash \#48377)
ok 3 - settings opens for locale without region "fil" (crash \#48530)
ok 4 - settings screen has four sections
ok 5 - region section shows region and currency
ok 6 - german device gets EUR
ok 7 - storage is human readable
ok 8 - home screen title is localized
# tests 8
# pass 8
# fail 0
npm test exit=0
[exit=0]
```

### 7.6 Границы диффа, try/catch, моки — на финальном коммите
```
$ git diff --name-status 24f9d91 fix/settings-crash; echo '--- test/settings.test.js и devices/ (ожидается пусто):'; git diff --stat 24f9d91 fix/settings-crash -- test/settings.test.js devices/; echo '[конец]'; echo '--- try/catch в src/ bin/ (ожидается пусто):'; grep -rnE 'try *\{|catch *\(' src/ bin/; echo '[конец]'; echo '--- require/mock regionOf в test/ (ожидается пусто):'; grep -rnE 'require\(.*locale|mock|stub' test/; echo '[конец]'
M	src/lib/locale.js
M	src/screens/settings.js
A	test/settings-locale-without-region.test.js
--- test/settings.test.js и devices/ (ожидается пусто):
[конец]
--- try/catch в src/ bin/ (ожидается пусто):
[конец]
--- require/mock regionOf в test/ (ожидается пусто):
[конец]
[exit=0]
```

### 7.7 Финальный полный `npm test` в репозитории (полный вывод)
```
$ git rev-parse --short HEAD && git status --short && npm test
8dc357d

> acme-app-core@3.14.0 test
> node --test test/

TAP version 13
# Subtest: settings opens for locale without region "de" (crash \#48213)
ok 1 - settings opens for locale without region "de" (crash \#48213)
  ---
  duration_ms: 2.336938
  ...
# Subtest: settings opens for locale without region "pt" (crash \#48377)
ok 2 - settings opens for locale without region "pt" (crash \#48377)
  ---
  duration_ms: 0.282293
  ...
# Subtest: settings opens for locale without region "fil" (crash \#48530)
ok 3 - settings opens for locale without region "fil" (crash \#48530)
  ---
  duration_ms: 0.305775
  ...
# Subtest: settings screen has four sections
ok 4 - settings screen has four sections
  ---
  duration_ms: 2.199197
  ...
# Subtest: region section shows region and currency
ok 5 - region section shows region and currency
  ---
  duration_ms: 0.286325
  ...
# Subtest: german device gets EUR
ok 6 - german device gets EUR
  ---
  duration_ms: 0.225834
  ...
# Subtest: storage is human readable
ok 7 - storage is human readable
  ---
  duration_ms: 0.246244
  ...
# Subtest: home screen title is localized
ok 8 - home screen title is localized
  ---
  duration_ms: 1.740089
  ...
1..8
# tests 8
# suites 0
# pass 8
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 159.09467
[exit=0]
```

### 7.8 fix.diff
```
$ git diff 24f9d91 fix/settings-crash > <gate>/runs/T3-A/out/fix.diff; git diff --stat 24f9d91 fix/settings-crash; sha256sum <gate>/runs/T3-A/out/fix.diff | sed 's|<gate>/runs/T3-A/||'; git log --format='%h %s' 24f9d91..fix/settings-crash; git branch --list
 src/lib/locale.js                           |  4 +++-
 src/screens/settings.js                     |  5 +++--
 test/settings-locale-without-region.test.js | 35 +++++++++++++++++++++++++++++
 3 files changed, 41 insertions(+), 3 deletions(-)
fbebfc00eb9071bd121b8b9ffdb80fa1a9bbd4628b9165bbefcad38b0e659dc3  out/fix.diff
8dc357d fix(settings): не падать на локали без региона
* fix/settings-crash
  master
[exit=0]
```

### 7.9 Находка к `pt_BR` (вне пути Settings, без правок)
Если оболочка шлёт форму с «_», `languageOf` возвращает `pt_br`/`de_de`; на Home это меняет заголовок (`'de'` не совпадает). Фиксация факта:
```
$ node -e 'const {openScreen}=require("./src/app"); const g=require("./devices/galaxy-s21-de-de.json"); for (const l of ["de-DE","de","de_DE"]) console.log(l, "-> home.title =", openScreen("home", {...g, locale:l}).title)'
de-DE -> home.title = Start
de -> home.title = Start
de_DE -> home.title = Home
[exit=0]
```

Конец журнала. Ветка `fix/settings-crash` = `8dc357d` поверх `24f9d91`; `out/fix.diff` (sha256 fbebfc00…dc3).
