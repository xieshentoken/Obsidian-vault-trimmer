from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "kb_organizer.py"
SPEC = importlib.util.spec_from_file_location("kb_organizer", SCRIPT)
kb = importlib.util.module_from_spec(SPEC)
sys.modules["kb_organizer"] = kb
assert SPEC.loader is not None
SPEC.loader.exec_module(kb)


class OrganizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        for name in (
            "00-Inbox",
            "00-Maps",
            "01-Projects",
            "02-Areas",
            "03-Resources",
            "04-Archives",
        ):
            (self.root / name).mkdir()
        self.write_note(
            "00-Maps/材料 MOC.md",
            """
---
type: moc
tags:
  - 材料
---
# 材料
""",
        )
        self.config = copy.deepcopy(kb.DEFAULT_CONFIG)
        self.config["index"]["enabled"] = False

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_note(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.strip() + "\n", encoding="utf-8")
        return path

    def write_policy(self, denied: str) -> kb.Policy:
        (self.root / kb.DEFAULT_POLICY_FILENAME).write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "deny_paths": [
                        {
                            "path": denied,
                            "deny": [
                                "read",
                                "index",
                                "classify",
                                "link",
                                "write",
                                "verify",
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return kb.load_policy(self.root)

    def test_policy_prunes_protected_tree_before_note_loading(self) -> None:
        protected = self.root / "01-Projects" / "private-area"
        protected.mkdir()
        self.write_note("01-Projects/private-area/secret.md", "# protected")
        self.write_note("02-Areas/allowed.md", "# allowed")
        policy = self.write_policy("01-Projects/private-area")

        paths = kb.collect_all_paths(self.root, self.config, policy)

        self.assertIn(self.root / "02-Areas/allowed.md", paths)
        self.assertNotIn(protected / "secret.md", paths)
        self.assertFalse(any(protected == path or protected in path.parents for path in paths))

    def test_global_policy_denies_protected_vault_and_parent_scope(self) -> None:
        policy_path = self.root / "global-policy.json"
        protected = self.root.parent / "Gsup_data"
        legacy = self.root / "01-Projects" / "GF_supply_chain"
        policy_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "protected_roots": [
                        {"path": str(protected), "owner": "Gsup_adqe"},
                        {
                            "path": str(legacy),
                            "owner": "Gsup_adqe",
                            "deny_ancestor_scopes": False,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {kb.GLOBAL_ACCESS_POLICY_ENV: str(policy_path)},
        ):
            policy = kb.load_global_access_policy()

        with self.assertRaisesRegex(SystemExit, "Global vault access policy denied"):
            kb.ensure_scope_allowed(protected, policy, "test")
        with self.assertRaisesRegex(SystemExit, "Global vault access policy denied"):
            kb.ensure_scope_allowed(protected.parent, policy, "test")
        with self.assertRaisesRegex(SystemExit, "Global vault access policy denied"):
            kb.ensure_scope_allowed(legacy, policy, "test")
        with self.assertRaisesRegex(SystemExit, "Global vault access policy denied"):
            kb.ensure_scope_allowed(legacy / "child", policy, "test")
        kb.ensure_scope_allowed(self.root, policy, "test")

        legacy.mkdir(parents=True)
        alias = self.root / "legacy-alias"
        alias.symlink_to(legacy, target_is_directory=True)
        with self.assertRaisesRegex(SystemExit, "Global vault access policy denied"):
            kb.ensure_scope_allowed(alias, policy, "test")

        merged = kb.merge_global_protections(
            self.root,
            kb.load_policy(self.root),
            policy,
        )
        self.assertTrue(kb.is_protected(legacy / "secret.md", merged))

    def test_policy_blocks_symlink_into_protected_tree(self) -> None:
        protected = self.root / "01-Projects" / "private-area"
        protected.mkdir()
        secret = self.write_note(
            "01-Projects/private-area/secret.md", "# protected"
        )
        (self.root / "02-Areas" / "indirect.md").symlink_to(secret)
        policy = self.write_policy("01-Projects/private-area")

        paths = kb.collect_all_paths(self.root, self.config, policy)

        self.assertNotIn(self.root / "02-Areas/indirect.md", paths)

    def test_root_config_is_discovered_automatically(self) -> None:
        config_path = self.root / kb.DEFAULT_CONFIG_FILENAME
        config_path.write_text('{"maintenance":{"full_review_days":7}}', encoding="utf-8")

        resolved = kb.resolve_config_file(self.root, None)
        config = kb.load_config(resolved)

        self.assertEqual(resolved, config_path)
        self.assertEqual(config["maintenance"]["full_review_days"], 7)

    def test_plan_with_protected_item_is_rejected(self) -> None:
        protected = self.root / "01-Projects" / "private-area"
        protected.mkdir()
        self.write_note("01-Projects/private-area/secret.md", "# protected")
        policy = self.write_policy("01-Projects/private-area")
        plan_path = self.root / ".knowledge-organizer-plan.json"
        plan_path.write_text(
            json.dumps(
                {
                    "version": kb.VERSION,
                    "root": str(self.root),
                    "policy_digest": policy.digest,
                    "items": [{"path": "01-Projects/private-area/secret.md"}],
                    "known_hubs": {},
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(SystemExit):
            kb.read_plan(self.root, plan_path, policy)

    def test_auto_mode_uses_baseline_then_growth_trigger(self) -> None:
        policy = kb.load_policy(self.root)
        detection = kb.detect_profile(self.root, self.config, None, policy)
        first = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "auto"
        )
        self.assertEqual(first.mode, "bootstrap")

        kb.write_json_atomic(
            kb.state_path(self.root, self.config),
            {
                "version": kb.VERSION,
                "last_verified_at": dt.datetime.now(
                    dt.timezone.utc
                ).isoformat(),
                "last_mode": "incremental",
            },
        )
        before_full_baseline = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "auto"
        )
        self.assertEqual(before_full_baseline.mode, "bootstrap")

        state = {
            "version": kb.VERSION,
            "last_full_verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            **first.snapshot,
        }
        kb.write_json_atomic(kb.state_path(self.root, self.config), state)
        second = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "auto"
        )
        self.assertEqual(second.mode, "incremental")

        for index in range(5):
            self.write_note(
                f"00-Inbox/new-{index}.md",
                f"---\ntags: [topic-{index}]\n---\n# New {index}",
            )
        third = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "auto"
        )
        self.assertEqual(third.mode, "full-review")
        self.assertTrue(any("pending Inbox" in value for value in third.triggers))

    def test_link_audit_resolves_existing_attachment(self) -> None:
        note = self.write_note(
            "00-Inbox/example.md",
            """
# Example
![[06-Attachments/images/example.png]]
[[Missing Note]]
""",
        )
        asset = self.root / "06-Attachments" / "images" / "example.png"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"png")
        policy = kb.load_policy(self.root)
        report = kb.link_issues(
            self.root,
            [kb.parse_note(self.root, note)],
            [asset],
            policy,
        )

        self.assertEqual(report["attachments"]["broken"], [])
        self.assertEqual(len(report["note_links"]["broken"]), 1)
        self.assertEqual(report["note_links"]["broken"][0]["target"], "Missing Note")

    def test_rule_can_require_specific_tag_combination(self) -> None:
        hub = kb.discover_hubs(
            [kb.parse_note(self.root, self.root / "00-Maps/材料 MOC.md")],
            self.config,
        )
        rule = kb.compile_rules(
            [
                {
                    "id": "semiconductor-yield",
                    "tags_all": ["半导体制造", "良率"],
                    "hubs": ["材料 MOC"],
                }
            ]
        )
        generic = self.write_note(
            "00-Inbox/mim.md",
            "---\ntags: [良率, 金属注射成形]\n---\n# MIM",
        )
        specific = self.write_note(
            "00-Inbox/wat.md",
            "---\ntags: [良率, 半导体制造]\n---\n# WAT",
        )

        self.assertEqual(
            kb.infer_hubs(kb.parse_note(self.root, generic), hub, self.config, rule),
            [],
        )
        self.assertEqual(
            kb.infer_hubs(
                kb.parse_note(self.root, specific), hub, self.config, rule
            )[0]["score"],
            100,
        )

    def test_incremental_explicit_path_reprocesses_v2_note_outside_inbox(self) -> None:
        path = self.write_note(
            "02-Areas/legacy.md",
            "---\ntags: [材料]\n---\n# Legacy",
        )
        note = kb.parse_note(self.root, path)
        current_hash = kb.organization_hash(note, self.config["fields"])
        self.write_note(
            "02-Areas/legacy.md",
            (
                "---\n"
                "tags: [材料]\n"
                "organization_status: unclassified\n"
                "organization_version: 2\n"
                f"organization_hash: {current_hash}\n"
                "---\n"
                "# Legacy"
            ),
        )
        policy = kb.load_policy(self.root)
        detection = kb.detect_profile(self.root, self.config, None, policy)
        maintenance = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "incremental"
        )

        plan = kb.build_plan(
            self.root,
            self.config,
            detection,
            maintenance,
            policy,
            ["02-Areas/legacy.md"],
        )

        self.assertEqual(plan["summary"]["scanned"], 1)
        self.assertEqual(plan["summary"]["linked"], 1)
        self.assertEqual(plan["items"][0]["path"], "02-Areas/legacy.md")
        self.assertEqual(plan["items"][0]["hubs"], ["[[材料 MOC]]"])

    def test_full_review_proposes_new_moc_cluster(self) -> None:
        for index in range(3):
            self.write_note(
                f"02-Areas/polymer-{index}.md",
                f"---\ntags: [高分子改性]\n---\n# Polymer {index}",
            )
        policy = kb.load_policy(self.root)
        notes = kb.load_notes(self.root, self.config, policy)
        hubs = kb.discover_hubs(
            [
                note
                for note in notes
                if note.relative.as_posix().startswith("00-Maps/")
            ],
            self.config,
        )

        report = kb.build_taxonomy_report(
            self.root, notes, hubs, self.config, policy
        )

        self.assertEqual(report["create_candidates"][0]["name"], "高分子改性 MOC")
        self.assertEqual(len(report["create_candidates"][0]["seed_notes"]), 3)
        self.assertTrue(report["requires_review"])

    def test_index_preserves_body_keyword_matching(self) -> None:
        note_path = self.write_note(
            "00-Inbox/body-match.md",
            "# Body match\nThis note contains a phase-change interface.",
        )
        self.config["index"] = {
            "enabled": True,
            "path": ".test-cache/index.json",
        }
        policy = kb.load_policy(self.root)
        rules = kb.compile_rules(
            [
                {
                    "id": "body-keyword",
                    "body_any": ["phase-change interface"],
                    "hubs": ["材料 MOC"],
                }
            ]
        )
        hub_notes = [
            kb.parse_note(self.root, self.root / "00-Maps/材料 MOC.md")
        ]
        hubs = kb.discover_hubs(hub_notes, self.config)

        first, first_hits, _ = kb.load_plan_notes(
            self.root, [note_path], self.config, policy
        )
        second, second_hits, _ = kb.load_plan_notes(
            self.root, [note_path], self.config, policy
        )

        self.assertEqual(first_hits, 0)
        self.assertEqual(second_hits, 1)
        self.assertEqual(
            kb.infer_hubs(first[0], hubs, self.config, rules)[0]["hub"],
            kb.infer_hubs(second[0], hubs, self.config, rules)[0]["hub"],
        )

    def test_taxonomy_review_is_required_before_full_baseline(self) -> None:
        for index in range(3):
            self.write_note(
                f"02-Areas/ceramic-{index}.md",
                f"---\ntags: [先进陶瓷]\n---\n# Ceramic {index}",
            )
        policy = kb.load_policy(self.root)
        detection = kb.detect_profile(self.root, self.config, None, policy)
        maintenance = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "full-review"
        )
        plan = kb.build_plan(
            self.root,
            self.config,
            detection,
            maintenance,
            policy,
            None,
        )
        plan_path = self.root / kb.DEFAULT_PLAN
        kb.write_json_atomic(plan_path, plan)

        self.assertTrue(plan["taxonomy"]["requires_review"])
        self.assertEqual(kb.apply_plan(self.root, plan_path, policy), 0)
        self.assertEqual(kb.verify_plan(self.root, plan_path, policy, False), 6)
        self.assertFalse(kb.state_path(self.root, self.config).exists())
        self.assertEqual(
            kb.verify_plan(
                self.root,
                plan_path,
                policy,
                False,
                taxonomy_reviewed=True,
            ),
            0,
        )
        self.assertTrue(kb.state_path(self.root, self.config).is_file())

    def test_full_plan_apply_verify_records_baseline(self) -> None:
        self.write_note(
            "00-Inbox/material.md",
            "---\ntags: [材料]\n---\n# Material",
        )
        policy = kb.load_policy(self.root)
        detection = kb.detect_profile(self.root, self.config, None, policy)
        maintenance = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "bootstrap"
        )
        plan = kb.build_plan(
            self.root,
            self.config,
            detection,
            maintenance,
            policy,
            None,
        )
        plan_path = self.root / kb.DEFAULT_PLAN
        kb.write_json_atomic(plan_path, plan)

        self.assertEqual(kb.apply_plan(self.root, plan_path, policy), 0)
        self.assertEqual(kb.verify_plan(self.root, plan_path, policy, False), 0)
        note = kb.parse_note(self.root, self.root / "00-Inbox/material.md")
        self.assertIn("[[材料 MOC]]", kb.normalize_links(note.frontmatter["moc"]))
        state = json.loads(
            kb.state_path(self.root, self.config).read_text(encoding="utf-8")
        )
        self.assertEqual(state["last_mode"], "bootstrap")
        self.assertIn("last_full_verified_at", state)

    def test_organization_hash_ignores_body_edits(self) -> None:
        path = self.write_note(
            "00-Inbox/hash.md",
            "---\ntags: [材料]\n---\n# Hash\nOriginal body.",
        )
        fields = self.config["fields"]
        before = kb.organization_hash(kb.parse_note(self.root, path), fields)
        self.write_note(
            "00-Inbox/hash.md",
            "---\ntags: [材料]\n---\n# Hash\nEdited body only.",
        )
        after = kb.organization_hash(kb.parse_note(self.root, path), fields)
        self.assertEqual(before, after)
        self.write_note(
            "00-Inbox/hash.md",
            "---\ntags: [材料, 改性]\n---\n# Hash\nEdited body only.",
        )
        changed = kb.organization_hash(kb.parse_note(self.root, path), fields)
        self.assertNotEqual(before, changed)

    def test_inline_body_tag_matches_hub(self) -> None:
        self.write_note("00-Inbox/inline.md", "# Inline\n讨论 #材料 的工艺。")
        hub_notes = [kb.parse_note(self.root, self.root / "00-Maps/材料 MOC.md")]
        hubs = kb.discover_hubs(hub_notes, self.config)
        candidates = kb.infer_hubs(
            kb.parse_note(self.root, self.root / "00-Inbox/inline.md"),
            hubs,
            self.config,
            [],
        )
        self.assertEqual(candidates[0]["hub"], "材料 MOC")
        self.assertEqual(candidates[0]["score"], 70)
        self.assertEqual(candidates[0]["reasons"], ["exact tag: 材料"])

    def test_markdown_backlink_counts_as_moc_evidence(self) -> None:
        self.write_note(
            "00-Maps/材料 MOC.md",
            "---\ntype: moc\ntags:\n  - 材料\n---\n[Legacy](02-Areas/legacy.md)",
        )
        self.write_note("02-Areas/legacy.md", "# Legacy")
        hubs = kb.discover_hubs(
            [kb.parse_note(self.root, self.root / "00-Maps/材料 MOC.md")],
            self.config,
        )
        candidates = kb.infer_hubs(
            kb.parse_note(self.root, self.root / "02-Areas/legacy.md"),
            hubs,
            self.config,
            [],
        )
        self.assertEqual(candidates[0]["score"], 95)
        self.assertEqual(candidates[0]["reasons"], ["already linked from MOC"])

    def test_review_item_persists_candidate_hubs(self) -> None:
        self.config["taxonomy"]["enabled"] = False
        self.write_note("00-Inbox/材料学基础.md", "# 材料学基础\n综述笔记。")
        policy = kb.load_policy(self.root)
        detection = kb.detect_profile(self.root, self.config, None, policy)
        maintenance = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "bootstrap"
        )
        plan = kb.build_plan(
            self.root, self.config, detection, maintenance, policy, None
        )
        item = plan["items"][0]
        self.assertEqual(item["action"], "review")
        self.assertEqual(item["candidate_hubs"], ["[[材料 MOC]]"])
        plan_path = self.root / kb.DEFAULT_PLAN
        kb.write_json_atomic(plan_path, plan)
        self.assertEqual(kb.apply_plan(self.root, plan_path, policy), 0)
        note = kb.parse_note(self.root, self.root / "00-Inbox/材料学基础.md")
        self.assertEqual(
            kb.normalize_links(note.frontmatter["organization_candidates"]),
            ["[[材料 MOC]]"],
        )
        self.assertEqual(kb.verify_plan(self.root, plan_path, policy, False), 0)

    def test_apply_creates_backup_and_diff_reads_plan(self) -> None:
        self.config["taxonomy"]["enabled"] = False
        self.write_note("00-Inbox/material.md", "---\ntags: [材料]\n---\n# Material")
        policy = kb.load_policy(self.root)
        detection = kb.detect_profile(self.root, self.config, None, policy)
        maintenance = kb.select_maintenance_mode(
            self.root, self.config, detection, policy, "bootstrap"
        )
        plan = kb.build_plan(
            self.root, self.config, detection, maintenance, policy, None
        )
        plan_path = self.root / kb.DEFAULT_PLAN
        kb.write_json_atomic(plan_path, plan)
        original = (self.root / "00-Inbox/material.md").read_text(encoding="utf-8")

        self.assertEqual(kb.apply_plan(self.root, plan_path, policy), 0)

        backups = sorted((self.root / kb.BACKUP_DIR_NAME).iterdir())
        self.assertEqual(len(backups), 1)
        backup_copy = backups[0] / "00-Inbox" / "material.md"
        self.assertEqual(backup_copy.read_text(encoding="utf-8"), original)
        self.assertNotIn(
            backup_copy, kb.collect_all_paths(self.root, self.config, policy)
        )
        self.assertEqual(kb.verify_plan(self.root, plan_path, policy, False), 0)
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            self.assertEqual(kb.diff_plan(self.root, plan_path, policy, 30), 0)
        printed = stdout.getvalue()
        self.assertIn("00-Inbox/material.md", printed)
        self.assertIn("[[材料 MOC]]", printed)


if __name__ == "__main__":
    unittest.main()
