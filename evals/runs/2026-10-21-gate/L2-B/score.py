"""Еженедельный скоринг: кто уйдёт в ближайшие 30 дней, почему и какой рычаг.

Пример:
  python -I score.py --events ../data/events_2025.csv --asof 2025-12-29 --top 0.10 \
      --out results/risk_list_2025-12-29.csv

Причины считаются самой моделью: для каждой семьи признаков её значения заменяются
«типичными» (медиана не ушедших), и смотрится, насколько падает риск.
"""
import argparse
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

from features import CAT_COLS, build_snapshot, day, load_events

LEVER = {
    "payment_failed": ("не прошло списание {days_since_pf:.0f} дн. назад",
                       "платёжный сценарий: повтор списания, письмо «обновите карту» — до отмены обычно 0–30 дн."),
    "recent_engagement": ("активность упала: {sess_28:.0f} сессий за 28 дн.{decay_txt}, последняя {days_since_session:.0f} дн. назад",
                          "возврат в продукт: персональное напоминание о ценности, сценарий повторной активации"),
    "support_ticket": ("обращение в поддержку {days_since_ticket:.0f} дн. назад",
                       "дожать обращение: проверить, решён ли вопрос, связаться лично"),
    "plan_downgrade": ("понизил план {days_since_dg:.0f} дн. назад",
                       "разговор о цене и плане до следующего списания"),
    "tenure_billing": ("списание через {days_to_bill:.0f} дн., срок жизни {tenure:.0f} дн.",
                       "контакт до ближайшего списания"),
    "onboarding_first14d": ("слабый старт: {sess_first14:.0f} сессий за первые 14 дн. (у остающихся медиана 7)",
                            "онбординг: довести до 2+ функций и регулярного использования"),
    "overall_engagement": ("низкая активность за всё время: {sess_rate:.1f} сессий в неделю",
                           "возврат в продукт"),
    "profile": ("сегмент: {plan}/{channel}/{device}/{country}", "—"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True)
    ap.add_argument("--asof", required=True, help="дата среза YYYY-MM-DD, используются события строго раньше")
    ap.add_argument("--top", type=float, default=0.10, help="доля активной базы в списке")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pkl"))
    a = ap.parse_args()

    M = pickle.load(open(a.model, "rb"))
    model, feats, fams, ref = M["model"], M["features"], M["families"], M["reference"]
    df, users, _ = load_events(a.events)
    T = day(a.asof)
    if T > df["t"].max() + 1:
        print(f"предупреждение: в логе нет событий после {pd.Timestamp('2025-01-01') + pd.Timedelta(days=df['t'].max())}")
    F = build_snapshot(df, users, T)
    raw = F.copy()
    for c in CAT_COLS:
        F[c] = pd.Categorical(F[c], categories=M["cat_levels"][c]).codes.astype(float)
    X = F[feats]
    p = model.predict_proba(X)[:, 1]
    z = model.decision_function(X)  # лог-шансы: не насыщаются, когда причин несколько и риск ~1
    contrib, p_without = {}, {}
    for fam, cols in fams.items():
        Xs = X.copy()
        for col in cols:
            Xs[col] = ref.get(col, np.nan)
        if fam == "payment_failed":
            # пропущенное списание видно и по n_pay < срок/30: «как если бы платёж прошёл»
            Xs["n_pay"] = np.floor(X["tenure"] / 30.0)
        contrib[fam] = z - model.decision_function(Xs)
        p_without[fam] = model.predict_proba(Xs)[:, 1]
    C = pd.DataFrame(contrib)
    PW = pd.DataFrame(p_without)
    out = pd.DataFrame({"user_id": users["user_id"].to_numpy()[F["uid"]], "risk_30d": p.round(4),
                        "plan": raw["plan"], "mrr": users["price"].to_numpy()[F["uid"]]})
    out["expected_mrr_loss"] = (out.risk_30d * out.mrr).round(2)
    order = np.argsort(-C.to_numpy(), axis=1)
    names = np.array(C.columns)
    # Сигналы «уход уже идёт» (свежие, <= 30 дн.) ставятся первыми по приоритету рычага:
    # при риске ~1 атрибуция модели в крайних листьях неустойчива, а рычаг очевиден.
    OVERRIDE = [("payment_failed", "days_since_pf"), ("plan_downgrade", "days_since_dg"),
                ("support_ticket", "days_since_ticket")]
    r1, r2, lever, lever2 = [], [], [], []
    for i in range(len(out)):
        row = raw.iloc[i].to_dict()
        d = row.get("decay_28")
        row["decay_txt"] = f" — {d:.0%} от прежнего темпа" if d == d and d is not None and d < 0.8 else ""
        cand = [fam for fam, col in OVERRIDE if row[col] == row[col] and row[col] <= 30]
        cand += [f for f in names[order[i]] if f not in cand and C.iloc[i][f] > 0.3]
        if not cand:
            cand = [names[order[i, 0]]]
        txt = lambda f: LEVER[f][0].format(**row) + f" (без этого риск {PW.iloc[i][f]:.2f})"
        r1.append(txt(cand[0]))
        r2.append(txt(cand[1]) if len(cand) > 1 else "")
        lever.append(LEVER[cand[0]][1])
        lever2.append(LEVER[cand[1]][1] if len(cand) > 1 and LEVER[cand[1]][1] != LEVER[cand[0]][1] else "")
    out["reason_1"], out["reason_2"], out["lever"], out["lever_2"] = r1, r2, lever, lever2
    out = out.sort_values("risk_30d", ascending=False).reset_index(drop=True)
    k = max(1, int(round(len(out) * a.top)))
    top = out.head(k)
    top.to_csv(a.out, index=False)
    print(f"срез {a.asof}: активных {len(out)}, в списке {k}; ожидаемо уйдут в 30 дн. "
          f"{out.risk_30d.sum():.0f} чел. по всей базе, {top.risk_30d.sum():.0f} из них в списке; "
          f"MRR под риском в списке {top.expected_mrr_loss.sum():.0f}")
    print(top.lever.value_counts().to_string())


if __name__ == "__main__":
    main()
