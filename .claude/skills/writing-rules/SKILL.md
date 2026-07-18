---
# .claude/rules/*.md ルールファイルの新規作成・修正・(新規/未文書化プロジェクトの)一括初期化をコンテキストに埋め込むためのスキル。
# 元々は writing-rules(作成・修正)と init-rules(全体初期化)の2スキルだったが1つに統合。
# 詳細手順・具体例・サブエージェント委譲戦略は同ディレクトリの init.md / writing.md に分離してあるので、
# 本文の分岐に従って状況に応じて読み込むこと。
name: writing-rules
description: Use when creating new .claude/rules/*.md rule files, editing/updating existing ones, or bootstrapping rules from scratch for a new or largely undocumented codebase via full-project analysis (with sub-agent delegation for large repos). Also use when migrating content out of a folder/CLAUDE.md or the root CLAUDE.md into a proper rule file.
---

# Writing `.claude/rules/*.md` Files

All persisted knowledge in this codebase is stored as **rule files** under `.claude/rules/` — never as `folder/CLAUDE.md` files, and never appended to the project-root `CLAUDE.md`. A rule file is a single Markdown file with YAML frontmatter listing the source paths it applies to; its body is the documentation loaded into context whenever those paths are touched.

## Which file to read next

- **`.claude/rules/` doesn't exist yet (or only has a couple of ad-hoc notes), or the user explicitly asked to initialize/bootstrap/regenerate rules for this project** → read **`init.md`** (same directory). It covers full-codebase discovery priorities, sub-agent delegation for large repos, and merge-with-existing-file handling. This is a costly, usually one-time operation — if the user didn't explicitly ask for a full init pass, confirm before running it.
- **Anything else — creating one new rule file, or editing/updating an existing one** (the common case: you just discovered cross-cutting knowledge worth persisting, or a rule went stale) → read **`writing.md`** (same directory). It covers the file format/frontmatter spec, when to add a rule, granularity, and style guide.

Both paths share the same file format and granularity rules, defined once in `writing.md`; `init.md` defers to it and only adds discovery/delegation strategy on top.
