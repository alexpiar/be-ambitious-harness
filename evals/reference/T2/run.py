# Эталон T2 (утечка и holdout): план — prompt.md рядом.
# Одна команда из корня репозитория (около 5 минут, пик памяти около 760 МБ):
#   OMP_NUM_THREADS=2 python -I evals/reference/T2/run.py
# Данные — evals/fixtures/gen_events.py, профиль l2, seed 2025, 6000 (sha256 сверяется).
# Порядок: holdout (сверка с holdout_ids.txt) → качество данных и подозрительные признаки на dev
# по правилу 0.3 → входная проверка D = 7 → базовая ветка: модель на срезах по датам без прокси
# метки, абляция → одна оценка на holdout → важность → model.json (сдаётся) и
# model_with_proxies.json (только для измерения цены решения). Итог — results.json.
#   --stage gate — до исхода проверки; --stage dev — без holdout.
import argparse
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I не кладёт папку скрипта в sys.path
import ref_lib as R  # noqa: E402

sc = R.sc
# семьи признаков по событию: срезы (HIST) и первая неделя (BEHAV)
FAMILY = {'payment_failed': (['n_payment_failed_last30', 'unrecovered_failure'], ['n_payment_failed']),
          'plan_downgrade': (['had_downgrade'], ['had_downgrade']),
          'support_ticket': (['n_support_ticket_last30'], ['n_support_ticket'])}
DERIVED = (['n_payment'], ['n_payment'])  # число списаний — вместе с payment_failed, если недостача = сбой


def proxy_rule(q):
    """Правило 0.3 prompt.md: событие есть у >= 30 ушедших и ни у одного оставшегося → прокси метки."""
    out = {}
    for e, s in q['precursors'].items():
        out[e] = dict(proxy=bool(s['churned_with'] >= 30 and s['retained_with'] == 0),
                      churned_with=s['churned_with'], retained_with=s['retained_with'])
    out['n_payment_derived'] = bool(out['payment_failed']['proxy'] and q['retained_with_missing_payments'] == 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=['gate', 'dev', 'all'], default='all')
    ap.add_argument('--workdir', help='куда сгенерировать CSV (по умолчанию временный каталог, удаляется)')
    a = ap.parse_args()
    t0 = time.time()
    tmp = None if a.workdir else tempfile.TemporaryDirectory(prefix='ref-t2-')
    out = {}

    # 0.1 holdout — первым действием
    path, out['data_sha256'] = R.generate('l2', a.workdir or tmp.name)
    ho, out['holdout_sha256'], _ = R.seal_holdout(path, os.path.join(R.HERE, 'holdout_ids.txt'))
    df = R.load(path)
    U = R.users_table(df)
    dev_u = U.index[~U.index.isin(ho)]
    print(f'holdout: {len(ho)} пользователей, sha256 {out["holdout_sha256"]}')

    # 0.2–0.3 качество данных и подозрительные признаки — только dev
    out['quality_dev'] = q = R.quality(df[df['user_id'].isin(dev_u)], U.loc[dev_u])
    out['proxy_rule'] = pr = proxy_rule(q)
    drop_hist, drop_behav = [], []
    for e, (h, b) in FAMILY.items():
        if pr[e]['proxy']:
            drop_hist += h
            drop_behav += b
    if pr['n_payment_derived']:
        drop_hist += DERIVED[0]
        drop_behav += DERIVED[1]
    main_hist = [c for c in sc.HIST if c not in drop_hist]
    gate_behav = [c for c in sc.BEHAV if c not in drop_behav]
    out['excluded'] = dict(snapshots=drop_hist, first_week=drop_behav)
    print('правило 0.3: ' + '; '.join(f"{e}: ушедших {v['churned_with']}, оставшихся {v['retained_with']} → "
                                      f"{'прокси' if v['proxy'] else 'нет'}" for e, v in pr.items() if e in FAMILY)
          + f"; n_payment вместе с payment_failed: {pr['n_payment_derived']}")
    print(f'исключены из основной модели: {drop_hist}')
    E = sc.Events(df)

    # 1. входная проверка, D = 7, только dev, без прокси метки
    P7 = R.d_points(U.loc[dev_u], 7, 60)
    out['gate'] = g = R.gate_l2a(R.features(E, P7), P7['y'].to_numpy(), gate_behav)
    print(f"GATE D=7 (dev): популяция {g['population']}, положительных {g['positives']}; AUC(Б) {R.f3(g['auc_B'])} "
          f"{R.fci(g['auc_B_ci'])}; AUC(Б) − AUC(А) {g['diff']:+.4f} {R.fci(g['diff_ci'])} → {g['outcome']}")
    if a.stage == 'gate':
        print(f'stage gate: {time.time() - t0:.0f} с')
        return

    # 2.3 абляция на dev: те же срезы, тот же C, что выберет основная модель
    Pd = R.snapshot_points(U.loc[dev_u], R.SNAP_TRAIN, R.SNAP_H)
    Fd, yd = R.features(E, Pd), Pd['y'].to_numpy()
    folds = R.user_folds(Pd['user_id'].to_numpy())
    holdout = a.stage == 'all'
    R.stage_snapshots(out, 'stage2_snapshots', df, E, U, dev_u, ho, main_hist, holdout=False)  # C по CV
    C = float(out['stage2_snapshots']['chosen'].split('C=')[1])
    variants = {'основная (без прокси)': main_hist,
                '+ payment_failed и n_payment': main_hist + [c for c in drop_hist if c != 'had_downgrade'],
                '+ plan_downgrade': main_hist + [c for c in drop_hist if c == 'had_downgrade'],
                'все признаки': list(sc.HIST)}
    abl = {}
    for name, cols in variants.items():
        lg = [c for c in R.LOG1P_HIST if c in cols]
        o, _ = R.oof(Fd, yd, folds, lambda f, t, cols=cols, lg=lg: R.fit_lr(f, t, cols, lg, C))
        abl[name] = R._auc(yd, o)
    out['ablation_dev_oof'] = dict(C=C, auc=abl)
    print('абляция, OOF ROC AUC на dev: ' + '; '.join(f'{k} {v:.4f}' for k, v in abl.items()))
    if not holdout:
        print(f'stage dev: {time.time() - t0:.0f} с')
        return
    lg_all = [c for c in R.LOG1P_HIST if c in sc.HIST]
    with_proxies = R.fit_lr(Fd, yd, list(sc.HIST), lg_all, C)
    model = R.stage_snapshots(out, 'stage2_snapshots', df, E, U, dev_u, ho, main_hist, holdout=True,
                              compare={'все признаки (с прокси метки)': with_proxies})

    trained = dict(data='gen_events.py l2 seed 2025 6000', data_sha256=out['data_sha256'], users='dev 80 %',
                   holdout_sha256=out['holdout_sha256'], rows=out['stage2_snapshots']['rows'],
                   snapshots='каждые 7 суток 2025-02-01…2025-12-01')
    definition = dict(moment='любая дата asof', population='signup <= asof, нет cancel с ts <= asof',
                      label='cancel в (asof, asof + 30 суток]',
                      features='события с ts(signup) <= ts <= asof, кроме cancel и exit_survey; история + статика')
    R.save_json(R.model_json(model, 'T2 · ЛР на срезах по датам, без прокси метки',
                             dict(definition, excluded=drop_hist), trained), os.path.join(R.HERE, 'model.json'))
    R.save_json(R.model_json(with_proxies, 'T2 · для измерения: те же срезы со всеми признаками (не сдаётся)',
                             definition, trained), os.path.join(R.HERE, 'model_with_proxies.json'))
    out['model_sha256'] = R.sha256(os.path.join(R.HERE, 'model.json'))
    out['model_with_proxies_sha256'] = R.sha256(os.path.join(R.HERE, 'model_with_proxies.json'))
    R.save_json(out, os.path.join(R.HERE, 'results.json'))
    s = out['stage2_snapshots']
    hs = s['holdout']
    print(f"\nholdout на срезах: {hs['rows']} строк ({hs['users']} польз.), {hs['positives']} положительных")
    R.print_metrics(hs, ['модель на срезах', 'все признаки (с прокси метки)', 'ЛР на статике',
                         'правило: дней с последней сессии', 'базовый уровень'])
    R.print_importance(s['importance'])
    print(f"одиночные ROC AUC > 0.90 на dev: "
          f"{[k for k, v in s['single_feature_auc_dev'].items() if v > 0.90] or 'нет'}; "
          f"максимум {max(s['single_feature_auc_dev'].values()):.3f}")
    print(f'stage all: {time.time() - t0:.0f} с')


if __name__ == '__main__':
    main()
