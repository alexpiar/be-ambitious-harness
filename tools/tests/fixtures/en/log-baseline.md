# Worker log — Settings crash (synthetic fixture for tools/gate-check.py, modelled on run T3-A of 2026-10-21)

## 22:59:57 — 0. Materials (section 3) and the gate check

The prompt has no section 4 — no gate check, baseline scheme (sections 1 and 7 say so). No GATE block.

```
$ git log --oneline --all
24f9d91 app-core 3.14.0
[exit=0]
```

## 23:00:04 — 1. Baseline on 24f9d91 and reproduction

```
$ npm test
# Subtest: settings screen has four sections
# tests 5
# pass 5
[exit=0]
```
