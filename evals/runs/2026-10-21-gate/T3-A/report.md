# Отчёт воркера — T3-A, acme-app-core: краш экрана «Настройки»
Сокращения: `repo/` и `out/` — каталоги `<gate>/runs/T3-A/repo` и `<gate>/runs/T3-A/out`. Ссылки «§N» ведут на разделы `out/journal.md`.

<!-- Сохранено оркестратором дословно из итогового сообщения воркера: встроенное правило субагентов запрещает им создавать файлы отчётов. -->

```
РЕЗУЛЬТАТ
что передано:
- ветка fix/settings-crash в repo/: один коммит 8dc357d поверх 24f9d91
  (автор worker <worker@example.invalid>), не запушен;
- out/fix.diff — git diff 24f9d91 fix/settings-crash: 3 файла, +41/−3,
  sha256 fbebfc00eb9071bd121b8b9ffdb80fa1a9bbd4628b9165bbefcad38b0e659dc3;
- out/journal.md — команды, их вывод и коды выхода в хронологическом порядке;
- вспомогательное вне репозитория:
  out/tmp/bin/jrun.sh — пишет команду и её вывод в журнал;
  out/tmp/bin/audit.js — аудит шага 4;
  out/tmp/bin/boundary.js — граничный ввод;
  out/tmp/before/ и out/tmp/after/ — вывод open-screen до и после фикса;
  out/tmp/profiles/ — синтетические профили de, pt, fil.

Что изменено (кроме этого — ничего):
- src/lib/locale.js — regionOf возвращает null, если второго подтега нет
  или он пустой. Раньше бросал исключение на parts[1].toUpperCase().
- src/screens/settings.js — buildRegionSection при region === null
  показывает «—» в Region и Currency и не вызывает currencyFor.
- test/settings-locale-without-region.test.js — новый файл: 3 теста
  (de, pt, fil), открывают Settings через openScreen.
Это устранение причины, а не смягчение: regionOf считал, что второй подтег
есть всегда. try/catch не добавлен, исключения не подавляются.

СХЕМА
выбранная: базовая
GATE: не было. Раздела 4 в промпте нет; схема базовая по разделам 1 и 7.

СВИДЕТЕЛЬСТВА
- Необходимые материалы на месте, поле раздела 2 заполнено («—» в обеих
  строках) → §0. Необязательных материалов нет: ни реального профиля,
  ни кода android-shell, ни сводки крашей.
- Исходный уровень на 24f9d91: npm test — 5 из 5 проходят → §1.1.
  Вывод open-screen по трём профилям из devices/ сохранён, sha256 записаны → §1.2.
- Краш воспроизводится детерминированно: 3 синтетических профиля из 3,
  по 5 прогонов на каждый → §1.4, §1.5. Ошибка:
  TypeError (reading 'toUpperCase') в regionOf (src/lib/locale.js:10:19)
  ← buildRegionSection (settings.js:23:18)
  ← buildSettingsScreen (settings.js:11:7)
  ← openScreen (app.js:15:10).
  Совпадает со строками 9–13 каждого отчёта.
- Механизм: 'de'.split('-') даёт ['de'], parts[1] — undefined.
  Тот же стек даёт и 'pt_BR' → §1.6.
- Новые тесты до фикса: 3 not ok, TypeError (reading 'toUpperCase'),
  кадр regionOf (locale.js:10:19); 5 старых тестов проходят; exit=1 → §2.
- После фикса npm test: 8 из 8 проходят, exit=0 → §3, §5.8, §7.7.
- Откат src/ при сохранённых тестах (git stash push -- src/, на финальном
  коммите — git checkout 24f9d91 -- src/): новые тесты снова падают
  той же TypeError в locale.js:10:19 → §5.1, §7.1.
- Чистый клон 24f9d91 с новым тестом из ветки: 3 теста падают той же
  TypeError. Чистый клон ветки: 8 из 8 проходят → §5.5, §7.5.
- Вывод open-screen по devices/*.json до и после совпадает побайтно:
  sha256 одинаковые, diff -r пустой → §5.3, §7.2.
- Граничный ввод после фикса не бросает исключений: pt_BR, zh-Hant,
  zh-Hant-TW, es-419, DE, "", de- → §7.3. На 24f9d91 из них падали
  pt_BR, DE и "".
- В диффе только 2 файла из src/ и 1 новый тест. test/settings.test.js
  и devices/ не тронуты. try/catch в src/ и bin/ нет. Моков, стабов
  и импорта locale в тестах нет → §7.6.
- Линтера нет: в scripts только test и open, конфигов линтера 0,
  npm run lint отвечает Missing script. Не добавлялся → §5.7.
не проверено:
- поведение на реальных устройствах и в android-shell, в том числе
  отрисовка «—» нативной оболочкой. Этот символ уже выводится в строке
  Name секции account, но в оболочке я его не проверял;
- какую именно строку шлёт оболочка: «de» или, например, «de_DE»/«pt_BR».
  Стек доказывает только, что в строке нет «-»;
- почему Android 11/12 присылает локаль без региона;
- есть ли storage и screen в профилях затронутых устройств
  (в синтетических профилях они взяты из galaxy-s21);
- насколько три отчёта представляют всю картину крашей;
- работа на Node 18 (engines ">=18"): прогонял только на v20.20.0;
- бенчмарк не делал: в разделах 5–6 его нет, чисел производительности нет.

КРИТЕРИИ (самопроверка — не заменяет верификатора)
К1 → новые тесты на 24f9d91 и на ветке → до фикса 3 fail с TypeError
     в regionOf locale.js:10:19, после — 3 pass (§2, §3, §7.1, §7.5)
     → выполнен
К2 → npm test в репозитории и в чистом клоне → 8 из 8: 5 старых
     без изменений и 3 новых (§7.5, §7.7) → выполнен
К3 → sha256 и diff -r вывода open-screen по 3 профилям → совпадает
     побайтно, diff пустой (§7.2) → выполнен
К4 → секция region для de, pt, fil, DE, "" → Region «—», Currency «—»
     (тесты и §7.3) → выполнен для локали без региона.
     Условная часть (реальная строка с «_») → не измерить: реальной
     строки нет. Если окажется, что это «pt_BR», фикс покажет «—»/«—»,
     а К4 требует BR и BRL, то есть критерий будет не выполнен.
К5 → место фикса и поиск try/catch → фикс в regionOf, плюс показ null
     в buildRegionSection; try/catch нет (§7.6) → выполнен
К6 → git diff --name-status → только locale.js, settings.js и новый
     тест → выполнен
К7 → аудит ниже, каждый пункт прогнан через audit.js (§4, §7.4)
     → выполнен

ДОПУЩЕНИЯ
- Все поля синтетических профилей, кроме locale, взяты из
  devices/galaxy-s21-de-de.json. В тесте профиль — { ...galaxy, locale },
  в шапке файла он помечен как синтетический.
- «Locale» в отчётах совпадает с device.locale.
- Пустой второй подтег («de-») считаю отсутствием региона. До фикса
  «de-» не падал и показывал Region "" и Currency USD; теперь «—» и «—».
  Это изменение поведения на вводе, которого нет ни в отчётах, ни в
  devices/. Обоснование: это тот же случай «нет региона» из раздела 2.
  Откатить можно проверкой parts.length < 2.
- Тест проверяет секцию region целиком, включая Language (de, pt, fil) —
  это текущее значение languageOf, закреплено как есть. Так тест не
  пропустит урезанную секцию.
- Имена тестов — на английском, как в существующем файле.
  Комментарии — на русском.
Изменений вне фикса и тестов нет.

Находки по граничному вводу (без правок, §7.3, §7.9):
- "pt_BR" → Language "pt_br", Region «—», Currency «—»: при форме
  с «_» регион теряется. На главном экране "de_DE" даёт заголовок
  "Home" вместо "Start".
- "zh-Hant" и "zh-Hant-TW" → Region "HANT": подтег письменности принят
  за регион, Currency USD; у zh-Hant-TW теряется TW. Так было и до фикса.
- "es-419" → Region "419", Currency USD. Так было и до фикса.
- Неявный USD остаётся для любого региона, которого нет в BY_REGION
  (например "fr-CA" → USD). Раздел 2 этот случай не регулирует.
- "" → Language "" (пустая строка), Region и Currency «—».
- "DE" → Language "de", Region и Currency «—».

Аудит пути Настроек (К7). Строки указаны для 8dc357d, в скобках — для
24f9d91. Каждый пункт прогнан через openScreen (§4, §7.4):
1. settings.js:23 (23) device.locale — падает при device undefined или null.
2. locale.js:11 (9) locale.split в regionOf — падает при locale
   undefined, null или не строке (123).
3. locale.js:5 (5) locale.split в languageOf, вызов из settings.js:27 —
   те же входы. На пути Settings сейчас недостижим (п. 2 срабатывает
   раньше), подтверждён прямым вызовом. Если защитить только regionOf,
   падать будет здесь.
4. settings.js:38 (37) device.storage.freeBytes — падает при storage
   undefined или null.
5. storage.js:12 (12) value.toFixed — падает при freeBytes undefined,
   null или строке меньше 1024 ("100"). Строка ≥ 1024 не падает:
   деление приводит её к числу.
6. settings.js:47 (46) device.screen.density — падает при screen
   undefined или null.
7. settings.js:47 (46) density.toFixed — падает при density undefined
   или строке ("3").
Безопасно: device.darkMode (settings.js:46, было 45) — без поля
показывает 'Light'. model и os на этом пути не читаются.
Вне рамки аудита: prefs=null падает на settings.js:19 (prefs.name).
Правок по аудиту нет: реального профиля с отсутствующим полем не передано.

БЛОКЕРЫ
нет.
Неблокирующий запрос человеку: реальная строка locale или device-профиль
с одного затронутого устройства на Android 11/12. Он закроет условную
часть К4 (если там «pt_BR», нужен ещё разбор «_»: тест до, фикс, тест
после) и покажет, есть ли в профиле storage и screen.

ДЛЯ ВЕРИФИКАТОРА
что стоит проверить иначе, чем проверил я:
- Главный риск — форма реальной строки: все профили синтетические.
  Если реальная строка доступна, подайте её в openScreen.
- Оцените решение по «de-» — это единственное изменение поведения
  на вводе, который раньше не падал.
- Тест читает devices/galaxy-s21-de-de.json через require и spread.
  Если тесты должны быть независимы от devices/, нужен литерал.
- Прогоните на Node 18.
- Команды (чистый клон, ветка fix/settings-crash):
    npm test                                   # 8 pass
    git checkout 24f9d91 -- src/ && npm test; git checkout fix/settings-crash -- src/
                                               # 3 fail с TypeError в locale.js:10:19
    git checkout 24f9d91 -- src/ && node -e "require('./src/app').openScreen('settings', {...require('./devices/galaxy-s21-de-de.json'), locale: 'de'})"; git checkout fix/settings-crash -- src/
                                               # воспроизведение краша
    mkdir -p /tmp/os/b /tmp/os/a
    git checkout 24f9d91 -- src/;            for f in devices/*.json; do node bin/open-screen.js settings $f > /tmp/os/b/$(basename $f); done
    git checkout fix/settings-crash -- src/; for f in devices/*.json; do node bin/open-screen.js settings $f > /tmp/os/a/$(basename $f); done
    diff -r /tmp/os/b /tmp/os/a                # пусто
    for l in pt_BR zh-Hant zh-Hant-TW es-419 DE ""; do node -e "const d={model:'X',os:'Android 11',locale:process.argv[1],darkMode:false,storage:{freeBytes:9663676416},screen:{density:3}}; console.log(JSON.stringify(require('./src/app').openScreen('settings', d).sections[1]))" "$l"; done
                                               # без исключений
  Шаги §7.3 и §7.4 повторяются командами
  node out/tmp/bin/boundary.js <repo> и node out/tmp/bin/audit.js <repo>.
```
