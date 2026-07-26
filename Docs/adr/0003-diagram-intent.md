# ADR 0003: Diagram IntentをVisual GrammarとDiagram Blueprintの間に置く

- 状態: Accepted
- 日付: 2026-07-18
- 対象: Phase 3.4

## 背景

Visual Profileは「何を描くか」、Visual Grammarは「どう構成するか」を定義します。しかし、同じReaction DiagramでもASTの測定原理と別の検査・疾患では伝える意味が異なります。IntentなしでBlueprintへ進むと、Blueprint Resolverが医学的な目的や必要概念まで判断し、責務が肥大化します。

## 採用した設計

Diagram IntentをPublisher Coreの独立した版付きProfileとして追加します。

- Intent TypeとEducational Goalを管理する
- Semantic Sequenceを概念IDと関係語で表す
- Required Conceptを明示する
- Claim Mapping結果ではなくStrategyだけを保存する
- Illustration IDではなくCategoryだけを要求する
- Compatible Grammar Rule IDでVisual Grammarと接続する
- Publication Plan 1.3へ解決済みIntentを固定する
- Publication Plan 1.0〜1.2を後方互換として残す

## 採用しなかった設計

### Visual Grammarへ医学的な意味順を保存する

構造と意味が混ざり、同じ構図を異なる医学テーマへ再利用できなくなるため採用しません。

### Diagram BlueprintがIntentを推測する

Resolverが医学的解釈を持ち、テスト・監修・Provider交換が困難になるため採用しません。

### Knowledge JSONへDiagram Intentを保存する

医学的事実の正本と教材表現の意味が混ざるため採用しません。

### Claim IDをDiagram Intentへ直接保存する

Intentの再利用性が下がり、Claim統合やVersion変更の影響を受けるため採用しません。

### AI PromptをIntentとして保存する

描画Providerやモデル更新に依存し、長期的な共通言語にならないため採用しません。

## 結果

Diagram Blueprint Resolverは、Intentが要求するConceptへ承認済みClaimを割り当てる小さな責務に限定できます。SVG、Mermaid、AI画像、PowerPoint等が変わってもIntentは維持できます。

## 将来変更する可能性

- Concept Type・Semantic Relationの共通Taxonomy Registry化
- 複数Sequence、分岐、循環、階層構造の表現強化
- Claim Mapping StrategyのCategory別Preset
- Diagram Intentの承認・差分レビュー画面
- Blueprint Resolverの不足Concept評価と人手修正フロー
