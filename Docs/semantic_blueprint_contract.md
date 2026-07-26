# Semantic Blueprint Contract Version 1.1

## 1. 目的

Semantic Blueprintは、BLUPRNT Labにおける「医学図解の意味構造」の正本です。医学的事実そのものの正本はKnowledge JSONとRegistryに残し、Blueprintは承認済みClaimへの参照だけを保持します。

Version 1.1ではDiagram TaxonomyのProfile参照、Taxonomy ID、解決済みPathを追加しました。大分類`intent_type`はTaxonomyのRootから解決した値であり、Diagram Intentが独自に分類した値ではありません。Version 1.0は旧Templateの再現用として引き続き読み込めます。

```text
Diagram Intent
  + 承認済みRegistry Claim
        ↓
Claim Mapping Resolver
        ↓
Semantic Blueprint
  - Concept
  - Claim Reference
  - Semantic Relation
  - Missing Concept
```

## 2. 保持する情報

| 項目 | 用途 |
|---|---|
| blueprint_id | 同じKnowledge・Intentの論理ID |
| revision_hash | 入力Versionと割り当て結果の再現確認 |
| intent_type | 図が伝える意味の種類 |
| semantic_sequences | Conceptの意味順 |
| concepts | 必須・任意と解決状態 |
| mapped_claims | Conceptから承認済みClaimへの参照 |
| missing_concepts | 不足元・理由・必要数・候補数 |
| semantic_relations | Concept間の意味関係 |

## 3. 保持しない情報

- Claim本文、説明文、要約
- 座標、寸法、色、フォント、線幅
- SVG、Mermaid、PowerPoint命令
- AI Prompt、Provider、モデル設定
- 画像、Illustration実体

## 4. 推測しないClaim Mapping

Resolverは次の順序で動きます。

1. PlanとSourceのID、Revision、Fingerprintを照合する
2. Registryから`approved`かつ未削除のClaimだけを抽出する
3. Intentが指定したClaim Key PrefixまたはField Path Prefixで照合する
4. Exam Priorityが指定されていれば、一致済み候補の順位だけを変える
5. 必要数を満たさないConceptをMissing Conceptとして記録する

Claim本文、単語検索、類似度、AIは使いません。Exam Priorityだけで新しい一致を作ることもありません。

## 5. Missing Concept判定

| origin | reason | 意味 |
|---|---|---|
| knowledge | no_matching_claim | 規則に一致するClaimが存在しない |
| knowledge | no_approved_claim | 一致候補はあるが承認済みClaimがない |
| knowledge | minimum_claims_not_met | 一部一致したが必要数に足りない |
| intent | mapping_rule_missing | Conceptの選択規則自体がない |

必須Conceptが1件でも不足すると`is_complete=false`になります。任意Conceptの不足は報告しますが、全体の完成判定を止めません。

## 6. AST MVP結果

```text
Measurement Principle
× Sample      knowledge / no_matching_claim
✓ Analyte
× Reagent     knowledge / no_matching_claim
✓ Reaction
✓ Detection
✓ Result

Comparison
✓ Subject
✓ Comparator
✓ Comparison Axis
✓ Interpretation

Disease Mechanism
× Cause       knowledge / no_matching_claim
× Tissue      knowledge / no_matching_claim
✓ Damage
✓ Biomarker
```

## 7. 将来のRender Blueprint

Render BlueprintはSemantic Blueprintを読み、媒体別の表示命令を作ります。SVG、Mermaid、PowerPoint、AI画像、動画でRender Blueprintは異なりますが、Semantic Blueprintは共通です。
