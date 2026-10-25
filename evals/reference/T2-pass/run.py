# Эталон T2-pass (gate пройдена → амбициозная ветка в пределе 2 часа): план — prompt.md рядом.
# Одна команда из корня репозитория (около 5 минут, пик памяти около 700 МБ):
#   OMP_NUM_THREADS=2 python -I evals/reference/T2-pass/run.py
# Данные — evals/fixtures/gen_events.py, профиль t2pass, seed 2026, 6000 (sha256 сверяется).
# Порядок: holdout (сверка с holdout_ids.txt) → качество данных на dev → входная проверка D = 7
# (раздел 4 prompt.md) → этап 2, базовая ветка D = 14 → этап 3, амбициозная ветка: модель на
# срезах по датам с историей → одна оценка каждой модели на holdout → model_base.json (D = 14),
# model.json (срезы; её по умолчанию грузит score.py). Итог — results.json.
#   --stage gate — только до исхода проверки; --stage dev — без holdout.
import argparse
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I не кладёт папку скрипта в sys.path
import ref_lib as R  # noqa: E402

sc = R.sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=['gate', 'dev', 'all'], default='all')
    ap.add_argument('--workdir', help='куда сгенерировать CSV (по умолчанию временный каталог, удаляется)')
    a = ap.parse_args()
    t0 = time.time()
    tmp = None if a.workdir else tempfile.TemporaryDirectory(prefix='ref-t2pass-')
    out = {}

    # 0.2 holdout — первым действием
    path, out['data_sha256'] = R.generate('t2pass', a.workdir or tmp.name)
    ho, out['holdout_sha256'], _ = R.seal_holdout(path, os.path.join(R.HERE, 'holdout_ids.txt'))
    df = R.load(path)
    U = R.users_table(df)
    dev_u = U.index[~U.index.isin(ho)]
    print(f'holdout: {len(ho)} пользователей, sha256 {out["holdout_sha256"]}')

    # 0.1 качество данных — только dev
    out['quality_dev'] = R.quality(df[df['user_id'].isin(dev_u)], U.loc[dev_u])
    E = sc.Events(df)

    # 1. входная проверка, D = 7, только dev
    P7 = R.d_points(U.loc[dev_u], 7, 60)
    out['gate'] = g = R.gate_l2a(R.features(E, P7), P7['y'].to_numpy())
    print(f"GATE D=7 (dev): популяция {g['population']}, положительных {g['positives']}; AUC(Б) {R.f3(g['auc_B'])} "
          f"{R.fci(g['auc_B_ci'])}; AUC(Б) − AUC(А) {g['diff']:+.4f} {R.fci(g['diff_ci'])} → {g['outcome']}")
    if a.stage == 'gate':
        print(f'stage gate: {time.time() - t0:.0f} с')
        return

    # 2. базовая ветка — при любом исходе
    holdout = a.stage == 'all'
    base = R.stage_d14(out, df, E, U, dev_u, ho, holdout=holdout)

    # 3. амбициозная ветка — только после «пройдена» (предел 2 часа задан в prompt.md)
    if not g['passed']:
        print('проверка не пройдена: амбициозная ветка не выполняется')
        amb = None
    else:
        t3 = time.time()
        amb = R.stage_snapshots(out, 'stage3_snapshots', df, E, U, dev_u, ho, sc.HIST, holdout=holdout,
                                compare={'базовая модель D=14': base} if base else None)
        print(f'этап 3: счёт {time.time() - t3:.0f} с')
    if not holdout:
        R.save_json(out, os.path.join(R.HERE, 'results_dev.json'))
        print(f'stage dev: {time.time() - t0:.0f} с')
        return

    trained = dict(data='gen_events.py t2pass seed 2026 6000', data_sha256=out['data_sha256'], users='dev 80 %',
                   holdout_sha256=out['holdout_sha256'])
    feats = 'события с ts(signup) <= ts <= asof, кроме cancel и exit_survey'
    R.save_json(R.model_json(base, 'T2-pass · базовая · ЛР на 14-й день',
                             dict(moment='T = ts(signup) + 14 суток', population='без cancel с ts <= T',
                                  label='cancel в (T, T + 60 суток]', features=feats + '; поведение BEHAV + статика'),
                             dict(trained, rows=out['stage2_cv']['population'])),
                os.path.join(R.HERE, 'model_base.json'))
    out['model_base_sha256'] = R.sha256(os.path.join(R.HERE, 'model_base.json'))
    if amb is not None:
        R.save_json(R.model_json(amb, 'T2-pass · амбициозная · ЛР на срезах по датам',
                                 dict(moment='любая дата asof', population='signup <= asof, нет cancel с ts <= asof',
                                      label='cancel в (asof, asof + 30 суток]',
                                      features=feats + '; история HIST + статика'),
                                 dict(trained, rows=out['stage3_snapshots']['rows'],
                                      snapshots='каждые 7 суток 2025-02-01…2025-12-01')),
                    os.path.join(R.HERE, 'model.json'))
        out['model_sha256'] = R.sha256(os.path.join(R.HERE, 'model.json'))
    R.save_json(out, os.path.join(R.HERE, 'results.json'))
    h = out['holdout']
    print(f"\nэтап 2, holdout D=14: {h['population']} пользователей, {h['positives']} положительных")
    R.print_metrics(h, ['модель D=14', 'ЛР на статике', 'правило −n_sessions', 'базовый уровень'])
    R.print_importance(out['importance'])
    if amb is not None:
        s = out['stage3_snapshots']
        hs = s['holdout']
        print(f"\nэтап 3, holdout на срезах: {hs['rows']} строк ({hs['users']} польз.), {hs['positives']} положительных")
        R.print_metrics(hs, ['модель на срезах', 'базовая модель D=14', 'ЛР на статике',
                             'правило: дней с последней сессии', 'базовый уровень'])
        R.print_importance(s['importance'])
    print(f'stage all: {time.time() - t0:.0f} с')


if __name__ == '__main__':
    main()
