# topgun

topgun is a scaffolding tool that installs and manages Claude Code configuration. This repo IS the source of truth for that configuration.

## Critical rule: edit the source code, not ~/.claude

When working inside this repo, any changes to Claude definitions — agents, commands, personas, hooks, settings — must be made to the source files here, **not** to `~/.claude` directly.

All definitions flow via `topgun upgrade`:

```
topgun source (global/)  →  topgun upgrade  →  ~/.claude/
```

If you edit `~/.claude` directly, the change will be lost the next time someone runs `topgun upgrade`. Always edit the source here; the user will apply it by running `topgun upgrade`.

## Testing changes

To test changes, build the image from source and then run `topgun upgrade`:

```bash
docker compose build topgun
topgun upgrade    # reinstall from this branch's source
```

Switch branches freely — build and upgrade again to pick up the new branch's changes.

## Claude configuration questions are feature requests

Topgun exists to install and manage Claude Code configuration. When a user asks about Claude Code settings, permissions, hooks, agents, commands, or any other aspect of Claude's configuration, treat it as a feature request for topgun — not as a one-off configuration task. The answer is always a change to topgun's source files that will be delivered via `topgun install` or `topgun upgrade`.

## Feedback about topgun behaviour

When the user gives feedback about how topgun behaves — its development flow, its tone, its planning discipline, or any other aspect of its installed configuration — the fix belongs in the topgun source files (this repo), not in Claude Code's memory system. Topgun installs a harness; the harness is the source of truth. Creating a memory to patch around a harness deficiency means the fix is invisible to every other session and will not survive a reinstall. Edit the source.
