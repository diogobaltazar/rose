# rose

rose is a scaffolding tool that installs and manages Claude Code configuration. This repo IS the source of truth for that configuration.

## Critical rule: edit the source code, not ~/.claude

When working inside this repo, any changes to Claude definitions — agents, commands, personas, hooks, settings — must be made to the source files here, **not** to `~/.claude` directly.

All definitions flow via `rose install` or `rose reinstall`:

```
rose source (global/)  →  rose install  →  ~/.claude/
rose source (global/)  →  rose reinstall  →  ~/.claude/
```

If you edit `~/.claude` directly, the change will be lost the next time someone runs `rose install` or `rose reinstall`. Always edit the source here; the user will apply it by running `rose reinstall`.

## Testing changes

With `ROSE_DEV=$HOME/rose` set (already in your `~/.zshrc`), rose rebuilds from this directory on every run:

```bash
rose reinstall    # reinstall from this branch's source
```

Switch branches freely — `rose reinstall` always installs from the current checkout.
