# ADR 0007: Approval GateをPresentation Engineから分離する

- 状態: 採用
- 日付: 2026-07-27
- 対象: Phase 5.14 Approval Gate MVP

## 背景

Source Bundleはレビュー用に`draft`でも生成する必要がある。一方、未承認Knowledgeを外部AIへ
送信してはならない。Gemini Adapter内だけで判定すると、将来のClaude、GPT、PDF、動画ごとに
同じ安全ルールが重複し、実装漏れが起きる。

## 決定

Approval ContractとGate判定をProvider非依存の共通契約として実装する。

- 承認順を`draft → owner_review → medical_review → approved → published`へ固定する
- 既存`deprecated`はRegistry互換の廃止状態として維持する
- 隣接段階への差し戻しを許可し、Registry履歴を必須とする
- Source Bundle生成は承認状態に関係なく許可する
- 公開と外部AI送信は`approved`だけを許可する
- Gate判定をPublisher監査ログへ保存する
- Knowledge JSONへ承認情報を追加しない

## 採用しなかった案

### Source Bundle生成自体を未承認時に禁止する

人が内容を確認するための派生物まで作れず、レビュー作業を妨げるため採用しない。

### Gemini Adapterだけで承認判定する

Provider追加のたびに安全ルールが重複し、判定漏れを防げないため採用しない。

### Workbenchのボタンを非表示にするだけ

APIや将来のバッチ処理から回避できるため採用しない。判定はPublisherのContractで行う。

## 影響

- Source Bundle metadataへApproval Snapshotを後方互換な追加項目として含める
- 既存Publisher Core、Knowledge JSON、Registry保存形式は維持する
- 将来の外部AI Adapterは`can_send_to_external_ai()`成功を送信前条件とする
- 権限管理と電子署名は別Phaseで追加する
