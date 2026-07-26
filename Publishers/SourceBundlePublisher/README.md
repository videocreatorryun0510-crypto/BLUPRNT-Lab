# Source Bundle Publisher

Knowledge JSON、Exam Metadata、Knowledge Registryを読み取り、外部のPresentation
Engineへ渡すSource Bundle JSON Version 1.0を生成します。

このPublisherは医学知識を書き換えません。PDF、スライド、画像、動画も生成せず、
Geminiなどの外部エンジンが理解しやすい入力契約だけを担当します。

Version 1.1.0ではApproval Gateを追加しました。Source Bundle自体は`draft`でもレビュー用に
生成できますが、`can_publish()`と`can_send_to_external_ai()`は`approved`だけを許可します。
判定結果はProviderに依存しないJSON Lines監査ログへ保存します。

現在のMVP対象は次の2件です。

- フェリチン（`knw_10000013`）
- 鉄欠乏性貧血（`knw_10000012`）

Knowledgeごとの教育目的、重要Claim、図解要求は`profiles/`で管理します。医学的事実は
Profileへ複製せず、安定した`claim_key`でRegistryのClaimを参照します。

出力先はWorkbenchの既定設定では
`Publisher Output/source_bundle/`です。生成物は派生データであり、Knowledge Registry
の正本ではありません。

既定の監査ログは`Publisher Output/logs/approval_gate.jsonl`です。
