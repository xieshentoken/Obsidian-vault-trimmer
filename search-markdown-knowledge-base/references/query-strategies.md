# Query Strategies

## Concept Queries

Start with the user's full question. The script identifies a topic anchor and separates intent terms such as advantages, limitations, safety, efficiency, mechanism, and application.

Read the best overview note and 1-4 primary-detail notes. Follow one-hop MOC or concept links only when they add definitions, evidence, comparison, parameters, applications, or limitations. Run a second focused query only for a clearly missing dimension.

Example:

```text
Query: CuCrZr 为什么时效后导电率提高？
Optional gap query: CuCrZr 析出相 导电率
```

## Industry Queries

Choose only facets relevant to the decision and submit them in one command with repeated `--facet` arguments.

- Landscape: aliases, upstream/downstream, and adjacent categories.
- Technology: architecture, process, material, equipment, performance, reliability.
- Supply chain: suppliers, customers, manufacturing, procurement, localization.
- Economics: cost, yield, capacity, pricing, business model.
- Policy and market: regulation, subsidy, standards, adoption, demand.
- Projects and evidence: active projects, cases, reports, and dated sources.

Avoid a fixed multi-pass checklist. Inspect the first ranked set, identify absent or weak facets, then issue one narrow follow-up query for those gaps.

## Evidence Discipline

- A MOC establishes scope, not truth.
- Support claims with note bodies or their cited sources.
- Prefer specific technical notes over summaries for parameters and mechanisms.
- Prefer dated project or source notes for market and policy claims.
- Flag conflicting values instead of averaging them without justification.
- Report expected facets that the vault cannot support.

## Answer Shape

For a concept, answer directly and cite 2-5 strong local notes. For an industry, begin with a concise landscape, organize evidence into 3-6 decision-relevant facets, and end with gaps or unresolved questions.
