# Presentation Artifact Registry & Approval MVP

## 1. 目的

Presentation Artifact Registry Version 1.0は、教材構成であるPresentation Artifactを、Knowledgeとは独立して長期管理する台帳です。Artifactの安定ID、版、承認、履歴、差分、構造的CompletenessをSQLiteへ保存します。

RendererはBuilderの一時JSONを直接読みません。必ずArtifact Registryから`active`かつ`approved`の版を取得します。

```text
Knowledge Registry
       ↓ 読取
Presentation Artifact Builder
       ↓ draft登録
Presentation Artifact Registry
       ↓ owner_review → education_review → approved
Artifact Renderer Gateway
       ↓
Renderer（将来）
```

## 2. Registry Contract

Artifact Seriesは`knowledge_id + profile_id`ごとに1つ作り、同じ用途の改訂では`artifact_id`を維持したまま`artifact_version`を増やします。

| 項目 | 役割 |
|---|---|
| `artifact_id` | 教材Seriesの永続ID |
| `artifact_version` | 教材構成の改訂版。1から連番 |
| `source_bundle_id` / `presentation_request_id` | 生成元の追跡 |
| `knowledge_id` / `knowledge_version` | 利用したKnowledge版 |
| `profile_id` / `profile_version` | 教育・媒体条件の版 |
| `fingerprint` | Artifact内容の改変検出 |
| `approval_state` | Artifact独自の承認状態 |
| `owner` / `review_comment` | 管理責任と判断記録 |
| `status` | Seriesの有効・廃止 |
| `created_at` / `updated_at` | 版の作成・更新日時 |

Knowledgeが`approved`でも、そこから作ったArtifactは必ず`draft`から始まります。Knowledge承認と教育構成承認は別の判断だからです。

## 3. Approval Flow

```text
draft → owner_review → education_review → approved → published（将来）
```

- 前方は1段階ずつ進める
- 差し戻しは前の任意段階へ戻せる
- すべての操作へ日時、操作者、Review Comment、Fingerprintを残す
- `published`は状態だけ予約し、Version 1.0のRenderer取得対象にはしない

`approved`へ到達した版はImmutableです。ページ本文、Claim対応、Reference対応、生成元、Profile、Fingerprintを変更できません。修正時は新Versionを登録します。

## 4. HistoryとDiff

HistoryはVersion作成と承認遷移を追記方式で保存します。WorkbenchのDiffは次を構造化して比較します。

- Headline変更
- Page追加・削除
- Claim追加・削除
- Reference追加・削除
- Diagram Instruction変更
- Layout Hint変更

## 5. Artifact Completeness

次の8区分を各12.5点、合計100点で評価します。

1. Page
2. Headline
3. Learning Goal
4. Claim
5. Diagram
6. Reference
7. Layout
8. Metadata / Fingerprint

これは「必要な構造が揃っているか」の評価です。100%でも、医学的正確性や教育品質を保証しません。最終判断は人のレビューで行います。

## 6. Validation

- Artifact Versionの重複・欠番を検出
- Fingerprint重複・不一致を検出
- approved / published版のImmutable状態を確認
- Version作成履歴と承認遷移履歴の欠落・不整合を検出
- Artifactが未来のKnowledge Versionを参照していないことを確認
- Renderer取得時に`active + approved + Fingerprint一致`を再確認

## 7. Workbench

「Artifact Registry」画面で次を確認できます。

- Artifact一覧と最新版
- Version一覧と版ごとの承認状態
- 承認・差し戻しとReview Comment
- History
- Version Diff
- Completeness
- Fingerprint
- Registry保存済みArtifact JSON
- Renderer利用可否

## 8. Product Owner確認項目

- 同じ教材の改訂でArtifact IDが変わらずVersionだけ増えるか
- Knowledge承認とArtifact承認が独立しているか
- 差し戻し理由がHistoryへ残るか
- approved版の本文を直接変更できないか
- 新しいdraftがあっても、Rendererが直近のapproved版だけを取得するか
- Diffが教材改訂の判断に十分か
- Completenessを教育品質スコアと誤解しない表示になっているか

## 9. 対象外

Phase 5.20ではRenderer実装、Artifact Backup / Restore、権限管理、電子署名、複数人同時編集、公開処理を実装しません。
