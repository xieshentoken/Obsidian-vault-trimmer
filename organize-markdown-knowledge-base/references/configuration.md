# Configuration

The script accepts an optional JSON configuration. JSON keeps the tool dependency-free and works across agent runtimes.

## Top-Level Fields

- `include_globs`: Markdown files to scan, relative to the root.
- `exclude_globs`: paths to ignore.
- `fields`: frontmatter field names used by the repository.
- `hub_detection`: how existing hubs are discovered.
- `rules`: explicit tag/keyword-to-hub mappings.
- `related`: concept-link recommendation controls.
- `relation_section`: optional body section settings.
- `defaults`: metadata added when absent.

## Rules

Each rule supports:

```json
{
  "tags_any": ["thermal/liquid-cooling", "liquid-cooling"],
  "tag_prefixes": ["thermal/"],
  "keywords_any": ["cold plate", "CDU"],
  "hubs": ["Thermal Management MOC", "Liquid Cooling MOC"]
}
```

A rule matches when any configured tag, prefix, or keyword matches. Hub values are note titles without `.md` unless the repository intentionally uses paths in wikilinks.

## Hub Discovery

The default detector recognizes frontmatter types `moc`, `hub`, `index`, and `map`, plus filename suffixes such as `MOC` and `Index`. Add repository-specific type values or suffixes rather than moving notes.

Hub topics come from:

- the hub filename after removing the suffix;
- hub frontmatter tags;
- the configurable `topics` field.

Explicit rules take precedence over automatic topic matching.

## Related Links

Use `stop_tags` for broad labels that should classify notes but should not produce concept links. Increase `min_shared_tags` for noisy repositories.

```json
{
  "limit": 3,
  "min_shared_tags": 1,
  "stop_tags": ["AI", "research", "notes", "general"]
}
```

## Relation Section

Set `enabled` to false when the repository stores all relationships only in frontmatter. Labels may use any language.

## Path Independence

Do not encode Inbox, Projects, Areas, Resources, or Attachments into the skill. Put repository-specific paths only in the copied configuration file.
