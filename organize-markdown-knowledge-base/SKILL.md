---
name: organize-markdown-knowledge-base
description: Audit, organize, and maintain Obsidian or plain Markdown knowledge bases by discovering existing hub/MOC notes, normalizing frontmatter, adding hub and concept links, detecting isolated or broken notes, and producing safe restructuring plans. Use when an agent needs to organize a note repository, connect generated notes, build or repair MOCs/indexes, classify an inbox, standardize tags and metadata, or automate ongoing knowledge-base maintenance without assuming a fixed directory layout. Works with Codex, OpenClaw, and other agents that can read SKILL.md and run Python.
---

# Organize Markdown Knowledge Base

Organize a Markdown knowledge base through content and metadata discovery rather than fixed folder names. Preserve user-authored content and make all mutations reviewable.

## Workflow

1. Locate the knowledge-base root. Do not assume PARA, Johnny Decimal, or any specific folder layout.
2. Inspect existing instructions, templates, configuration, hub/MOC notes, and working-tree changes.
3. Run a read-only audit:

```bash
python3 <skill-dir>/scripts/kb_organizer.py audit --root <knowledge-base-root>
```

4. Read `references/organization-model.md` when deciding whether a note belongs in a hub, needs a concept link, or should remain unclassified.
5. If the repository needs custom rules, copy `assets/config.example.json`, edit it for the repository, and pass it with `--config`. Read `references/configuration.md` for the schema.
6. Generate a dry-run organization plan:

```bash
python3 <skill-dir>/scripts/kb_organizer.py organize \
  --root <knowledge-base-root> \
  --config <config.json>
```

7. Review every proposed hub and related-note link. Reject relationships based only on broad tags such as `AI`, `notes`, `research`, or `general`.
8. Apply only when the user requested changes or approved the plan:

```bash
python3 <skill-dir>/scripts/kb_organizer.py organize \
  --root <knowledge-base-root> \
  --config <config.json> \
  --apply
```

9. Re-run the same command without `--apply`; it must report no changes. Then run `audit` again and report before/after metrics.

## Decision Rules

- Treat folders as lifecycle or storage hints, not semantic truth.
- Treat tags as classification signals, hubs/MOCs as navigation, and direct note links as conceptual relationships.
- Add at least one hub link when confidence is high. Leave a note unclassified when evidence is weak.
- Add related-note links only from specific shared tags or an explicit rule. Prefer no link over a misleading link.
- Discover hubs from frontmatter (`type: moc|hub|index|map`) and filename suffixes (`MOC`, `Index`, `Map`, `Hub`). Override discovery with configuration when needed.
- Preserve existing frontmatter fields and links. Merge rather than replace.
- Do not move, rename, archive, or delete notes or attachments unless the user explicitly requests it.
- Default to dry-run. Never treat a successful script exit as semantic validation; inspect representative diffs.
- Work with concurrent user changes. Do not overwrite unrelated edits.

## Common Tasks

### Audit a repository

Run `audit --json` when machine-readable metrics are useful. Report note count, frontmatter coverage, hubs, link edges, isolated notes, broken links, and tag concentration.

### Classify an inbox or selected path

Pass one or more `--path` values. Paths are relative to the knowledge-base root and may be files or directories.

```bash
python3 <skill-dir>/scripts/kb_organizer.py organize \
  --root <root> --path Inbox --path Clippings --config <config.json>
```

### Create a repository-specific configuration

Generate a neutral starting file:

```bash
python3 <skill-dir>/scripts/kb_organizer.py init-config \
  --root <root> --output <root>/.knowledge-organizer.json
```

Then add explicit rules for domain vocabulary and broad-tag exclusions. Keep repository-specific MOC names out of this skill.

### Support another agent runtime

Keep the complete skill directory intact. `SKILL.md` and bundled scripts are runtime-neutral; `agents/openai.yaml` is optional Codex UI metadata and may be ignored by OpenClaw or other Agent Skills-compatible runtimes. Read `references/agent-compatibility.md` when installing or handing off the skill.

## Resources

- `scripts/kb_organizer.py`: dependency-free audit and organization CLI.
- `references/organization-model.md`: semantic model and review rules.
- `references/configuration.md`: configuration schema and examples.
- `references/agent-compatibility.md`: Codex/OpenClaw portability guidance.
- `assets/config.example.json`: repository-specific configuration starter.
- `assets/note-template.md`: neutral note template with hub and related fields.
