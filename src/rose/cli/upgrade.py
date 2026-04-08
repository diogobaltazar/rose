import json
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

ROSE_DIR = Path("/rose")


def _merge_hooks(dest: dict, src: dict) -> list[str]:
    """
    Merge hook entries from src settings into dest settings in-place.

    For each hook event type (e.g. PostToolUse):
      - If the event type is absent in dest, add it wholesale.
      - Otherwise, for each matcher group in src:
          - If no group with that matcher exists in dest, append the group.
          - If a matching group exists, add only the individual hook commands
            that are not already present (matched by command string).

    Returns a list of human-readable change descriptions.
    """
    changes = []
    src_hooks = src.get("hooks", {})
    dest_hooks = dest.setdefault("hooks", {})

    for event_type, src_groups in src_hooks.items():
        if event_type not in dest_hooks:
            dest_hooks[event_type] = src_groups
            changes.append(f"added event type '{event_type}'")
            continue

        dest_groups = dest_hooks[event_type]
        for src_group in src_groups:
            src_matcher = src_group.get("matcher")
            dest_group = next(
                (g for g in dest_groups if g.get("matcher") == src_matcher),
                None,
            )
            if dest_group is None:
                dest_groups.append(src_group)
                label = f"'{src_matcher}'" if src_matcher else "(no matcher)"
                changes.append(f"added matcher {label} to '{event_type}'")
                continue

            existing_commands = {h["command"] for h in dest_group.get("hooks", [])}
            for hook in src_group.get("hooks", []):
                if hook["command"] not in existing_commands:
                    dest_group.setdefault("hooks", []).append(hook)
                    label = f"'{src_matcher}'" if src_matcher else "(no matcher)"
                    changes.append(f"added hook to '{event_type}/{label}'")

    return changes


def upgrade(
    claude_dir: Path = typer.Argument(
        Path("/claude"),
        help="Host ~/.claude directory (mounted into container)",
        show_default=False,
    ),
):
    """Safely upgrade commands, hooks, and hook settings from the rose source."""

    console.print()
    console.print(Panel("[bold magenta]rose upgrade[/bold magenta]", expand=False))
    console.print(f"  Target: [cyan]~/.claude[/cyan]\n")

    if not claude_dir.exists():
        console.print(f"  [red]Error:[/red] {claude_dir} does not exist.\n")
        raise typer.Exit(1)

    global_src = ROSE_DIR / "global"
    results = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    results.add_column("status", style="bold", width=4)
    results.add_column("item")
    results.add_column("note", style="dim")

    # 1. Copy command files individually — never delete existing commands
    src_commands = global_src / "commands"
    if src_commands.exists():
        dst_commands = claude_dir / "commands"
        dst_commands.mkdir(parents=True, exist_ok=True)
        for src_file in sorted(src_commands.iterdir()):
            if src_file.is_file():
                shutil.copy2(src_file, dst_commands / src_file.name)
                results.add_row("[green]✓[/green]", f"commands/{src_file.name}", "copied")

    # 2. Copy agent definitions individually — never delete existing agents
    src_agents = global_src / "agents"
    if src_agents.exists():
        dst_agents = claude_dir / "agents"
        dst_agents.mkdir(parents=True, exist_ok=True)
        for src_file in sorted(src_agents.iterdir()):
            if src_file.is_file():
                shutil.copy2(src_file, dst_agents / src_file.name)
                results.add_row("[green]✓[/green]", f"agents/{src_file.name}", "copied")

    # 4. Copy hook scripts individually — never delete existing hooks
    src_hooks_dir = global_src / "hooks"
    if src_hooks_dir.exists():
        dst_hooks_dir = claude_dir / "hooks"
        dst_hooks_dir.mkdir(parents=True, exist_ok=True)
        for src_file in sorted(src_hooks_dir.iterdir()):
            if src_file.is_file():
                shutil.copy2(src_file, dst_hooks_dir / src_file.name)
                results.add_row("[green]✓[/green]", f"hooks/{src_file.name}", "copied")

    # 5. Merge hook configuration into settings.json — never replace the file wholesale
    src_settings_path = global_src / "settings.json"
    dst_settings_path = claude_dir / "settings.json"

    if src_settings_path.exists():
        src_settings = json.loads(src_settings_path.read_text())

        if dst_settings_path.exists():
            try:
                dst_settings = json.loads(dst_settings_path.read_text())
            except json.JSONDecodeError as e:
                results.add_row("[red]✗[/red]", "settings.json", f"could not parse: {e}")
                console.print(results)
                console.print()
                raise typer.Exit(1)

            changes = _merge_hooks(dst_settings, src_settings)
            dst_settings_path.write_text(json.dumps(dst_settings, indent=2) + "\n")

            if changes:
                for change in changes:
                    results.add_row("[green]✓[/green]", "settings.json", change)
            else:
                results.add_row("~", "settings.json", "hooks already up to date")
        else:
            # No existing settings.json — write only the hooks section
            dst_settings_path.write_text(
                json.dumps({"hooks": src_settings.get("hooks", {})}, indent=2) + "\n"
            )
            results.add_row("[green]✓[/green]", "settings.json", "created with hooks")

    console.print(results)
    console.print()
