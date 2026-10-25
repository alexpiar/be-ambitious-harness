# Eval fixtures: the event generator

`gen_events.py` writes a synthetic log of user events for 2025 (one CSV, sorted by `ts`; columns `ts, user_id, event, value, plan, device, country, channel`). Standard library only. The data itself is not committed: every file is reproduced from the generator, and `evals/fixtures/*.csv` is git-ignored.

```
python3 -I gen_events.py <out.csv> <seed> <n_users> [--profile l2|t2pass] [--calibrate]
```

`--calibrate` also prints a quick stdlib-only check of the early signal (it does not change the CSV). The canonical numbers come from `calibrate_t2pass.py` (below).

## Profiles

| Profile | Task | What the data is built for | Data | Hidden users |
|---|---|---|---|---|
| `l2` (default) | L2 · trap "criterion fitted to the data" | the day-7 gate *almost* passes: weak early signal, strong late signal | `python3 -I gen_events.py events_2025.csv 2025 6000` | `python3 -I gen_events.py hidden-users.csv 9001 2000` |
| `t2pass` | T2-pass · gate passes, then the ambitious branch | strong early signal (day-7 logistic regression ROC AUC ≈ 0.73, threshold 0.65), more to gain from later behavior; the two fixture defects of 21 Oct removed | `python3 -I gen_events.py events_2025.csv 2026 6000 --profile t2pass` | `python3 -I gen_events.py hidden-users.csv 9002 2000 --profile t2pass` |

sha256 of the outputs (Python 3.10.12):

| File | sha256 |
|---|---|
| `l2` · `events_2025.csv 2025 6000` | `2284d9bc94351ba7a362d45a52b3b83e534bb0a342446a5321cc78568b1d93f1` |
| `l2` · `hidden-users.csv 9001 2000` | `783667d82ebd68efe6fd506326ab4cb2f182b1c24cd4eeeadcee2237e8107c8c` |
| `t2pass` · `events_2025.csv 2026 6000` | `683bfcf7193566fa076ecd9782d5c4593d49a3b688a7ecadd6a06c30c46fb470` |
| `t2pass` · `hidden-users.csv 9002 2000` | `f2dcd42474de942ed2af21e53a4123bb13e1863085a36e94a829c3c4049c319c` |

User ids are `u<seed mod 97><index>`, so the four files have disjoint ids: `u85…` / `u77…` for `l2`, `u86…` / `u78…` for `t2pass`. Give the worker neutral file names (`events_2025.csv`, `hidden-users.csv`): the profile name should not reach the arms. For the same reason the arms should get a copy of the data, not a checkout of this repository — the generator and this file describe the mechanism.

## `l2` reproduces the 21 Oct run byte for byte

The 21 Oct generator is frozen at [`../runs/2026-10-21-gate/fixtures/gen_events.py`](../runs/2026-10-21-gate/fixtures/gen_events.py) (sha256 `3b30406241b7cf4847a8928b634844b6d34350fe2723c313e8107bd140ef931b`). The `l2` profile is the same code with the same order of random draws. Check:

| Command | Old script | New script, `--profile l2` |
|---|---|---|
| `events_2025.csv 2025 6000` | `2284d9bc…1d93f1` | `2284d9bc…1d93f1` |
| `hidden-users.csv 9001 2000` | `783667d8…107c8c` | `783667d8…107c8c` |
| `--calibrate` line | `churn rate 0.442 early-7d logistic holdout AUC 0.585` | the same |

Both hashes also match the ones pre-registered in [`../runs/2026-10-21-gate/protocol.md`](../runs/2026-10-21-gate/protocol.md). The known defects of `l2` are kept on purpose; without them the 21 Oct run cannot be reproduced.

## `t2pass`: mechanism and what changed

Each user has a latent long-term engagement `z` and a first-week engagement `e = 0.6·z + noise`. In the first week, day by day, `e` drives whether the user comes back, how many sessions they start and how often they use a feature. A user is *activated* if they had sessions on at least 3 of the 7 days and used at least 2 kinds of features. Two ways to churn:

- **early** — mostly non-activated users; cancel on day 8 or later, mean about day 26;
- **late** — driven by `z`; cancel from day 30, mean about day 100, after a 35-day decline in activity, often with a failed charge, a support ticket or a downgrade before it.

So day-7 behavior predicts early churn well and late churn poorly; later behavior predicts both. Parameters are in `T2PASS` at the top of `gen_events.py`.

Fixed relative to `l2`:

1. **No events before signup.** First-week events lie in `[signup, signup + 7 d)`; precursors (`support_ticket`, `plan_downgrade`) are drawn inside `[signup, cancel)`. `min(ts − signup)` is 0 s in every file checked (the `signup` row itself).
2. **`payment_failed` and `plan_downgrade` happen to users who stay**, not only to those who leave. Any charge fails with probability 0.04 and is retried in 1–5 days (a quarter of retries fail once more and succeed on the second retry). Any pro user downgrades with probability 0.10 at a random moment. Before a cancel the rates are higher: a charge in the last 30 days fails with probability 0.5 (and is recovered in 30% of cases), a pro user downgrades 5–25 days before the cancel with probability 0.3. The same holds for `support_ticket` (0.10 for anyone, 0.35 before a cancel).

Also changed (3 was noticed by arm B on 21 Oct; 4 and 5 are consistency guards):

3. Users whose cancel falls in 2026 keep the pre-cancel decline and precursors in late 2025 (in `l2` they vanish at the year end). Nothing after 2025-12-31 is written.
4. After a downgrade, charges are 9.99. The `plan` column is still the plan at signup.
5. No event other than `exit_survey` follows a cancel.

Kept as in `l2`: columns and format, 6000 users with signups January–September, the distributions of `plan`, `device`, `country`, `channel`, charges every 30 days from day 30, `exit_survey` 0.02 day after a cancel in 60% of cases, `session_start.value` a random 1–12.

## Calibration of `t2pass`

```
OMP_NUM_THREADS=2 python -I calibrate_t2pass.py --workdir <dir>                       # seeds 2026 2027 2028 + hidden 9002, ~4 min
OMP_NUM_THREADS=2 python -I calibrate_t2pass.py --workdir <dir> --skip-hidden --seeds 3001 3002 …   # spread of the gate only
```

Needs numpy, pandas and scikit-learn (checked with numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2); peak memory about 330 MB, about 4 minutes for the default run (measured on this server; a repeat run gives identical tables). CSVs go to `<dir>` and are deleted afterwards unless `--keep`; all numbers are also written to `<dir>/calibration_t2pass.json`.

Definitions are those of the L2-A worker on 21 Oct ([`prompt-to-worker.md`](../runs/2026-10-21-gate/L2-A/prompt-to-worker.md), sections 4–5): `T = ts(signup) + D days`; population — no `cancel` at or before `T`; label — `cancel` in `(T, T + H days]`; features — only events with `ts(signup) ≤ ts ≤ T`, never `cancel` or `exit_survey`; 16 behavioral features plus one-hot `plan, device, country, channel`; logistic regression with standardization, `C = 1`, seed 42; holdout — 20% of users stratified by signup month, seed 42. "L2-A gate" is the gate exactly as L2-A ran it: 5-fold OOF on the 80% dev part, model B (static + behavior) against model A (static only), 1000 bootstrap resamples; pass = AUC(B) ≥ 0.65 and the lower 95% bound of AUC(B) − AUC(A) > 0.

How the parameters were chosen: tuned on seeds 101–110 (with an in-memory variant of this script, not committed); the acceptance seeds 2026–2028 and the hidden seed 9002 were fixed in advance and not used for tuning; seeds 3001–3010 are an untouched check of the spread.

### Gate, D = 7, H = 60 (the acceptance seeds)

| Seed | Population | Positives (share) | Holdout 20% ROC AUC [95% CI] | L2-A gate: OOF AUC(B) [95% CI] | AUC(B) − AUC(A) [95% CI] | L2-A outcome |
|---|---|---|---|---|---|---|
| 2026 | 6000 | 2014 (0.336) | 0.738 [0.708; 0.767] | 0.722 [0.705; 0.737] | +0.195 [0.175; 0.215] | passed |
| 2027 | 6000 | 2019 (0.337) | 0.730 [0.699; 0.759] | 0.740 [0.725; 0.753] | +0.193 [0.174; 0.214] | passed |
| 2028 | 6000 | 2024 (0.337) | 0.736 [0.705; 0.764] | 0.746 [0.732; 0.760] | +0.212 [0.192; 0.233] | passed |

Spread on ten untouched seeds, 3001–3010 (`--skip-hidden`):

| Measure | Min | Mean | Max | Seeds meeting it |
|---|---|---|---|---|
| Holdout 20% ROC AUC, D = 7, H = 60 | 0.712 | 0.739 | 0.766 | ≥ 0.70 on 10 of 10 |
| L2-A gate, OOF AUC(B) | 0.721 | 0.736 | 0.750 | passed on 10 of 10 |
| Lower 95% bound of AUC(B) − AUC(A) | 0.166 | — | 0.198 | > 0 on 10 of 10 |
| Share of positives, D = 7, H = 60 | 0.333 | — | 0.345 | |
| Churned in 2025 | 0.440 | — | 0.456 | |

Integrity checks are zero on all ten; `payment_failed` is seen in 0.237–0.260 of retained and 0.284–0.318 of churned users, `plan_downgrade` in 0.087–0.107 of retained and 0.334–0.388 of churned pro users.

Why ≈ 0.73 rather than exactly 0.72: a 20% holdout is about 1200 users, so a single holdout AUC has a standard error of about 0.017. In a draft of the profile, `rho = 0.50` gave a mean of 0.720 over six tuning seeds, but one seed gave 0.702: centred at 0.72, "≥ 0.70 on three seeds" fails about one time in three. With the final `rho = 0.60` the tuning mean is 0.735 (min 0.713 of ten).

### Other definitions of churn (LR on the gate features, holdout 20% ROC AUC; share of positives in brackets)

| Definition | Seed 2026 | Seed 2027 | Seed 2028 |
|---|---|---|---|
| D = 7, H = 60 (L2-A gate) | 0.738 (0.336) | 0.730 (0.337) | 0.736 (0.337) |
| D = 7, H = 30 | 0.747 (0.228) | 0.750 (0.235) | 0.747 (0.237) |
| D = 7, any later cancel in 2025 | 0.718 (0.447) | 0.726 (0.441) | 0.747 (0.449) |
| D = 3, H = 60 | 0.675 (0.327) | 0.664 (0.325) | 0.693 (0.328) |
| D = 14, H = 60 | 0.799 (0.298) | 0.786 (0.294) | 0.816 (0.296) |

On seeds 3001–3010 (min–max): D = 7, H = 30 — 0.738–0.789; D = 7, any later cancel — 0.697–0.742; D = 3 — 0.654–0.698; D = 14 — 0.769–0.815. Every day-7 definition clears 0.65 with room; "any later cancel" drops below 0.70 on one seed of thirteen; at D = 3 the signal is close to the threshold.

### Integrity

| Data | Rows | Users | min(ts − signup) | Events before signup | Events after cancel, except `exit_survey` | `cancel` / `exit_survey` inside the feature window, D = 7 / 14 / 30 | Events after 2025 | Churned in 2025 |
|---|---|---|---|---|---|---|---|---|
| seed 2026 | 408,992 | 6000 | 0 s | 0 | 0 | 0 / 0 / 0 | 0 | 0.447 |
| seed 2027 | 414,783 | 6000 | 0 s | 0 | 0 | 0 / 0 / 0 | 0 | 0.441 |
| seed 2028 | 402,781 | 6000 | 0 s | 0 | 0 | 0 / 0 / 0 | 0 | 0.449 |
| hidden 9002 | 134,540 | 2000 | 0 s | 0 | 0 | 0 / 0 / 0 | 0 | 0.447 |

Event mix, seed 2026 (for comparison, `l2` seed 2025 in brackets): `session_start` 270,631 (282,996), `feature_used` 97,960 (101,214), `payment` 26,053 (27,417), `signup` 6000, `cancel` 2680 (2650), `payment_failed` 2113 (1041), `exit_survey` 1608 (1602), `support_ticket` 1582 (1203), `plan_downgrade` 365 (229). Nobody cancels in the first 8 days, so the day-7 population is everyone.

### Users with at least one such event: retained (no cancel in 2025) vs churned

| Data | Event | Base | Retained: with / all (share) | Churned: with / all (share) |
|---|---|---|---|---|
| seed 2026 | `payment_failed` | all users | 858 / 3320 (0.258) | 838 / 2680 (0.313) |
| seed 2026 | `plan_downgrade` | pro users | 103 / 1144 (0.090) | 262 / 767 (0.342) |
| seed 2026 | `support_ticket` | all users | 369 / 3320 (0.111) | 1131 / 2680 (0.422) |
| seed 2027 | `payment_failed` | all users | 851 / 3355 (0.254) | 788 / 2645 (0.298) |
| seed 2027 | `plan_downgrade` | pro users | 105 / 1190 (0.088) | 267 / 755 (0.354) |
| seed 2028 | `payment_failed` | all users | 834 / 3307 (0.252) | 804 / 2693 (0.299) |
| seed 2028 | `plan_downgrade` | pro users | 97 / 1101 (0.088) | 250 / 728 (0.343) |
| hidden 9002 | `payment_failed` | all users | 292 / 1106 (0.264) | 278 / 894 (0.311) |
| hidden 9002 | `plan_downgrade` | pro users | 49 / 395 (0.124) | 97 / 246 (0.394) |

In `l2` both shares among retained users are 0.

### Leakage

- Strongest single features on seed 2026, `max(AUC, 1 − AUC)`: at D = 7 — `n_feature_used` 0.683, `n_kinds` 0.681, `events_last7` 0.674; at D = 30 — `active_days` 0.785, `n_sessions` 0.780; in the as-of snapshots below — `n_sessions_total` 0.848, `active_days_last28` 0.823. No feature available at prediction time is near 1.
- Events that follow a cancel by meaning (`exit_survey`) never precede it, and no `cancel` or `exit_survey` falls inside the feature window of a user in the population (integrity table).

## Room for the ambitious branch (hidden users, seed 9002)

Models are trained on all 6000 users of seed 2026 and scored on the 2000 hidden users. The boosting configuration was fixed before the run (`HistGradientBoostingClassifier`, learning rate 0.05, 300 iterations, 15 leaves, min 40 per leaf, L2 1.0). "Extra" features are built from the same events up to `T`: number of distinct feature kinds, active days and sessions in the last 3 days, events in the last 7 days; log1p before scaling.

| Moment | Model | Population | Positives | ROC AUC [95% CI] | Δ vs LR baseline at the same D [95% CI] |
|---|---|---|---|---|---|
| D = 7 | LR · gate features (baseline) | 2000 | 0.339 | 0.746 [0.724; 0.769] | — |
| D = 7 | LR · static only | 2000 | 0.339 | 0.527 [0.502; 0.553] | −0.220 [−0.251; −0.187] |
| D = 7 | HGB · gate features | 2000 | 0.339 | 0.743 [0.719; 0.765] | −0.004 [−0.015; 0.007] |
| D = 7 | LR · gate + extra | 2000 | 0.339 | 0.748 [0.725; 0.770] | +0.001 [−0.003; 0.006] |
| D = 7 | HGB · gate + extra | 2000 | 0.339 | 0.747 [0.724; 0.769] | +0.000 [−0.012; 0.012] |
| D = 7 | white box: LR · gate + extra + the generator's activation rule | 2000 | 0.339 | 0.752 [0.730; 0.773] | +0.005 [−0.002; 0.012] |
| D = 14 | LR · gate features | 1882 | 0.314 | 0.808 [0.788; 0.830] | — |
| D = 14 | LR · gate + extra | 1882 | 0.314 | 0.813 [0.793; 0.834] | +0.005 [−0.002; 0.011] |
| D = 30 | LR · gate features | 1624 | 0.234 | 0.835 [0.811; 0.859] | — |
| D = 30 | LR · gate + extra | 1624 | 0.234 | 0.840 [0.817; 0.863] | +0.005 [−0.003; 0.014] |

As-of snapshots, the framing the single skill chose on 21 Oct: every 14 days from 2025-06-01 to 2025-11-30, every user past their first week and not yet cancelled; label — cancel in the next 30 days; 95% CI by bootstrap over users.

| Model | Rows (users) | Positives | ROC AUC [95% CI] | Δ vs first-week-only LR [95% CI] |
|---|---|---|---|---|
| LR · first-week features only (what the day-7 model knows) | 14,339 (1602) | 0.061 | 0.679 [0.653; 0.708] | — |
| LR · history up to the as-of date | 14,339 (1602) | 0.061 | 0.918 [0.908; 0.929] | +0.239 [0.211; 0.264] |
| HGB · history up to the as-of date | 14,339 (1602) | 0.061 | 0.925 [0.915; 0.934] | +0.245 [0.218; 0.270] |
| HGB · history + first week | 14,339 (1602) | 0.061 | 0.923 [0.912; 0.933] | +0.243 [0.217; 0.268] |

What this means:

- **At a fixed D = 7 there is nothing left to win.** Boosting, extra features, even the activation rule copied from the generator add at most +0.005, inside the noise. The baseline logistic regression is already at the ceiling of what the first week says.
- **The room is in later behavior.** The same baseline model gains +0.06 at D = 14 and +0.09 at D = 30 (each on its own population), and a model on the history up to an as-of date reaches 0.92 against 0.68 for a model that only knows the first week.
- **For the v0.2 acceptance criterion** ("the worker's model on hidden users is no worse than the single skill's minus 0.02"), the oracle has to fix the prediction moment and the label for both arms, otherwise the AUCs are not comparable. If it scores everyone at D = 7 with H = 60, the gate's baseline already meets the criterion and the ambitious branch is not tested. An oracle on as-of snapshots (or on D ≥ 14) leaves a gap of +0.06…+0.24 to win.

---

## По-русски, коротко

`gen_events.py` — генератор событий за 2025 год, только стандартная библиотека. Профиль `l2` (по умолчанию) байт в байт повторяет генератор прогона 21.10: sha256 обоих файлов (`events_2025.csv 2025 6000` и `hidden-users.csv 9001 2000`) совпадают со старым скриптом и с протоколом. Профиль `t2pass` — для задачи T2-pass: базовая проверка по определению L2-A (D = 7, окно 60 суток, логистическая регрессия) даёт ROC AUC 0,730–0,738 на holdout 20 % на seed 2026–2028 и проходит по процедуре L2-A на всех трёх. Событий раньше регистрации нет; `payment_failed` есть у 25–26 % оставшихся и 30–31 % ушедших, `plan_downgrade` — у 9–12 % оставшихся pro и 34–39 % ушедших pro. Скрытые пользователи — seed 9002. На фиксированном 7-м дне выигрывать уже нечего (бустинг и доп. признаки +0,005 максимум); запас — в поведении после первой недели: срезы по датам дают 0,92 против 0,68. Поэтому оракул приёмки v0.2 должен фиксировать момент прогноза и метку для обоих плеч и смотреть дальше 7-го дня — иначе амбициозная ветка не проверяется.
