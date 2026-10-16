# V4 Configuration

The CLI automatically loads `<root>/.knowledge-organizer.json`. An explicit
`--config` overrides normal settings, but never overrides the protected-path policy.
JSON keeps the portable core dependency-free.

## Profile And Mode

- `profile`: `auto`, `para-inbox`, or `generic`.
- `para.inbox_names`, `map_names`, and `support_names`: normalized directory roles.
- `maintenance.default_mode`: normally `auto`.
- `maintenance.full_review_days`: maximum age of a verified full baseline.
- `maintenance.note_growth_count`: absolute growth trigger.
- `maintenance.note_growth_ratio`: proportional growth trigger.
- `maintenance.pending_inbox_count`: unset Inbox notes that trigger full review.

`auto` selects:

- `bootstrap` when no verified V3 baseline exists;
- `incremental` while the baseline remains current;
- `full-review` when any configured trigger fires.

`verify` writes the small, portable `state.path` JSON file. It contains counts,
timestamps, and digests, never an absolute machine path. If bootstrap/full-review
emits taxonomy proposals, verification checks note mutations but does not update
the full baseline until the agent reruns it with `--taxonomy-reviewed`.

## Protected-Path Policy

Keep durable no-touch boundaries in `<root>/.knowledge-organizer-policy.json`:

```json
{
  "schema_version": 1,
  "deny_paths": [
    {
      "path": "relative/private-directory",
      "deny": ["read", "index", "classify", "link", "write", "verify"]
    }
  ]
}
```

All listed paths are full-deny paths. The script:

- loads this policy before profile detection or traversal;
- prunes denied directories from top-down walking;
- resolves symlinks before accepting files;
- rejects requested targets, plans, hubs, writes, and verification under denied paths;
- invalidates plans when the policy digest changes.

Retain matching `exclude_globs` as a second layer, but do not use globs as the only
protection for a strict privacy boundary.

For machine-wide boundaries, install
`assets/global-access-policy.example.json` as
`~/.config/knowledge-vault-access/policy.json`. Add an adjacent file named
`required` to make a missing or malformed global policy fail closed.
`deny_ancestor_scopes` defaults to `true`. Set it to `false` only for a protected
subdirectory inside a legitimate parent vault, and only when that parent also
has a repository policy that denies the same relative path. Direct access to the
protected root or any descendant remains denied.

## Managed Fields

`fields` maps repository names for:

- `type`, `tags`, `aliases`, `hubs`, and `topics`;
- `organization_status`;
- `organization_version`;
- `organization_hash`;
- `organization_candidates` (top candidate hub links persisted on `review`/`unclassified` notes so semantic review survives without the plan file).

The script preserves all unknown frontmatter and body text.
The organization hash covers only the title and tag/alias/topic frontmatter;
body edits alone do not force reclassification.

## Matching

Automatic evidence scores remain conservative:

Inline body `#tags` count as tags for matching. A MOC backlink counts as
strong evidence whether written as a `[[wiki]]` or `[text](note.md)` link.

- explicit rule: configurable, normally 100;
- existing MOC backlink: 95;
- exact specific tag/topic: 70 or higher;
- hierarchical tag: 55;
- title topic: 45.

Use `matching.stop_topics` for broad words and `matching.topic_aliases` for local
normalization:

```json
{
  "matching": {
    "topic_aliases": {
      "液冷散热": ["液冷", "液冷冷板"],
      "微通道冷板": ["液冷冷板"]
    }
  }
}
```

Rules support:

```json
{
  "id": "semiconductor-yield",
  "tags_all": ["半导体制造", "良率"],
  "tags_any": ["WAT", "晶圆测试"],
  "tag_prefixes": ["semiconductor/"],
  "title_any": ["Wafer Acceptance Test"],
  "body_any": ["E-test"],
  "exclude_tags": ["金属注射成形"],
  "exclude_keywords": ["MIM"],
  "match": "any",
  "score": 100,
  "hubs": ["半导体制造与封装 MOC"]
}
```

`keywords_any` remains a compatibility alias for `title_any`. Use `match: all`
when every configured positive group must match. Avoid broad single-token rules.

## Taxonomy Review

- `taxonomy.cluster_min_notes`: minimum shared-topic cluster for a new MOC proposal.
- `taxonomy.broad_moc_note_limit`: membership count that raises a split proposal.
- `taxonomy.max_proposals`: output cap for each proposal type.
- `taxonomy.evidence_chars`: bounded excerpt length for semantic review.

Full review emits candidates only. It never creates, deletes, splits, or merges MOC
files automatically. After reviewing all create/split/merge candidates, use
`verify --taxonomy-reviewed` to record the full baseline.

## Scope, Cache, And Output

- `include_globs` and `exclude_globs` control ordinary allowed scope.
- `--path` narrows plan targets and is rejected for protected paths.
- `index.enabled` controls the lightweight metadata cache.
- `index.path` may select a custom cache; an empty value uses a hashed file under
  the user's cache directory.
- the cache retains frontmatter, links, hashes, and only the bounded body prefix
  needed for deterministic rule matching; it does not duplicate full note bodies.
- unchanged cache payloads are not rewritten.
- `output.max_items` limits detailed audit arrays.

Detailed audit separates broken note links from broken or ambiguous attachments.
It remains scoped unless `--link-scope vault` is explicit.

`apply` copies affected notes into `.knowledge-organizer-backup/<UTC-timestamp>/` before writing unless `--no-backup` is set; those copies are excluded from ordinary scans.
## Organization States

- `linked`: high-confidence membership was applied.
- `review`: a plausible candidate needs semantic review.
- `unclassified`: no reliable current MOC exists; include it in full taxonomy review.

An unchanged state/hash pair is skipped. Existing notes with non-empty `moc` and no
An unchanged state/hash pair is skipped. Existing notes with non-empty `moc` and no V4 state are also skipped to avoid one-time churn.
