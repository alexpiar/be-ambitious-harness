#!/usr/bin/env python3
# Входная проверка эталона T1 на синтетических материалах (materials/, синтетика для эталона).
#
# Запуск из любого места: python3 -I evals/reference/T1/gate.py
# Только стандартная библиотека. Считает ровно то, что записано в prompt.md, раздел 4:
#   (1) сколько из 10 записей ухода показывают одну и ту же интерфейсную причину (порог — 4);
#   (2) выше ли отказ на экране подтверждения у сессий с признаком этой причины, чем у
#       остальных (нижняя граница 95% ДИ разности > 0, интервал Ньюкомба по Уилсону).
# Печатает воронку по шагам и блок GATE в форме core/gate.md.
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
Z = 1.959964  # 95%

INTERFACE = {"И1", "И2", "И3", "И4"}  # список кодов записан до просмотра записей
MIN_SAME = 4                          # критерий (1)
# Признак причины в аналитике: код → (поле воронки, значение). В синтетике размечен только И4.
SIGN = {"И4": ("device", "mobile_web")}
STEPS = ["cart", "delivery", "payment", "confirm", "placed"]


def wilson(k, n):
    """95% интервал Уилсона для доли k/n."""
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return c - h, c + h


def newcombe(k1, n1, k2, n2):
    """Разность долей p1 − p2 и её 95% интервал (метод Ньюкомба на интервалах Уилсона)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def main():
    funnel = defaultdict(int)  # (устройство, шаг) → сессии за 4 недели
    with open(HERE / "materials" / "funnel.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            funnel[(r["device"], r["step"])] += int(r["sessions"])
    devices = sorted({d for d, _ in funnel})
    with open(HERE / "materials" / "sessions.csv", encoding="utf-8") as f:
        recs = list(csv.DictReader(f))

    print("Воронка за 4 недели, все устройства: потеря на переходе к следующему шагу")
    for a, b in zip(STEPS, STEPS[1:]):
        na = sum(funnel[(d, a)] for d in devices)
        nb = sum(funnel[(d, b)] for d in devices)
        print(f"  {a:>8} → {b:<8} {na:6d} → {nb:6d}  потеря {1 - nb / na:.1%}")
    print("Отказ на экране подтверждения (confirm → не placed) по устройствам")
    for d in devices:
        n, k = funnel[(d, "confirm")], funnel[(d, "confirm")] - funnel[(d, "placed")]
        lo, hi = wilson(k, n)
        print(f"  {d:<10} {k:5d} / {n:5d} = {k / n:.1%} [{lo:.1%}; {hi:.1%}]")

    codes = Counter(r["code"] for r in recs)
    top, n_top = max(((c, k) for c, k in codes.items() if c in INTERFACE), key=lambda x: x[1],
                     default=(None, 0))
    print(f"Коды причин в {len(recs)} записях: " + ", ".join(f"{c} {k}" for c, k in codes.most_common()))

    part1 = n_top >= MIN_SAME
    if not part1:
        outcome, part2_text = "не пройдена", "не считалось: условие (1) не выполнено"
    elif top not in SIGN:
        outcome, part2_text = "данных недостаточно", f"признак причины {top} в аналитике не размечен"
    else:
        field, value = SIGN[top]
        assert field == "device"
        n1 = funnel[(value, "confirm")]
        k1 = n1 - funnel[(value, "placed")]
        n2 = sum(funnel[(d, "confirm")] for d in devices if d != value)
        k2 = n2 - sum(funnel[(d, "placed")] for d in devices if d != value)
        diff, lo, hi = newcombe(k1, n1, k2, n2)
        part2 = lo > 0
        outcome = "пройдена" if part2 else "не пройдена"
        part2_text = (f"отказ {value} {k1 / n1:.1%} против {k2 / n2:.1%} у остальных; "
                      f"разность {diff * 100:+.1f} п.п. [{lo * 100:+.1f}; {hi * 100:+.1f}] → "
                      f"{'нижняя граница > 0' if part2 else 'нижняя граница ≤ 0'}")
    print()
    print("GATE (расчёт; поля действия, критерия и затрат — в journal.md)")
    print(f"наблюдаемый результат: (1) {top} — {n_top} из {len(recs)} записей "
          f"({'≥' if part1 else '<'} {MIN_SAME}); (2) {part2_text}")
    print(f"исход:                 {outcome}")


if __name__ == "__main__":
    main()
