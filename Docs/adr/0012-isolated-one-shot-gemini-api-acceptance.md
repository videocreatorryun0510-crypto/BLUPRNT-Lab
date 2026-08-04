# ADR 0012: Isolated one-shot Gemini API acceptance

- Status: Accepted
- Date: 2026-08-04

## Decision

Gemini実APIの受入テストには、実Registryから完全に分離した一時SQLiteと固定Test Fixtureを使用する。Fixtureだけを隔離環境内で`approved`へ進め、Workbenchの送信前確認と明示ボタンを通した1回限りのSandbox通信を許可する。

Provider-neutral Presentation Promptと既存Traceable Responseは変更せず、Gemini向け構造化応答と厳格な受入検証をAdapter内部へ置く。監査には本文・Prompt・生Response・Secretを保存しない。

## Reasons

- API接続確認のために未監修の実Knowledgeを承認する誤運用を防げる。
- 実Registryの版、承認、履歴、Relationを変えずに全経路を確認できる。
- 通信成功と教材として採用可能な応答を分けて判定できる。
- Provider固有処理をAdapter内へ閉じ込めたPhase 5.18の境界を維持できる。
- 送信量、通信回数、課金、Secret漏えいの範囲を最小化できる。

## Rejected

- フェリチン、鉄欠乏性貧血、Gram染色を受入テストのためだけに承認する案。
- 実Registryを複製せず、その場で承認状態を書き換えて戻す案。
- ページ読込またはKnowledge保存を契機に自動送信する案。
- Provider応答を通信成功だけで採用する案。
- Prompt全文、Response全文、APIキー、HTTP Headerを監査へ保存する案。

## Consequences

受入テストは実KnowledgeのPresentation品質を評価しない。実Knowledge送信は医学レビューと権限管理が整った別Phaseとする。Workbench再起動後は新しい1回枠になるため、将来は永続的な実行許可と役割ベース権限が必要になる。

