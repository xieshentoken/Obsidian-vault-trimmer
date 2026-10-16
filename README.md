# Obsidian-vault-trimmer
An AI agent skill for classify obsidian vault
## 核心能力：
- 不依赖 PARA 或固定目录名称。
- 自动发现任意位置的 MOC、Hub、Index、Map。
- 审计 frontmatter、标签、孤岛、断链和链接密度。
- 根据标签、关键词、配置规则自动关联 Hub。
- 可选生成概念链接，并排除宽泛标签造成的弱关联。
- 默认 dry-run，不移动、重命名或删除文件。
- 支持配置自定义字段、语言、Hub 名称和匹配规则。
- 纯 Python 标准库，兼容 Python 3.9+。
SKILL.md 为平台中立入口；agents/openai.yaml 供 Codex 使用，OpenClaw 可忽略。
## 常用命令：
‘’‘
python3 scripts/kb_organizer.py audit --root /path/to/notes
python3 scripts/kb_organizer.py init-config --root /path/to/notes
python3 scripts/kb_organizer.py organize --root /path/to/notes
python3 scripts/kb_organizer.py organize --root /path/to/notes --apply
‘’‘

## V4 改进（organize-markdown-knowledge-base）
- `organization_hash` 只覆盖标题与 tags/aliases/topics frontmatter，正文修改不再触发重新分类。
- 正文内联 `#标签` 计入匹配；MOC 回链同时识别 `[[wiki]]` 与 `[text](note.md)` 链接。
- `apply` 写盘前自动备份到 `.knowledge-organizer-backup/<UTC时间戳>/`（`--no-backup` 可关闭），备份目录不参与扫描。
- 新增 `diff` 子命令，输出人话版计划摘要（哪篇笔记 → 哪个 MOC、证据与分数）。
- `review`/`unclassified` 笔记把候选 Hub 持久化到 `organization_candidates` 字段，语义复查不再依赖 plan 文件。
- 附带 18 个单元测试（`python3 -m unittest discover -s organize-markdown-knowledge-base/tests`）。
# Obsidian-search
查找总结obsidian笔记中的相关信息
