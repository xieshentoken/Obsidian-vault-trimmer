# V2 Configuration

Use JSON to keep the script dependency-free. Generate `.knowledge-organizer.json` with `init-config`, then override only repository-specific values.

## Profile

- `profile`: `auto`, `para-inbox`, or `generic`.
- `para.inbox_names`: normalized root-directory names that identify Inbox.
- `para.map_names`: normalized names that identify Map/MOC directories.
- `para.support_names`: PARA roles used as supporting evidence.
- `para.high_confidence`: automatic PARA threshold.
- `para.medium_confidence`: detection threshold that requires confirmation.

Numeric prefixes and separators are ignored when matching directory names. For example, `00-Inbox` matches `Inbox`, and `00-Maps` matches `Maps`.

## Managed Fields

`fields` maps repository names for:

- `type`, `tags`, `hubs`, and `topics`;
- `organization_status`;
- `organization_version`;
- `organization_hash`.

The script preserves all other frontmatter text and modifies only managed fields. V2 never adds a body relation section.

## Hub Detection

Hubs are discovered from configured type values and filename suffixes. In PARA mode discovery is restricted to Map directories. In generic mode it covers the configured Markdown scope.

## Matching

- Explicit rule: score 100.
- Existing MOC backlink: score 95.
- Exact tag/topic: score 70 or higher.
- Hierarchical tag: score 55.
- Title topic: score 45.

`matching.high_score` controls automatic linking. `matching.review_score` controls review candidates. Put generic topics in `matching.stop_topics`.

Explicit rules use this shape:

```json
{
  "tags_any": ["thermal/liquid-cooling", "liquid-cooling"],
  "tag_prefixes": ["thermal/"],
  "keywords_any": ["cold plate", "CDU"],
  "hubs": ["Thermal Management MOC", "Liquid Cooling MOC"]
}
```

Hub names must match note filenames without `.md`.

## Scope And Output

- `include_globs` and `exclude_globs` control generic scanning.
- `--path` narrows plan targets without changing hub discovery.
- `index.enabled` controls the lightweight metadata cache.
- `index.path` sets the cache file; unchanged `mtime + size` entries are not reparsed.
- `output.max_items` limits detailed audit arrays.
- Plan output is compact in the terminal; complete decisions and reasons live in the JSON plan.

## Organization States

- `linked`: high-confidence MOC membership was applied.
- `review`: a plausible candidate needs semantic review.
- `unclassified`: no reliable MOC exists yet.

An unchanged state/hash pair is skipped on later runs. Existing notes with a non-empty `moc` and no V2 state are also skipped, avoiding one-time repository churn.
