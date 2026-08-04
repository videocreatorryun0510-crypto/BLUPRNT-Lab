# ADR 0011: Provider-neutral Prompt Builder and Gemini Sandbox

- Status: Accepted
- Date: 2026-08-04

## Decision

Provider PayloadとProvider Adapterの間に、独立した`PresentationPromptBuilder`を置く。BuilderはProvider非依存のPresentation Prompt 1.0だけを生成する。

Gemini Interactions API、Gemini Prompt変換、認証、Timeout、Retry、Response解釈は`GeminiSandboxAdapter`内部だけに置く。既存のKnowledge、Registry、Source Bundle、Presentation Request、Provider Payload、Traceable Response、Publisher Core Contractは変更しない。

## Reasons

- GeminiからClaude、OpenAI、Canva、NotebookLMへ交換できる
- 医学本文の無断書き換えをProvider共通Policyで禁止できる
- Gemini APIの変更をAdapter内だけで吸収できる
- Prompt Builderを媒体・Provider横断で再利用できる
- ApprovalとFingerprint不一致を外部送信前に停止できる

## Rejected

- Gemini Adapter内で医学教材の構成を直接組み立てる案
- ProviderごとにSource BundleやPresentation Requestを作り直す案
- APIキーや料金をコードへ固定する案
- Provider生レスポンスや医学本文を監査ログへ保存する案

## Consequences

Provider追加時はAdapterとResponse Mapperだけを追加する。Provider固有の出力能力差は今後Capability Contractで表現し、Presentation Prompt Contractへ混在させない。
