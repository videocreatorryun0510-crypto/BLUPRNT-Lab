# ADR 0013: Presentation Artifact as the sole educational output contract

- Status: Accepted
- Date: 2026-08-04

## Decision

Presentation Artifact Version 1.0を、Presentation Engineにおける唯一の教育成果物Contractとする。Artifactはページ構成、無変更Claim、Reference、Diagram Instruction、Layout Hintだけを保持し、Provider・API・描画技術から独立させる。

外部AIはPresentation Draftだけを生成する。Draftを正本Artifactへ変換・検証する責務はProvider外部のArtifact Mapperに置く。PowerPoint、PDF、Instagram、HTML、Canva等は共通`Renderer` Interfaceを通じて同じArtifactを読む。

## Reasons

- Providerを交換しても教育成果物の正本が変わらない
- 1つの教材構成から複数媒体を再生成できる
- 医学的事実、教育構成、描画の責務を分離できる
- ClaimとReferenceを媒体横断で追跡できる
- Provider障害やサービス終了後も成果物を再利用できる
- Gemini固有出力の変更をArtifactより手前で吸収できる

## Rejected

- Gemini専用スライドJSONを正本とする案
- Gemini ResponseをPowerPointへ直接変換する案
- Providerごとに異なる教育成果物Contractを持つ案
- Knowledgeから直接PDFを生成する案
- Artifactへ座標、色、Font、API情報を保存する案

## Consequences

新しい媒体はRendererだけを追加する。新しいProviderはAdapter、Draft Mapper、応答検証だけを追加する。Artifact Contractの破壊的変更は全Rendererへ影響するため、Version 2以降は移行期間と互換Readerを必須とする。

Version 1.0のBuilderは決定的な規則でページを構成する。AI DraftからArtifactへ変換する具体Mapper、Renderer Capability、アクセシビリティ表現、言語別組版は将来Phaseで追加する。
