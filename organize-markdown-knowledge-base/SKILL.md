---
name: organize-markdown-knowledge-base
description: Audit and incrementally organize Obsidian or plain Markdown knowledge bases by detecting PARA plus Map structures, linking new or changed Inbox notes to MOCs, or safely planning generic hub repairs for other layouts. Use when an agent needs to classify an inbox, connect generated notes, repair MOC membership, detect missing or ambiguous links, or maintain a knowledge base with compact output and low token usage. Works with Codex, Claude Code, OpenClaw, WorkBuddy, and other agents that can read SKILL.md and run Python.
---

# Organize Markdown Knowledge Base

Use a reusable plan instead of repeatedly scanning and reasoning over the entire repository. Keep all mutations reviewable and preserve user-authored YAML and body text.

## Workflow

1. Detect the repository profile:

```bash
python3 <skill-dir>/scripts/kb_organizer.py detect --root <root>
```

2. Create a compact plan:

```bash
python3 <skill-dir>/scripts/kb_organizer.py plan --root <root>
```

3. Read the terminal summary. Open `.knowledge-organizer-plan.json` only for `review`, `unclassified`, conflicts, or representative semantic checks. Do not paste the whole plan into context.
4. Apply only after the user requests changes or approves the plan:

```bash
python3 <skill-dir>/scripts/kb_organizer.py apply --root <root>
python3 <skill-dir>/scripts/kb_organizer.py verify --root <root>
```

5. Run `plan` again. A stable repository should report zero new items.

## Profiles

### PARA Inbox

Select automatically only when confidence is high: an Inbox directory, a Map/MOC directory containing hubs, and at least two PARA support roles are present. Read only Inbox and Map notes.

- Treat an existing `moc` as already organized.
- Reprocess V2-managed notes only when their organization hash changes.
- Link high-confidence matches, mark medium matches `review`, and mark weak matches `unclassified`.
- Write only `moc`, `organization_status`, `organization_version`, and `organization_hash`.
- Do not move Inbox notes or rewrite MOC bodies; Obsidian backlinks provide the reverse connection.

### Generic

Use for all other structures. Discover hubs across Markdown files, plan missing MOC membership, and require explicit apply. Never add relation sections or bulk metadata by default.

Force a profile only when detection is wrong:

```bash
python3 <skill-dir>/scripts/kb_organizer.py plan --root <root> --profile generic
```

## Review Rules

- Accept exact specific tags, explicit rules, or an existing MOC backlink as strong evidence.
- Inspect title-only and hierarchical-tag matches before applying.
- Prefer `unclassified` over a misleading link.
- Never move, rename, archive, delete, or edit attachments without an explicit request.
- Treat hash conflicts as concurrent edits; regenerate the plan instead of overwriting.

## Other Commands

```bash
# Compact profile-aware audit
python3 <skill-dir>/scripts/kb_organizer.py audit --root <root>

# Restrict a generic or Inbox plan
python3 <skill-dir>/scripts/kb_organizer.py plan --root <root> --path <relative-path>

# Create repository configuration
python3 <skill-dir>/scripts/kb_organizer.py init-config --root <root>
```

Read `references/configuration.md` only when detection, fields, thresholds, directory aliases, or explicit rules need customization. Read `references/organization-model.md` for uncertain classifications and `references/agent-compatibility.md` for installation in another runtime.

## Resources

- `scripts/kb_organizer.py`: dependency-free detect, audit, plan, apply, and verify CLI.
- `assets/config.example.json`: V2 configuration starter.
- `assets/note-template.md`: optional organization metadata example.
