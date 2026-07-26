# ADR 0004: Claim Mappingを決定的にし、Semantic BlueprintをRenderから分離する

- 状態: Accepted
- 日付: 2026-07-18
- 対象: Phase 3.5

## 背景

Diagram Intentは必要Conceptを示しますが、どの承認済みClaimが各Conceptを支えるかは未解決でした。ここで本文検索やAIを利用すると、同じ入力でも結果が変わり、医学的推測がPublisherへ混入します。また、Claim割り当てとSVG座標等を同じBlueprintへ保存すると媒体交換が困難になります。

## 採用した設計

- Claim Key Prefix／Field Path Prefixの明示規則だけで照合する
- `approved`かつ未削除のRegistry Claimだけを利用する
- Claim本文を照合に使わない
- Exam Priorityは一致済み候補の順位付けだけに使う
- 一致しなければMissing Conceptとして残す
- Knowledge不足とIntent不足を構造化Reasonで分ける
- Semantic BlueprintはClaim参照・Concept・Relationだけを保持する
- Render Blueprintを将来の別モデルにする
- 入力と結果からRevision Hashを生成する

## 採用しなかった設計

### AIや文章類似度でClaimを割り当てる

再現性がなく、誤った医学的関連を作る可能性があるため採用しません。

### Claim本文をSemantic Blueprintへ複製する

KnowledgeとBlueprintに二つの医学的正本ができるため採用しません。

### 未承認Claimを仮採用する

Publisher経路へ未監修情報が入るため採用しません。

### Exam PriorityだけでConceptへ割り当てる

重要なClaimであることと、Conceptの意味に一致することは別だからです。

### Semantic Blueprintへ描画命令を保存する

媒体変更で意味モデルまで変更されるため採用しません。

## 結果

同じPlan・Registry Versionから同じBlueprintとRevision Hashを再生成できます。不足情報は隠さず、Knowledge追加またはIntent修正のどちらが必要かを判断できます。

## 将来変更する可能性

- ClaimのSemantic TagによるPrefix依存の縮小
- Claim Merge Redirectの完全な解決
- Semantic Blueprintの永続Registry・承認・履歴
- Blueprint差分と影響分析
- Concept単位の人手によるMapping修正
- Category別Mapping Preset
