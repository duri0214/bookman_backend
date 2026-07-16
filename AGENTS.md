# Codex Project Instructions

このリポジトリで作業するときは、同じ親フォルダにある `portfolio/.codex` を Codex 運用ルールの管理元として参照する。

## 前提

- `portfolio` と `bookman_backend` は同じ親フォルダに配置する。
- 例:
  - `C:\Users\yoshi\OneDrive\dev\portfolio`
  - `C:\Users\yoshi\OneDrive\dev\bookman_backend`

## Rules

- `.codex/rules/` 配下の各 Markdown は参照スタブであり、実体は `../portfolio/.codex/rules/` にある。
- 着手前に `../portfolio/.codex/rules/` のうち、作業内容に関係するルールを確認する。
- Python・Django・テストに関係する変更では、対応する rule を読んでから作業する。
- `main` へ直接コミットせず、Issue に対応するトピックブランチで作業する。

## Skills

- `.codex/skills/` 配下の各 `SKILL.md` は参照スタブであり、実体は `../portfolio/.codex/skills/` にある。
- ブランチ作成、コミット、PR、Issue 作成などの運用手順は `../portfolio/.codex/skills/` を参照する。
- ユーザー依頼が skill の `description` に該当する場合は、該当 `SKILL.md` を読んでから作業する。
