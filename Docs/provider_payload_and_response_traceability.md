# Provider Payload Preparation & Response Traceability MVP

## 1. 役割

Phase 5.17は、Presentation Requestの参照IDを承認済み正本へ解決し、外部Presentation Engineへ送信可能な最小データへ変換する境界です。

```text
Registry + Source Bundle + Presentation Request
        ↓
Provider Payload Resolver
        ├── Approval Gate再確認
        ├── Stale Check
        ├── Claim・図解・出典解決
        ├── Data Egress Policy
        └── Payload Fingerprint
        ↓
Presentation Payload 1.0
        ↓
Provider Adapter（Dummyのみ）
        ↓
Traceable Response 1.0
```

Knowledge、Registry、Claim ID、Relation、Source Bundle、Presentation Request、Approval Gate、既存Adapter Interface、Publisher Coreは変更しません。

## 2. Claim解決

- Presentation Requestで選択されたClaimだけを解決する
- Registryの`assertion`を`exact_text`へ一字も変えずに複写する
- 要約、言い換え、結合、補完を行わない
- `approved`のClaimだけを許可する
- deprecated ClaimはRegistryのMerge Redirectをたどり、現行Claimを利用する
- 1件でも解決できなければPayload全体を停止する

Previewも未承認の医学本文を含むProvider Payloadは生成しません。既存のPresentation Request Previewは引き続きdraftで利用できます。

## 3. Key Message・Exam Metadata

Key MessageはSource Bundleの`key_messages`とPresentation Requestの`key_message_claim_ids`を照合し、選択済みClaimの`exact_text`だけを再利用します。新しい文章は作りません。

Exam MetadataはSource Bundleに試験重要Claimが存在する場合だけ投影します。存在しない場合は空配列とし、AI補完しません。

## 4. Diagram Request・Reference

Diagram RequestはSource Bundle内のID、教育目的、図解種別、source Claimだけを利用します。`provider_neutral_instruction`は既存の教育目的を再利用し、Provider固有Promptを保存しません。

ReferenceはSource Bundleに含まれる確認済みMetadataだけを解決します。初期PolicyではPublic URLも送信対象外です。DOI、PMID、章、ページはLocatorとして保持できます。Referenceが未選択Claimを参照する場合は停止します。

## 5. Data Egress Policy 1.0

初期許可：

- 承認済みの選択Claim本文
- 選択Reference Metadata
- 教育目的、対象者、媒体条件、図解要求
- Traceability IDとFingerprint

初期禁止：

- 未承認・未選択・deprecated未解決Claim
- Registry全体、履歴全文、内部監査コメント
- `.env`、API Key、Access Token、Private Key、認証付きURL
- ローカル絶対パス、DBファイル、個人情報候補
- Source Bundle外の医学情報
- 医学的な言い換え、事実追加

PolicyはProvider共通であり、Gemini・Claude・OpenAIの個別Adapterへ委任しません。

## 6. FingerprintとTraceability

Payload FingerprintはRequest、Knowledge Version、Source Fingerprint、Review Version、Claim ID・Version・本文、図解ID、出典ID、Resolver Version、Policyを正規化してSHA-256で生成します。Payload IDと作成日時はFingerprintから除外するため、同じ入力は同じFingerprintになります。

Trace Mapは本文を重複保存せず、次の対応だけを保持します。

- Claim ID → Payload位置・利用目的・表示優先度
- Diagram Request ID → source Claim・教育目的
- Reference ID → supported Claim

## 7. Traceable Response 1.0

ResponseはPayload ID・Fingerprint、Provider情報、実行状態、使用／省略したClaim・図解・出典ID、Artifact Metadata、検証結果だけを持ちます。医学本文は複製しません。

実行状態は将来の非同期処理を考慮し、`accepted`、`queued`、`running`、`completed`、`failed`、`cancelled`、`expired`を契約に含めます。Dummyは通信なしで即時`completed`になります。

## 8. 監査と保存先

```text
Publisher Output/
  provider_payload/
  presentation_response/
  logs/provider_payload.jsonl
  logs/presentation_response.jsonl
```

監査ログにはID、状態、Fingerprint、各Validation結果、理由、日時だけを保存します。Claim本文、Reference全文、Secretは保存しません。`Publisher Output/`はGit対象外です。

## 9. 互換性

Phase 5.16のPresentation Request直接Dummy実行経路は回帰互換のため残します。実Provider追加時はPhase 5.17の`PresentationPayload`経路を正規経路とします。既存のAdapter Interfaceは変更せず、Dummyへ`execute_traceable_payload()`を追加しています。

## 10. 対象外

- Gemini・Claude・OpenAI APIと認証
- Provider固有Prompt
- PDF・PowerPoint・画像・動画の生成
- Retry、Rate Limit、課金、Webhook
- AI結果の医学承認・Knowledge更新
- 複数利用者の権限管理
