---
name: search-markdown-knowledge-base
description: Search and synthesize concepts, technologies, companies, projects, and industries from Obsidian or plain Markdown knowledge bases. Use when an agent needs to answer from local notes, retrieve a concept or industry efficiently, trace MOC/hub links and backlinks, compare evidence, locate source-backed details, or identify knowledge gaps without assuming a fixed vault structure.
---

# Search Markdown Knowledge Base

Retrieve local evidence with a compact candidate pass, then read only the notes needed for the answer.

## Workflow

1. Locate the knowledge-base root without assuming PARA or fixed folder names.
2. Pass the user's natural-language request directly to the script. Let it separate topic anchors from question facets.
3. Run one compact search:

```bash
python3 <skill-dir>/scripts/search_kb.py \
  --root <knowledge-base-root> \
  --query "<question>" \
  --mode concept
```

4. Inspect the default top 6 candidates. Read the complete contents of only the strongest 2-5 evidence notes; never answer from filenames or MOCs alone.
5. Run a second search only when the first pass exposes a specific coverage gap. Use `--verbose` only when ranking metadata or graph reasons require inspection.
6. Synthesize by useful facets and link the local source notes. State contradictions, uncertainty, recency limits, and missing coverage.

## Industry Search

Combine relevant facets into one indexed search instead of repeating full-vault passes:

```bash
python3 <skill-dir>/scripts/search_kb.py --root <root> \
  --query "液冷 冷板" --mode industry \
  --facet "材料 工艺 可靠性" \
  --facet "供应链 采购 OEM JDM" \
  --facet "成本 政策 市场"
```

Read `references/query-strategies.md` when choosing facets or shaping an industry answer.

## Retrieval Controls

- Default output is compact: 6 candidates and snippets for only the first 3.
- `--limit N`, `--snippet-count N`, and `--snippet-width N` control output volume.
- `--verbose` includes tags, MOCs, related links, and graph reasons.
- `--json` emits compact structured results; combine it with `--verbose` only when needed.
- `--anchor TERM` overrides automatic topic detection; repeat for aliases.
- `--facet TERMS` adds decision dimensions in the same retrieval pass; repeat by facet group.
- `--path PATH` restricts results to selected files or directories.
- `--exclude GLOB` adds repository-specific exclusions.
- `--minimum-terms N` tightens direct matching; exact title or alias anchors still survive.

## Index Behavior

The script maintains `<root>/.knowledge-search-index.sqlite3` using file modification time and size. It reparses only changed Markdown files and stores bidirectional link metadata. It never changes Markdown notes.

- Use `--stats` to inspect reuse and update counts.
- Use `--rebuild-index` after suspected index corruption.
- Use `--index PATH` to place the index elsewhere.
- Use `--no-index` for a fully read-only direct scan.

## Evidence Rules

- Treat exact title, alias, tag, and MOC matches as scope signals; verify claims in note bodies.
- Use MOCs for navigation, not as factual evidence by themselves.
- Require industry results to match the topic anchor or its one-hop graph neighborhood.
- Prefer specific technical notes for mechanisms and parameters, and dated notes for market or policy claims.
- Keep local evidence separate from inference or external web findings.
- Do not edit notes unless the user separately requests it.

## Resources

- `scripts/search_kb.py`: dependency-free indexed Markdown and bidirectional graph search.
- `references/query-strategies.md`: facet selection, evidence discipline, and answer patterns.
