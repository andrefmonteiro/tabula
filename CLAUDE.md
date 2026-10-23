# Tabula
Read docs/tabula-overview.md for the full design before working on anything.
Progress and next ticket: todo.md. Work one ticket at a time.

## Git branches
- Every ticket is worked on a branch named after its `##` section in todo.md:
  lowercase, words joined by `-`, punctuation dropped
  (`## M0 — Setup` → `m0-setup`, `## M1 — Capture` → `m1-capture`).
- Branch off `main` if the branch doesn't exist yet; otherwise reuse it.
  Never commit ticket work directly to `main`.
- One commit per ticket (`T-xx: ...`). Merge the branch into `main` once
  every ticket in that section is ticked.
