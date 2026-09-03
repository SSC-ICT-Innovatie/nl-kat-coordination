# PR Review Log

Notities van uitgevoerde reviews, bewaard naast de PR-comment op GitHub voor
terugzoekbaarheid.

## PR #5252 — Bump setuptools 81→83 in rocky/ (Dependabot)

- **Datum review**: 2026-08-27
- **Auteur PR**: dependabot (bot)
- **Status**: Merge-worthy, `BLOCKED` op required review-approval
- **Review-comment**: https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/pull/5252#issuecomment-5437149790

### Wat de PR doet

Dependabot-bump in `rocky/` die drie packages tegelijk raakt (niet alleen
setuptools, zoals de titel suggereert):

| Package | Van → Naar | Reden |
|---|---|---|
| setuptools | 81.0.0 → 83.0.0 | Security-fix, vereist Python ≥3.10 |
| pytest-drf | 1.1.3 → 1.1.4 | Verwijdert `pkg_resources`-import |
| pytest-lambda | 1.3.0 → 2.2.1 | Transitieve dep van pytest-drf |

### Belangrijkste bevinding

underdarknl's comment van 23 jul ("breekt op pytest_drf's pkg_resources-import,
lib lijkt onmaintained") is opgelost — door underdarknl zelf:

- [theY4Kman/pytest-drf#24](https://github.com/theY4Kman/pytest-drf/pull/24)
  vervangt `pkg_resources` door `importlib` (auteur: underdarknl, merged 27 jul).
- `pytest-drf` 1.1.4 gereleased op 27 aug 2026 met die fix + pytest-8 support.
- Deze PR trekt 1.1.4 mee.

### Verificatiepunten

- **pytest-lambda 2.x**: enige breaking change (2.0.0, 2022) betreft
  destructured parametrization via custom `pytest_generate_tests`-hook.
  OpenKAT gebruikt in `tests/test_api_organization.py` alleen `lambda_fixture`
  en `static_fixture` (basis-API), niet de destructuring-feature. CI groen
  op 3.10–3.13 bevestigt dit.
- **setuptools 83.0.0**: vereist Python ≥3.10 (OpenKAT: 3.10–3.13, OK).
  Bevat security-fix GHSA-h35f-9h28-mq5c (MANIFEST.in Unicode-normalisatie).
- **CI**: alles SUCCESS (tests 3.10–3.13, Debian/Ubuntu builds, pre-commit,
  CodeQL, makelang, container image).

### Conclusie

Merge-worthy. Geen verdere actie nodig behalve goedkeuring door code owner.
