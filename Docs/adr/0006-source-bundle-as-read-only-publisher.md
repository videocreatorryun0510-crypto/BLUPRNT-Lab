# ADR 0006: Source Bundleを読取専用Publisherとして分離する

- 状態: 採用
- 日付: 2026-07-26
- 対象: Phase 5.13 Source Bundle Publisher MVP

## 背景

BLUPRNT Labは医学知識の正本をKnowledge JSON・Registry・Exam Metadataとして保持し、
GeminiなどのPresentation Engineへ、媒体非依存の入力を渡す必要がある。Knowledgeへ
図解指示や対象者、教材向け文章を保存すると、医学的事実と表示・教育方針が再び混ざる。
既存Publisher CoreをGemini専用へ変更すると、Publication PlanやPDF Adapterの既存契約へ
不要な影響が及ぶ。

## 決定

`SourceBundlePublisher`を既存Publisher Coreとは別の、読取専用Publisher Adapterとして
追加する。

- 入力はKnowledge JSON、Registry、任意のExam Metadataとする
- 出力はSource Bundle JSON Version 1.0だけとする
- Knowledge別の教育目的、重要Claim、図解要求は版付きProfileで管理する
- Claim本文は作り直さず、Registryの有効Claimをそのまま複写する
- `key_messages`と`exam_points`も既存Claimへの選択・投影とする
- `diagram_requests`はPublisher側で作り、Knowledgeへ保存しない
- JSONは一時ファイルから置換する方法で安全に保存する
- Source BundleにはKnowledgeのVersion、Category、承認状態、生成日時、入力Fingerprintを
  記録する
- MVPではWorkbenchレビュー用に`draft`も生成できる。外部AI送信と公開の承認Gateは、
  [ADR 0007](0007-provider-neutral-approval-gate.md)でProvider接続より先に実装した

## 採用しなかった案

### Knowledge JSONへSource Bundle項目を追加する

教育目的・図解要求・対象媒体が医学的事実の正本へ混入するため採用しない。

### 既存Publication PlanをGemini入力として流用する

Publication Planはレイアウト・Profile・Semantic Blueprintの既存契約を持ち、今回の
最小Source Bundleより責務が広い。Gemini入力の変更がPDF系の契約へ波及するため採用しない。

### Gemini固有Promptを保存する

AI提供者の変更で契約全体が揺れるため採用しない。Source Bundleは提供者非依存のJSONとし、
Gemini固有の変換は将来のPresentation Engine Adapterへ閉じ込める。

## 影響

- Knowledge JSON、Registry、Exam Metadata、Publisher Coreは変更しない
- 同じSource BundleをGemini以外のPresentation Engineにも渡せる
- Profileが存在するKnowledgeだけを明示的に生成するため、意図しない自動対応を防げる
- Profile数が増えるため、将来はProfile承認、互換性検証、Catalog管理が必要になる
- Source Bundleは派生物なので、正本変更後は再生成する
