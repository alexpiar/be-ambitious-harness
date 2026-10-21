#!/usr/bin/env bash
# Запускает команду в репозитории и дописывает в журнал команду, вывод и код выхода.
# usage: jrun.sh "<команда>" [рабочий_каталог]
B=<gate>/runs/T3-A
J=$B/out/journal.md
DIR=${2:-$B/repo}
cd "$DIR" || exit 99
out=$(bash -c "$1" 2>&1); rc=$?
{
  echo '```'
  echo "\$ $1"
  printf '%s\n' "$out"
  echo "[exit=$rc]"
  echo '```'
} >> "$J"
printf '%s\n[exit=%s]\n' "$out" "$rc"
