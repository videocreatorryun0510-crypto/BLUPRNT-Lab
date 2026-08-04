# Phase 5.19 Presentation Artifact Contract MVP

## 目的

Presentation Artifact Version 1.0は、Presentation Engineが生成する教材構成の唯一の正本です。PowerPoint、PDF、Instagram、HTML、Canvaなどの描画先や、Gemini、Claude、OpenAIなどの生成Providerから独立します。

```text
Knowledge + Source Bundle + Presentation Request
                    ↓
        Presentation Artifact Builder
                    ↓
       Presentation Artifact 1.0（正本）
                    ↓
             Renderer Interface
       ┌──────┼──────┬──────┐
       PPTX   PDF    HTML  Instagram ...
```

## Contract

Artifactは次だけを保持します。

- Identity：Artifact ID、版、Request ID、Source Bundle ID、Profile
- Source：Knowledge ID・版、Source Fingerprint
- Presentation Profile：対象者、学習目標、ページ数、表示方針
- Claim Catalog：Claim ID・Key、Source Bundleから無変更で複製した本文、出典ID
- Reference Catalog：出典ID、資料情報、支えるClaim ID
- Pages：Page番号、種類、見出し、学習目標、Claim参照、本文Block、図解指示、出典参照、Layout Hint
- Metadata：Artifact Fingerprint、生成日時、Builder版、Artifact版

Provider名、モデル、API、Endpoint、認証、Token、料金、描画座標、色、Fontは保存しません。

## Builder

Builderは医学的文章を作成・要約・言い換えません。Presentation Requestが選んだClaimをSource Bundleから一字も変えずに取得し、指定ページ数へ配置します。見出し、ページ番号、Layout Hintなど、医学的事実ではない教材構造だけを決めます。

Source Bundleに独立IDがないため、Version 1.0ではSource Fingerprintの先頭32桁から安定した`source_bundle_id`を派生します。既存Source Bundle Contractは変更しません。

## Validation

保存前に次を検証します。

- Page番号が重複せず1から連続する
- Requestのページ数と一致する
- Claim IDがSource BundleとKnowledgeの両方に存在する
- Claim本文、Claim Key、Field Pathが正本と一致する
- Reference IDと対応ClaimがSource Bundleと一致する
- Diagram Request ID、種類、根拠Claimが一致する
- 図解の有無とLayout Hintが整合する
- Request ID、Knowledge版、Source Fingerprintが一致する
- Artifact Fingerprintが内容と一致する
- Provider固有キーがArtifactへ混入していない

1件でも失敗した場合、Artifact JSONは保存しません。判定結果だけを本文なしAuditへ記録します。

## Renderer Interface

`Renderer.render(artifact)`だけを共通境界として定義します。PowerPoint、PDF、Instagram、HTML、Canva用の具体Rendererは今後このInterfaceを実装します。Phase 5.19では描画を行いません。

## AI Draftとの関係

外部AIはArtifactの正本を直接返しません。将来はProvider応答をProvider非依存の`PresentationDraft`へ正規化し、`ArtifactMapper`がSource Bundleと照合してArtifactへ変換します。Gemini Adapterは通信とDraft生成までに限定し、Artifact ContractへGemini固有情報を持ち込みません。

## Workbench

1. Source Bundleを生成する
2. Presentation Requestを生成する
3. 「Presentation Artifact生成・保存」を押す
4. Page一覧、Headline、Claim・Diagram・Reference件数、Fingerprint、Validation、JSON全文、保存先を確認する
5. 必要に応じてJSONをコピーする

Knowledge、Registry、Provider、Rendererは変更・実行されません。
