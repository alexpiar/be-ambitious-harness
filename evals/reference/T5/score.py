#!/usr/bin/env python3
# Взвешенные суммы и чувствительность таблицы вариантов эталона T5.
#
# Запуск: python3 -I evals/reference/T5/score.py
# Веса и оценки — те же, что в journal.md (веса записаны до оценок). Только стандартная библиотека.
# Чувствительность: вес одного критерия меняется от 0 до 1 с шагом 0,01, остальные
# масштабируются пропорционально, чтобы сумма оставалась 1; печатается, где меняется лидер.

WEIGHTS = {"К1": 0.30, "К2": 0.20, "К3": 0.20, "К4": 0.15, "К5": 0.15}
SCORES = {  # оценки 1–5, больше — лучше; основания — в reference.md
    "О0 ничего": {"К1": 1, "К2": 1, "К3": 5, "К4": 5, "К5": 4},
    "О1 нанять двоих": {"К1": 2, "К2": 5, "К3": 2, "К4": 1, "К5": 4},
    "О2 аутсорс части": {"К1": 4, "К2": 3, "К3": 2, "К4": 4, "К5": 2},
    "О3 минимальный тест": {"К1": 3, "К2": 2, "К3": 4, "К4": 5, "К5": 3},
    "О4 контракторы на 6 мес": {"К1": 4, "К2": 2, "К3": 2, "К4": 4, "К5": 3},
}


def total(weights, scores):
    return sum(weights[k] * scores[k] for k in weights)


def leader(weights):
    return max(SCORES, key=lambda o: total(weights, SCORES[o]))


def main():
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9
    print("Взвешенные суммы:")
    for o in sorted(SCORES, key=lambda o: -total(WEIGHTS, SCORES[o])):
        print(f"  {o:<26} {total(WEIGHTS, SCORES[o]):.2f}")
    base = leader(WEIGHTS)
    print(f"Лидер при записанных весах: {base}")
    print("Чувствительность (вес одного критерия, остальные пропорционально):")
    for k in WEIGHTS:
        rest = 1 - WEIGHTS[k]
        prev, spans = None, []
        for i in range(0, 101):
            w = i / 100
            ws = {j: (w if j == k else WEIGHTS[j] * (1 - w) / rest) for j in WEIGHTS}
            cur = leader(ws)
            if cur != prev:
                spans.append((w, cur))
                prev = cur
        print(f"  {k} (записан {WEIGHTS[k]:.2f}): " + "; ".join(f"с {w:.2f} — {o}" for w, o in spans))


if __name__ == "__main__":
    main()
