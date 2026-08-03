# Provider Payload Resolver

Phase 5.17で追加した、Provider非依存の安全な送信Payload境界です。

Presentation Requestの参照IDを、最新のSource BundleとKnowledge Registryから解決します。医学的文章を要約・言い換え・結合せず、承認済みClaimの本文だけを`exact_text`として複写します。

## 安全方針

- Previewを含め、未承認Claimを含むProvider Payloadは生成しません。
- `approved`以外は停止します。
- Source Bundle、Knowledge Version、Review Version、Fingerprintの不一致を停止します。
- Secret、`.env`、認証付きURL、ローカル絶対パス、個人情報候補を送信前に検査します。
- Public URLは初期設定ではPayloadへ含めません。
- 監査ログにはID、判定、Fingerprintだけを保存し、医学本文を保存しません。

既存のKnowledge、Registry、Source Bundle、Presentation Request、Approval Gate、Presentation Engine Adapter Interfaceは変更しません。
