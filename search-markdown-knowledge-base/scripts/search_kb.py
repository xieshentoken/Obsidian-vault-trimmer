#!/usr/bin/env python3
"""Search Markdown knowledge bases with incremental indexing and graph ranking."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sqlite3
import sys
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence


INDEX_VERSION = "2"
DEFAULT_INDEX = ".knowledge-search-index.sqlite3"
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
PUNCT_RE = re.compile(r"[\s,，、;；/|!?！？。.:：()（）\[\]【】\"']+")
HUB_TYPES = {"moc", "hub", "index", "map"}
QUERY_STOP = {
    "查询", "查找", "搜索", "相关", "信息", "资料", "笔记", "内容", "关于",
    "有哪些", "是什么", "什么", "如何", "怎么", "介绍", "简单介绍", "帮我", "请",
    "moc", "hub", "index", "map",
}
GENERIC_ANCHORS = {
    "行业", "产业", "概念", "技术", "市场", "项目", "公司", "企业", "材料", "工艺",
    "设备", "政策", "供应链", "优点", "缺点", "优缺点", "优势", "劣势", "风险",
    "moc", "hub", "index", "map",
}
FACET_GROUPS = OrderedDict(
    (
        ("优缺点", ("优缺点", "优点", "缺点", "优势", "劣势", "局限", "不足", "advantages", "disadvantages", "pros", "cons", "limitations")),
        ("原理", ("原理", "机制", "机理", "工作原理", "principle", "mechanism")),
        ("技术", ("技术", "架构", "路线", "材料", "工艺", "设备", "参数", "性能", "technology", "architecture", "material", "process", "equipment", "performance")),
        ("安全可靠性", ("安全", "风险", "可靠性", "事故", "失效", "safety", "risk", "reliability", "failure")),
        ("效率", ("效率", "能效", "热效率", "利用率", "efficiency")),
        ("供应链", ("供应链", "供应商", "客户", "制造", "采购", "国产化", "OEM", "JDM", "supply chain", "supplier", "customer", "manufacturing", "procurement", "localization")),
        ("经济性", ("成本", "价格", "产能", "良率", "商业模式", "经济性", "cost", "price", "capacity", "yield", "economics")),
        ("政策市场", ("政策", "法规", "标准", "补贴", "市场", "需求", "渗透率", "policy", "regulation", "standard", "market", "demand", "adoption")),
        ("项目证据", ("项目", "案例", "报告", "进展", "落地", "project", "case", "report", "evidence")),
    )
)


@dataclass
class Note:
    path: Path
    relative: str
    title: str
    tags: list[str]
    aliases: list[str]
    mocs: list[str]
    related: list[str]
    links: list[str]
    headings: list[str]
    metadata: list[str]
    note_type: str
    body: str = ""
    body_loaded: bool = False


@dataclass
class QuerySpec:
    raw: str
    anchors: list[str]
    facets: list[str]
    facet_terms: list[str]
    terms: list[str]


@dataclass
class Result:
    note: Note
    score: int = 0
    matched_fields: set[str] = field(default_factory=set)
    matched_terms: set[str] = field(default_factory=set)
    graph_reasons: list[str] = field(default_factory=list)
    exact_match: bool = False
    anchor_matched: bool = False
    graph_anchor: bool = False


@dataclass
class IndexStats:
    total: int = 0
    updated: int = 0
    removed: int = 0
    reused: int = 0
    fts: bool = False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Knowledge-base root.")
    parser.add_argument("--query", required=True, help="Natural-language question or focused terms.")
    parser.add_argument("--mode", choices=("concept", "industry"), default="concept")
    parser.add_argument("--anchor", action="append", help="Override topic anchor; repeatable.")
    parser.add_argument("--facet", action="append", default=[], help="Add a facet group; repeatable.")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--minimum-terms", type=int, help="Required direct matches; exact anchors bypass it.")
    parser.add_argument("--path", action="append", help="Relative file or directory; repeatable.")
    parser.add_argument("--exclude", action="append", default=[], help="Additional glob exclusion.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results.")
    parser.add_argument("--verbose", action="store_true", help="Include full retrieval metadata.")
    parser.add_argument("--snippet-count", type=int, help="Number of ranked results with snippets.")
    parser.add_argument("--snippet-width", type=int, default=120)
    parser.add_argument("--index", help=f"Index path; defaults to <root>/{DEFAULT_INDEX}.")
    parser.add_argument("--no-index", action="store_true", help="Scan Markdown directly without writing an index.")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild the incremental index.")
    parser.add_argument("--stats", action="store_true", help="Print index statistics to stderr.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"knowledge-base root is not a directory: {root}")

    connection: sqlite3.Connection | None = None
    stats = IndexStats()
    try:
        if args.no_index:
            notes = load_notes(root, DEFAULT_EXCLUDES, None)
            body_loader = lambda paths: None
        else:
            index_path = resolve_index_path(root, args.index)
            try:
                connection, notes, stats = load_indexed_notes(
                    root, index_path, DEFAULT_EXCLUDES, args.rebuild_index
                )
                body_loader = make_body_loader(connection, notes)
            except (OSError, sqlite3.Error) as error:
                print(f"Index unavailable; using direct scan: {error}", file=sys.stderr)
                notes = load_notes(root, DEFAULT_EXCLUDES, None)
                body_loader = lambda paths: None

        notes = filter_notes(root, notes, args.path, args.exclude)
        if not notes:
            parser.error("no Markdown notes found in the selected scope")

        spec = parse_query(args.query, notes, args.facet, args.anchor)
        if not spec.terms:
            parser.error("query must contain at least one searchable term")

        minimum_terms = args.minimum_terms
        if minimum_terms is None:
            minimum_terms = 1 if spec.anchors else max(1, (len(spec.terms) + 1) // 2)
        minimum_terms = max(1, min(minimum_terms, len(spec.terms)))

        if connection is None:
            candidate_paths = {note.relative for note in notes}
        else:
            allowed = {note.relative for note in notes}
            candidate_paths = metadata_candidate_paths(notes, spec.terms)
            candidate_paths.update(body_candidate_paths(connection, spec.terms, allowed))

        results = rank_notes(
            notes,
            candidate_paths,
            spec,
            args.mode,
            minimum_terms,
            max(args.limit, 0),
            body_loader,
        )[: max(args.limit, 0)]

        snippet_count = args.snippet_count
        if snippet_count is None:
            snippet_count = len(results) if args.verbose else min(3, len(results))
        snippet_count = max(0, min(snippet_count, len(results)))
        body_loader({result.note.relative for result in results[:snippet_count]})

        if args.json:
            payload = format_json(root, spec, results, args.verbose, snippet_count, args.snippet_width)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(format_text(spec, results, args.verbose, snippet_count, args.snippet_width))
        if args.stats and not args.no_index:
            print(
                f"Index: total={stats.total} reused={stats.reused} "
                f"updated={stats.updated} removed={stats.removed} fts={str(stats.fts).lower()}",
                file=sys.stderr,
            )
    finally:
        if connection is not None:
            connection.close()
    return 0


def resolve_index_path(root: Path, value: str | None) -> Path:
    if not value:
        return root / DEFAULT_INDEX
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def load_indexed_notes(
    root: Path, index_path: Path, excludes: Sequence[str], rebuild: bool
) -> tuple[sqlite3.Connection, list[Note], IndexStats]:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(index_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA synchronous=NORMAL")
    fts = ensure_schema(connection)

    stored_root = get_meta(connection, "root")
    if rebuild or stored_root not in {None, str(root)}:
        connection.execute("DELETE FROM notes")
    set_meta(connection, "root", str(root))

    paths = scan_markdown_paths(root, excludes, None)
    current = {path.relative_to(root).as_posix(): path for path in paths}
    stored = {
        row["relative"]: (row["mtime_ns"], row["size"])
        for row in connection.execute("SELECT relative, mtime_ns, size FROM notes")
    }
    stats = IndexStats(total=len(current), fts=fts)

    removed = sorted(set(stored) - set(current))
    if removed:
        connection.executemany("DELETE FROM notes WHERE relative = ?", ((item,) for item in removed))
    stats.removed = len(removed)

    for relative, path in sorted(current.items()):
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        if not rebuild and stored.get(relative) == signature:
            stats.reused += 1
            continue
        note = parse_note(root, path)
        connection.execute(
            """
            INSERT INTO notes (
                relative, mtime_ns, size, title, tags, aliases, mocs, related,
                links, headings, metadata, note_type, body
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(relative) DO UPDATE SET
                mtime_ns=excluded.mtime_ns, size=excluded.size, title=excluded.title,
                tags=excluded.tags, aliases=excluded.aliases, mocs=excluded.mocs,
                related=excluded.related, links=excluded.links, headings=excluded.headings,
                metadata=excluded.metadata, note_type=excluded.note_type, body=excluded.body
            """,
            (
                relative,
                stat.st_mtime_ns,
                stat.st_size,
                note.title,
                dump_list(note.tags),
                dump_list(note.aliases),
                dump_list(note.mocs),
                dump_list(note.related),
                dump_list(note.links),
                dump_list(note.headings),
                dump_list(note.metadata),
                note.note_type,
                note.body,
            ),
        )
        stats.updated += 1
    connection.commit()

    rows = connection.execute(
        """
        SELECT relative, title, tags, aliases, mocs, related, links, headings,
               metadata, note_type
        FROM notes ORDER BY relative
        """
    )
    notes = [
        Note(
            path=root / row["relative"],
            relative=row["relative"],
            title=row["title"],
            tags=load_list(row["tags"]),
            aliases=load_list(row["aliases"]),
            mocs=load_list(row["mocs"]),
            related=load_list(row["related"]),
            links=load_list(row["links"]),
            headings=load_list(row["headings"]),
            metadata=load_list(row["metadata"]),
            note_type=row["note_type"] or "",
        )
        for row in rows
    ]
    return connection, notes, stats


def ensure_schema(connection: sqlite3.Connection) -> bool:
    connection.execute("CREATE TABLE IF NOT EXISTS kb_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    version = get_meta(connection, "version")
    if version != INDEX_VERSION:
        connection.executescript(
            """
            DROP TRIGGER IF EXISTS notes_ai;
            DROP TRIGGER IF EXISTS notes_ad;
            DROP TRIGGER IF EXISTS notes_au;
            DROP TABLE IF EXISTS notes_fts;
            DROP TABLE IF EXISTS notes;
            """
        )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY,
            relative TEXT NOT NULL UNIQUE,
            mtime_ns INTEGER NOT NULL,
            size INTEGER NOT NULL,
            title TEXT NOT NULL,
            tags TEXT NOT NULL,
            aliases TEXT NOT NULL,
            mocs TEXT NOT NULL,
            related TEXT NOT NULL,
            links TEXT NOT NULL,
            headings TEXT NOT NULL,
            metadata TEXT NOT NULL,
            note_type TEXT NOT NULL,
            body TEXT NOT NULL
        )
        """
    )
    fts = True
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                body, content='notes', content_rowid='id', tokenize='trigram'
            )
            """
        )
        connection.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                INSERT INTO notes_fts(rowid, body) VALUES (new.id, new.body);
            END;
            CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, body) VALUES ('delete', old.id, old.body);
            END;
            CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, body) VALUES ('delete', old.id, old.body);
                INSERT INTO notes_fts(rowid, body) VALUES (new.id, new.body);
            END;
            """
        )
    except sqlite3.OperationalError:
        fts = False
    set_meta(connection, "version", INDEX_VERSION)
    connection.commit()
    return fts


def get_meta(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM kb_meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT INTO kb_meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def make_body_loader(connection: sqlite3.Connection, notes: list[Note]) -> Callable[[Iterable[str]], None]:
    by_relative = {note.relative: note for note in notes}

    def load(paths: Iterable[str]) -> None:
        wanted = sorted(
            relative for relative in set(paths)
            if relative in by_relative and not by_relative[relative].body_loaded
        )
        if not wanted:
            return
        placeholders = ",".join("?" for _ in wanted)
        rows = connection.execute(
            f"SELECT relative, body FROM notes WHERE relative IN ({placeholders})", wanted
        )
        for row in rows:
            note = by_relative[row["relative"]]
            note.body = row["body"]
            note.body_loaded = True

    return load


def body_candidate_paths(
    connection: sqlite3.Connection, terms: Sequence[str], allowed: set[str], per_term: int = 240
) -> set[str]:
    output: set[str] = set()
    has_fts = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts'"
    ).fetchone()
    for term in terms:
        rows: Iterable[sqlite3.Row]
        if has_fts and len(term) >= 3:
            phrase = '"' + term.replace('"', '""') + '"'
            try:
                rows = connection.execute(
                    """
                    SELECT n.relative FROM notes_fts
                    JOIN notes n ON n.id = notes_fts.rowid
                    WHERE notes_fts MATCH ? LIMIT ?
                    """,
                    (phrase, per_term),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = body_like_rows(connection, term, per_term)
        else:
            rows = body_like_rows(connection, term, per_term)
        output.update(row["relative"] for row in rows if row["relative"] in allowed)
    return output


def body_like_rows(connection: sqlite3.Connection, term: str, limit: int) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT relative FROM notes
        WHERE instr(body, ?) > 0 OR instr(lower(body), lower(?)) > 0
        LIMIT ?
        """,
        (term, term, limit),
    ).fetchall()


def load_notes(root: Path, excludes: Sequence[str], selected: list[str] | None) -> list[Note]:
    return [parse_note(root, path) for path in scan_markdown_paths(root, excludes, selected)]


def scan_markdown_paths(root: Path, excludes: Sequence[str], selected: list[str] | None) -> list[Path]:
    targets = [(root / item).resolve() for item in selected] if selected else [root]
    paths: set[Path] = set()
    for target in targets:
        if target.is_file() and target.suffix.lower() == ".md":
            paths.add(target)
        elif target.is_dir():
            paths.update(target.rglob("*.md"))
    return sorted(path for path in paths if include_path(root, path, excludes))


def include_path(root: Path, path: Path, excludes: Sequence[str]) -> bool:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return not any(fnmatch.fnmatch(relative, pattern) for pattern in excludes)


def filter_notes(
    root: Path, notes: list[Note], selected: list[str] | None, excludes: Sequence[str]
) -> list[Note]:
    prefixes: list[str] = []
    if selected:
        for value in selected:
            target = (root / value).resolve()
            try:
                prefixes.append(target.relative_to(root).as_posix().rstrip("/"))
            except ValueError:
                continue
    output = []
    for note in notes:
        if prefixes and not any(
            note.relative == prefix or note.relative.startswith(prefix + "/") for prefix in prefixes
        ):
            continue
        if any(fnmatch.fnmatch(note.relative, pattern) for pattern in excludes):
            continue
        output.append(note)
    return output


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
    aliases = unique(
        normalize_values(frontmatter.get("aliases")) + normalize_values(frontmatter.get("alias"))
    )
    mocs = normalize_links(frontmatter.get("moc"))
    related = normalize_links(frontmatter.get("related"))
    links = unique(WIKILINK_RE.findall(body) + mocs + related)
    headings = [match.strip() for match in HEADING_RE.findall(body)]
    metadata = [
        str(value) for key, value in frontmatter.items()
        if key not in {"tags", "aliases", "alias", "moc", "related", "type"}
    ]
    return Note(
        path=path,
        relative=path.relative_to(root).as_posix(),
        title=title,
        tags=tags,
        aliases=aliases,
        mocs=mocs,
        related=related,
        links=links,
        headings=headings,
        metadata=metadata,
        note_type=str(frontmatter.get("type") or "").casefold(),
        body=body,
        body_loaded=True,
    )


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


def parse_query(
    query: str, notes: Sequence[Note], facet_inputs: Sequence[str], anchor_override: list[str] | None
) -> QuerySpec:
    cleaned = query.strip().casefold()
    cleaned = re.sub(r"^(?:请)?(?:帮我)?(?:查询|查找|搜索|了解|介绍)", "", cleaned)
    cleaned = re.sub(r"(?:的)?(?:相关)?(?:信息|资料|笔记|内容)$", "", cleaned)
    compact = compact_text(cleaned)

    facets: list[str] = []
    facet_terms: list[str] = []
    matched_aliases: list[str] = []
    extra_facet_text = " ".join(facet_inputs).casefold()
    facet_haystack = compact + compact_text(extra_facet_text)
    for name, aliases in FACET_GROUPS.items():
        present = [alias.casefold() for alias in aliases if compact_text(alias.casefold()) in facet_haystack]
        if present:
            facets.append(name)
            matched_aliases.extend(present)
            facet_terms.extend(alias.casefold() for alias in aliases)
    for value in facet_inputs:
        facet_terms.extend(tokenize_focus_terms(value.casefold()))

    explicit_parts = tokenize_focus_terms(cleaned)
    matched_alias_tokens = {
        token for alias in matched_aliases for token in tokenize_focus_terms(alias)
    }
    residual_parts: list[str] = []
    for part in explicit_parts:
        if part in matched_alias_tokens:
            continue
        residual = part
        for alias in sorted(set(matched_aliases), key=len, reverse=True):
            residual = residual.replace(alias, "")
        residual = residual.strip("的地得和与及以及并")
        residual = strip_topic_suffix(residual)
        if len(residual) >= 2 and residual not in QUERY_STOP and residual not in GENERIC_ANCHORS:
            residual_parts.append(residual)

    if anchor_override:
        anchors = unique(
            strip_topic_suffix(term)
            for value in anchor_override
            for term in tokenize_focus_terms(value.casefold())
            if len(strip_topic_suffix(term)) >= 2
        )
    else:
        vocabulary = build_vocabulary(notes)
        known = [term for term in vocabulary if compact_text(term) and compact_text(term) in compact]
        anchor_phrase = max(known, key=lambda item: len(compact_text(item)), default="")
        anchors = unique(([anchor_phrase] if anchor_phrase else []) + residual_parts)
        if not anchors:
            anchors = [
                strip_topic_suffix(part) for part in explicit_parts
                if part not in QUERY_STOP and part not in GENERIC_ANCHORS
            ][:1]

    anchors = [term for term in unique(anchors) if len(term) >= 2 and term not in GENERIC_ANCHORS]
    facet_terms = [term for term in unique(facet_terms) if len(term) >= 2]
    terms = unique(anchors + residual_parts + facet_terms)
    return QuerySpec(query, anchors, facets, facet_terms, terms)


def tokenize_focus_terms(value: str) -> list[str]:
    return [
        token.strip("!?！？。:：()（）[]【】\"'")
        for token in TOKEN_SPLIT_RE.split(value)
        if len(token.strip("!?！？。:：()（）[]【】\"'")) >= 2
        and token.strip("!?！？。:：()（）[]【】\"'") not in QUERY_STOP
    ]


def build_vocabulary(notes: Sequence[Note]) -> list[str]:
    terms: list[str] = []
    for note in notes:
        values = [note.title, note.path.stem, *note.aliases, *note.tags, *note.mocs]
        for value in values:
            term = strip_hub_suffix(value.casefold().strip())
            if 2 <= len(term) <= 60 and term not in GENERIC_ANCHORS:
                terms.append(term)
    return unique(terms)


def strip_topic_suffix(value: str) -> str:
    value = value.strip()
    for suffix in ("行业", "产业", "概念"):
        if value.endswith(suffix) and len(value) > len(suffix) + 1:
            return value[: -len(suffix)]
    return value


def strip_hub_suffix(value: str) -> str:
    return re.sub(r"\s+(?:moc|hub|index|map)$", "", value, flags=re.IGNORECASE).strip()


def compact_text(value: str) -> str:
    return PUNCT_RE.sub("", value)


def metadata_candidate_paths(notes: Sequence[Note], terms: Sequence[str]) -> set[str]:
    output: set[str] = set()
    for note in notes:
        values = [
            note.title, note.relative, *note.tags, *note.aliases, *note.mocs,
            *note.related, *note.headings, *note.metadata,
        ]
        haystack = "\n".join(values).casefold()
        if any(term in haystack for term in terms):
            output.add(note.relative)
    return output


def rank_notes(
    notes: list[Note],
    candidate_paths: set[str],
    spec: QuerySpec,
    mode: str,
    minimum_terms: int,
    limit: int,
    body_loader: Callable[[Iterable[str]], None],
) -> list[Result]:
    by_relative = {note.relative: note for note in notes}
    candidate_paths.intersection_update(by_relative)
    body_loader(candidate_paths)
    results = {
        relative: score_note(by_relative[relative], spec, mode)
        for relative in candidate_paths
    }

    outgoing, incoming = build_graph(notes)
    direct = sorted(results.values(), key=result_sort_key)
    seeds = [result for result in direct if direct_eligible(result, spec, minimum_terms)]
    seeds = seeds[: max(20, limit * 4)]

    graph_updates: dict[str, list[tuple[int, str, bool]]] = defaultdict(list)
    for seed in seeds:
        if mode == "concept" and note_is_hub(seed.note) and not seed.exact_match:
            continue
        anchor_seed = seed.exact_match or seed.anchor_matched
        for target in outgoing.get(seed.note.relative, set()):
            graph_updates[target].append((graph_bonus(seed, mode), f"linked from {seed.note.title}", anchor_seed))
        for source in incoming.get(seed.note.relative, set()):
            graph_updates[source].append((graph_bonus(seed, mode), f"links to {seed.note.title}", anchor_seed))

    missing = set(graph_updates) - set(results)
    body_loader(missing)
    for relative in missing:
        if relative in by_relative:
            results[relative] = score_note(by_relative[relative], spec, mode)
    for relative, updates in graph_updates.items():
        result = results.get(relative)
        if not result:
            continue
        for bonus, reason, anchor_seed in updates:
            result.score += bonus
            result.matched_fields.add("graph")
            result.graph_reasons.append(reason)
            result.graph_anchor = result.graph_anchor or anchor_seed

    ranked = sorted(results.values(), key=result_sort_key)
    return [
        result for result in ranked
        if result.score > 0 and final_eligible(result, spec, mode, minimum_terms)
    ]


def build_graph(notes: Sequence[Note]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    aliases: dict[str, set[str]] = defaultdict(set)
    for note in notes:
        for value in [note.title, note.path.stem, note.relative.removesuffix(".md"), *note.aliases]:
            aliases[normalize_link_key(value)].add(note.relative)

    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    for note in notes:
        for link in note.links:
            keys = [normalize_link_key(link), normalize_link_key(Path(link).stem)]
            targets: set[str] = set()
            for key in keys:
                targets.update(aliases.get(key, set()))
            for target in targets:
                if target == note.relative:
                    continue
                outgoing[note.relative].add(target)
                incoming[target].add(note.relative)
    return outgoing, incoming


def normalize_link_key(value: str) -> str:
    return value.strip().removesuffix(".md").casefold()


def graph_bonus(seed: Result, mode: str) -> int:
    if mode == "industry" and note_is_hub(seed.note):
        return 9
    return 5 if seed.exact_match else 4


def score_note(note: Note, spec: QuerySpec, mode: str) -> Result:
    result = Result(note)
    title = note.title.casefold()
    path = note.relative.casefold()
    aliases = [value.casefold() for value in note.aliases]
    tags = [value.casefold() for value in note.tags]
    mocs = [value.casefold() for value in note.mocs]
    related = [value.casefold() for value in note.related]
    headings = [value.casefold() for value in note.headings]
    metadata = [value.casefold() for value in note.metadata]
    body = note.body.casefold() if note.body_loaded else ""
    anchor_set = set(spec.anchors)

    for term in spec.terms:
        base = 0
        fields: set[str] = set()
        exact_anchor = False
        if title == term or (note_is_hub(note) and strip_hub_suffix(title) == term):
            base += 40
            fields.add("title")
            exact_anchor = term in anchor_set
        elif term in title:
            base += 24
            fields.add("title")
        if term in aliases:
            base += 34
            fields.add("alias")
            exact_anchor = exact_anchor or term in anchor_set
        elif any(term in value for value in aliases):
            base += 18
            fields.add("alias")
        if term in tags:
            base += 20
            fields.add("tags")
        elif any(term in value for value in tags):
            base += 12
            fields.add("tags")
        if any(term in value for value in mocs):
            base += 14
            fields.add("moc")
        if any(term in value for value in related):
            base += 10
            fields.add("related")
        if any(term in value for value in headings):
            base += 10
            fields.add("heading")
        if any(term in value for value in metadata):
            base += 5
            fields.add("metadata")
        if term in path and term not in title:
            base += 4
            fields.add("path")
        occurrences = body.count(term) if body else 0
        if occurrences:
            base += min(occurrences, 4) * 2
            fields.add("body")

        if not fields:
            continue
        factor = 1.0 if term in anchor_set else 0.55
        result.score += max(1, round(base * factor))
        result.matched_fields.update(fields)
        result.matched_terms.add(term)
        if term in anchor_set:
            result.anchor_matched = True
        if exact_anchor:
            result.exact_match = True

    if result.anchor_matched:
        result.score += 12
    if result.exact_match:
        result.score += 18
    if mode == "industry" and result.anchor_matched and note_is_hub(note):
        result.score += 10
        result.matched_fields.add("hub")
    if proximity_match(body, spec.anchors, spec.facet_terms):
        result.score += 8
        result.matched_fields.add("proximity")
    return result


def proximity_match(body: str, anchors: Sequence[str], facets: Sequence[str], window: int = 240) -> bool:
    if not body or not anchors or not facets:
        return False
    anchor_positions = [body.find(term) for term in anchors if body.find(term) >= 0]
    facet_positions = [body.find(term) for term in facets if body.find(term) >= 0]
    return bool(anchor_positions and facet_positions) and min(
        abs(anchor - facet) for anchor in anchor_positions for facet in facet_positions
    ) <= window


def direct_eligible(result: Result, spec: QuerySpec, minimum_terms: int) -> bool:
    if result.exact_match:
        return True
    if spec.anchors:
        return result.anchor_matched and len(result.matched_terms) >= minimum_terms
    return len(result.matched_terms) >= minimum_terms


def final_eligible(result: Result, spec: QuerySpec, mode: str, minimum_terms: int) -> bool:
    if result.exact_match:
        return True
    if result.graph_anchor and mode == "concept":
        return result.anchor_matched or note_is_hub(result.note)
    if result.graph_anchor:
        return True
    if spec.anchors:
        return result.anchor_matched and len(result.matched_terms) >= minimum_terms
    return len(result.matched_terms) >= minimum_terms or bool(result.graph_reasons)


def note_is_hub(note: Note) -> bool:
    if note.note_type:
        return note.note_type in HUB_TYPES
    return note.path.stem.casefold().endswith(("moc", "hub", "index", "map"))


def result_sort_key(result: Result) -> tuple[int, int, str]:
    return (-int(result.exact_match), -result.score, result.note.relative.casefold())


def format_text(
    spec: QuerySpec,
    results: Sequence[Result],
    verbose: bool,
    snippet_count: int,
    snippet_width: int,
) -> str:
    anchor = ", ".join(spec.anchors) if spec.anchors else "(none)"
    facets = ", ".join(spec.facets) if spec.facets else "(none)"
    lines = [f"Anchor: {anchor} | Facets: {facets} | Results: {len(results)}"]
    if not results:
        return "\n".join(lines + ["No matching notes found."])
    for index, result in enumerate(results, 1):
        fields = ",".join(sorted(result.matched_fields))
        terms = ",".join(sorted(result.matched_terms, key=len, reverse=True)[:4])
        lines.append(f"{index}. {result.note.title} [{result.score}; {fields}; {terms}]")
        lines.append(f"   {result.note.relative}")
        if index <= snippet_count and result.note.body_loaded:
            snippet = best_snippet(result.note.body, result.matched_terms or spec.anchors, snippet_width)
            if snippet:
                lines.append(f"   {snippet}")
        if verbose:
            if result.note.tags:
                lines.append("   tags: " + ", ".join(result.note.tags[:10]))
            if result.note.mocs:
                lines.append("   moc: " + ", ".join(result.note.mocs))
            if result.note.related:
                lines.append("   related: " + ", ".join(result.note.related))
            if result.graph_reasons:
                lines.append("   graph: " + "; ".join(unique(result.graph_reasons)[:4]))
    return "\n".join(lines)


def format_json(
    root: Path,
    spec: QuerySpec,
    results: Sequence[Result],
    verbose: bool,
    snippet_count: int,
    snippet_width: int,
) -> dict:
    output = []
    for index, result in enumerate(results):
        item = {
            "title": result.note.title,
            "path": result.note.relative,
            "score": result.score,
            "matched_fields": sorted(result.matched_fields),
            "matched_terms": sorted(result.matched_terms),
        }
        if index < snippet_count and result.note.body_loaded:
            item["snippet"] = best_snippet(
                result.note.body, result.matched_terms or spec.anchors, snippet_width
            )
        if verbose:
            item.update(
                {
                    "tags": result.note.tags,
                    "moc": result.note.mocs,
                    "related": result.note.related,
                    "graph_reasons": unique(result.graph_reasons),
                }
            )
        output.append(item)
    return {
        "root": str(root),
        "query": spec.raw,
        "anchors": spec.anchors,
        "facets": spec.facets,
        "terms": spec.terms,
        "results": output,
    }


def best_snippet(body: str, terms: Iterable[str], width: int = 120) -> str:
    compact = re.sub(r"\s+", " ", body).strip()
    lowered = compact.casefold()
    positions = []
    for term in terms:
        position = lowered.find(term)
        if position >= 0:
            positions.append(position)
    if not positions:
        return compact[:width] + ("..." if len(compact) > width else "")
    center = min(positions)
    start = max(0, center - width // 3)
    end = min(len(compact), start + width)
    return ("..." if start else "") + compact[start:end].strip() + ("..." if end < len(compact) else "")


def normalize_values(value: object) -> list[str]:
    if value is None or value == "":
        return []
    values = value if isinstance(value, list) else re.split(r"[,，]", str(value))
    return unique(unquote(str(item)).lstrip("#").strip() for item in values if str(item).strip())


def normalize_links(value: object) -> list[str]:
    values = normalize_values(value)
    return unique(
        item[2:-2].strip() if item.startswith("[[") and item.endswith("]]" ) else item
        for item in values
    )


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def dump_list(values: Sequence[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def load_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


if __name__ == "__main__":
    raise SystemExit(main())
