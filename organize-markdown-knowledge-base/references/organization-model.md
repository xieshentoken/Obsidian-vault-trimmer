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

## Safe Mutation Policy

- Preserve body text, headings, embeds, aliases, and unknown frontmatter fields.
- Merge generated links with existing links.
- Add a relation section only when configured and absent.
- Run dry-run before apply.
- Re-run after apply to confirm idempotence.
- Validate that every generated internal link resolves.

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

Zero isolated notes is not automatically good. A forced, misleading link is worse than an intentional unclassified note.
