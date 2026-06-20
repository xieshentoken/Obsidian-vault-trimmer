#!/usr/bin/env python3
"""Audit and organize a Markdown knowledge base without fixed folder assumptions."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_CONFIG = {
    "include_globs": ["**/*.md", "*.md"],
    "exclude_globs": [
        ".git/**",
        ".obsidian/**",
        ".trash/**",
        "node_modules/**",
        "agent-skills/**",
        "**/.git/**",
        "**/.obsidian/**",
        "**/.trash/**",
        "**/node_modules/**",
        "**/agent-skills/**",
    ],
    "fields": {
        "type": "type",
        "status": "status",
        "tags": "tags",
        "hubs": "moc",
        "related": "related",
        "topics": "topics",
        "created": "created",
        "updated": "updated",
    },
    "hub_detection": {
        "type_values": ["moc", "hub", "index", "map"],
        "filename_suffixes": ["MOC", "Index", "Map", "Hub"],
        "max_hubs_per_note": 3,
        "minimum_score": 2,
    },
    "rules": [],
    "related": {
        "limit": 0,
        "min_shared_tags": 1,
        "stop_tags": ["AI", "notes", "research", "general"],
    },
    "relation_section": {
        "enabled": True,
        "heading": "Related",
        "hub_label": "Hubs",
        "related_label": "Concepts",
    },
    "defaults": {"type": "note", "status": "active"},
}

FIELD_ORDER = [
    "title",
    "type",
    "status",
    "author",
    "source",
    "tags",
    "moc",
    "related",
    "topics",
    "created",
    "updated",
]

WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
ALL_WIKILINK_RE = re.compile(r"!?\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")


@dataclass
class Note:
    path: Path
    relative: Path
    frontmatter: OrderedDict
    body: str
    original: str
    had_frontmatter: bool

    def value(self, field: str) -> object:
        return self.frontmatter.get(field)

    @property
    def title(self) -> str:
        title = self.frontmatter.get("title")
        return str(title).strip() if title else self.path.stem


@dataclass
class Hub:
    note: Note
    topics: set[str]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit_parser = sub.add_parser("audit", help="Read-only repository health report.")
    add_common_arguments(audit_parser)
    audit_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    init_parser = sub.add_parser("init-config", help="Create a neutral JSON config.")
    init_parser.add_argument("--root", default=".")
    init_parser.add_argument("--output", default=".knowledge-organizer.json")
    init_parser.add_argument("--force", action="store_true")

    organize_parser = sub.add_parser("organize", help="Classify and link notes.")
    add_common_arguments(organize_parser)
    organize_parser.add_argument("--path", action="append", help="Relative file or directory; repeatable.")
    organize_parser.add_argument("--apply", action="store_true", help="Write changes.")
    organize_parser.add_argument("--related-limit", type=int, help="Override related link limit.")

    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()

    if args.command == "init-config":
        return init_config(root, root / args.output, args.force)

    config = load_config(Path(args.config).expanduser() if args.config else None)
    notes = load_notes(root, config)

    if args.command == "audit":
        report = audit(root, notes, config)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_audit(report))
        return 0

    targets = select_targets(root, notes, args.path)
    related_limit = args.related_limit
    if related_limit is None:
        related_limit = int(config["related"].get("limit", 0))
    return organize(root, notes, targets, config, args.apply, max(related_limit, 0))


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Knowledge-base root.")
    parser.add_argument("--config", help="Optional JSON configuration.")


def init_config(root: Path, output: Path, force: bool) -> int:
    if output.exists() and not force:
        print(f"Refusing to overwrite existing config: {output}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created: {output.relative_to(root) if output.is_relative_to(root) else output}")
    return 0


def load_config(path: Optional[Path]) -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        user = json.loads(path.read_text(encoding="utf-8"))
        deep_merge(config, user)
    return config


def deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def load_notes(root: Path, config: dict) -> list[Note]:
    paths: set[Path] = set()
    for pattern in config["include_globs"]:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    filtered = [path for path in paths if not excluded(root, path, config["exclude_globs"])]
    return [parse_note(root, path) for path in sorted(filtered)]


def excluded(root: Path, path: Path, patterns: Iterable[str]) -> bool:
    rel = path.relative_to(root).as_posix()
    return any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch("/" + rel, pattern) for pattern in patterns)


def parse_note(root: Path, path: Path) -> Note:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if text.startswith("---\n") or text.startswith("---\r\n"):
        lines = text.splitlines()
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                fm = parse_frontmatter("\n".join(lines[1:index]))
                body = "\n".join(lines[index + 1 :]).lstrip("\n")
                return Note(path, path.relative_to(root), fm, body, text, True)
    return Note(path, path.relative_to(root), OrderedDict(), text, text, False)


def parse_frontmatter(text: str) -> OrderedDict:
    data: OrderedDict[str, object] = OrderedDict()
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"^([A-Za-z0-9_\-\u4e00-\u9fff]+):\s*(.*)$", lines[index])
        if not match:
            index += 1
            continue
        key, raw = match.group(1), match.group(2).strip()
        if raw:
            if raw.startswith("[") and raw.endswith("]"):
                data[key] = [unquote(item.strip()) for item in raw[1:-1].split(",") if item.strip()]
            else:
                data[key] = unquote(raw)
            index += 1
            continue
        values: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            item = re.match(r"^\s+-\s*(.*)$", lines[cursor])
            if not item:
                break
            values.append(unquote(item.group(1).strip()))
            cursor += 1
        data[key] = values if values else ""
        index = cursor
    return data


def discover_hubs(notes: list[Note], config: dict) -> list[Hub]:
    fields = config["fields"]
    detection = config["hub_detection"]
    type_values = {str(value).casefold() for value in detection["type_values"]}
    suffixes = tuple(str(value).casefold() for value in detection["filename_suffixes"])
    hubs: list[Hub] = []
    for note in notes:
        note_type = str(note.value(fields["type"]) or "").casefold()
        stem = note.path.stem.casefold()
        type_declares_hub = note_type in type_values
        filename_declares_hub = not note_type and stem.endswith(suffixes)
        if not type_declares_hub and not filename_declares_hub:
            continue
        topics = set(normalize_list(note.value(fields["tags"])))
        topics.update(normalize_list(note.value(fields["topics"])))
        cleaned = note.path.stem
        for suffix in detection["filename_suffixes"]:
            cleaned = re.sub(rf"\s*{re.escape(suffix)}\s*$", "", cleaned, flags=re.IGNORECASE)
        if cleaned.strip():
            topics.add(cleaned.strip())
        hubs.append(Hub(note, {topic.casefold() for topic in topics if not is_meta_topic(topic)}))
    return hubs


def is_meta_topic(topic: str) -> bool:
    lowered = topic.casefold()
    return lowered in {"moc", "hub", "index", "map"} or lowered.endswith("/moc")


def select_targets(root: Path, notes: list[Note], requested: list[str] | None) -> list[Note]:
    if not requested:
        return notes
    target_paths = [(root / value).resolve() for value in requested]
    selected = []
    for note in notes:
        for target in target_paths:
            if note.path == target or target in note.path.parents:
                selected.append(note)
                break
    return selected


def organize(
    root: Path,
    notes: list[Note],
    targets: list[Note],
    config: dict,
    apply: bool,
    related_limit: int,
) -> int:
    hubs = discover_hubs(notes, config)
    hub_paths = {hub.note.path for hub in hubs}
    changed: list[tuple[Note, str, list[str], list[str]]] = []

    for note in targets:
        if note.path in hub_paths:
            continue
        inferred_hubs = infer_hubs(note, hubs, config)
        inferred_related = infer_related(note, notes, config, related_limit, hub_paths)
        updated = update_note(note, inferred_hubs, inferred_related, config)
        if updated != note.original:
            changed.append((note, updated, inferred_hubs, inferred_related))
            if apply:
                note.path.write_text(updated, encoding="utf-8")

    action = "updated" if apply else "would update"
    if not changed:
        print("No changes needed.")
    else:
        print(f"{action}: {len(changed)} file(s)")
        for note, _, hub_links, related_links in changed:
            details = []
            if hub_links:
                details.append("hubs=" + ", ".join(hub_links))
            if related_links:
                details.append("related=" + ", ".join(related_links))
            suffix = f" ({'; '.join(details)})" if details else ""
            print(f"- {note.relative}{suffix}")
    if not apply:
        print("Dry-run only. Add --apply to write changes.")
    return 0


def infer_hubs(note: Note, hubs: list[Hub], config: dict) -> list[str]:
    fields = config["fields"]
    tags = {tag.casefold() for tag in normalize_list(note.value(fields["tags"]))}
    haystack = f"{note.title} {note.path.stem}".casefold()
    explicit: list[str] = []
    for rule in config.get("rules", []):
        tags_any = {str(value).casefold() for value in rule.get("tags_any", [])}
        prefixes = [str(value).casefold() for value in rule.get("tag_prefixes", [])]
        keywords = [str(value).casefold() for value in rule.get("keywords_any", [])]
        matched = bool(tags.intersection(tags_any))
        matched = matched or any(tag.startswith(prefix) for tag in tags for prefix in prefixes)
        matched = matched or any(keyword in haystack for keyword in keywords)
        if matched:
            explicit.extend(as_wikilink(value) for value in rule.get("hubs", []))

    scores: list[tuple[int, str]] = []
    for hub in hubs:
        score = 0
        for topic in hub.topics:
            if topic in tags:
                score += 3
            elif any(tag.startswith(topic + "/") or topic.startswith(tag + "/") for tag in tags):
                score += 2
            if len(topic) >= 3 and topic in haystack:
                score += 2
        if score >= int(config["hub_detection"]["minimum_score"]):
            scores.append((score, as_wikilink(hub.note.path.stem)))
    scores.sort(key=lambda item: (-item[0], item[1]))
    max_hubs = int(config["hub_detection"]["max_hubs_per_note"])
    automatic = [link for _, link in scores[:max_hubs]]
    return unique(explicit + automatic)


def infer_related(
    note: Note,
    notes: list[Note],
    config: dict,
    limit: int,
    hub_paths: set[Path],
) -> list[str]:
    if limit <= 0:
        return []
    fields = config["fields"]
    stop = {str(value).casefold() for value in config["related"].get("stop_tags", [])}
    source_tags = {tag.casefold() for tag in normalize_list(note.value(fields["tags"]))} - stop
    if not source_tags:
        return []
    minimum = int(config["related"].get("min_shared_tags", 1))
    scored: list[tuple[int, str]] = []
    for candidate in notes:
        if candidate.path == note.path or candidate.path in hub_paths:
            continue
        candidate_tags = {tag.casefold() for tag in normalize_list(candidate.value(fields["tags"]))} - stop
        shared = source_tags.intersection(candidate_tags)
        if len(shared) >= minimum:
            scored.append((len(shared), as_wikilink(candidate.path.stem)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [link for _, link in scored[:limit]]


def update_note(note: Note, hubs: list[str], related: list[str], config: dict) -> str:
    fields = config["fields"]
    today = dt.date.today().isoformat()
    fm = note.frontmatter
    if fields["type"] not in fm:
        fm[fields["type"]] = config["defaults"].get("type", "note")
    if fields["status"] not in fm:
        fm[fields["status"]] = config["defaults"].get("status", "active")
    if fields["created"] not in fm:
        fm[fields["created"]] = today

    if fields["tags"] in fm:
        fm[fields["tags"]] = normalize_list(fm[fields["tags"]])
    if hubs:
        fm[fields["hubs"]] = merge_links(fm.get(fields["hubs"]), hubs)
    if related:
        fm[fields["related"]] = merge_links(fm.get(fields["related"]), related)

    body = note.body
    section = config["relation_section"]
    if section.get("enabled", True) and (hubs or related or fm.get(fields["hubs"]) or fm.get(fields["related"])):
        body = ensure_relation_section(
            body,
            normalize_links(fm.get(fields["hubs"])),
            normalize_links(fm.get(fields["related"])),
            section,
        )

    provisional = render_note(fm, body)
    if provisional != note.original:
        fm[fields["updated"]] = today
    return render_note(fm, body)


def ensure_relation_section(body: str, hubs: list[str], related: list[str], config: dict) -> str:
    heading = str(config["heading"])
    hub_label = str(config["hub_label"])
    related_label = str(config["related_label"])
    heading_re = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    if not heading_re.search(body):
        block = [
            f"## {heading}",
            f"- {hub_label}: " + ", ".join(hubs),
            f"- {related_label}: " + ", ".join(related),
            "",
        ]
        return "\n".join(block) + body.lstrip("\n")

    lines = body.splitlines()
    output: list[str] = []
    in_section = False
    saw_hubs = False
    saw_related = False
    for line in lines:
        if re.match(rf"^##\s+{re.escape(heading)}\s*$", line):
            in_section = True
            output.append(line)
            continue
        if in_section and re.match(r"^##\s+", line):
            if not saw_hubs:
                output.append(f"- {hub_label}: " + ", ".join(hubs))
            if not saw_related:
                output.append(f"- {related_label}: " + ", ".join(related))
            in_section = False
        if in_section and line.startswith(f"- {hub_label}:"):
            saw_hubs = True
            output.append(merge_relation_line(line, hubs, hub_label))
        elif in_section and line.startswith(f"- {related_label}:"):
            saw_related = True
            output.append(merge_relation_line(line, related, related_label))
        else:
            output.append(line)
    if in_section:
        if not saw_hubs:
            output.append(f"- {hub_label}: " + ", ".join(hubs))
        if not saw_related:
            output.append(f"- {related_label}: " + ", ".join(related))
    return "\n".join(output).rstrip() + "\n"


def merge_relation_line(line: str, new_links: list[str], label: str) -> str:
    existing = re.findall(r"\[\[[^\]]+\]\]", line)
    return f"- {label}: " + ", ".join(unique(existing + new_links))


def render_note(frontmatter: OrderedDict, body: str) -> str:
    normalized_body = body.lstrip("\n").rstrip()
    return "---\n" + render_frontmatter(frontmatter) + "---\n" + normalized_body + "\n"


def render_frontmatter(frontmatter: OrderedDict) -> str:
    keys = [key for key in FIELD_ORDER if key in frontmatter]
    keys.extend(key for key in frontmatter if key not in keys)
    lines: list[str] = []
    for key in keys:
        value = frontmatter[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {quote_if_needed(str(item))}" for item in value)
        elif value == "":
            lines.append(f"{key}:")
        else:
            lines.append(f"{key}: {quote_if_needed(str(value))}")
    return "\n".join(lines) + "\n"


def audit(root: Path, notes: list[Note], config: dict) -> dict:
    hubs = discover_hubs(notes, config)
    fields = config["fields"]
    by_stem: defaultdict[str, list[Note]] = defaultdict(list)
    for note in notes:
        by_stem[note.path.stem].append(note)

    outgoing: defaultdict[Path, set[Path]] = defaultdict(set)
    incoming: defaultdict[Path, set[Path]] = defaultdict(set)
    broken: list[dict] = []
    tags = Counter()
    with_frontmatter = 0
    for note in notes:
        if note.had_frontmatter:
            with_frontmatter += 1
        tags.update(normalize_list(note.value(fields["tags"])))
        clean = strip_code(note.original)
        targets = list(ALL_WIKILINK_RE.findall(clean)) + list(MARKDOWN_LINK_RE.findall(clean))
        for raw in targets:
            target = raw.split("#", 1)[0].strip()
            if not target or Path(target).suffix.lower() not in {"", ".md"}:
                continue
            stem = Path(target).stem
            matches = by_stem.get(stem, [])
            if matches:
                for match in matches:
                    if match.path != note.path:
                        outgoing[note.path].add(match.path)
                        incoming[match.path].add(note.path)
            else:
                broken.append({"source": note.relative.as_posix(), "target": target})

    isolated = [
        note.relative.as_posix()
        for note in notes
        if not outgoing[note.path] and not incoming[note.path] and note.path not in {hub.note.path for hub in hubs}
    ]
    return {
        "root": str(root),
        "notes": len(notes),
        "frontmatter": {"with": with_frontmatter, "without": len(notes) - with_frontmatter},
        "hubs": len(hubs),
        "hub_files": [hub.note.relative.as_posix() for hub in hubs],
        "links": {
            "edges": sum(len(values) for values in outgoing.values()),
            "with_outgoing": sum(bool(outgoing[note.path]) for note in notes),
            "with_backlinks": sum(bool(incoming[note.path]) for note in notes),
            "isolated": len(isolated),
            "broken": len(broken),
        },
        "isolated_files": isolated,
        "broken_links": broken,
        "tags": {
            "unique": len(tags),
            "singletons": sum(count == 1 for count in tags.values()),
            "top": tags.most_common(20),
        },
    }


def format_audit(report: dict) -> str:
    lines = [
        f"Root: {report['root']}",
        f"Notes: {report['notes']}",
        f"Frontmatter: {report['frontmatter']['with']} with, {report['frontmatter']['without']} without",
        f"Hubs: {report['hubs']}",
        (
            "Links: "
            f"{report['links']['edges']} edges, "
            f"{report['links']['isolated']} isolated, "
            f"{report['links']['broken']} broken"
        ),
        f"Tags: {report['tags']['unique']} unique, {report['tags']['singletons']} singletons",
    ]
    if report["isolated_files"]:
        lines.append("Isolated notes:")
        lines.extend(f"- {value}" for value in report["isolated_files"][:30])
    if report["broken_links"]:
        lines.append("Broken links:")
        lines.extend(
            f"- {item['source']} -> {item['target']}" for item in report["broken_links"][:30]
        )
    return "\n".join(lines)


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.sub(r"`[^`]*`", "", text)


def normalize_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    raw = value if isinstance(value, list) else re.split(r"[,\s]+", str(value))
    return unique(
        item
        for item in (unquote(str(value).strip()).lstrip("#").strip() for value in raw)
        if item
    )


def normalize_links(value: object) -> list[str]:
    return [as_wikilink(item) for item in normalize_list(value)]


def merge_links(existing: object, links: list[str]) -> list[str]:
    return unique(normalize_links(existing) + [as_wikilink(link) for link in links])


def as_wikilink(value: str) -> str:
    value = unquote(str(value).strip())
    return value if value.startswith("[[") and value.endswith("]]" ) else f"[[{value}]]"


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def quote_if_needed(value: str) -> str:
    if value.startswith("[[") and value.endswith("]]" ):
        return json.dumps(value, ensure_ascii=False)
    if not value or value.startswith("#") or ": " in value or value.startswith("["):
        return json.dumps(value, ensure_ascii=False)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
