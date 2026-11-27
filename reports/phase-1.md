# PHASE 1 REPORT

Built:

- Added multilingual script and Romanized-language detection for Bengali, Hindi, and English.
- Added amount parsing across digits, native scripts, Romanized forms, lakh/crore, and special fractions.
- Added digit parsing with repeated-digit phrases and explicit length errors.
- Added whole-word command matching, fuzzy bank/scheme resolvers, and redaction.
- Added registry validation and low-confidence routing with PM-KISAN and overlap rules.

Gate results:

| Check | Exact command | Result | Evidence |
|---|---|---|---|
| Ruff | `python -m ruff check .` | PASS | `All checks passed!` |
| NLU and regression tests | `pytest -q` | PASS | `150 passed, 1 warning` |
| Registry validator | `python tools/validate_registries.py` | PASS | `Registry validation passed: 5 portals, 12+ banks, translated prompts present.` |
| Required corpus counts | Phase 1 test corpus | PASS | 64 amount, 25 digit, 20 bank, 20 command, and 15 language cases. |

Must-pass amount output:

```text
paanch hazaar -> 5000.0
5 hajar -> 5000.0
\u09aa\u09be\u0981\u099a \u09b9\u09be\u099c\u09be\u09b0 -> 5000.0
\u092a\u093e\u0902\u091a \u0939\u091c\u093e\u0930 -> 5000.0
five thousand -> 5000.0
5k -> 5000.0
\u20b95,000 -> 5000.0
do sau pachas -> 250.0
dhai hazaar -> 2500.0
derh hazaar -> 1500.0
sade teen hazaar -> 3500.0
ek lakh -> 100000.0
one lakh twenty thousand -> 120000.0
paanch hazaar do sau -> 5200.0
\u092a\u093e\u0902\u091a \u0939\u091c\u093e\u0930 \u0926\u094b \u0938\u094c -> 5200.0
do hazaar paanch sau -> 2500.0
```

Try it yourself:

1. `python tools/validate_registries.py`
2. `python -c "from services.api.entities import parse_amount; print(parse_amount('dhai hazaar'))"`
3. `python -c "from services.api.router import route; print(route('asdf qwerty hmm')); print(route('PM Kisan status'))"`

Stubs / not verified live / deviations:

- Routing remains deterministic keyword fallback; the LLM interface is not implemented until Phase 7.
- The parser has no model training or GPU dependency.
- Native-script output in this report is escaped because the PowerShell console is CP1252; the tests use the actual Unicode strings.
- Wispr, browser, and external portal integrations remain unverified and are out of scope for this phase.

Next: Phase 2. Reply `continue`.
