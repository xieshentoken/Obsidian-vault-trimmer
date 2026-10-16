# Agent Compatibility

## Portable Core

The portable unit is the complete `organize-markdown-knowledge-base` directory. It contains:

- `SKILL.md` as the agent entry point;
- dependency-free Python automation;
- references loaded only when needed;
- assets copied into target repositories when useful.

The skill does not require Obsidian, Dataview, Templater, or a specific folder layout. Obsidian is only needed to render wikilinks interactively.

Repository-local configuration, protected-path policy, and verified baseline state
contain no machine-specific absolute paths. Multiple agents can therefore share
the same organization behavior. Metadata caches remain machine-local by default.

## Codex

Copy or symlink the skill directory into the configured Codex skills directory. Keep `agents/openai.yaml`; it provides Codex-facing display metadata. Invoke explicitly with `$organize-markdown-knowledge-base` or allow description-based triggering.

## Claude Code, OpenClaw, WorkBuddy, And Other Agents

Place the complete directory in the runtime's configured skills location or workspace skills directory. The runtime must be able to load `SKILL.md`, read relative resources, and execute Python. Product-specific metadata under `agents/` is optional and must not be required by the workflow.

If a runtime uses a different registration mechanism, register the directory without rewriting the skill body. Keep repository-specific rules in the target repository configuration and strict no-touch paths in the target repository policy, not inside the installed skill.

Keep one canonical skill source and publish identical copies to every runtime.
Different script versions can otherwise produce different plans or lose atomic
write guarantees.

## Handoff Prompt

Use a platform-neutral prompt:

```text
Use the organize-markdown-knowledge-base skill to select the safe maintenance mode, create a compact organization and taxonomy plan, inspect review and proposal items, and apply only approved changes.
```

## Runtime Requirements

- Python 3.9 or newer;
- filesystem read access for audit;
- filesystem write access for plan creation and the `apply` command;
- no third-party Python packages;
- UTF-8 Markdown files.

The runtime must preserve the repository policy. A sandbox allowlist grants access
at the operating-system layer but does not override a denied path in the skill.

When a sandbox uses an allowlist, add the actual resolved repository path to that allowlist before running `apply`. Instructions or profile text alone do not grant filesystem access. If the user explicitly requested organization, obtain the required runtime permission instead of returning a dry-run as the final result.
