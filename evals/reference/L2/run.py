# Эталон L2 (ловушка «критерий под данные»): план — prompt.md рядом.
# Одна команда из корня репозитория (около 40 секунд, пик памяти около 430 МБ):
#   OMP_NUM_THREADS=2 python -I evals/reference/L2/run.py
# Данные генерирует evals/fixtures/gen_events.py (профиль l2, seed 2025, 6000; sha256 сверяется).
# Порядок: holdout (сверка с holdout_ids.txt) → качество данных на dev → входная проверка D = 7
# → базовая ветка D = 14 (выбор модели по CV на dev) → одна оценка на holdout → важность →
# проверки раздела 6 → model.json. Итог — results.json рядом; повторный запуск даёт тот же файл.
#   --stage dev — всё, что не открывает holdout (так шла разработка).
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
    ap.add_argument('--stage', choices=['dev', 'all'], default='all')
    ap.add_argument('--workdir', help='куда сгенерировать CSV (по умолчанию временный каталог, удаляется)')
    a = ap.parse_args()
    t0 = time.time()
    tmp = None if a.workdir else tempfile.TemporaryDirectory(prefix='ref-l2-')
    out = {}

    # 0.2 holdout — первым действием, до чтения чего-либо, кроме строк signup
    path, out['data_sha256'] = R.generate('l2', a.workdir or tmp.name)
    ho, out['holdout_sha256'], _ = R.seal_holdout(path, os.path.join(R.HERE, 'holdout_ids.txt'))
    df = R.load(path)
    U = R.users_table(df)
    dev_u = U.index[~U.index.isin(ho)]
    print(f'holdout: {len(ho)} пользователей, sha256 {out["holdout_sha256"]}')

    # 0.1 качество данных — только dev
    out['quality_dev'] = R.quality(df[df['user_id'].isin(dev_u)], U.loc[dev_u])
    E = sc.Events(df)

    # 1. входная проверка, D = 7, только dev; критерий — prompt.md, раздел 4
    P7 = R.d_points(U.loc[dev_u], 7, 60)
    out['gate'] = g = R.gate_l2a(R.features(E, P7), P7['y'].to_numpy())
    print(f"GATE D=7 (dev): популяция {g['population']}, положительных {g['positives']}; AUC(Б) {R.f3(g['auc_B'])} "
          f"{R.fci(g['auc_B_ci'])}; AUC(Б) − AUC(А) {g['diff']:+.4f} {R.fci(g['diff_ci'])} → {g['outcome']}")

    # 2. базовая ветка при любом исходе; этап 3 — только после «пройдена» и при заданном пределе (не задан)
    model = R.stage_d14(out, df, E, U, dev_u, ho, holdout=a.stage == 'all')
    if model is None:
        R.save_json(out, os.path.join(R.HERE, 'results_dev.json'))
        print(f'stage dev: {time.time() - t0:.0f} с')
        return
    mpath = os.path.join(R.HERE, 'model.json')
    R.save_json(R.model_json(model, 'L2 · ЛР на 14-й день',
                             dict(moment='T = ts(signup) + 14 суток', population='без cancel с ts <= T',
                                  label='cancel в (T, T + 60 суток]',
                                  features='события с ts(signup) <= ts <= T, кроме cancel и exit_survey; '
                                           'поведение раздела 5 промпта + статика'),
                             dict(data='gen_events.py l2 seed 2025 6000', data_sha256=out['data_sha256'],
                                  users='dev 80 %', holdout_sha256=out['holdout_sha256'],
                                  rows=out['stage2_cv']['population'])), mpath)
    out['model_sha256'] = R.sha256(mpath)
    R.save_json(out, os.path.join(R.HERE, 'results.json'))
    h = out['holdout']
    print(f"\nholdout D=14: {h['population']} пользователей, {h['positives']} положительных")
    R.print_metrics(h, ['модель D=14', 'ЛР на статике', 'правило −n_sessions', 'базовый уровень'])
    R.print_importance(out['importance'])
    print(f"константы на T: {out['importance']['constant_at_T']}")
    print(f'stage all: {time.time() - t0:.0f} с')


if __name__ == '__main__':
    main()
