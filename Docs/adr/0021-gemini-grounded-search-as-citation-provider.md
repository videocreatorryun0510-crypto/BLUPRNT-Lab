# ADR 0021: Gemini Grounded SearchをCitation Providerへ限定する

- Status: Accepted
- Date: 2026-08-11
- Phase: 5.26 Gemini Grounded Evidence Search Provider MVP

## Context

Phase 5.25でEvidence Bundleだけを後段へ渡す境界を固定した。最初の実検索としてGemini Google Search Groundingを接続する際、Gemini回答本文をEvidenceとみなすと、外部原典とAI生成文の境界が消え、根拠追跡と医学レビューが成立しない。またGemini固有応答をWorkbenchへ渡すと、Provider交換が後段変更になる。

## Decision

1. `GeminiGroundedSearchProvider`は既存Search Provider Interfaceを実装し、Gemini固有の認証、Interactions API、Google Search Tool、Response解析を内部へ閉じ込める。
2. 1用語から最大4 Intentを作り、1 Requestへまとめる。
3. `model_output`の本文を破棄し、`url_citation`だけをRaw Evidenceへ変換する。
4. Domain分類、Evidence Level、Information PriorityはEvidence Intelligence側の明示Policyで決め、Geminiの判断を使用しない。
5. WorkbenchはEvidence Bundleだけを表示し、明示ボタン操作なしに外部検索しない。
6. `store=false`を必須とし、Secret、回答本文、HTTP Header、医学本文をAuditへ保存しない。
7. Retryは一時障害だけ最大1回、QueryとCitation件数に上限を設ける。
8. Knowledge Contract、Draft、Promotion、Registry、Approval、Publisherを変更しない。

## Not selected

- Gemini回答本文をEvidenceにする案：外部原典ではなく、医学的Claimの追跡性を保証できない。
- Gemini固有JSONをWorkbenchへ表示する案：Provider交換時に画面と後段が壊れる。
- GeminiにEvidence Levelを決めさせる案：判定根拠が不透明で、未知Domainを過大評価し得る。
- Citation先を無条件に全面取得する案：利用規約、robots.txt、著作権、保存範囲の確認が未整備。
- 入力・保存時の自動検索：Product Ownerの明示操作と費用管理を迂回する。
- 失敗するまで無制限にRetryする案：費用と外部負荷を制御できない。

## Consequences

実Web検索からProvider非依存Evidence Bundleを作れる。一方、Citation Metadataだけでは医学Claimの根拠箇所確認に不足するため、Claim自動生成はまだ許可しない。GoogleのRedirect URL、Domain Policyの版管理、Source本文取得Policy、検索結果の再現性と失効監視は将来の課題である。

## Compatibility

既存Search Interface、Evidence Contract、Bundle、Knowledge、Promotion、Registry、Approvalは不変である。既存DeduplicatorのInterfaceを変えず、同名別版を誤統合しない内部安全判定だけを追加した。
