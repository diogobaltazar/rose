# rose

rose is a scaffolding tool that installs and manages Claude Code configuration. This repo IS the source of truth for that configuration.

## Critical rule: edit the source code, not ~/.claude

When working inside this repo, any changes to Claude definitions — agents, commands, personas, hooks, settings — must be made to the source files here, **not** to `~/.claude` directly.

All definitions flow via `rose upgrade`:

```
rose source (global/)  →  rose upgrade  →  ~/.claude/
```

If you edit `~/.claude` directly, the change will be lost the next time someone runs `rose upgrade`. Always edit the source here; the user will apply it by running `rose upgrade`.

## Testing changes

With `ROSE_DEV=$HOME/rose` set (already in your `~/.zshrc`), rose rebuilds from this directory on every run:

```bash
rose upgrade    # reinstall from this branch's source
```

Switch branches freely — `rose upgrade` always installs from the current checkout.

## Feedback about rose behaviour

When the user gives feedback about how rose behaves — its development flow, its tone, its planning discipline, or any other aspect of its installed configuration — the fix belongs in the rose source files (this repo), not in Claude Code's memory system. Rose installs a harness; the harness is the source of truth. Creating a memory to patch around a harness deficiency means the fix is invisible to every other session and will not survive a reinstall. Edit the source.
