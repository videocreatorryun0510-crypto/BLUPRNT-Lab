# ADR 0015: Knowledge–Artifact Dual Approval Gate

- Status: Accepted
- Date: 2026-08-05

## Decision

正式Renderer経路は、Artifact承認だけでなく、元Knowledgeと参照Claimの現在状態も毎回確認する。`ArtifactRendererGateway`は信頼されたSource Snapshot Providerから現在のKnowledge状態を取得し、Artifact Registryの保存済み状態とのAND判定に成功した場合だけRendererへ渡す。

Artifactを`approved`へ進める時点でも同じSource検証を行う。Knowledgeが`draft`、`owner_review`、`medical_review`、`deprecated`の場合、Artifactは`education_review`までは進行できるが`approved`へは進めない。拒否理由はArtifact Gate Auditへ追記する。

Artifact承認後にKnowledge Version、Review Version、Source Fingerprint、Knowledge承認、Claim承認、Claim Redirectのいずれかが変わった場合、Artifact自体と承認履歴は変更しない。Renderer利用可否を派生値として`stale`または`ineligible`と判定する。

## Reasons

- Artifact承認だけで既存Knowledge Approval Gateを迂回できる経路をなくす
- 医学監修前の知識を外部成果物へ描画しない
- 過去のArtifactと承認履歴を改変せず、現在利用できない理由を監査できる
- Claim Merge後もRedirectを明示的に検証し、参照切れを隠さない
- Rendererや描画形式に依存しない共通安全境界にする

## Rejected

- Artifact承認だけでRenderer利用を許可する案
- Knowledge差し戻し時にArtifact Approval Stateを自動変更する案
- 古いArtifactを削除または上書きする案
- RendererごとにKnowledge承認を個別実装する案
- Workbench画面の表示だけで事故を防ぐ案

## Consequences

Artifact Approval StateとRenderer Eligibilityは別概念になる。Artifactが`approved`のままでも、元Knowledgeの変更によりRenderer利用不可となり得る。再利用するには、現在のKnowledgeから新しいSource BundleとArtifact Versionを作り、改めて教育承認する。

MVPではKnowledge RegistryとArtifact Registryが同一アプリケーション内にあるため、整合性確認は同期的に行う。将来Registryを別サービスへ移す場合も、Source Snapshot Provider境界と理由コードは維持する。
