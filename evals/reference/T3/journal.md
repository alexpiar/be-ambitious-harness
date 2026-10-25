# Журнал — T3 · acme-app-core, краш экрана «Настройки»

Работа шла во временной копии фикстуры `evals/runs/2026-10-21-gate/fixtures/t3-acme-settings/` (далее `repo/`), инициализированной как git-репозиторий, чтобы фиксировать порядок коммитами. Время — UTC, 25.10.2026. Пути в выводах укорочены до `repo/`. Полный повтор всех шагов одной командой — `bash evals/reference/T3/check.sh`.

## 18:32:46 — 0. Материалы

Входной проверки нет (план, раздел 1): схема базовая, блока GATE нет. Необходимые материалы есть: репозиторий, три отчёта о краше, Node 20. Поле раздела 2 о строках Region и Currency заполнено: «—» в обеих строках. Необязательных (реальный профиль устройства, код android-shell) нет.

```
$ cp -r <fixture> repo && cd repo && git init -q && git add -A && git commit -qm "app-core 3.14.0 (fixture copy)"
$ git rev-parse HEAD^{tree}
5823e994bbec2eace48434cbd50b9a5fc5c33b0a          # = дерево из evals/runs/2026-10-21-gate/protocol.md
```

## 18:33:00 — 1. Исходный уровень и воспроизведение (до любых правок)

```
$ npm test
ok 1 - settings screen has four sections
ok 2 - region section shows region and currency
ok 3 - german device gets EUR
ok 4 - storage is human readable
ok 5 - home screen title is localized
# tests 5
# pass 5
# fail 0
[exit=0]
$ for f in devices/*.json; do node bin/open-screen.js settings $f > before/$(basename $f); done; sha256sum before/*
df5a3e8cf3751318c2d484283ce2812939d017e20b71864326d4719d42b11715  before/galaxy-s21-de-de.json
05a4b1521fb623ece511e5751d028ca67081425b112d1cb3a49d30cf864705e7  before/iphone-13-en-gb.json
1943dda1467ee37212d3c3bd6eca89289d95badfe0693e61d985699095cbf2ac  before/pixel-7-en-us.json
$ for loc in de pt fil; do 10 × node -e "require('./src/app').openScreen('settings', {...galaxy, locale: '$loc'})"; done
locale=de crashed 10/10
locale=pt crashed 10/10
locale=fil crashed 10/10
$ node -e "…openScreen('settings', {...galaxy, locale: 'de'})"
repo/src/lib/locale.js:10
  return parts[1].toUpperCase();
                  ^
TypeError: Cannot read properties of undefined (reading 'toUpperCase')
    at regionOf (repo/src/lib/locale.js:10:19)
    at buildRegionSection (repo/src/screens/settings.js:23:18)
    at buildSettingsScreen (repo/src/screens/settings.js:11:7)
```

Воспроизводится детерминированно: 30 из 30, стек совпадает с тремя отчётами до строки и колонки. Синтетические профили — копия `devices/galaxy-s21-de-de.json` с заменённым `locale` (допущение: остальные поля как в существующем профиле).

## 18:33:13 — 2. Тест до фикса

Добавлен `test/settings-locale-without-region.test.js` (в эталоне — `T3/test/`): Settings через `openScreen` с `locale` `de`, `pt`, `fil`; четыре секции; строки секции `region` — `[Language = locale, Region = —, Currency = —]`. Исходники не тронуты (`git status`: только новый файл).

```
$ git status --short
?? test/settings-locale-without-region.test.js
$ npm test
not ok 1 - settings opens for locale without region "de" (crash \#48213)
  name: 'TypeError'
not ok 2 - settings opens for locale without region "pt" (crash \#48377)
  name: 'TypeError'
not ok 3 - settings opens for locale without region "fil" (crash \#48530)
  name: 'TypeError'
ok 4 … ok 8 — пять существующих
# tests 8
# pass 5
# fail 3
[exit=1]
$ node --test test/settings-locale-without-region.test.js
  error: "Cannot read properties of undefined (reading 'toUpperCase')"
  stack: regionOf (src/lib/locale.js:10:19) ← buildRegionSection (src/screens/settings.js:23:18) ← buildSettingsScreen ← openScreen (src/app.js:15:10)
```

## 18:33:27 — 3. Фикс причины

Тест зафиксирован коммитом `test: settings opens for locales without region (failing)` раньше любой правки исходников. Затем две правки (`T3/fix.diff`):
- `src/lib/locale.js` — `regionOf` возвращает `null`, если второго подтега нет;
- `src/screens/settings.js` — при `region === null` строки Region и Currency показывают «—»; `currencyFor` не вызывается, неявного USD нет.

```
$ npm test
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
[exit=0]
```

## 18:33:36 — 5. Самопроверка: откат фикса и сравнение вывода

```
$ git stash push -- src/ && npm test && git stash pop     # откат только исходников, тест остаётся
not ok 1 … "de"   error: "Cannot read properties of undefined (reading 'toUpperCase')"
not ok 2 … "pt"   error: "Cannot read properties of undefined (reading 'toUpperCase')"
not ok 3 … "fil"  error: "Cannot read properties of undefined (reading 'toUpperCase')"
# tests 8
# pass 5
# fail 3
[exit=1]
$ for f in devices/*.json; do node bin/open-screen.js settings $f > after/$(basename $f); done; diff -r before after
(пусто) — 3 из 3 профилей совпадают побайтно
```

## 18:33:51 — 5. Граничный ввод и скрытый оракул

```
$ node -e "…for locale of ['pt_BR','zh-Hant','zh-Hant-TW','es-419','DE','','de-']…"
"pt_BR" -> ["pt_br","—","—"]
"zh-Hant" -> ["zh","HANT","USD"]
"zh-Hant-TW" -> ["zh","HANT","USD"]
"es-419" -> ["es","419","USD"]
"DE" -> ["de","—","—"]
"" -> ["","—","—"]
"de-" -> ["de","—","—"]
```

Ни один ввод не бросает. Странные значения — находки, не правки (режим «сохранить масштаб»): `zh-Hant*` даёт Region `HANT` (скрипт принят за регион), `es-419` и `zh-Hant` — неявный USD через `currencyFor`, `pt_BR` с «_» — «—» (регион не распознан, `languageOf` даёт `pt_br`).

Скрытый оракул (sha256 `fdfae773…eef9`, как в протоколе прогона), CWD — копия репозитория:

```
$ node --test evals/runs/2026-10-21-gate/fixtures/hidden/t3-hidden.test.js        # с фиксом
# tests 9
# pass 9
# fail 0
$ git stash push -q -- src/ && node --test …/t3-hidden.test.js; git stash pop -q   # исходный код
not ok 1 - settings opens for locale de
not ok 2 - settings opens for locale pt
not ok 3 - settings opens for locale fil
not ok 4 - settings opens for locale en
# tests 9
# pass 5
# fail 4
```

## 18:34:09 — правка комментария

Комментарий над `regionOf` переписан яснее (код не менялся), коммит фикса исправлен (`--amend`). Повтор: `npm test` → 8 из 8. Итоговый `fix.diff` снят как `git diff <коммит теста> HEAD -- src/`.

## 21:29 — 4. Аудит пути Настроек (незащищённые обращения к `device`)

Выполнен позже остальных шагов, после работы над эталонами данных; фикс от него не зависит. Номера строк — исходного кода. Проверено вызовами `openScreen('settings', {...galaxy, <поле>})` на исправленной копии.

| Место | Обращение | Вход, который роняет | Ошибка |
|---|---|---|---|
| `src/screens/settings.js:23`, `:27` → `src/lib/locale.js:9`, `:5` | `device.locale.split` | `locale` нет или не строка | TypeError (reading 'split') |
| `src/screens/settings.js:37` | `device.storage.freeBytes` | нет `storage` | TypeError (reading 'freeBytes') |
| `src/lib/storage.js:12` | `value.toFixed` | `storage` без `freeBytes` | TypeError (reading 'toFixed') |
| `src/screens/settings.js:46` | `device.screen.density.toFixed` | нет `screen`; `density` не число | TypeError |
| `src/screens/settings.js:45` | `device.darkMode` | нет поля | не падает: «Light» |

Ни одно из этих полей не отсутствует в отчётах о краше; реального профиля затронутых устройств нет, поэтому правок по аудиту нет.
