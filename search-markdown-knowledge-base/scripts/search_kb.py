#!/usr/bin/env python3
"""Rank Markdown notes by metadata, content, MOC membership, and wikilinks."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDES = (
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
)
WIKILINK_RE = re.compile(r"!?(?:\[\[)([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
TOKEN_SPLIT_RE = re.compile(r"[\s,，、;；/|]+")


@dataclass
class Note:
    path: Path
    relative: str
    title: str
    frontmatter: OrderedDict
    body: str
    tags: list[str]
    mocs: list[str]
    related: list[str]
    links: list[str]
    headings: list[str]


@dataclass
class Result:
    note: Note
    score: int = 0
    matched_fields: set[str] = field(default_factory=set)
    matched_terms: set[str] = field(default_factory=set)
    graph_reasons: list[str] = field(default_factory=list)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Knowledge-base root.")
    parser.add_argument("--query", required=True, help="Focused search terms.")
    parser.add_argument("--mode", choices=("concept", "industry"), default="concept")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--minimum-terms", type=int, help="Required direct term matches; defaults to half.")
    parser.add_argument("--path", action="append", help="Relative file or directory; repeatable.")
    parser.add_argument("--exclude", action="append", default=[], help="Additional glob exclusion.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    notes = load_notes(root, DEFAULT_EXCLUDES + tuple(args.exclude), args.path)
    terms = query_terms(args.query)
    if not terms:
        parser.error("query must contain at least one searchable term")

    minimum_terms = args.minimum_terms
    if minimum_terms is None:
        minimum_terms = 1 if len(terms) <= 2 else (len(terms) + 1) // 2
    minimum_terms = max(1, min(minimum_terms, len(terms)))
    results = rank_notes(notes, terms, args.mode, minimum_terms)
    results = [
        result
        for result in results
        if result.score > 0
        and (len(result.matched_terms) >= minimum_terms or result.graph_reasons)
    ][: max(args.limit, 0)]
    if args.json:
        print(json.dumps(format_json(root, args.query, terms, results), ensure_ascii=False, indent=2))
    else:
        print(format_text(args.query, terms, results))
    return 0


def load_notes(root: Path, excludes: Iterable[str], selected: list[str] | None) -> list[Note]:
    targets = [(root / item).resolve() for item in selected] if selected else [root]
    paths: set[Path] = set()
    for target in targets:
        if target.is_file() and target.suffix.lower() == ".md":
            paths.add(target)
        elif target.is_dir():
            paths.update(target.rglob("*.md"))
    return [parse_note(root, path) for path in sorted(paths) if include_path(root, path, excludes)]


def include_path(root: Path, path: Path, excludes: Iterable[str]) -> bool:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return not any(fnmatch.fnmatch(relative, pattern) for pattern in excludes)


def parse_note(root: Path, path: Path) -> Note:
    text = path.read_text(encoding="utf-8", errors="ignore")
    frontmatter: OrderedDict[str, object] = OrderedDict()
    body = text
    if text.startswith("---\n") or text.startswith("---\r\n"):
        lines = text.splitlines()
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                frontmatter = parse_frontmatter("\n".join(lines[1:index]))
                body = "\n".join(lines[index + 1 :])
                break
    title = str(frontmatter.get("title") or path.stem).strip()
    tags = normalize_values(frontmatter.get("tags"))
    mocs = normalize_links(frontmatter.get("moc"))
    related = normalize_links(frontmatter.get("related"))
    links = unique(WIKILINK_RE.findall(body) + mocs + related)
    headings = [match.strip() for match in HEADING_RE.findall(body)]
    return Note(path, path.relative_to(root).as_posix(), title, frontmatter, body, tags, mocs, related, links, headings)


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
            if raw.startswith("[") and raw.endswith("]") and not raw.startswith("[["):
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


def query_terms(query: str) -> list[str]:
    query = query.strip().casefold()
    query = re.sub(r"^(?:请)?(?:帮我)?(?:查询|查找|搜索|了解)", "", query)
    query = re.sub(r"(?:的)?(?:相关)?(?:信息|资料|笔记|内容)$", "", query)
    raw = TOKEN_SPLIT_RE.split(query)
    stop = {"查询", "查找", "搜索", "相关", "信息", "资料", "笔记", "关于", "有哪些", "什么"}
    terms = [token.strip("!?！？。:：()（）[]【】\"'") for token in raw]
    terms = [token for token in terms if len(token) >= 2 and token not in stop]
    expanded: list[str] = []
    for term in terms:
        expanded.append(term)
        for suffix in ("行业", "产业", "概念"):
            if term.endswith(suffix) and len(term) > len(suffix) + 1:
                expanded.append(term[: -len(suffix)])
    return unique(expanded)


def rank_notes(notes: list[Note], terms: list[str], mode: str, minimum_terms: int) -> list[Result]:
    results = {note.relative: score_note(note, terms, mode) for note in notes}
    aliases: dict[str, list[Note]] = defaultdict(list)
    for note in notes:
        aliases[note.path.stem.casefold()].append(note)
        aliases[note.title.casefold()].append(note)

    direct = sorted(results.values(), key=result_sort_key)
    seed_limit = min(12, len(direct))
    for seed in direct[:seed_limit]:
        if seed.score <= 0 or len(seed.matched_terms) < minimum_terms:
            continue
        is_hub = note_is_hub(seed.note)
        bonus = 7 if mode == "industry" and is_hub else 3
        for link in seed.note.links:
            for target in aliases.get(link.casefold(), []):
                target_result = results[target.relative]
                target_result.score += bonus
                target_result.matched_fields.add("graph")
                target_result.graph_reasons.append(f"linked from {seed.note.title}")

    return sorted(results.values(), key=result_sort_key)


def score_note(note: Note, terms: list[str], mode: str) -> Result:
    result = Result(note)
    title = note.title.casefold()
    path = note.relative.casefold()
    tags = [value.casefold() for value in note.tags]
    metadata = [str(value).casefold() for key, value in note.frontmatter.items() if key not in {"tags", "moc", "related"}]
    mocs = [value.casefold() for value in note.mocs]
    related = [value.casefold() for value in note.related]
    headings = [value.casefold() for value in note.headings]
    body = note.body.casefold()

    for term in terms:
        matched = False
        if title == term:
            result.score += 24
            result.matched_fields.add("title")
            matched = True
        elif term in title:
            result.score += 14
            result.matched_fields.add("title")
            matched = True
        if term in path and term not in title:
            result.score += 3
            result.matched_fields.add("path")
            matched = True
        if term in tags:
            result.score += 14
            result.matched_fields.add("tags")
            matched = True
        elif any(term in value for value in tags):
            result.score += 8
            result.matched_fields.add("tags")
            matched = True
        if any(term in value for value in mocs):
            result.score += 8
            result.matched_fields.add("moc")
            matched = True
        if any(term in value for value in related):
            result.score += 6
            result.matched_fields.add("related")
            matched = True
        if any(term in value for value in headings):
            result.score += 7
            result.matched_fields.add("heading")
            matched = True
        if any(term in value for value in metadata):
            result.score += 4
            result.matched_fields.add("metadata")
            matched = True
        occurrences = body.count(term)
        if occurrences:
            result.score += min(occurrences, 4) * 2
            result.matched_fields.add("body")
            matched = True
        if matched:
            result.matched_terms.add(term)

    if mode == "industry" and note_is_hub(note) and result.score:
        result.score += 8
        result.matched_fields.add("hub")
    if len(result.matched_terms) > 1:
        result.score += (len(result.matched_terms) - 1) * 4
    return result


def note_is_hub(note: Note) -> bool:
    note_type = str(note.frontmatter.get("type") or "").casefold()
    return note_type in {"moc", "hub", "index", "map"} or note.path.stem.casefold().endswith(("moc", "hub", "index", "map"))


def result_sort_key(result: Result) -> tuple[int, str]:
    return (-result.score, result.note.relative.casefold())


def format_text(query: str, terms: list[str], results: list[Result]) -> str:
    lines = [f"Query: {query}", "Terms: " + ", ".join(terms), f"Results: {len(results)}"]
    if not results:
        return "\n".join(lines + ["No matching notes found."])
    for index, result in enumerate(results, 1):
        note = result.note
        fields = ", ".join(sorted(result.matched_fields))
        lines.append(f"\n{index}. {note.title}  [score={result.score}; {fields}]")
        lines.append(f"   path: {note.relative}")
        if note.tags:
            lines.append("   tags: " + ", ".join(note.tags[:10]))
        if note.mocs:
            lines.append("   moc: " + ", ".join(note.mocs))
        snippet = best_snippet(note.body, result.matched_terms)
        if snippet:
            lines.append("   snippet: " + snippet)
        if result.graph_reasons:
            lines.append("   graph: " + "; ".join(unique(result.graph_reasons)[:3]))
    return "\n".join(lines)


def format_json(root: Path, query: str, terms: list[str], results: list[Result]) -> dict:
    return {
        "root": str(root),
        "query": query,
        "terms": terms,
        "results": [
            {
                "title": result.note.title,
                "path": result.note.relative,
                "score": result.score,
                "matched_fields": sorted(result.matched_fields),
                "matched_terms": sorted(result.matched_terms),
                "tags": result.note.tags,
                "moc": result.note.mocs,
                "related": result.note.related,
                "snippet": best_snippet(result.note.body, result.matched_terms),
                "graph_reasons": unique(result.graph_reasons),
            }
            for result in results
        ],
    }


def best_snippet(body: str, terms: Iterable[str], width: int = 220) -> str:
    compact = re.sub(r"\s+", " ", body).strip()
    lowered = compact.casefold()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return compact[:width] + ("..." if len(compact) > width else "")
    center = min(positions)
    start = max(0, center - width // 3)
    end = min(len(compact), start + width)
    prefix = "..." if start else ""
    suffix = "..." if end < len(compact) else ""
    return prefix + compact[start:end].strip() + suffix


def normalize_values(value: object) -> list[str]:
    if value is None or value == "":
        return []
    values = value if isinstance(value, list) else re.split(r"[,，]", str(value))
    return unique([unquote(str(item)).lstrip("#").strip() for item in values if str(item).strip()])


def normalize_links(value: object) -> list[str]:
    values = normalize_values(value)
    return unique([item[2:-2].strip() if item.startswith("[[") and item.endswith("]]" ) else item for item in values])


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


if __name__ == "__main__":
    raise SystemExit(main())
