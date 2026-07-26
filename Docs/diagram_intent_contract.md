# Diagram Intent Contract Version 1.1

## 1. 目的

Diagram Intentは、BLUPRNT Labにおける医学図解の意味を標準化するPublisher Coreの共通言語です。AI Promptや完成図ではありません。

```text
Visual Profile   = 何を図にするか
Visual Grammar   = 図の内部をどう構成するか
Diagram Taxonomy = 図解をどの分類へ所属させるか
Diagram Intent   = Taxonomy IDを参照し、図で何を理解させるか
Diagram Blueprint（将来） = 承認済み事実をどの概念へ割り当てたか
Renderer（将来） = どの技術で描画するか
```

## 2. 保持する情報

| 項目 | 役割 |
|---|---|
| Taxonomy ID | 図が所属する版付き分類への参照 |
| Educational Goal | 学習者へ到達させる理解の型 |
| Semantic Sequence | 概念同士の意味上の順序と関係 |
| Required Concepts | Blueprintが最低限満たす概念 |
| Claim Mapping Strategy | 将来Claim候補を探す順序と範囲 |
| Illustration Requirement | 将来必要になる素材Category |
| Compatible Grammar Rule | 使用できるVisual Grammarとの接続 |

Version 1.1のDiagram Intent自身は`intent_type`や分類階層を持ちません。大分類はDiagram TaxonomyのRootから解決します。旧Version 1.0の`intent_type`は既存Publication Plan再現用に残します。

## 3. 保持しない情報

- 医学本文、説明文、Claim本文
- `claim_id`と個別Claim割り当て
- AI PromptとProvider固有設定
- 図の座標、色、フォント、線幅
- 画像、SVG、Mermaid、PowerPoint素材
- Diagram BlueprintとRenderer命令

## 4. Claim Mapping Strategy

Phase 3.4ではClaimを割り当てません。次の選択規則だけを固定します。

- 承認済みClaimだけを対象にする
- Field Path Prefix、Claim Key Prefix、Exam Priorityを順番に利用できる
- Conceptごとの必要Claim数上限・下限を持つ
- 同じClaimを複数Conceptで再利用できるかを指定する
- Required Conceptを満たせない場合は不足を報告し、Blueprint生成を止める

これにより将来のResolverは独自に医学知識を推測せず、明示された範囲だけから候補を選びます。

## 5. AST Version 1

### Measurement Principle

```text
Sample → Reaction → Detection → Result
```

必須概念はSample、Analyte、Reagent、Reaction、Detection、Resultです。

### Comparison

```text
Subject → Comparator → Comparison Axis → Interpretation
```

### Disease Mechanism

```text
Cause → Tissue → Damage → Biomarker
```

これらは医学本文ではなく、図解が満たす意味の枠です。

## 6. Diagram Blueprintへの将来接続

```text
Diagram Intent
  + Visual Grammar
  + 承認済みClaim参照
  + Registry
        ↓
Claim Mapping Resolver（Phase 3.5実装）
        ↓
ConceptごとのClaim割り当て
Grammar Nodeへの配置候補
不足Conceptレポート
        ↓
Render Blueprint／Renderer Contract（未実装）
```

Resolverは医学本文を新規生成せず、Registryで承認されたClaimを割り当てるだけにします。
