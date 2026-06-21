# Agent Compatibility

## Portable Core

The portable unit is the complete `organize-markdown-knowledge-base` directory. It contains:

- `SKILL.md` as the agent entry point;
- dependency-free Python automation;
- references loaded only when needed;
- assets copied into target repositories when useful.

The skill does not require Obsidian, Dataview, Templater, or a specific folder layout. Obsidian is only needed to render wikilinks interactively.

## Codex

Copy or symlink the skill directory into the configured Codex skills directory. Keep `agents/openai.yaml`; it provides Codex-facing display metadata. Invoke explicitly with `$organize-markdown-knowledge-base` or allow description-based triggering.

## Claude Code, OpenClaw, WorkBuddy, And Other Agents

Place the complete directory in the runtime's configured skills location or workspace skills directory. The runtime must be able to load `SKILL.md`, read relative resources, and execute Python. Product-specific metadata under `agents/` is optional and must not be required by the workflow.

If a runtime uses a different registration mechanism, register the directory without rewriting the skill body. Keep repository-specific rules in a target repository configuration, not inside the installed skill.

## Handoff Prompt

Use a platform-neutral prompt:

```text
Use the organize-markdown-knowledge-base skill to detect this repository profile, create a compact organization plan, inspect review and unclassified items, and apply only approved changes.
```

## Runtime Requirements

- Python 3.9 or newer;
- filesystem read access for audit;
- filesystem write access for plan creation and the `apply` command;
- no third-party Python packages;
- UTF-8 Markdown files.
