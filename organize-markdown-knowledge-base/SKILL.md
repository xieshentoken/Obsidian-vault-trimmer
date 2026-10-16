---
name: organize-markdown-knowledge-base
description: Audit and organize Obsidian or plain Markdown knowledge bases with automatic PARA detection, incremental Inbox-to-MOC routing, periodic full taxonomy review, new/split/merge MOC proposals, protected-path enforcement, and compact review packets. Use when an agent needs to classify new notes, evolve a MOC structure, repair memberships or links, run scheduled knowledge-base maintenance, or keep organization work safe and token-efficient across Codex, Claude Code, OpenClaw, WorkBuddy, Hermes, or another SKILL.md-compatible runtime.
---

# Organize Markdown Knowledge Base

Use a reusable plan instead of repeatedly loading the repository into model context. Keep mutations reviewable, preserve user-authored content, and enforce repository policy before traversal.

## Workflow

1. Detect the repository profile and selected maintenance mode:

```bash
python3 <skill-dir>/scripts/kb_organizer.py detect --root <root>
```

Before resolving or traversing `<root>`, the CLI loads the machine-local global
vault access policy. It then loads `<root>/.knowledge-organizer.json` and enforces
`<root>/.knowledge-organizer-policy.json` when present. A machine marked as
requiring the global policy fails closed when that policy is missing or malformed.

2. Create a compact plan:

```bash
python3 <skill-dir>/scripts/kb_organizer.py plan --root <root>
```

3. Read the terminal summary. Print the human-readable plan diff for a quick review:

```bash
python3 <skill-dir>/scripts/kb_organizer.py diff --root <root>
```

Open `.knowledge-organizer-plan.json` only for `review`, `unclassified`, taxonomy
proposals, conflicts, or representative semantic checks. Do not paste the whole
plan into context.
4. Apply only after the user requests changes or approves the plan:

```bash
python3 <skill-dir>/scripts/kb_organizer.py apply --root <root>
python3 <skill-dir>/scripts/kb_organizer.py verify --root <root>
```
`apply` first copies every affected note into `.knowledge-organizer-backup/<UTC-timestamp>/` before writing; pass `--no-backup` to skip it. Prefer committing the repository to git before apply when it is available.

When a bootstrap/full-review plan contains taxonomy proposals, inspect those
proposals semantically before recording the full baseline:

```bash
python3 <skill-dir>/scripts/kb_organizer.py verify \
  --root <root> --taxonomy-reviewed
```

Before `apply`, ensure the agent runtime grants write access to the repository root. An explicit user request to organize the repository is authorization to request or use that access; do not silently downgrade the task to a report. The script preflights every destination directory and changes no notes when access is missing.

5. Run `plan` again. A stable repository should report zero new items.

## Maintenance Modes

Use `--mode auto` by default:

- `bootstrap`: no verified full baseline exists; inspect all allowed Markdown.
- `incremental`: the baseline is current; read Inbox and Map notes only.
- `full-review`: age, note growth, pending Inbox count, or Map changes require a
  full allowed-scope review.

`verify` records a shared repository baseline after successful `bootstrap` or
`full-review`. Full review analyzes local metadata and bounded excerpts, then emits
`propose_create`, `propose_split`, and `propose_merge` taxonomy candidates. When
any candidate exists, baseline recording remains blocked until
`--taxonomy-reviewed` confirms semantic review. Never apply taxonomy proposals
without that review.

Override mode only for a deliberate diagnostic:

```bash
python3 <skill-dir>/scripts/kb_organizer.py plan \
  --root <root> --mode full-review
```

## Profiles

### PARA Inbox

Select automatically only when confidence is high: an Inbox directory, a Map/MOC
directory containing hubs, and at least two PARA support roles are present.
Incremental mode reads Inbox and Map notes; bootstrap/full-review reads the full
allowed scope.

- Treat an existing `moc` as already organized.
- Reprocess V4-managed notes only when their title, tags, aliases, or topics change; body edits alone do not force reclassification.
- Link high-confidence matches, mark medium matches `review`, and mark weak matches `unclassified`.
- Count inline body `#tags` as tags; accept MOC backlinks written as `[[wiki]]` or `[text](note.md)` links.
- Write only `moc`, `organization_status`, `organization_version`, `organization_hash`, and `organization_candidates` (top candidate hub links on `review`/`unclassified` notes).
- Do not move Inbox notes or rewrite MOC bodies; Obsidian backlinks provide the reverse connection.
- Treat unclassified notes as taxonomy-review inputs, not permanent dead ends.

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
- Treat broad tags as supporting evidence, not sufficient high-confidence rules.
- Prefer a specific child MOC over adding unrelated broad siblings.

## Protected Paths

Never use raw root-wide `rg --files`, `find`, `Path.rglob`, `os.walk`, or an
equivalent helper to inspect a protected repository. Use this CLI for detection,
auditing, planning, link checks, and verification so pruning occurs before
directory traversal. Do not open a protected path to confirm that it is protected.

Use a repository policy when any directory must never be read, indexed, classified,
linked, written, or verified:

```bash
python3 <skill-dir>/scripts/kb_organizer.py init-policy \
  --root <root> --deny "<relative/path>"
```

Policy paths are pruned before directory traversal, cannot be overridden by
`--config`, are checked again during plan/apply/verify, and include symlink
resolution. A policy change invalidates existing plans.

The machine-local policy defaults to
`~/.config/knowledge-vault-access/policy.json` and may be overridden with
`KNOWLEDGE_VAULT_ACCESS_POLICY`. It protects complete vault roots before this
skill checks whether the requested root exists. A root equal to or inside a
protected vault is always rejected. Ancestor roots are rejected by default; a
policy entry may set `deny_ancestor_scopes: false` only when that legitimate
parent vault has a repository policy that prunes the protected child. This
generic skill has no owner override or force flag; an authorized domain gateway
must use its own dedicated entrypoint.

## Other Commands

```bash
# Compact profile-aware audit
python3 <skill-dir>/scripts/kb_organizer.py audit --root <root>

# Human-readable plan summary for review
python3 <skill-dir>/scripts/kb_organizer.py diff --root <root>

# Check note and attachment links only in the selected scope
python3 <skill-dir>/scripts/kb_organizer.py audit \
  --root <root> --details

# Expand link checking to all allowed Markdown explicitly
python3 <skill-dir>/scripts/kb_organizer.py audit \
  --root <root> --details --link-scope vault

# Restrict a generic or Inbox plan
python3 <skill-dir>/scripts/kb_organizer.py plan --root <root> --path <relative-path>

# Create repository configuration
python3 <skill-dir>/scripts/kb_organizer.py init-config --root <root>
```

Read `references/configuration.md` when thresholds, policy, aliases, fields, or
rules need customization. Read `references/organization-model.md` for taxonomy
proposals and uncertain classifications. Read `references/agent-compatibility.md`
for installation in another runtime.

## Resources

- `scripts/kb_organizer.py`: dependency-free detect, audit, plan, apply, and verify CLI.
- `assets/config.example.json`: V3 configuration starter.
- `assets/global-access-policy.example.json`: machine-wide protected-root policy starter.
- `assets/policy.example.json`: protected-path policy starter.
- `assets/note-template.md`: optional organization metadata example.
