---
name: search-markdown-knowledge-base
description: Search and synthesize concepts, technologies, companies, projects, and industries from Obsidian or plain Markdown knowledge bases. Use when an agent needs to answer questions from local notes, find all material related to a concept or industry, trace MOC/hub and related-note links, compare evidence across notes, locate source-backed details, or identify knowledge gaps without assuming a fixed vault structure.
---

# Search Markdown Knowledge Base

Retrieve evidence from a local Markdown knowledge graph, then synthesize an answer that distinguishes note evidence from inference.

## Workflow

1. Locate the knowledge-base root. Treat it as an ordinary folder; do not assume PARA or specific directory names.
2. Convert the request into 1-5 focused terms. Keep distinctive names, abbreviations, materials, processes, products, and industry terms. Remove conversational filler.
3. Run the bundled search script:

```bash
python3 <skill-dir>/scripts/search_kb.py \
  --root <knowledge-base-root> \
  --query "<focused terms>" \
  --mode concept \
  --limit 12
```

4. Inspect the highest-ranked notes. Read complete notes when their snippets support the question; never answer from filenames alone.
5. Follow useful `moc`, `related`, and body wikilinks one hop. Prefer links whose relationship can be explained.
6. For an industry query, run complementary searches for the main topic plus relevant facets such as technology, materials, supply chain, companies, policy, cost, reliability, or market. Read `references/query-strategies.md` for the facet workflow.
7. Answer with:
   - a direct synthesis;
   - findings grouped by useful facets, not by folder;
   - links to the local source notes;
   - contradictions, uncertainty, recency limits, and missing coverage.

## Search Modes

- `--mode concept`: prioritize exact title, tag, metadata, and body matches, then expand through links.
- `--mode industry`: give extra weight to matching hubs/MOCs and their linked notes to broaden coverage.
- `--json`: return machine-readable ranked results for further processing.
- `--minimum-terms N`: tighten or relax multi-term direct matching; the default requires half of the terms.
- `--path <relative-path>`: restrict retrieval to one or more files or directories.
- `--exclude <glob>`: add repository-specific exclusions; repeat as needed.

## Retrieval Rules

- Rank title and exact tag matches above raw body frequency.
- Use MOCs as navigation and scope signals, not as factual evidence by themselves.
- Treat `moc` as classification and `related` as a candidate conceptual relationship.
- Do not infer relevance solely from a broad tag such as `AI`, `notes`, `research`, or `general`.
- Resolve claims against note content and preserve links to notes containing the evidence.
- State when the vault lacks enough information. Do not silently fill local knowledge gaps with memory or web sources.
- Search the web only when the user asks for current/external information or when local evidence must be verified; clearly separate local and external findings.
- Keep all operations read-only unless the user separately asks to create or edit notes.

## Useful Commands

```bash
# Focused concept
python3 <skill-dir>/scripts/search_kb.py --root <root> \
  --query "CuCrZr 析出相 时效" --mode concept

# Broad industry scan
python3 <skill-dir>/scripts/search_kb.py --root <root> \
  --query "液冷 冷板" --mode industry --limit 20

# Search a selected collection and emit JSON
python3 <skill-dir>/scripts/search_kb.py --root <root> \
  --path Research --query "silicon carbide SiC sintering" --json
```

## Resources

- `scripts/search_kb.py`: dependency-free ranked Markdown and graph search.
- `references/query-strategies.md`: concept and industry query decomposition and answer patterns.
