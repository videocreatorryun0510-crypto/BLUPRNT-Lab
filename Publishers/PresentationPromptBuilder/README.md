# Presentation Prompt Builder

Provider Payloadを、特定のAIベンダーに依存しないPresentation Promptへ変換します。

- Claim本文は一字も書き換えません。
- `approved`以外は停止します。
- Provider名、API URL、SDK名、Gemini固有Promptを保持しません。
- Content / Layout / Validation Policyを明示します。
- Prompt JSONと監査ログは`Publisher Output/`配下へ保存します。

Gemini・Claude・OpenAI・Canva・NotebookLMなどへの変換は、各Provider Adapterの責務です。
