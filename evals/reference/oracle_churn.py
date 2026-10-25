# Скрытый оракул для задач на данных (T2, T2-pass, L2): ROC AUC модели исполнителя на
# скрытых пользователях. Код исполнителя запускается как есть — отдельным процессом:
#
#   python -I <score.py> <events.csv> <points.csv> <out.csv> [аргументы --score-args]
#
# (контракт ru/scenarios/data-analysis.md, блок «Для воркера»). Оракул не импортирует
# код исполнителя и не правит его: sha256 всех файлов в папке score.py до и после прогона
# сверяются, рабочий каталог процесса — пустая временная папка.
#
# Запуск из корня репозитория (OMP_NUM_THREADS=2; около 20 секунд, пик памяти около 250 МБ):
#   python -I evals/reference/oracle_churn.py --profile l2 --score evals/reference/L2/score.py
#   python -I evals/reference/oracle_churn.py --profile t2pass --score evals/reference/T2-pass/score.py \
#          --score-args "--model evals/reference/T2-pass/model_base.json"
#   python -I evals/reference/oracle_churn.py --profile t2pass --score <плечо A>/score.py --vs <плечо B>/score.py
#          # парная разность ROC AUC двух плеч на одних точках (критерий T2-pass «не ниже … минус 0,02»)
#   python -I evals/reference/oracle_churn.py --self-test      # оракул ловит заглядывание вперёд
#
# Скрытые пользователи генерируются evals/fixtures/gen_events.py (l2: seed 9001, t2pass: seed
# 9002; 2000 пользователей); sha256 сверяется с evals/fixtures/README.md. Или --hidden <csv>.
#
# Протоколы (одинаковые для всех эталонов):
#   (а) D = 7 от регистрации: asof = ts(signup) + D суток; популяция — без cancel с ts <= asof;
#       метка — cancel в (asof, asof + 60 суток]. --days 7 14 добавляет другие D.
#   (б) срезы по датам каждые 14 дней с 2025-06-01 по 2025-11-30 (asof = дата 00:00:00);
#       популяция — активные на asof: signup <= asof и нет cancel с ts <= asof;
#       метка — cancel в (asof, asof + 30 суток].
# ROC AUC и 95% бутстрэп-ДИ (1000 повторов по пользователям, seed 42).
# Проверка заглядывания вперёд: события скрытых пользователей обрезаются по asof
# ((а) — по asof своего пользователя, (б) — по дате среза), score.py запускается заново,
# оценки должны совпасть (|разность| <= 1e-12). Второй score.py (--vs) так не проверяется и его
# файлы не сверяются: для этого его запускают отдельно через --score.
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, 'evals', 'fixtures', 'gen_events.py')
HIDDEN = {  # профиль → (seed, пользователей, sha256 из evals/fixtures/README.md)
    'l2': (9001, 2000, '783667d82ebd68efe6fd506326ab4cb2f182b1c24cd4eeeadcee2237e8107c8c'),
    't2pass': (9002, 2000, 'f2dcd42474de942ed2af21e53a4123bb13e1863085a36e94a829c3c4049c319c'),
}
FMT = '%Y-%m-%dT%H:%M:%S'
DAY = pd.Timedelta(days=1)
SNAP = pd.date_range('2025-06-01', '2025-11-30', freq='14D')
N_BOOT, SEED, TOL = 1000, 42, 1e-12


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def rel(path):
    p = os.path.abspath(path)
    return os.path.relpath(p, ROOT) if p.startswith(ROOT + os.sep) else p


def tree_hashes(folder):
    out = {}
    for d, _, files in os.walk(folder):
        if '__pycache__' in d:
            continue
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, folder)] = sha256(p)
    return out


# ---------------------------------------------------------------------------- метрика
def auc_boot(y, scores, groups, n=N_BOOT, seed=SEED):
    """ROC AUC и 95% ДИ для каждой оценки; бутстрэп по пользователям через веса (повтор пользователя —
    вес), общие веса для всех оценок. Две оценки — ещё и парная разность AUC(первая) − AUC(вторая)."""
    y = np.asarray(y, float)
    _, g = np.unique(groups, return_inverse=True)
    m = g.max() + 1
    prep = []
    for s in scores:
        o = np.argsort(s, kind='mergesort')
        ss = s[o]
        prep.append((o, np.flatnonzero(np.r_[True, ss[1:] != ss[:-1]])))

    def auc(w, k):  # w: (B, n) веса строк
        o, starts = prep[k]
        wo = w[:, o]
        pos = np.add.reduceat(wo * y[o], starts, axis=1)
        neg = np.add.reduceat(wo * (1 - y[o]), starts, axis=1)
        below = np.cumsum(neg, axis=1) - neg
        return (pos * (below + 0.5 * neg)).sum(1) / (pos.sum(1) * neg.sum(1))

    one = np.ones((1, len(y)))
    points = [float(auc(one, k)[0]) for k in range(len(scores))]
    rng = np.random.default_rng(seed)
    vals = [[] for _ in scores]
    for b in range(0, n, 100):
        w = rng.multinomial(m, np.full(m, 1.0 / m), size=min(100, n - b))[:, g].astype(float)
        for k in range(len(scores)):
            vals[k].append(auc(w, k))
    vals = [np.concatenate(v) for v in vals]
    ci = [[float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for v in vals]
    out = dict(points=points, ci=ci)
    if len(scores) == 2:
        d = vals[0] - vals[1]
        out['diff'], out['diff_ci'] = points[0] - points[1], [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]
    return out


# ---------------------------------------------------------------------------- точки и метки
def load(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df['t'] = pd.to_datetime(df['ts'], format=FMT)
    return df


def protocol_points(df, name):
    su = df[df['event'] == 'signup'].groupby('user_id')['t'].min()
    can = df[df['event'] == 'cancel'].groupby('user_id')['t'].min().reindex(su.index)
    if name.startswith('a'):
        D = int(name[1:])
        asof = su + D * DAY
        keep = ~(can <= asof)
        p = pd.DataFrame({'user_id': su.index[keep], 'asof': asof[keep].to_numpy()})
        p['y'] = ((can[keep] > asof[keep]) & (can[keep] <= asof[keep] + 60 * DAY)).astype(int).to_numpy()
        return p
    parts = []
    for A in SNAP:
        keep = (su <= A) & ~(can <= A)
        c = can[keep]
        parts.append(pd.DataFrame({'user_id': su.index[keep], 'asof': A,
                                   'y': ((c > A) & (c <= A + 30 * DAY)).astype(int).to_numpy()}))
    return pd.concat(parts, ignore_index=True)


def write_points(p, path):
    p.assign(asof=p['asof'].dt.strftime(FMT))[['user_id', 'asof']].to_csv(path, index=False)


# ---------------------------------------------------------------------------- запуск исполнителя
def run_score(score, extra, events, points, out, log):
    cmd = [sys.executable, '-I', score, events, points, out] + extra
    cwd = tempfile.mkdtemp(prefix='oracle-cwd-', dir=os.path.dirname(out))
    env = dict(os.environ, OMP_NUM_THREADS='2')
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    work = os.path.dirname(out)

    def show(c):  # пути в журнале вызовов: от корня репозитория или от рабочего каталога
        if os.path.isabs(c) and c.startswith(ROOT + os.sep):
            return rel(c)
        if os.path.isabs(c) and c.startswith(work + os.sep):
            return '<workdir>/' + os.path.relpath(c, work)
        return shlex.quote(c)

    log.append({'cmd': ' '.join(show(c) for c in cmd[1:]), 'exit': r.returncode})
    if r.returncode != 0:
        sys.exit(f'oracle: score.py завершился с кодом {r.returncode}\n{r.stderr[-2000:]}')
    got = pd.read_csv(out, dtype={'user_id': str, 'asof': str})
    want = pd.read_csv(points, dtype=str)
    if list(got.columns[:3]) != ['user_id', 'asof', 'score']:
        sys.exit(f'oracle: out.csv должен иметь колонки user_id,asof,score, а не {list(got.columns)}')
    key_got = got['user_id'] + '|' + got['asof']
    key_want = want['user_id'] + '|' + want['asof']
    if len(got) != len(want) or key_got.duplicated().any() or set(key_got) != set(key_want):
        sys.exit('oracle: строки out.csv не совпадают с points.csv')
    s = pd.Series(got['score'].to_numpy(float), index=key_got).reindex(key_want).to_numpy()
    if not np.isfinite(s).all():
        sys.exit('oracle: в out.csv есть нечисловые оценки')
    return s


def evaluate(score, extra, hidden, work, protocols, lookahead, vs=None):
    df = load(hidden)
    cols = [c for c in df.columns if c != 't']
    before = tree_hashes(os.path.dirname(os.path.abspath(score)))
    res, log = {}, []
    for name in protocols:
        p = protocol_points(df, name)
        pts = os.path.join(work, f'points_{name}.csv')
        write_points(p, pts)
        s = run_score(score, extra, hidden, pts, os.path.join(work, f'out_{name}.csv'), log)
        ss = [s]
        if vs:
            ss.append(run_score(vs[0], vs[1], hidden, pts, os.path.join(work, f'vs_{name}.csv'), log))
        b = auc_boot(p['y'].to_numpy(), ss, p['user_id'].to_numpy())
        r = dict(rows=int(len(p)), users=int(p['user_id'].nunique()), positives=int(p['y'].sum()),
                 positive_share=float(p['y'].mean()), roc_auc=b['points'][0], ci95=b['ci'][0])
        if vs:
            r['vs'] = dict(roc_auc=b['points'][1], ci95=b['ci'][1], diff=b['diff'], diff_ci95=b['diff_ci'])
        if lookahead:
            diffs = []
            if name.startswith('a'):
                cut = df.merge(p[['user_id', 'asof']], on='user_id')
                groups = [(cut[cut['t'] <= cut['asof']][cols], p)]
            else:
                groups = [(df[df['t'] <= A][cols], p[p['asof'] == A]) for A in SNAP]
            for k, (ev, pp) in enumerate(groups):
                ev_path, pp_path = os.path.join(work, 'trunc_events.csv'), os.path.join(work, 'trunc_points.csv')
                ev.to_csv(ev_path, index=False)
                write_points(pp, pp_path)
                st = run_score(score, extra, ev_path, pp_path, os.path.join(work, 'trunc_out.csv'), log)
                diffs.append(float(np.max(np.abs(st - s[pp.index.to_numpy()]))) if len(pp) else 0.0)
            r['lookahead'] = dict(runs=len(groups), max_abs_diff=max(diffs),
                                  passed=bool(max(diffs) <= TOL))
        res[name] = r
    after = tree_hashes(os.path.dirname(os.path.abspath(score)))
    return res, log, before == after, before


def hidden_csv(profile, work, given):
    seed, n, want = HIDDEN[profile]
    if given:
        return given, sha256(given), want
    path = os.path.join(work, 'hidden-users.csv')
    subprocess.run([sys.executable, '-I', GEN, path, str(seed), str(n), '--profile', profile],
                   check=True, capture_output=True)
    got = sha256(path)
    if got != want:
        sys.exit(f'oracle: sha256 скрытых пользователей {got} не совпадает с {want} (evals/fixtures/README.md)')
    return path, got, want


LEAKY = '''import sys, pandas as pd
ev, pts, out = sys.argv[1:4]
e = pd.read_csv(ev, dtype=str)
p = pd.read_csv(pts, dtype=str)
can = set(e.loc[e['event'] == 'cancel', 'user_id'])
p['score'] = p['user_id'].isin(can).astype(float)
p[['user_id', 'asof', 'score']].to_csv(out, index=False)
'''


def fmt_table(res):
    vs = any('vs' in r for r in res.values())
    lines = ['| протокол | строк (пользователей) | положительных (доля) | ROC AUC [95% ДИ] | заглядывание вперёд |'
             + (' сравнение (--vs): ROC AUC [95% ДИ] | разность [95% ДИ] |' if vs else ''),
             '|---|---|---|---|---|' + ('---|---|' if vs else '')]
    names = {'b': '(б) срезы каждые 14 дней 2025-06-01…2025-11-30, H = 30'}
    for k, r in res.items():
        title = f'(а) D = {k[1:]}, H = 60' if k.startswith('a') else names[k]
        la = r.get('lookahead')
        la_txt = (f"{'нет' if la['passed'] else 'ЕСТЬ'} (прогонов: {la['runs']}, max |Δ| = {la['max_abs_diff']:.1e})"
                  if la else 'не проверялось')
        lines.append(f"| {title} | {r['rows']} ({r['users']}) | {r['positives']} ({r['positive_share']:.3f}) | "
                     f"{r['roc_auc']:.3f} [{r['ci95'][0]:.3f}; {r['ci95'][1]:.3f}] | {la_txt} |"
                     + (f" {r['vs']['roc_auc']:.3f} [{r['vs']['ci95'][0]:.3f}; {r['vs']['ci95'][1]:.3f}] | "
                        f"{r['vs']['diff']:+.3f} [{r['vs']['diff_ci95'][0]:+.3f}; {r['vs']['diff_ci95'][1]:+.3f}] |"
                        if 'vs' in r else ''))
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Скрытый оракул ROC AUC для score.py исполнителя.')
    ap.add_argument('--profile', choices=sorted(HIDDEN), default='l2')
    ap.add_argument('--score', help='путь к score.py исполнителя')
    ap.add_argument('--score-args', default='', help='дополнительные аргументы score.py, одной строкой')
    ap.add_argument('--days', type=int, nargs='+', default=[7], help='D протокола (а); по умолчанию 7')
    ap.add_argument('--hidden', help='готовый CSV скрытых пользователей вместо генерации')
    ap.add_argument('--workdir', help='рабочий каталог (по умолчанию временный, удаляется)')
    ap.add_argument('--no-lookahead', action='store_true', help='без проверки заглядывания вперёд')
    ap.add_argument('--vs', help='второй score.py (другое плечо или модель): ROC AUC и парная разность на тех же точках')
    ap.add_argument('--vs-args', default='', help='дополнительные аргументы второго score.py')
    ap.add_argument('--json', help='куда записать итог в JSON')
    ap.add_argument('--self-test', action='store_true',
                    help='прогнать заведомо заглядывающий вперёд score.py и убедиться, что проверка его ловит')
    a = ap.parse_args(argv)
    if not a.score and not a.self_test:
        ap.error('нужен --score или --self-test')
    tmp = tempfile.TemporaryDirectory(prefix='oracle-') if not a.workdir else None
    work = a.workdir or tmp.name
    os.makedirs(work, exist_ok=True)
    hidden, got_hash, want_hash = hidden_csv(a.profile, work, a.hidden)
    protocols = [f'a{d}' for d in a.days] + ['b']
    if a.self_test:
        leaky_dir = os.path.join(work, 'leaky')
        os.makedirs(leaky_dir, exist_ok=True)
        score = os.path.join(leaky_dir, 'score.py')
        with open(score, 'w') as fh:
            fh.write(LEAKY)
        extra = []
    else:
        score, extra = os.path.abspath(a.score), shlex.split(a.score_args)
        extra = [os.path.abspath(x) if os.path.exists(x) else x for x in extra]
    vs = None
    if a.vs:
        vs = (os.path.abspath(a.vs), [os.path.abspath(x) if os.path.exists(x) else x for x in shlex.split(a.vs_args)])
    res, log, unchanged, hashes = evaluate(score, extra, hidden, work, protocols, not a.no_lookahead, vs)
    head = 'самопроверка оракула: score.py, который читает cancel из будущего' if a.self_test else rel(score)
    print(f'oracle_churn · профиль {a.profile} · скрытые пользователи sha256 {got_hash[:12]}… '
          f"({'совпадает с README' if got_hash == want_hash else 'свой файл'})")
    print(f'исполнитель: {head}; вызовов score.py: {len(log)}, все с кодом 0')
    print(f'первый вызов: python {log[0]["cmd"]}')
    print(f"файлы в папке score.py до и после: {'не изменились' if unchanged else 'ИЗМЕНИЛИСЬ'} "
          f'({len(hashes)} файлов)')
    print(fmt_table(res))
    ok_look = all(r.get('lookahead', {'passed': True})['passed'] for r in res.values())
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as fh:
            json.dump(dict(profile=a.profile, hidden_sha256=got_hash, score=None if a.self_test else rel(score),
                           score_args=a.score_args, vs=rel(a.vs) if a.vs else None, vs_args=a.vs_args or None,
                           files_unchanged=unchanged, files_sha256=hashes,
                           protocols=res, calls=log), fh, ensure_ascii=False, indent=1)
            fh.write('\n')
    if tmp:
        tmp.cleanup()
    if a.self_test:
        print('самопроверка: ' + ('OK — заглядывание вперёд поймано' if not ok_look else 'FAIL — не поймано'))
        return 0 if not ok_look else 1
    return 0 if (ok_look and unchanged) else 1


if __name__ == '__main__':
    sys.exit(main())
