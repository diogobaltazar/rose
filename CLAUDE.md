# rose

rose is a scaffolding tool that installs and manages Claude Code configuration. This repo IS the source of truth for that configuration.

## Critical rule: edit the source code, not ~/.claude

When working inside this repo, any changes to Claude definitions — agents, commands, personas, hooks, settings — must be made to the source files here, **not** to `~/.claude` directly.

All definitions flow via `rose install`:

```
rose source (global/)  →  rose install  →  ~/.claude/
```

If you edit `~/.claude` directly, the change will be lost the next time someone runs `rose install`. Always edit the source here; the user will apply it by running `rose reinstall`.

## Project layout

```
global/        # Installed to ~/.claude/ by `rose install`
├── CLAUDE.md
├── settings.json
├── hooks/
├── agents/
│   ├── analyst.md      # Product analyst — feature analysis and spec reconciliation
│   ├── engineer.md     # Implementation agent
│   ├── github.md       # GitHub operations
│   └── git.md          # Git operations
└── commands/
    ├── feature.md      # /feature workflow (propose, work, push, merge)
    ├── github.md       # /github skill
    ├── git.md          # /git skill
    └── project.md      # /project skill (init, spec update)
src/rose/      # Python CLI package
├── cli.py     # Typer entrypoint
└── commands/  # Command implementations
pyproject.toml
Dockerfile
compose.yml
```

## Testing changes

With `ROSE_DEV=$HOME/rose` set (already in your `~/.zshrc`), rose rebuilds from this directory on every run:

```bash
rose reinstall    # wipe ~/.claude and reinstall from this branch's source
```

Switch branches freely — `rose reinstall` always installs from the current checkout.
