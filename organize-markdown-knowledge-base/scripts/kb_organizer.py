#!/usr/bin/env python3
"""Plan and apply token-efficient MOC organization for Markdown knowledge bases."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


VERSION = 2
DEFAULT_PLAN = ".knowledge-organizer-plan.json"
DEFAULT_CONFIG = {
    "profile": "auto",
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
        "tags": "tags",
        "hubs": "moc",
        "topics": "topics",
        "organization_status": "organization_status",
        "organization_version": "organization_version",
        "organization_hash": "organization_hash",
    },
    "para": {
        "inbox_names": ["Inbox"],
        "map_names": ["Map", "Maps", "MOC", "MOCs"],
        "support_names": ["Projects", "Areas", "Resources", "Archives"],
        "high_confidence": 0.85,
        "medium_confidence": 0.65,
    },
    "hub_detection": {
        "type_values": ["moc", "hub", "index", "map"],
        "filename_suffixes": ["MOC", "Index", "Map", "Hub"],
        "max_hubs_per_note": 3,
    },
    "matching": {
        "high_score": 70,
        "review_score": 45,
        "stop_topics": ["AI", "notes", "research", "general", "MOC", "hub", "index", "map"],
    },
    "rules": [],
    "index": {"enabled": True, "path": ".knowledge-organizer-index.json"},
    "output": {"max_items": 10},
}

WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
ALL_WIKILINK_RE = re.compile(r"!?\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")
TOP_FIELD_RE = re.compile(r"^([A-Za-z0-9_\-\u4e00-\u9fff]+):(?:\s|$)")


@dataclass
class Note:
    path: Path
    relative: Path
    original: str
    frontmatter_text: str
    frontmatter: OrderedDict
    body: str
    had_frontmatter: bool
    cached_file_hash: Optional[str] = None
    cached_organization_hash: Optional[str] = None
    cached_links: Optional[list[str]] = None

    @property
    def title(self) -> str:
        value = self.frontmatter.get("title")
        return str(value).strip() if value else self.path.stem

    @property
    def file_hash(self) -> str:
        return self.cached_file_hash or digest(self.original)

    @property
    def outgoing_links(self) -> list[str]:
        if self.cached_links is not None:
            return self.cached_links
        return WIKILINK_RE.findall(strip_code(self.body))


@dataclass
class Hub:
    note: Note
    topics: set[str]
    links: set[str]


@dataclass
class Detection:
    selected_profile: str
    candidate_profile: str
    confidence: str
    score: float
    inbox_dirs: list[Path]
    map_dirs: list[Path]
    support_roles: list[str]
    hub_count: int
    requires_confirmation: bool


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    detect_parser = sub.add_parser("detect", help="Detect PARA/Map structure and selected profile.")
    add_common_arguments(detect_parser)
    detect_parser.add_argument("--json", action="store_true")

    audit_parser = sub.add_parser("audit", help="Read-only compact repository audit.")
    add_common_arguments(audit_parser)
    audit_parser.add_argument("--json", action="store_true")
    audit_parser.add_argument("--details", action="store_true")
    audit_parser.add_argument("--max-items", type=int)

    plan_parser = sub.add_parser("plan", help="Create a reusable organization plan.")
    add_common_arguments(plan_parser)
    add_plan_arguments(plan_parser)

    apply_parser = sub.add_parser("apply", help="Apply an existing plan with hash checks.")
    apply_parser.add_argument("--root", default=".")
    apply_parser.add_argument("--plan", default=DEFAULT_PLAN)

    verify_parser = sub.add_parser("verify", help="Verify only files referenced by a plan.")
    verify_parser.add_argument("--root", default=".")
    verify_parser.add_argument("--plan", default=DEFAULT_PLAN)
    verify_parser.add_argument("--json", action="store_true")

    init_parser = sub.add_parser("init-config", help="Create a neutral V2 JSON config.")
    init_parser.add_argument("--root", default=".")
    init_parser.add_argument("--output", default=".knowledge-organizer.json")
    init_parser.add_argument("--force", action="store_true")

    legacy = sub.add_parser("organize", help="Compatibility wrapper for plan/apply.")
    add_common_arguments(legacy)
    add_plan_arguments(legacy)
    legacy.add_argument("--apply", action="store_true")

    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()

    if args.command == "init-config":
        return init_config(root, resolve_path(root, args.output), args.force)
    if args.command in {"apply", "verify"}:
        plan_path = resolve_path(root, args.plan)
        return apply_plan(root, plan_path) if args.command == "apply" else verify_plan(root, plan_path, args.json)

    config = load_config(Path(args.config).expanduser() if args.config else None)
    detection = detect_profile(root, config, args.profile)
    if args.command == "detect":
        print(json.dumps(detection_dict(root, detection), ensure_ascii=False, indent=2) if args.json else format_detection(root, detection))
        return 0
    if args.command == "audit":
        report = audit(root, config, detection, args.details, effective_max_items(args.max_items, config))
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_audit(report))
        return 0

    plan_path = resolve_path(root, args.output)
    plan = build_plan(root, config, detection, args.path)
    write_json(plan_path, plan)
    print(format_plan_summary(plan, plan_path, root))
    if args.command == "organize" and args.apply:
        return apply_plan(root, plan_path)
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Knowledge-base root.")
    parser.add_argument("--config", help="Optional V2 JSON configuration.")
    parser.add_argument("--profile", choices=("auto", "para-inbox", "generic"), help="Override profile detection.")


def add_plan_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--path", action="append", help="Relative target file or directory; repeatable.")
    parser.add_argument("--output", default=DEFAULT_PLAN, help="Reusable JSON plan path.")


def init_config(root: Path, output: Path, force: bool) -> int:
    if output.exists() and not force:
        print(f"Refusing to overwrite existing config: {output}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, DEFAULT_CONFIG)
    print(f"Created: {display_path(root, output)}")
    return 0


def load_config(path: Optional[Path]) -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        deep_merge(config, json.loads(path.read_text(encoding="utf-8")))
    return config


def deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def detect_profile(root: Path, config: dict, override: Optional[str]) -> Detection:
    para = config["para"]
    dirs = [path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")]
    inbox_dirs = match_role_dirs(dirs, para["inbox_names"])
    map_dirs = match_role_dirs(dirs, para["map_names"])
    support_roles = [
        role for role in para["support_names"] if match_role_dirs(dirs, [role])
    ]
    map_notes = load_notes_from_targets(root, map_dirs, config) if map_dirs else []
    hubs = discover_hubs(map_notes, config)

    score = 0.0
    score += 0.35 if inbox_dirs else 0.0
    score += 0.35 if map_dirs else 0.0
    score += min(len(support_roles), 2) * 0.10
    score += 0.10 if hubs else 0.0
    required = bool(inbox_dirs and map_dirs)
    high = float(para["high_confidence"])
    medium = float(para["medium_confidence"])
    confidence = "high" if required and score >= high else "medium" if required and score >= medium else "low"
    candidate = "para-inbox" if required and confidence in {"high", "medium"} else "generic"

    requested = override or str(config.get("profile", "auto"))
    if requested == "para-inbox" and not required:
        raise SystemExit("para-inbox requires both an Inbox directory and a Map/MOC directory")
    if requested in {"para-inbox", "generic"}:
        selected = requested
        requires_confirmation = False
    elif confidence == "high":
        selected = "para-inbox"
        requires_confirmation = False
    else:
        selected = "generic"
        requires_confirmation = confidence == "medium"
    return Detection(
        selected, candidate, confidence, round(score, 2), inbox_dirs, map_dirs,
        support_roles, len(hubs), requires_confirmation,
    )


def normalize_dir_name(name: str) -> str:
    value = name.casefold().strip()
    value = re.sub(r"^\d+[\s._-]*", "", value)
    return re.sub(r"[\s._-]+", "", value)


def match_role_dirs(dirs: list[Path], names: Iterable[str]) -> list[Path]:
    wanted = {normalize_dir_name(name) for name in names}
    return sorted(path for path in dirs if normalize_dir_name(path.name) in wanted)


def detection_dict(root: Path, detection: Detection) -> dict:
    return {
        "selected_profile": detection.selected_profile,
        "candidate_profile": detection.candidate_profile,
        "confidence": detection.confidence,
        "score": detection.score,
        "requires_confirmation": detection.requires_confirmation,
        "inbox_dirs": [display_path(root, path) for path in detection.inbox_dirs],
        "map_dirs": [display_path(root, path) for path in detection.map_dirs],
        "support_roles": detection.support_roles,
        "hubs": detection.hub_count,
    }


def format_detection(root: Path, detection: Detection) -> str:
    data = detection_dict(root, detection)
    return "\n".join([
        f"Profile: {data['selected_profile']} (confidence: {data['confidence']}, score: {data['score']:.2f})",
        "Inbox: " + (", ".join(data["inbox_dirs"]) or "not found"),
        "Maps: " + (", ".join(data["map_dirs"]) or "not found"),
        f"PARA roles: {len(data['support_roles'])}; hubs: {data['hubs']}",
        "Confirmation required: yes" if data["requires_confirmation"] else "Confirmation required: no",
    ])


def load_notes(root: Path, config: dict) -> list[Note]:
    return [parse_note(root, path) for path in collect_all_paths(root, config)]


def load_notes_from_targets(root: Path, targets: Iterable[Path], config: dict) -> list[Note]:
    return [parse_note(root, path) for path in collect_target_paths(root, targets, config)]


def collect_all_paths(root: Path, config: dict) -> list[Path]:
    paths: set[Path] = set()
    for pattern in config["include_globs"]:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(path for path in paths if not excluded(root, path, config["exclude_globs"]))


def collect_target_paths(root: Path, targets: Iterable[Path], config: dict) -> list[Path]:
    paths: set[Path] = set()
    for target in targets:
        if target.is_file() and target.suffix.casefold() == ".md":
            paths.add(target)
        elif target.is_dir():
            paths.update(target.rglob("*.md"))
    return sorted(path for path in paths if not excluded(root, path, config["exclude_globs"]))


def load_plan_notes(root: Path, paths: list[Path], config: dict) -> tuple[list[Note], int, int]:
    index_config = config.get("index", {})
    if not index_config.get("enabled", True):
        notes = [parse_note(root, path) for path in paths]
        return notes, 0, len(notes)
    index_path = resolve_path(root, str(index_config.get("path", ".knowledge-organizer-index.json")))
    config_digest = digest(json.dumps({
        "fields": config["fields"],
        "hub_detection": config["hub_detection"],
        "matching": config["matching"],
        "rules": config.get("rules", []),
    }, ensure_ascii=False, sort_keys=True))
    cache = load_index(index_path, config_digest)
    entries: dict[str, dict] = {}
    notes: list[Note] = []
    hits = 0
    parsed = 0
    for path in paths:
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        cached = cache.get("entries", {}).get(relative)
        if cached and cached.get("mtime_ns") == stat.st_mtime_ns and cached.get("size") == stat.st_size:
            note = note_from_index(root, path, cached)
            hits += 1
        else:
            note = parse_note(root, path)
            parsed += 1
        notes.append(note)
        entries[relative] = index_entry(note, stat, config["fields"])
    write_json(index_path, {
        "version": VERSION,
        "config_digest": config_digest,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "entries": entries,
    })
    return notes, hits, parsed


def load_index(path: Path, config_digest: str) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if int(value.get("version", 0)) != VERSION or value.get("config_digest") != config_digest:
        return {}
    return value


def index_entry(note: Note, stat, fields: dict) -> dict:
    return {
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "frontmatter": note.frontmatter,
        "had_frontmatter": note.had_frontmatter,
        "file_hash": note.file_hash,
        "organization_hash": organization_hash(note, fields),
        "links": note.outgoing_links,
    }


def note_from_index(root: Path, path: Path, entry: dict) -> Note:
    return Note(
        path=path,
        relative=path.relative_to(root),
        original="",
        frontmatter_text="",
        frontmatter=OrderedDict(entry.get("frontmatter", {})),
        body="",
        had_frontmatter=bool(entry.get("had_frontmatter")),
        cached_file_hash=str(entry.get("file_hash") or ""),
        cached_organization_hash=str(entry.get("organization_hash") or ""),
        cached_links=[str(value) for value in entry.get("links", [])],
    )


def excluded(root: Path, path: Path, patterns: Iterable[str]) -> bool:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return True
    return any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch("/" + rel, pattern) for pattern in patterns)


def parse_note(root: Path, path: Path) -> Note:
    text = path.read_text(encoding="utf-8", errors="ignore")
    frontmatter_text, body, had_frontmatter = split_document(text)
    return Note(
        path=path,
        relative=path.relative_to(root),
        original=text,
        frontmatter_text=frontmatter_text,
        frontmatter=parse_frontmatter(frontmatter_text),
        body=body,
        had_frontmatter=had_frontmatter,
    )


def split_document(text: str) -> tuple[str, str, bool]:
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return "", text, False
    match = re.search(r"\A---\r?\n(.*?)\r?\n---\r?\n?", text, flags=re.DOTALL)
    if not match:
        return "", text, False
    return match.group(1), text[match.end():], True


def parse_frontmatter(text: str) -> OrderedDict:
    data: OrderedDict[str, object] = OrderedDict()
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = TOP_FIELD_RE.match(lines[index])
        if not match:
            index += 1
            continue
        key = match.group(1)
        raw = lines[index].split(":", 1)[1].strip()
        if raw:
            data[key] = parse_scalar_or_inline_list(raw)
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


def parse_scalar_or_inline_list(raw: str) -> object:
    if raw.startswith("[") and raw.endswith("]") and not raw.startswith("[["):
        try:
            value = json.loads(raw)
            if isinstance(value, list):
                return [str(item) for item in value]
        except json.JSONDecodeError:
            return [unquote(item.strip()) for item in raw[1:-1].split(",") if item.strip()]
    return unquote(raw)


def build_plan(root: Path, config: dict, detection: Detection, requested: list[str] | None) -> dict:
    if detection.selected_profile == "para-inbox":
        target_paths = collect_target_paths(root, detection.inbox_dirs, config)
        hub_paths_for_load = collect_target_paths(root, detection.map_dirs, config)
        all_paths = sorted(set(target_paths + hub_paths_for_load))
        all_notes, cache_hits, parsed_count = load_plan_notes(root, all_paths, config)
        target_path_set = set(target_paths)
        hub_path_set = set(hub_paths_for_load)
        target_notes = [note for note in all_notes if note.path in target_path_set]
        hub_notes = [note for note in all_notes if note.path in hub_path_set]
    else:
        all_paths = collect_all_paths(root, config)
        all_notes, cache_hits, parsed_count = load_plan_notes(root, all_paths, config)
        hub_notes = all_notes
        target_notes = all_notes
    hubs = discover_hubs(hub_notes, config)
    hub_paths = {hub.note.path for hub in hubs}
    target_notes = select_targets(root, target_notes, requested)

    if not hubs:
        return {
            "version": VERSION,
            "root": str(root),
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "profile": detection_dict(root, detection),
            "config_digest": digest(json.dumps(config, ensure_ascii=False, sort_keys=True)),
            "fields": config["fields"],
            "summary": {
                "profile": detection.selected_profile,
                "confidence": detection.confidence,
                "scanned": len(target_notes),
                "hubs": 0,
                "skipped": len(target_notes),
                "linked": 0,
                "review": 0,
                "unclassified": 0,
                "skip_reasons": {"no_hubs": len(target_notes)},
                "blocked": "no hubs discovered; create hubs or configure hub detection before apply",
                "cache_hits": cache_hits,
                "parsed": parsed_count,
            },
            "items": [],
        }

    fields = config["fields"]
    compiled_rules = compile_rules(config.get("rules", []))
    items: list[dict] = []
    skipped = Counter()
    status_counts = Counter()
    for note in target_notes:
        if note.path in hub_paths:
            skipped["hub"] += 1
            continue
        mocs = normalize_links(note.frontmatter.get(fields["hubs"]))
        status = str(note.frontmatter.get(fields["organization_status"]) or "")
        saved_hash = str(note.frontmatter.get(fields["organization_hash"]) or "")
        current_hash = organization_hash(note, fields)
        if mocs and not status:
            skipped["existing_moc"] += 1
            continue
        if status in {"linked", "review", "unclassified"} and saved_hash == current_hash:
            skipped["unchanged"] += 1
            continue

        candidates = infer_hubs(note, hubs, config, compiled_rules)
        high_score = int(config["matching"]["high_score"])
        review_score = int(config["matching"]["review_score"])
        high = [candidate for candidate in candidates if candidate["score"] >= high_score]
        if high:
            selected = high[: int(config["hub_detection"]["max_hubs_per_note"])]
            action = "link"
            target_status = "linked"
            target_hubs = [candidate["link"] for candidate in selected]
        elif candidates and candidates[0]["score"] >= review_score:
            action = "review"
            target_status = "review"
            target_hubs = []
        else:
            action = "mark"
            target_status = "unclassified"
            target_hubs = []
        status_counts[target_status] += 1
        items.append({
            "path": note.relative.as_posix(),
            "expected_file_hash": note.file_hash,
            "organization_hash": current_hash,
            "action": action,
            "organization_status": target_status,
            "hubs": target_hubs,
            "candidates": candidates[:5],
        })

    summary = {
        "profile": detection.selected_profile,
        "confidence": detection.confidence,
        "scanned": len(target_notes),
        "hubs": len(hubs),
        "skipped": sum(skipped.values()),
        "linked": status_counts["linked"],
        "review": status_counts["review"],
        "unclassified": status_counts["unclassified"],
        "skip_reasons": dict(skipped),
        "cache_hits": cache_hits,
        "parsed": parsed_count,
    }
    return {
        "version": VERSION,
        "root": str(root),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "profile": detection_dict(root, detection),
        "config_digest": digest(json.dumps(config, ensure_ascii=False, sort_keys=True)),
        "fields": config["fields"],
        "summary": summary,
        "items": items,
    }


def select_targets(root: Path, notes: list[Note], requested: list[str] | None) -> list[Note]:
    if not requested:
        return notes
    targets = [resolve_under_root(root, value) for value in requested]
    return [note for note in notes if any(note.path == target or target in note.path.parents for target in targets)]


def discover_hubs(notes: list[Note], config: dict) -> list[Hub]:
    fields = config["fields"]
    detection = config["hub_detection"]
    type_values = {str(value).casefold() for value in detection["type_values"]}
    suffixes = tuple(str(value).casefold() for value in detection["filename_suffixes"])
    hubs: list[Hub] = []
    for note in notes:
        note_type = str(note.frontmatter.get(fields["type"]) or "").casefold()
        is_hub = note_type in type_values or (not note_type and note.path.stem.casefold().endswith(suffixes))
        if not is_hub:
            continue
        topics = set()
        for value in normalize_list(note.frontmatter.get(fields["tags"])) + normalize_list(note.frontmatter.get(fields["topics"])):
            topics.update(topic_variants(value))
        cleaned = clean_hub_title(note.path.stem, detection["filename_suffixes"])
        topics.update(topic_variants(cleaned))
        hubs.append(Hub(note, {topic.casefold() for topic in topics if topic}, {link.casefold() for link in note.outgoing_links}))
    return hubs


def clean_hub_title(title: str, suffixes: Iterable[str]) -> str:
    value = title
    for suffix in suffixes:
        value = re.sub(rf"\s*{re.escape(str(suffix))}\s*$", "", value, flags=re.IGNORECASE)
    return value.strip()


def topic_variants(value: str) -> set[str]:
    value = str(value).strip().lstrip("#")
    if not value:
        return set()
    parts = [item.strip() for item in re.split(r"[/|,，、]", value) if item.strip()]
    return {value, *parts}


def infer_hubs(note: Note, hubs: list[Hub], config: dict, rules: list[dict]) -> list[dict]:
    fields = config["fields"]
    tags = {tag.casefold() for tag in normalize_list(note.frontmatter.get(fields["tags"]))}
    expanded_tags = set(tags)
    for tag in list(tags):
        expanded_tags.update(part.casefold() for part in topic_variants(tag))
    title = f"{note.title} {note.path.stem}".casefold()
    stop = {str(value).casefold() for value in config["matching"].get("stop_topics", [])}
    scores: dict[str, dict] = {}

    hub_by_title = {hub.note.path.stem.casefold(): hub for hub in hubs}
    for rule in rules:
        matched = bool(expanded_tags.intersection(rule["tags_any"]))
        matched = matched or any(tag.startswith(prefix) for tag in expanded_tags for prefix in rule["tag_prefixes"])
        matched = matched or any(keyword in title for keyword in rule["keywords_any"])
        if not matched:
            continue
        for hub_name in rule["hubs"]:
            hub = hub_by_title.get(hub_name.casefold())
            if hub:
                add_candidate(scores, hub, 100, "explicit rule")

    for hub in hubs:
        if note.path.stem.casefold() in hub.links or note.title.casefold() in hub.links:
            add_candidate(scores, hub, 95, "already linked from MOC")
        exact = sorted((hub.topics - stop).intersection(expanded_tags))
        if exact:
            add_candidate(scores, hub, 70 + min(len(exact) - 1, 2) * 5, "exact tag: " + ", ".join(exact[:3]))
        hierarchical = sorted(
            topic for topic in hub.topics - stop
            if any(tag.startswith(topic + "/") or topic.startswith(tag + "/") for tag in tags)
        )
        if hierarchical:
            add_candidate(scores, hub, 55, "hierarchical tag: " + ", ".join(hierarchical[:3]))
        title_topics = sorted(topic for topic in hub.topics - stop if len(topic) >= 2 and topic in title)
        if title_topics:
            add_candidate(scores, hub, 45, "title topic: " + ", ".join(title_topics[:3]))
    return sorted(scores.values(), key=lambda item: (-item["score"], item["hub"]))


def compile_rules(rules: Iterable[dict]) -> list[dict]:
    return [{
        "tags_any": {str(value).casefold() for value in rule.get("tags_any", [])},
        "tag_prefixes": [str(value).casefold() for value in rule.get("tag_prefixes", [])],
        "keywords_any": [str(value).casefold() for value in rule.get("keywords_any", [])],
        "hubs": [str(value) for value in rule.get("hubs", [])],
    } for rule in rules]


def add_candidate(scores: dict[str, dict], hub: Hub, score: int, reason: str) -> None:
    key = hub.note.path.stem
    current = scores.setdefault(key, {"hub": key, "link": f"[[{key}]]", "score": 0, "reasons": []})
    current["score"] = max(current["score"], score)
    if reason not in current["reasons"]:
        current["reasons"].append(reason)


def organization_hash(note: Note, fields: dict) -> str:
    if note.cached_organization_hash:
        return note.cached_organization_hash
    payload = {
        "title": note.title,
        "tags": normalize_list(note.frontmatter.get(fields["tags"])),
        "body": note.body,
    }
    return digest(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def apply_plan(root: Path, plan_path: Path) -> int:
    plan = read_plan(root, plan_path)
    if plan.get("summary", {}).get("blocked"):
        print("Refusing blocked plan: " + plan["summary"]["blocked"], file=sys.stderr)
        return 2
    fields = plan.get("fields", DEFAULT_CONFIG["fields"])
    updated = Counter()
    conflicts: list[str] = []
    for item in plan.get("items", []):
        path = resolve_under_root(root, item["path"])
        if not path.is_file():
            conflicts.append(f"{item['path']}: missing")
            continue
        note = parse_note(root, path)
        if note.file_hash != item["expected_file_hash"]:
            conflicts.append(f"{item['path']}: changed since plan")
            continue
        updates: dict[str, object] = {
            fields["organization_status"]: item["organization_status"],
            fields["organization_version"]: str(VERSION),
            fields["organization_hash"]: item["organization_hash"],
        }
        if item["action"] == "link":
            existing = normalize_links(note.frontmatter.get(fields["hubs"]))
            updates[fields["hubs"]] = unique(existing + item.get("hubs", []))
        rendered = update_document(note, updates)
        if rendered != note.original:
            path.write_text(rendered, encoding="utf-8")
            updated[item["organization_status"]] += 1
    print("Apply summary")
    print(f"Updated: {sum(updated.values())}; linked: {updated['linked']}; review: {updated['review']}; unclassified: {updated['unclassified']}")
    print(f"Conflicts: {len(conflicts)}")
    for conflict in conflicts[:10]:
        print(f"- {conflict}")
    return 3 if conflicts else 0


def verify_plan(root: Path, plan_path: Path, as_json: bool) -> int:
    plan = read_plan(root, plan_path)
    fields = plan.get("fields", DEFAULT_CONFIG["fields"])
    failures: list[dict] = []
    checked = 0
    for item in plan.get("items", []):
        path = resolve_under_root(root, item["path"])
        if not path.is_file():
            failures.append({"path": item["path"], "reason": "missing"})
            continue
        checked += 1
        note = parse_note(root, path)
        status = str(note.frontmatter.get(fields["organization_status"]) or "")
        saved_hash = str(note.frontmatter.get(fields["organization_hash"]) or "")
        mocs = set(normalize_links(note.frontmatter.get(fields["hubs"])))
        reasons = []
        if status != item["organization_status"]:
            reasons.append("status")
        if saved_hash != item["organization_hash"] or organization_hash(note, fields) != item["organization_hash"]:
            reasons.append("hash")
        if item["action"] == "link" and not set(item.get("hubs", [])).issubset(mocs):
            reasons.append("moc")
        if reasons:
            failures.append({"path": item["path"], "reason": ", ".join(reasons)})
    report = {"checked": checked, "passed": checked - len(failures), "failed": len(failures), "failures": failures}
    print(json.dumps(report, ensure_ascii=False, indent=2) if as_json else f"Verified: {report['passed']}/{checked}; failed: {report['failed']}")
    return 4 if failures else 0


def update_document(note: Note, updates: dict[str, object]) -> str:
    frontmatter = update_frontmatter(note.frontmatter_text, updates)
    body = note.body
    if note.had_frontmatter:
        return f"---\n{frontmatter.rstrip()}\n---\n{body}"
    return f"---\n{frontmatter.rstrip()}\n---\n{body.lstrip()}"


def update_frontmatter(text: str, updates: dict[str, object]) -> str:
    lines = text.splitlines()
    spans = top_field_spans(lines)
    replacements = {key: render_field(key, value) for key, value in updates.items()}
    output: list[str] = []
    index = 0
    while index < len(lines):
        key = next((name for name, (start, _) in spans.items() if start == index), None)
        if key is None:
            output.append(lines[index])
            index += 1
            continue
        start, end = spans[key]
        output.extend(replacements.pop(key, lines[start:end]))
        index = end
    for key, rendered in replacements.items():
        output.extend(rendered)
    return "\n".join(output)


def top_field_spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    starts: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = TOP_FIELD_RE.match(line)
        if match and not line.startswith((" ", "\t")):
            starts.append((match.group(1), index))
    return {
        key: (start, starts[position + 1][1] if position + 1 < len(starts) else len(lines))
        for position, (key, start) in enumerate(starts)
    }


def render_field(key: str, value: object) -> list[str]:
    if isinstance(value, list):
        return [f"{key}:", *(f"  - {quote_yaml(str(item))}" for item in value)]
    return [f"{key}: {quote_yaml(str(value))}"]


def quote_yaml(value: str) -> str:
    if value.startswith("[[") or not value or value.startswith("#") or ": " in value or value.startswith(("[", "{")):
        return json.dumps(value, ensure_ascii=False)
    return value


def audit(root: Path, config: dict, detection: Detection, details: bool, max_items: int) -> dict:
    if detection.selected_profile == "para-inbox":
        notes = load_notes_from_targets(root, [*detection.inbox_dirs, *detection.map_dirs], config)
        scope = "Inbox + Maps"
        subject_notes = [note for note in notes if path_in_targets(note.path, detection.inbox_dirs)]
    else:
        notes = load_notes(root, config)
        scope = "all Markdown"
        subject_notes = notes
    hubs = discover_hubs(notes, config)
    hub_paths = {hub.note.path for hub in hubs}
    fields = config["fields"]
    tags = Counter(tag for note in subject_notes for tag in normalize_list(note.frontmatter.get(fields["tags"])))
    missing_moc = [note.relative.as_posix() for note in subject_notes if note.path not in hub_paths and not normalize_links(note.frontmatter.get(fields["hubs"]))]
    statuses = Counter(str(note.frontmatter.get(fields["organization_status"]) or "unset") for note in subject_notes if note.path not in hub_paths)
    links_checked = detection.selected_profile != "para-inbox" or details
    link_notes = load_notes(root, config) if detection.selected_profile == "para-inbox" and details else notes
    broken, ambiguous = link_issues(link_notes) if links_checked else ([], [])
    report = {
        "profile": detection.selected_profile,
        "confidence": detection.confidence,
        "scope": scope,
        "notes": len(subject_notes),
        "map_notes": len(notes) - len(subject_notes) if detection.selected_profile == "para-inbox" else 0,
        "hubs": len(hubs),
        "missing_moc": len(missing_moc),
        "organization_status": dict(statuses),
        "links": {"checked": links_checked, "broken": len(broken), "ambiguous": len(ambiguous)},
        "tags": {"unique": len(tags), "singletons": sum(count == 1 for count in tags.values()), "top": tags.most_common(10)},
    }
    if details:
        report["details"] = {
            "missing_moc": missing_moc[:max_items],
            "broken_links": broken[:max_items],
            "ambiguous_links": ambiguous[:max_items],
            "truncated": any(len(values) > max_items for values in (missing_moc, broken, ambiguous)),
        }
    return report


def link_issues(notes: list[Note]) -> tuple[list[dict], list[dict]]:
    by_stem: defaultdict[str, list[Note]] = defaultdict(list)
    by_relative: dict[str, Note] = {}
    for note in notes:
        by_stem[note.path.stem.casefold()].append(note)
        by_relative[note.relative.with_suffix("").as_posix().casefold()] = note
    broken: list[dict] = []
    ambiguous: list[dict] = []
    for note in notes:
        clean = strip_code(note.original)
        for raw in [*ALL_WIKILINK_RE.findall(clean), *MARKDOWN_LINK_RE.findall(clean)]:
            target = raw.split("#", 1)[0].strip().removesuffix(".md")
            if not target:
                continue
            if "/" in target:
                matches = [by_relative[target.casefold()]] if target.casefold() in by_relative else []
            else:
                matches = by_stem.get(Path(target).stem.casefold(), [])
            if not matches:
                broken.append({"source": note.relative.as_posix(), "target": target})
            elif len(matches) > 1:
                ambiguous.append({"source": note.relative.as_posix(), "target": target, "matches": [match.relative.as_posix() for match in matches]})
    return broken, ambiguous


def format_audit(report: dict) -> str:
    status = report["organization_status"]
    link_text = (
        f"broken={report['links']['broken']}, ambiguous={report['links']['ambiguous']}"
        if report["links"].get("checked") else "not checked in scoped audit; use --details"
    )
    return "\n".join([
        f"Profile: {report['profile']} (confidence: {report['confidence']})",
        f"Scope: {report['scope']}",
        f"Notes: {report['notes']}; map notes: {report.get('map_notes', 0)}; hubs: {report['hubs']}; missing MOC: {report['missing_moc']}",
        f"Status: linked={status.get('linked', 0)}, review={status.get('review', 0)}, unclassified={status.get('unclassified', 0)}, unset={status.get('unset', 0)}",
        "Links: " + link_text,
        f"Tags: {report['tags']['unique']} unique; {report['tags']['singletons']} singletons",
    ])


def path_in_targets(path: Path, targets: Iterable[Path]) -> bool:
    return any(path == target or target in path.parents for target in targets)


def format_plan_summary(plan: dict, plan_path: Path, root: Path) -> str:
    summary = plan["summary"]
    lines = [
        f"Profile: {summary['profile']} (confidence: {summary['confidence']})",
        f"Scanned: {summary['scanned']}; hubs: {summary['hubs']}; skipped: {summary['skipped']}",
        f"Index: cache hits={summary.get('cache_hits', 0)}; parsed={summary.get('parsed', summary['scanned'])}",
        f"Linked: {summary['linked']}; review: {summary['review']}; unclassified: {summary['unclassified']}",
        f"Plan: {display_path(root, plan_path)}",
    ]
    if summary.get("blocked"):
        lines.append("Blocked: " + summary["blocked"])
    return "\n".join(lines)


def read_plan(root: Path, plan_path: Path) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if int(plan.get("version", 0)) != VERSION:
        raise SystemExit(f"Unsupported plan version: {plan.get('version')}")
    if Path(plan.get("root", "")).resolve() != root:
        raise SystemExit("Plan root does not match --root")
    return plan


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_under_root(root: Path, value: str) -> Path:
    resolved = resolve_path(root, value)
    if resolved != root and root not in resolved.parents:
        raise SystemExit(f"Path escapes knowledge-base root: {value}")
    return resolved


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def effective_max_items(value: Optional[int], config: dict) -> int:
    return max(0, value if value is not None else int(config["output"].get("max_items", 10)))


def normalize_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    raw = value if isinstance(value, list) else re.split(r"[,，]", str(value))
    return unique(unquote(str(item).strip()).lstrip("#").strip() for item in raw if str(item).strip())


def normalize_links(value: object) -> list[str]:
    links = []
    for item in normalize_list(value):
        item = unquote(item)
        links.append(item if item.startswith("[[") and item.endswith("]]" ) else f"[[{item}]]")
    return unique(links)


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.sub(r"`[^`]*`", "", text)


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
