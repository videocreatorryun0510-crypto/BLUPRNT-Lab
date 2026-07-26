# Prototype Phase 1 — AI → Knowledge JSON

## 目的

正式版の承認基盤を作る前に、検査項目から国家試験向けKnowledge JSONを生成し、Version 1.0の構造と情報の揃い具合を評価します。

## 実装した範囲

- Knowledge Workbenchの入力・確認画面
- OpenAI Responses APIによる構造化出力
- Knowledge JSON Version 1.0（検査項目MVP）
- 検査項目専用テンプレート`test_item_v1.0`
- OpenAI出力をVersion 0.3で受け取り、Version 1.0へ変換するMapper
- 検査項目と国家試験科目を分離した分類
- JSON Schema Draft 2020-12による検証
- Knowledge CompletenessとExam Completeness、改善候補
- 独立したExam Metadata Version 1.0
- AST、HbA1c用の手作業ダミー出題履歴、重要claim、出題パターン
- AI会社を交換できるProvider境界
- AST、HbA1cのVersion 1.0固定動作確認
- 設定、入力、AI接続、Schemaエラーの表示
- 交換可能なExamMetadataProvider（Dummy、CSV、将来Database）
- 列名Mapping → Normalized Exam Record → Knowledge/claim MappingのCSV Pipeline
- CSV列・行・画像のImport Validationと前回Importとの差分
- CSV履歴からの設定可能なimportance_score再計算
- `ExamImages/`に置いた画像とExam Metadataの自動関連付け
- Knowledge・Claimの安定ID、意味キー、版、状態、承認情報を管理するKnowledge Registry
- Claim Dictionaryと変更履歴のSQLite永続保存
- AI生成順に依存せず、既存`claim_key`と`claim_id`を再利用する照合処理

## データの位置付け

Prototype Phase 1のVersion 1.0 JSONでは、`evidence`とPublisher優先指定を空にします。国家試験情報はKnowledge JSONと別のExam Metadataへ保存し、`knowledge_id`と`claim_id`で関連付けます。

AIは医学的事実だけを生成します。`knowledge_id`、`claim_id`、`claim_key`、出典、Exam Metadata、Publisher指定はWorkbench側が管理します。`claim_key`は医学的な意味を固定する名前、`claim_id`は内部IDです。現在のExam Metadataは動作確認用ダミーで、実際の出題実績ではありません。

Phase 2.6のサンプルCSVと画像も、Pipelineの動作だけを確認するダミーです。Workbench上のCSV ImportはOpenAIを呼びません。CSV由来の情報はまず共通形式へ変換し、その後にKnowledge JSONの`knowledge_id`と`claim_id`へ関連付けます。画像本体はKnowledge JSONにもExam Metadataにも保存せず、ファイル参照だけを保持します。

## Version 1.0 MVPのカテゴリ境界

検査項目だけが、検査目的、検体、測定方法、測定原理、基準範囲、高値・低値、他検査との組み合わせ、解釈上の注意を持ちます。高値・低値は病態と代表疾患を分けます。

疾患・微生物・寄生虫・染色法などのVersion 0.3データとテストは互換性確認のため残しますが、Version 1.0 MVPへは変換しません。今回の画面とAPIは検査項目だけを受け付けます。

## 正式版へ引き継げる部分

- `Packages/knowledge-contracts/` の版付きJSON契約
- JSON Schema検証
- AIに依存しない生成手順
- OpenAIを隔離したProvider Adapter
- 版付きプロンプト
- Version 0.3の5テーマを壊していないことを確認する回帰テスト
- AST、HbA1cのVersion 1.0変換・Schema・完全性評価テスト
- Exam MetadataのSchema、Knowledge JSONとの参照、Exam Completenessのテスト

## Phase 2.7で正式基盤へ近づいた部分

- Registryは`KnowledgeRegistry`という共通の接続口を通すため、SQLiteから将来のデータベースへ交換できる
- 既存ClaimはAIが並び替わっても同じ`claim_key`と`claim_id`を再利用する
- `draft`、`owner_review`、`medical_review`、`approved`、`deprecated`を管理できる
- 表現修正ではClaim Versionを変えず、医学的意味の変更だけ版を上げる
- 追加、更新、削除、deprecated、状態変更の履歴を再起動後も保持する

## プロトタイプ専用の部分

- ローカルで動く単一利用者向け画面
- Knowledge JSONとExam Metadataの正式スナップショット保存は未実装（Registry台帳は永続保存する）
- 固定テスト用Provider
- ログインと利用者別権限がない状態（承認状態・承認記録の土台は実装済み）

これらをそのまま本番運用へ移しません。

## Phase 1の完了条件

- ASTとHbA1cでVersion 1.0 Schemaに適合するJSONを生成できる
- Schemaとは別にKnowledge・Examの完全性スコアと改善候補を計算できる
- 重要claimとダミー出題履歴を画面で確認できる
- JSONとclaim ID付き医学的事実を画面で確認できる
- エラーが画面に表示される
- AI接続がアプリケーションの業務処理から分離されている
- プロダクトオーナーが情報量と項目構造を評価できる

Schema Validationは「JSONの形と参照が正しいか」、Knowledge Completenessは「医学知識がどの程度揃っているか」、Exam Completenessは「国家試験情報がどの程度揃っているか」を確認します。完全性スコアは正確性や承認を意味しません。

OpenAI実接続の最終確認には、利用者自身の `OPENAI_API_KEY` が必要です。キーなしでも固定テストによる画面・Schema・自動テストは実行できます。
