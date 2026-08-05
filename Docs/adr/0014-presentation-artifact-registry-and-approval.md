# ADR 0014: Presentation Artifact Registry and independent approval

- Status: Accepted
- Date: 2026-08-05

## Decision

Presentation Artifactを直接Rendererへ渡さず、独立したSQLite Artifact Registryへ版付きで保存する。Renderer Interfaceは変更せず、`ArtifactRendererGateway`がRegistryから`active`かつ`approved`のArtifactだけを取得してRendererへ渡す。

Artifact承認はKnowledge承認から分離し、`draft → owner_review → education_review → approved → published`をArtifact専用Flowとする。同じ`knowledge_id + profile_id`の改訂は安定`artifact_id`を維持し、追記型`artifact_version`として保存する。approved到達後の教育内容・参照・FingerprintはImmutableとする。

## Reasons

- 医学知識の承認と教材構成の承認は異なる判断である
- 教材改訂履歴をKnowledge改訂と独立して追跡できる
- ProviderやRendererを交換してもArtifactの版・承認契約が変わらない
- 未承認教材をPDF、PowerPoint、Instagram等へ描画する事故を共通境界で防げる
- Rendererごとに承認や版管理を重複実装しなくてよい
- 過去のapproved版を再現しながら次版をdraftで編集できる

## Rejected

- KnowledgeからRendererへ直接渡す案
- Builder出力JSONをRendererが直接読む案
- Renderer側でVersionとApprovalを管理する案
- Gemini等のProvider成果物をRendererへ直接渡す案
- Knowledge RegistryのApproval StateをArtifactへ流用する案

## Consequences

正式な描画経路はArtifact RegistryとGatewayを必須とする。BuilderのJSON保存は検証・デバッグ用の一時出力であり、Rendererの入力正本ではない。

SQLiteはMVPとして十分だが、多人数同時編集、細かな権限、電子署名、保持Policyが必要になった時点で同じRepository境界をRDBサービスへ交換する。Artifact Contract Version 1.0とRenderer Interfaceは変更しない。
