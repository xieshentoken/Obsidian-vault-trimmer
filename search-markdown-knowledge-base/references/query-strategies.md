# Query Strategies

## Concept Queries

Use the smallest set of distinctive terms that captures the concept:

1. Search the canonical term and common abbreviation together.
2. Search a mechanism, property, process, or application term when the first pass is broad.
3. Read the best overview note and the strongest primary-detail notes.
4. Follow one-hop links only when they add definitions, evidence, comparison, parameters, or applications.
5. Report definition, mechanism, key parameters, applications, limitations, and linked concepts when supported.

Example decomposition:

```text
Request: CuCrZr 为什么时效后导电率提高？
Pass 1: CuCrZr 时效
Pass 2: CuCrZr 析出相 导电率
```

## Industry Queries

Use a breadth-first MOC pass followed by focused facet searches. Select only facets relevant to the user's decision.

- Landscape: industry name, aliases, upstream/downstream terms.
- Technology: architecture, process, material, equipment, performance, reliability.
- Supply chain: suppliers, customers, manufacturing, procurement, localization.
- Economics: cost, yield, capacity, pricing, business model.
- Policy and market: regulation, subsidy, standards, adoption, demand.
- Projects and evidence: active projects, case studies, reports, dated sources.

Typical sequence:

```text
Pass 1: liquid cooling cold plate
Pass 2: liquid cooling materials process reliability
Pass 3: liquid cooling supply chain procurement OEM JDM
Pass 4: liquid cooling standard policy market
```

## Evidence Discipline

- A MOC establishes scope, not truth.
- A note can support a claim only when its body or cited source contains the relevant information.
- Prefer specific technical notes over summaries for parameters and mechanisms.
- Prefer dated project or source notes for market and policy claims.
- Flag conflicting values instead of averaging them without justification.
- Include a knowledge-gap section when expected facets have no relevant notes.

## Answer Shape

For a narrow concept, answer directly and cite 2-5 strongest local notes. For an industry, begin with a concise landscape, then organize evidence into 3-6 decision-relevant facets. End with gaps or questions that the current vault cannot answer.
