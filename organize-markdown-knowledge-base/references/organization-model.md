# Organization Model

## Layers

Use three distinct relationship layers:

1. **Metadata**: type, status, source, dates, and ownership.
2. **Classification**: tags and hub/MOC membership.
3. **Concept graph**: direct links between notes that explain, contrast, depend on, or apply one another.

Do not use one layer as a substitute for all three.

## Hub Selection

Link a note to a hub when at least one condition is strong:

- A specific tag matches the hub topic.
- The title contains a distinctive hub topic term.
- An explicit repository rule maps the note to the hub.
- The note is part of a project or domain whose home note is the hub.

A backlink counts whether the MOC writes `[[wiki]]` or `[text](note.md)` links; inline body `#tags` count as tags.
Do not classify from folder location alone. Multiple hubs are valid when the note genuinely crosses domains.

## Concept Links

Add a direct related-note link when the relationship can be stated as one of:

- explains or defines;
- provides evidence for;
- compares or contradicts;
- applies a method to;
- supplies parameters, standards, or data for;
- is a prerequisite or downstream consequence.

Shared broad tags are insufficient. Exclude generic tags from automatic recommendations and inspect every proposed link.

Concept links are outside the V4 automatic apply path. Use them only during explicit semantic review or with a separate retrieval workflow; routine Inbox classification should add MOC membership only.

## Taxonomy Evolution

Incremental classification and taxonomy evolution are separate jobs:

1. Incremental mode routes new Inbox notes to reliable existing MOCs.
2. Full review inspects all allowed metadata and bounded excerpts.
3. Unmapped clusters become `propose_create` candidates.
4. Overloaded hubs become `propose_split` candidates.
5. Highly overlapping hubs become `propose_merge` candidates.

Treat a proposal as evidence for semantic review, not as an automatic mutation.
Create a MOC when the topic is coherent, durable, useful as a query boundary, and
not already represented by an alias or child hub. One strategic note may justify a
MOC only through explicit user judgment; ordinary automatic proposals require the
configured cluster minimum.

Add the new MOC under an appropriate parent, define its inclusion and exclusion
scope, link seed notes, and add aliases or matching rules needed for future
incremental routing. Re-run full review after structural changes. If all proposals
were accepted, rejected, or deferred consciously, record that review with
`verify --taxonomy-reviewed`; otherwise the repository remains due for full review.

## Safe Mutation Policy

- Preserve body text, headings, embeds, aliases, and unknown frontmatter fields.
- Merge generated links with existing links.
- Never add a body relation section automatically.
- Create a hash-checked and policy-bound plan before apply.
- Preflight every target directory before the first note write; abort without changes on access failure.
- Replace each note atomically after preflight.
- Copy affected notes into `.knowledge-organizer-backup/` before the first write unless `--no-backup` is set.
- Verify the plan, then plan again to confirm idempotence.
- Validate that every generated internal link resolves.
- Never enter a protected path during scanning; revalidate policy during apply and verify.

## Repository Health Metrics

Track these metrics over time:

- percentage of notes with frontmatter;
- number of discovered hubs;
- notes with outgoing links and backlinks;
- isolated notes;
- broken note links;
- unique tags and singleton tags;
- broad tags dominating the graph;
- inbox notes without hub membership.
- candidate clusters lacking a MOC;
- MOCs exceeding the configured membership limit;
- high-overlap MOC pairs;
- age and note growth since the last verified full baseline.

Zero isolated notes is not automatically good. A forced, misleading link is worse than an intentional unclassified note.
