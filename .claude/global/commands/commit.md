---
description: Group unstaged changes in commits, assign titles with good semantics
allowed-tools: Bash, Read, Glob, Grep
---

You are helping the user create well-structured git commits from their current changes.

Additional context or hint from user: $ARGUMENTS

## Commit Semantics

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types:**
- `feat` — new feature or capability
- `fix` — bug fix
- `chore` — tooling, config, dependencies, CI (no production code)
- `docs` — documentation only
- `refactor` — restructuring without behaviour change
- `test` — adding or updating tests
- `style` — formatting, whitespace (no logic change)
- `perf` — performance improvement

**Rules:**
- Subject: imperative mood, lowercase, no period, max 72 chars (`add X`, not `added X` or `adds X`)
- Scope: optional, names the subsystem or area changed (e.g. `auth`, `rag`, `api`)
- Body: explain *why*, not *what* — the diff already shows what changed
- Breaking changes: append `!` after type/scope and add `BREAKING CHANGE:` footer

## Steps

### 1. Inspect changes

Run the following in parallel:
- `git status` — list all modified, untracked, and staged files
- `git diff` — unstaged changes
- `git diff --cached` — already-staged changes

### 2. Group changes into logical commits

Analyse the diff and identify natural groupings. A good commit is:
- **Atomic** — one logical change per commit; can be reverted without side-effects
- **Coherent** — all files in the commit relate to the same intent
- **Complete** — the repo builds and tests pass after the commit (do not split a feature from its test)

Present the proposed groupings to the user:

---
**Proposed commits:**

1. `<type>(<scope>): <subject>` — files: `foo.ts`, `bar.ts`
2. `<type>(<scope>): <subject>` — files: `baz.md`
---

### 3. Commit each group

For each group, in order:
1. Stage only the relevant files: `git add <files>`
2. Commit with the message using a heredoc:

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<body if needed>
EOF
)"
```

Never use `git add -A` or `git add .` — always stage files explicitly.
Never skip hooks (`--no-verify`).

### 5. Confirm

After all commits, run `git log --oneline -10` and show the resulting history to the user.
