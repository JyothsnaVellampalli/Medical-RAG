---
description: Verify and close the current phase
---
1. Run `mypy src`. Fix failures caused by this phase.
2. Check every "Done when" criterion of the current phase in `docs/roadmap.md` and report pass/fail for each.
3. If all pass: write `docs/progress/phase-XX.md` from `docs/progress/_template.md`, tick the phase in `docs/roadmap.md`, and add any new decisions to `docs/architecture.md`.
4. Give me a summary under 10 lines. Do NOT start the next phase.