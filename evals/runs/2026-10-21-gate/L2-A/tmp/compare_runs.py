# Сравнение всех числовых значений двух прогонов churn.py all (JSON) и CSV-таблиц
import json, sys, os, numpy as np, pandas as pd
a, b = sys.argv[1], sys.argv[2]
def flat(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items(): yield from flat(v, f"{p}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from flat(v, f"{p}[{i}]")
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield p, float(o)
tot, worst = 0, (0.0, "")
for fn in sorted(os.listdir(a)):
    if fn.endswith(".json") and os.path.exists(os.path.join(b, fn)):
        da = dict(flat(json.load(open(os.path.join(a, fn))))); db = dict(flat(json.load(open(os.path.join(b, fn)))))
        assert da.keys() == db.keys(), fn
        for k in da:
            if "elapsed" in k: continue
            d = abs(da[k] - db[k]) if not (np.isnan(da[k]) and np.isnan(db[k])) else 0.0
            tot += 1
            if d > worst[0]: worst = (d, fn + k)
for fn in sorted(os.listdir(a)):
    if fn.endswith(".csv") and os.path.exists(os.path.join(b, fn)):
        x = pd.read_csv(os.path.join(a, fn)); y = pd.read_csv(os.path.join(b, fn))
        num = x.select_dtypes("number").columns
        d = float(np.nanmax(np.abs(x[num].to_numpy() - y[num].to_numpy()))) if len(num) else 0.0
        same_other = bool((x.drop(columns=num).fillna("") == y.drop(columns=num).fillna("")).all().all())
        tot += x[num].size
        print(f"{fn}: max|diff| = {d:.3g}; нечисловые совпадают: {same_other}")
        if d > worst[0]: worst = (d, fn)
print(f"сравнено чисел: {tot}; максимум |разности| = {worst[0]:.3g} ({worst[1]})")
