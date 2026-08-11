const form = document.querySelector("#generateForm");
const input = document.querySelector("#term");
const submitButton = document.querySelector("#submitButton");
const normalLabel = document.querySelector(".button-label");
const loadingLabel = document.querySelector(".button-loading");
const resultPanel = document.querySelector("#resultPanel");
const errorPanel = document.querySelector("#errorPanel");
const errorMessage = document.querySelector("#errorMessage");
const jsonOutput = document.querySelector("#jsonOutput");
const testItemPanel = document.querySelector("#testItemPanel");
const testItemSections = document.querySelector("#testItemSections");
const csvFile = document.querySelector("#csvFile");
const previewCsvButton = document.querySelector("#previewCsvButton");
const samplePreviewButton = document.querySelector("#samplePreviewButton");
const commitImportButton = document.querySelector("#commitImportButton");
const importReportPanel = document.querySelector("#importReportPanel");
const importErrorPanel = document.querySelector("#importErrorPanel");
const importErrorMessage = document.querySelector("#importErrorMessage");
const registryKnowledgeSelect = document.querySelector("#registryKnowledgeSelect");
const knowledgeJsonEditor = document.querySelector("#knowledgeJsonEditor");
const saveKnowledgeButton = document.querySelector("#saveKnowledgeButton");
const generateSourceBundleButton = document.querySelector(
  "#generateSourceBundleButton",
);
const generatePresentationRequestButton = document.querySelector(
  "#generatePresentationRequestButton",
);
const generatePresentationArtifactButton = document.querySelector(
  "#generatePresentationArtifactButton",
);
const presentationRequestMode = document.querySelector(
  "#presentationRequestMode",
);
const executeDummyAdapterButton = document.querySelector(
  "#executeDummyAdapterButton",
);
const generateProviderPayloadButton = document.querySelector(
  "#generateProviderPayloadButton",
);
const executeTraceableDummyButton = document.querySelector(
  "#executeTraceableDummyButton",
);
const generatePresentationPromptButton = document.querySelector(
  "#generatePresentationPromptButton",
);
const executeGeminiSandboxButton = document.querySelector(
  "#executeGeminiSandboxButton",
);
const knowledgeEditorMessage = document.querySelector("#knowledgeEditorMessage");
const sourceBundlePanel = document.querySelector("#sourceBundlePanel");
const sourceBundleMessage = document.querySelector("#sourceBundleMessage");
const sourceBundleOutput = document.querySelector("#sourceBundleOutput");
const knowledgeApprovalSummary = document.querySelector(
  "#knowledgeApprovalSummary",
);
const sourceBundleGateReason = document.querySelector(
  "#sourceBundleGateReason",
);
const presentationRequestPanel = document.querySelector(
  "#presentationRequestPanel",
);
const presentationRequestOutput = document.querySelector(
  "#presentationRequestOutput",
);
const presentationRequestReason = document.querySelector(
  "#presentationRequestReason",
);
const presentationArtifactPanel = document.querySelector(
  "#presentationArtifactPanel",
);
const presentationArtifactOutput = document.querySelector(
  "#presentationArtifactOutput",
);
const presentationArtifactPages = document.querySelector(
  "#presentationArtifactPages",
);
const artifactRegistrySelect = document.querySelector("#artifactRegistrySelect");
const artifactRegistryPanel = document.querySelector("#artifactRegistryPanel");
const artifactVersionSelect = document.querySelector("#artifactVersionSelect");
const artifactRegistryJson = document.querySelector("#artifactRegistryJson");
const presentationEnginePanel = document.querySelector(
  "#presentationEnginePanel",
);
const presentationResultOutput = document.querySelector(
  "#presentationResultOutput",
);
const presentationEngineReason = document.querySelector(
  "#presentationEngineReason",
);
const providerPayloadPanel = document.querySelector("#providerPayloadPanel");
const providerPayloadOutput = document.querySelector("#providerPayloadOutput");
const providerPayloadReason = document.querySelector("#providerPayloadReason");
const traceableResponsePanel = document.querySelector(
  "#traceableResponsePanel",
);
const traceableResponseOutput = document.querySelector(
  "#traceableResponseOutput",
);
const traceableResponseReason = document.querySelector(
  "#traceableResponseReason",
);
const presentationPromptPanel = document.querySelector(
  "#presentationPromptPanel",
);
const presentationPromptOutput = document.querySelector(
  "#presentationPromptOutput",
);
const presentationPromptReason = document.querySelector(
  "#presentationPromptReason",
);
const geminiSandboxPanel = document.querySelector("#geminiSandboxPanel");
const geminiSandboxOutput = document.querySelector("#geminiSandboxOutput");
const geminiSandboxReason = document.querySelector("#geminiSandboxReason");
const prepareGeminiAcceptanceButton = document.querySelector(
  "#prepareGeminiAcceptanceButton",
);
const executeGeminiAcceptanceButton = document.querySelector(
  "#executeGeminiAcceptanceButton",
);
const geminiAcceptancePreflight = document.querySelector(
  "#geminiAcceptancePreflight",
);
const geminiAcceptanceResultPanel = document.querySelector(
  "#geminiAcceptanceResultPanel",
);
const diseaseVocabularyBadge = document.querySelector("#diseaseVocabularyBadge");
const diseaseVocabularyList = document.querySelector("#diseaseVocabularyList");
let currentRegistry = null;
let currentPreviewId = null;
let currentPreviewCanCommit = false;
let geminiAcceptanceFingerprint = null;
let geminiAcceptanceExecutionStarted = false;
let currentArtifactRegistry = null;

const termTypeLabels = {
  test_item: "検査項目",
  staining_method: "染色法",
  specimen: "検体・標本",
  reagent: "試薬",
  biological_structure: "生体構造",
  disease: "疾患",
  laboratory_test_item: "臨床検査項目",
};

const examDomainLabels = {
  clinical_chemistry: "臨床化学",
  hematology: "血液学",
  microbiology: "微生物学",
  immunology: "免疫学",
  transfusion: "輸血学",
  pathology_cytology: "病理・細胞診",
  physiology: "生理学",
  public_health: "公衆衛生",
  medical_engineering: "医用工学",
  other: "その他",
};

const registryStatusLabels = {
  draft: "下書き",
  owner_review: "オーナー確認中",
  medical_review: "医学監修中",
  approved: "承認済み",
  published: "公開済み",
  deprecated: "廃止",
};

const artifactApprovalLabels = {
  draft: "下書き",
  owner_review: "オーナー確認中",
  education_review: "教育設計確認中",
  approved: "承認済み",
  published: "公開済み",
};

document.querySelectorAll("[data-term]").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.term;
    input.focus();
  });
});

samplePreviewButton.addEventListener("click", async () => {
  await runExamPreview("/api/import/exam-csv/preview/sample");
});

previewCsvButton.addEventListener("click", async () => {
  const file = csvFile.files?.[0];
  if (!file) {
    showImportError("先にCSVファイルを1つ選択してください。");
    return;
  }
  if (!file.name.toLowerCase().endsWith(".csv")) {
    showImportError("拡張子が.csvのファイルを選択してください。");
    return;
  }
  if (file.size > 5_000_000) {
    showImportError("Prototypeでは5MB以下のCSVを選択してください。");
    return;
  }
  const csvBase64 = await readFileAsBase64(file);
  await runExamPreview("/api/import/exam-csv/preview", {
    source_file: file.name,
    csv_base64: csvBase64,
    import_mode: "replace",
  });
});

commitImportButton.addEventListener("click", async () => {
  if (!currentPreviewId) {
    showImportError("先にCSVをPreviewしてください。");
    return;
  }
  await commitExamImport(currentPreviewId);
});

document.querySelector("#loadRegistryButton").addEventListener("click", async () => {
  await loadSelectedRegistry();
});

document.querySelector("#refreshRegistryButton").addEventListener("click", async () => {
  await refreshRegistryList(true);
});

document.querySelector("#loadArtifactRegistryButton").addEventListener("click", async () => {
  await loadSelectedArtifactRegistry();
});

document.querySelector("#refreshArtifactRegistryButton").addEventListener(
  "click",
  async () => {
    await refreshArtifactRegistryList(true);
  },
);

artifactVersionSelect.addEventListener("change", async () => {
  await loadSelectedArtifactVersion();
});

document.querySelector("#changeArtifactApprovalButton").addEventListener(
  "click",
  async () => {
    await changeArtifactApproval();
  },
);

document.querySelector("#compareArtifactVersionsButton").addEventListener(
  "click",
  async () => {
    await compareArtifactVersions();
  },
);

document.querySelector("#checkRendererEligibilityButton").addEventListener(
  "click",
  async () => {
    await checkRendererEligibility();
  },
);

document.querySelector("#copyArtifactRegistryJsonButton").addEventListener(
  "click",
  async (event) => {
    await navigator.clipboard.writeText(artifactRegistryJson.textContent);
    event.currentTarget.textContent = "コピー済み";
    window.setTimeout(() => {
      event.currentTarget.textContent = "JSONをコピー";
    }, 1300);
  },
);

document.querySelector("#changeClaimStatusButton").addEventListener("click", async () => {
  await changeSelectedClaimStatus();
});

document.querySelector("#changeKnowledgeStatusButton").addEventListener("click", async () => {
  await changeKnowledgeStatus();
});

document.querySelector("#mergeClaimsButton").addEventListener("click", async () => {
  await mergeSelectedClaims();
});

document.querySelector("#createBackupButton").addEventListener("click", async () => {
  await createRegistryBackup();
});

document.querySelector("#restoreBackupButton").addEventListener("click", async () => {
  await restoreRegistryBackup();
});

document.querySelector("#loadGramStarterButton").addEventListener("click", async () => {
  await loadGramStarter();
});

document.querySelector("#loadAcidFastStarterButton").addEventListener("click", async () => {
  await loadAcidFastStarter();
});

document.querySelector("#loadSpecimenStarterButton").addEventListener("click", async () => {
  await loadSpecimenStarter();
});

document.querySelector("#loadReagentStarterButton").addEventListener("click", async () => {
  await loadReagentStarter();
});

document.querySelector("#loadBiologicalStructureStarterButton").addEventListener(
  "click",
  async () => {
    await loadBiologicalStructureStarter();
  },
);

document.querySelector("#loadDiseaseStarterButton").addEventListener("click", async () => {
  await loadDiseaseStarter();
});

document.querySelector("#loadLaboratoryTestItemStarterButton").addEventListener(
  "click",
  async () => {
    await loadLaboratoryTestItemStarter();
  },
);

saveKnowledgeButton.addEventListener("click", async () => {
  await saveKnowledgeRecord();
});

generateSourceBundleButton.addEventListener("click", async () => {
  await generateSourceBundle();
});

generatePresentationRequestButton.addEventListener("click", async () => {
  await generatePresentationRequest();
});

generatePresentationArtifactButton.addEventListener("click", async () => {
  await generatePresentationArtifact();
});

executeDummyAdapterButton.addEventListener("click", async () => {
  await executeDummyAdapter();
});

generateProviderPayloadButton.addEventListener("click", async () => {
  await generateProviderPayload();
});

executeTraceableDummyButton.addEventListener("click", async () => {
  await executeTraceableDummy();
});

generatePresentationPromptButton.addEventListener("click", async () => {
  await generatePresentationPrompt();
});

executeGeminiSandboxButton.addEventListener("click", async () => {
  await executeGeminiSandbox();
});

prepareGeminiAcceptanceButton.addEventListener("click", async () => {
  await prepareGeminiAcceptance();
});

executeGeminiAcceptanceButton.addEventListener("click", async () => {
  await executeGeminiAcceptance();
});

presentationRequestMode.addEventListener("change", () => {
  executeDummyAdapterButton.disabled = true;
  presentationEnginePanel.hidden = true;
  resetPresentationArtifactState();
  resetProviderPayloadState();
});

document.querySelector("#copySourceBundleButton").addEventListener(
  "click",
  async (event) => {
    await navigator.clipboard.writeText(sourceBundleOutput.textContent);
    event.currentTarget.textContent = "コピー済み";
    window.setTimeout(() => {
      event.currentTarget.textContent = "JSONをコピー";
    }, 1300);
  },
);

document.querySelector("#copyPresentationRequestButton").addEventListener(
  "click",
  async (event) => {
    await navigator.clipboard.writeText(presentationRequestOutput.textContent);
    event.currentTarget.textContent = "コピー済み";
    window.setTimeout(() => {
      event.currentTarget.textContent = "JSONをコピー";
    }, 1300);
  },
);

document.querySelector("#copyPresentationArtifactButton").addEventListener(
  "click",
  async (event) => {
    const button = event.currentTarget;
    await navigator.clipboard.writeText(presentationArtifactOutput.textContent);
    button.textContent = "コピー済み";
    window.setTimeout(() => {
      button.textContent = "JSONをコピー";
    }, 1300);
  },
);

document.querySelector("#copyPresentationResultButton").addEventListener(
  "click",
  async (event) => {
    await navigator.clipboard.writeText(presentationResultOutput.textContent);
    event.currentTarget.textContent = "コピー済み";
    window.setTimeout(() => {
      event.currentTarget.textContent = "Result JSONをコピー";
    }, 1300);
  },
);

document.querySelector("#copyProviderPayloadButton").addEventListener(
  "click",
  async (event) => {
    await navigator.clipboard.writeText(providerPayloadOutput.textContent);
    event.currentTarget.textContent = "コピー済み";
    window.setTimeout(() => {
      event.currentTarget.textContent = "JSONをコピー";
    }, 1300);
  },
);

document.querySelector("#copyTraceableResponseButton").addEventListener(
  "click",
  async (event) => {
    await navigator.clipboard.writeText(traceableResponseOutput.textContent);
    event.currentTarget.textContent = "コピー済み";
    window.setTimeout(() => {
      event.currentTarget.textContent = "Responseをコピー";
    }, 1300);
  },
);

document.querySelector("#copyPresentationPromptButton").addEventListener(
  "click",
  async (event) => {
    await navigator.clipboard.writeText(presentationPromptOutput.textContent);
    event.currentTarget.textContent = "コピー済み";
    window.setTimeout(() => {
      event.currentTarget.textContent = "Promptをコピー";
    }, 1300);
  },
);

document.querySelector("#copyGeminiResponseButton").addEventListener(
  "click",
  async (event) => {
    await navigator.clipboard.writeText(geminiSandboxOutput.textContent);
    event.currentTarget.textContent = "コピー済み";
    window.setTimeout(() => {
      event.currentTarget.textContent = "Responseをコピー";
    }, 1300);
  },
);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  hideError();
  resultPanel.hidden = true;

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ term: input.value }),
    });
    const payload = await response.json();
    if (!response.ok || payload.status !== "success") {
      const message = payload.errors?.[0]?.message || "不明なエラーが発生しました。";
      throw new Error(message);
    }
    renderResult(
      payload.data,
      payload.knowledge_completeness,
      payload.exam_metadata,
      payload.exam_completeness,
      payload.registry,
      payload.relations,
    );
  } catch (error) {
    showError(error instanceof Error ? error.message : "通信に失敗しました。");
  } finally {
    setLoading(false);
  }
});

async function loadGramStarter() {
  knowledgeEditorMessage.textContent = "正式下書きを読み込んでいます…";
  try {
    const response = await fetch("/api/knowledge-templates/staining-method/gram-stain");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "下書きを読み込めませんでした。");
    }
    knowledgeJsonEditor.value = JSON.stringify(payload.data, null, 2);
    setSourceBundleAvailability(payload.data, payload.persisted);
    document.querySelector("#knowledgeEditorComment").value = "Gram染色の正式Category登録・更新";
    saveKnowledgeButton.disabled = false;
    knowledgeEditorMessage.textContent = payload.persisted
      ? "保存済みの正本を開きました · Schema OK · 染色法Completeness " +
        payload.knowledge_completeness.score + "%"
      : "Schema OK · 染色法Completeness " +
        payload.knowledge_completeness.score +
        "% · まだRegistryは変更していません。";
    knowledgeJsonEditor.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error ? error.message : "下書きの通信に失敗しました。";
  }
}

async function loadAcidFastStarter() {
  knowledgeEditorMessage.textContent = "抗酸菌染色の正式下書きを読み込んでいます…";
  try {
    const response = await fetch("/api/knowledge-templates/staining-method/acid-fast-stain");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "下書きを読み込めませんでした。");
    }
    knowledgeJsonEditor.value = JSON.stringify(payload.data, null, 2);
    setSourceBundleAvailability(payload.data, payload.persisted);
    document.querySelector("#knowledgeEditorComment").value =
      "抗酸菌染色を既存staining_method Categoryへ登録・更新";
    saveKnowledgeButton.disabled = false;
    knowledgeEditorMessage.textContent = payload.persisted
      ? "保存済みの正本を開きました · Schema OK · 染色法Completeness " +
        payload.knowledge_completeness.score + "%"
      : "Schema OK · 染色法Completeness " +
        payload.knowledge_completeness.score +
        "% · まだRegistryは変更していません。";
    knowledgeJsonEditor.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error ? error.message : "下書きの通信に失敗しました。";
  }
}

async function loadSpecimenStarter() {
  knowledgeEditorMessage.textContent = "Specimenの正式下書きを読み込んでいます…";
  try {
    const response = await fetch("/api/knowledge-templates/specimen/smear-specimen");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "下書きを読み込めませんでした。");
    }
    knowledgeJsonEditor.value = JSON.stringify(payload.data, null, 2);
    setSourceBundleAvailability(payload.data, payload.persisted);
    document.querySelector("#knowledgeEditorComment").value = "塗抹標本の正式Category登録・更新";
    saveKnowledgeButton.disabled = false;
    knowledgeEditorMessage.textContent = payload.persisted
      ? "保存済みの正本を開きました · Schema OK · Specimen Completeness " +
        payload.knowledge_completeness.score + "%"
      : "Schema OK · Specimen Completeness " +
        payload.knowledge_completeness.score +
        "% · まだRegistryは変更していません。";
    knowledgeJsonEditor.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error ? error.message : "下書きの通信に失敗しました。";
  }
}

async function loadReagentStarter() {
  const selector = document.querySelector("#reagentStarterSelect");
  const selectedName = selector.options[selector.selectedIndex].text;
  knowledgeEditorMessage.textContent = selectedName + "の正式下書きを読み込んでいます…";
  try {
    const response = await fetch(
      "/api/knowledge-templates/reagent/" + encodeURIComponent(selector.value),
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "下書きを読み込めませんでした。");
    }
    knowledgeJsonEditor.value = JSON.stringify(payload.data, null, 2);
    setSourceBundleAvailability(payload.data, payload.persisted);
    document.querySelector("#knowledgeEditorComment").value =
      payload.data.term.canonical_name + "の正式Category登録・更新";
    saveKnowledgeButton.disabled = false;
    knowledgeEditorMessage.textContent = payload.persisted
      ? "保存済みの正本を開きました · Schema OK · Reagent Completeness " +
        payload.knowledge_completeness.score + "%"
      : "Schema OK · Reagent Completeness " +
        payload.knowledge_completeness.score +
        "% · まだRegistryは変更していません。";
    knowledgeJsonEditor.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error ? error.message : "下書きの通信に失敗しました。";
  }
}

async function loadBiologicalStructureStarter() {
  knowledgeEditorMessage.textContent = "細菌細胞壁の正式下書きを読み込んでいます…";
  try {
    const response = await fetch(
      "/api/knowledge-templates/biological-structure/bacterial-cell-wall",
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "下書きを読み込めませんでした。");
    }
    knowledgeJsonEditor.value = JSON.stringify(payload.data, null, 2);
    setSourceBundleAvailability(payload.data, payload.persisted);
    document.querySelector("#knowledgeEditorComment").value =
      "細菌細胞壁をbiological_structure Categoryへ登録・更新";
    saveKnowledgeButton.disabled = false;
    knowledgeEditorMessage.textContent = payload.persisted
      ? "保存済みの正本を開きました · Schema OK · Biological Structure Completeness " +
        payload.knowledge_completeness.score + "%"
      : "Schema OK · Biological Structure Completeness " +
        payload.knowledge_completeness.score +
        "% · まだRegistryは変更していません。";
    knowledgeJsonEditor.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error ? error.message : "下書きの通信に失敗しました。";
  }
}

async function loadDiseaseStarter() {
  knowledgeEditorMessage.textContent = "鉄欠乏性貧血の正式下書きを読み込んでいます…";
  try {
    const response = await fetch(
      "/api/knowledge-templates/disease/iron-deficiency-anemia",
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "下書きを読み込めませんでした。");
    }
    knowledgeJsonEditor.value = JSON.stringify(payload.data, null, 2);
    setSourceBundleAvailability(payload.data, payload.persisted);
    document.querySelector("#knowledgeEditorComment").value =
      "鉄欠乏性貧血をdisease Categoryへ登録・更新";
    saveKnowledgeButton.disabled = false;
    knowledgeEditorMessage.textContent = payload.persisted
      ? "保存済みの正本を開きました · Schema OK · Disease Completeness " +
        payload.knowledge_completeness.score + "%"
      : "Schema OK · Disease Completeness " +
        payload.knowledge_completeness.score +
        "% · まだRegistryは変更していません。";
    knowledgeJsonEditor.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error ? error.message : "下書きの通信に失敗しました。";
  }
}

async function loadLaboratoryTestItemStarter() {
  knowledgeEditorMessage.textContent = "フェリチンの正式下書きを読み込んでいます…";
  try {
    const response = await fetch(
      "/api/knowledge-templates/laboratory-test-item/ferritin",
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "下書きを読み込めませんでした。");
    }
    knowledgeJsonEditor.value = JSON.stringify(payload.data, null, 2);
    setSourceBundleAvailability(payload.data, payload.persisted);
    document.querySelector("#knowledgeEditorComment").value =
      "フェリチンをlaboratory_test_item Categoryへ登録・更新";
    saveKnowledgeButton.disabled = false;
    knowledgeEditorMessage.textContent = payload.persisted
      ? "保存済みの正本を開きました · Schema OK · Laboratory Test Item Completeness " +
        payload.knowledge_completeness.score + "%"
      : "Schema OK · Laboratory Test Item Completeness " +
        payload.knowledge_completeness.score +
        "% · まだRegistryは変更していません。";
    knowledgeJsonEditor.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error ? error.message : "下書きの通信に失敗しました。";
  }
}

async function saveKnowledgeRecord() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "JSONの記号やカンマを確認してください。";
    return;
  }
  const actor = document.querySelector("#knowledgeEditorActor").value.trim();
  const comment = document.querySelector("#knowledgeEditorComment").value.trim();
  if (!actor || !comment || !record.knowledge_id) {
    knowledgeEditorMessage.textContent = "操作者、変更理由、knowledge_idが必要です。";
    return;
  }
  saveKnowledgeButton.disabled = true;
  knowledgeEditorMessage.textContent = "Schema確認後、Registryへ保存しています…";
  try {
    const response = await fetch(
      "/api/knowledge-records/" + encodeURIComponent(record.knowledge_id),
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ record, actor, comment }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "保存できませんでした。");
    }
    knowledgeJsonEditor.value = JSON.stringify(payload.data, null, 2);
    setSourceBundleAvailability(payload.data, true);
    knowledgeEditorMessage.textContent =
      "保存しました · Schema OK · Completeness " +
      payload.knowledge_completeness.score + "% · Knowledge Version v" +
      payload.registry.knowledge.knowledge_version +
      resolutionReportMessage(payload.resolution_report);
    renderResolutionReport(payload.resolution_report);
    renderResult(
      payload.data,
      payload.knowledge_completeness,
      payload.exam_metadata,
      payload.exam_completeness,
      payload.registry,
      payload.relations,
    );
    await refreshRegistryList(false);
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error ? error.message : "保存の通信に失敗しました。";
  } finally {
    saveKnowledgeButton.disabled = false;
  }
}

function setSourceBundleAvailability(record, persisted) {
  const supportedIds = new Set(["knw_10000012", "knw_10000013"]);
  const available =
    persisted === true &&
    record !== null &&
    supportedIds.has(record.knowledge_id);
  generateSourceBundleButton.disabled = !available;
  generatePresentationRequestButton.disabled = true;
  resetPresentationArtifactState();
  executeDummyAdapterButton.disabled = true;
  resetProviderPayloadState();
  sourceBundlePanel.hidden = true;
  presentationRequestPanel.hidden = true;
  presentationEnginePanel.hidden = true;
}

async function generateSourceBundle() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "先に保存済みKnowledgeを開いてください。";
    return;
  }
  generateSourceBundleButton.disabled = true;
  sourceBundlePanel.hidden = true;
  resetPresentationArtifactState();
  executeDummyAdapterButton.disabled = true;
  resetProviderPayloadState();
  presentationEnginePanel.hidden = true;
  knowledgeEditorMessage.textContent =
    "Registryへ保存済みの版からSource Bundleを生成しています…";
  try {
    const response = await fetch(
      "/api/source-bundles/" + encodeURIComponent(record.knowledge_id),
      { method: "POST" },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message || "Source Bundleを生成できませんでした。",
      );
    }
    sourceBundleOutput.textContent = JSON.stringify(payload.bundle, null, 2);
    const canPublish = payload.approval_gate.can_publish;
    const canSend = payload.approval_gate.can_send_to_external_ai;
    setText(
      "#sourceBundleApprovalState",
      registryStatusLabels[payload.bundle.metadata.approval_state] ||
        payload.bundle.metadata.approval_state,
    );
    setText("#sourceBundleCanPublish", canPublish.allowed ? "許可" : "停止");
    setText("#sourceBundleCanSend", canSend.allowed ? "許可" : "停止");
    sourceBundleGateReason.textContent =
      canSend.reason + " · 監査ログ：" + payload.audit_log_path;
    sourceBundleGateReason.className = canSend.allowed
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    sourceBundleMessage.textContent =
      "保存先：" + payload.output_path +
      " · Knowledge v" + payload.bundle.metadata.version +
      " · " + (registryStatusLabels[payload.bundle.metadata.approval_state] ||
        payload.bundle.metadata.approval_state) +
      " · KnowledgeとRegistryは変更していません。";
    sourceBundlePanel.hidden = false;
    generatePresentationRequestButton.disabled = false;
    presentationRequestPanel.hidden = true;
    resetPresentationArtifactState();
    presentationEnginePanel.hidden = true;
    resetProviderPayloadState();
    knowledgeEditorMessage.textContent =
      "Source Bundle JSON Version 1.0を生成・保存しました。";
    sourceBundlePanel.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error
        ? error.message
        : "Source Bundle生成の通信に失敗しました。";
  } finally {
    generateSourceBundleButton.disabled = false;
  }
}

async function generatePresentationRequest() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "先に保存済みKnowledgeを開いてください。";
    return;
  }
  generatePresentationRequestButton.disabled = true;
  executeDummyAdapterButton.disabled = true;
  presentationRequestPanel.hidden = true;
  resetPresentationArtifactState();
  presentationEnginePanel.hidden = true;
  resetProviderPayloadState();
  const mode = presentationRequestMode.value;
  knowledgeEditorMessage.textContent =
    (mode === "external" ? "External" : "Preview") +
    " Presentation Requestを検証しています…";
  try {
    const response = await fetch(
      "/api/presentation-requests/" + encodeURIComponent(record.knowledge_id),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_mode: mode,
          profile_id: "presentation_document_basic_v1",
          profile_version: "1.0",
        }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message ||
          "Presentation Requestを生成できませんでした。",
      );
    }
    const context = payload.request_context;
    setText("#presentationType", context.presentation_type);
    setText("#presentationOutputFormat", context.output_format);
    setText(
      "#presentationProfile",
      context.profile_id + " v" + context.profile_version,
    );
    setText("#presentationMode", context.request_mode);
    setText(
      "#presentationApprovalState",
      registryStatusLabels[context.approval_state] || context.approval_state,
    );
    setText("#presentationKnowledgeVersion", "v" + context.knowledge_version);
    setText("#presentationClaimCount", String(context.claim_count));
    setText("#presentationKeyMessageCount", String(context.key_message_count));
    setText("#presentationDiagramCount", String(context.diagram_request_count));
    setText(
      "#presentationExternalUse",
      payload.decision.external_use_allowed ? "許可" : "停止",
    );
    setText("#presentationFingerprint", context.source_fingerprint);
    presentationRequestReason.textContent =
      payload.decision.reason +
      " · Freshness " +
      (payload.decision.freshness.is_current ? "OK" : "NG") +
      " · 監査ログ：" +
      payload.audit_log_path;
    presentationRequestReason.className = payload.decision.allowed
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    setText(
      "#presentationRequestPath",
      payload.output_path
        ? "保存先：" + payload.output_path
        : "停止理由：" + payload.decision.reason_code + " · JSONは保存していません。",
    );
    presentationRequestOutput.textContent = payload.request
      ? JSON.stringify(payload.request, null, 2)
      : "Presentation Requestは生成されませんでした。";
    presentationRequestPanel.hidden = false;
    executeDummyAdapterButton.disabled = !payload.decision.allowed;
    generatePresentationArtifactButton.disabled = !payload.decision.allowed;
    generateProviderPayloadButton.disabled = !payload.decision.allowed;
    knowledgeEditorMessage.textContent = payload.decision.allowed
      ? "Presentation Request JSON Version 1.0を生成・保存しました。"
      : "安全確認によりPresentation Request生成を停止しました。";
    presentationRequestPanel.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error
        ? error.message
        : "Presentation Request生成の通信に失敗しました。";
  } finally {
    generatePresentationRequestButton.disabled = false;
  }
}

function resetPresentationArtifactState() {
  generatePresentationArtifactButton.disabled = true;
  presentationArtifactPanel.hidden = true;
  presentationArtifactOutput.textContent = "";
  presentationArtifactPages.replaceChildren();
}

async function generatePresentationArtifact() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "先に保存済みKnowledgeを開いてください。";
    return;
  }
  const mode = presentationRequestMode.value;
  const actor = document.querySelector("#knowledgeEditorActor").value.trim();
  const reviewComment = document.querySelector("#knowledgeEditorComment").value.trim();
  generatePresentationArtifactButton.disabled = true;
  presentationArtifactPanel.hidden = true;
  knowledgeEditorMessage.textContent =
    "Presentation Artifactを構成・検証しています…";
  try {
    const response = await fetch(
      "/api/presentation-artifacts/" + encodeURIComponent(record.knowledge_id),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_mode: mode,
          owner: actor || "product_owner",
          actor: actor || "product_owner",
          review_comment: reviewComment || "Presentation Artifact登録",
        }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message ||
          "Presentation Artifactを生成できませんでした。",
      );
    }
    const context = payload.artifact_context;
    setText("#artifactId", context.artifact_id || "--");
    setText("#artifactVersion", context.artifact_version ? "v" + context.artifact_version : "--");
    setText("#artifactPageCount", String(context.page_count));
    setText("#artifactClaimCount", String(context.claim_count));
    setText("#artifactDiagramCount", String(context.diagram_count));
    setText("#artifactReferenceCount", String(context.reference_count));
    setText("#artifactValidation", context.validation === "passed" ? "OK" : "NG");
    setText("#artifactBuilderVersion", "v" + context.builder_version);
    setText("#artifactFingerprint", context.fingerprint || "--");
    setText(
      "#presentationArtifactPath",
      payload.artifact_registry_path
        ? "正本台帳：" + payload.artifact_registry_path
        : "Validation失敗のため保存していません。",
    );
    const artifact = payload.artifact;
    presentationArtifactOutput.textContent = artifact
      ? JSON.stringify(artifact, null, 2)
      : "Artifactは保存されませんでした。";
    presentationArtifactPages.replaceChildren();
    for (const page of artifact?.pages || []) {
      const card = document.createElement("div");
      card.className = "artifact-page-card";
      const headline = document.createElement("strong");
      headline.textContent = "Page " + page.page_number + " · " + page.headline;
      const summary = document.createElement("span");
      const diagrams = page.diagram_instruction?.items?.length || 0;
      summary.textContent =
        "Claim " + page.supporting_claim_ids.length +
        "件 · Diagram " + diagrams +
        "件 · Reference " + page.reference_ids.length + "件";
      card.append(headline, summary);
      presentationArtifactPages.append(card);
    }
    setText(
      "#presentationArtifactMessage",
      payload.validation.is_valid
        ? "Validation OK · Artifact Registryへdraftとして保存しました。Knowledge Registryは変更していません。"
        : "Validation NG · Artifactは保存していません。",
    );
    presentationArtifactPanel.hidden = false;
    knowledgeEditorMessage.textContent = payload.validation.is_valid
      ? "Presentation Artifactを生成し、専用RegistryへVersion保存しました。"
      : "Artifact Validationが失敗しました。";
    await refreshArtifactRegistryList(false, context.artifact_id);
    presentationArtifactPanel.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error
        ? error.message
        : "Presentation Artifact生成の通信に失敗しました。";
  } finally {
    generatePresentationArtifactButton.disabled = false;
  }
}

function resetProviderPayloadState() {
  generateProviderPayloadButton.disabled = true;
  executeTraceableDummyButton.disabled = true;
  generatePresentationPromptButton.disabled = true;
  executeGeminiSandboxButton.disabled = true;
  providerPayloadPanel.hidden = true;
  traceableResponsePanel.hidden = true;
  presentationPromptPanel.hidden = true;
  geminiSandboxPanel.hidden = true;
}

async function generateProviderPayload() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "先に保存済みKnowledgeを開いてください。";
    return;
  }
  generateProviderPayloadButton.disabled = true;
  executeTraceableDummyButton.disabled = true;
  generatePresentationPromptButton.disabled = true;
  executeGeminiSandboxButton.disabled = true;
  providerPayloadPanel.hidden = true;
  traceableResponsePanel.hidden = true;
  presentationPromptPanel.hidden = true;
  geminiSandboxPanel.hidden = true;
  const mode = presentationRequestMode.value;
  knowledgeEditorMessage.textContent =
    "承認済み正本からProvider Payloadを安全確認しています…";
  try {
    const response = await fetch(
      "/api/provider-payloads/" + encodeURIComponent(record.knowledge_id),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_mode: mode, adapter: "dummy" }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message || "Provider Payloadを確認できませんでした。",
      );
    }
    const context = payload.payload_context;
    const validation = payload.validation;
    setText("#payloadId", context.payload_id);
    setText("#payloadContractVersion", "v" + context.payload_contract_version);
    setText("#payloadRequestId", context.request_id);
    setText(
      "#payloadKnowledge",
      context.knowledge_id + " v" + context.knowledge_version,
    );
    setText(
      "#payloadApprovalState",
      registryStatusLabels[context.approval_state] || context.approval_state,
    );
    setText("#payloadClaimCount", String(context.claim_count));
    setText("#payloadKeyMessageCount", String(context.key_message_count));
    setText("#payloadExamPointCount", String(context.exam_point_count));
    setText("#payloadDiagramCount", String(context.diagram_request_count));
    setText("#payloadReferenceCount", String(context.reference_count));
    setText("#payloadEgressResult", validation.egress_policy_result ? "OK" : "停止");
    setText("#payloadSecretResult", validation.secret_scan_result ? "OK" : "検出");
    setText("#payloadStaleResult", validation.stale_check_result ? "OK" : "不一致");
    setText("#payloadExternalUse", context.external_use_allowed ? "許可" : "停止");
    setText("#payloadFingerprint", context.payload_fingerprint || "未生成");
    providerPayloadReason.textContent =
      (payload.stop_reasons.length
        ? "停止理由：" + payload.stop_reasons.join(" / ")
        : "承認・Stale・Secret・Data Egress検証に合格しました。") +
      " · 監査ログ：" +
      payload.audit_log_path;
    providerPayloadReason.className = payload.validation.is_valid
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    document.querySelector("#providerPayloadMessage").textContent =
      payload.output_path
        ? "保存先：" + payload.output_path + " · 外部AI通信なし"
        : "安全確認によりJSONは生成・保存していません。";
    providerPayloadOutput.textContent = payload.payload
      ? JSON.stringify(payload.payload, null, 2)
      : "Provider Payloadは生成されませんでした。";
    providerPayloadPanel.hidden = false;
    executeTraceableDummyButton.disabled = payload.status !== "success";
    generatePresentationPromptButton.disabled = payload.status !== "success";
    knowledgeEditorMessage.textContent = payload.validation.is_valid
      ? "Provider Payload JSON Version 1.0を生成・保存しました。"
      : "未承認または安全検証によりProvider Payload生成を停止しました。";
    providerPayloadPanel.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error
        ? error.message
        : "Provider Payload確認の通信に失敗しました。";
  } finally {
    generateProviderPayloadButton.disabled = false;
  }
}

async function executeTraceableDummy() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "先に保存済みKnowledgeを開いてください。";
    return;
  }
  executeTraceableDummyButton.disabled = true;
  traceableResponsePanel.hidden = true;
  const mode = presentationRequestMode.value;
  knowledgeEditorMessage.textContent =
    "Traceable Dummy Responseを検証しています…";
  try {
    const response = await fetch(
      "/api/provider-payloads/" +
        encodeURIComponent(record.knowledge_id) +
        "/execute-dummy",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_mode: mode, adapter: "dummy" }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message || "Traceable Dummyを実行できませんでした。",
      );
    }
    const context = payload.response_context;
    setText("#traceResponseId", context.response_id);
    setText(
      "#traceProvider",
      context.provider + " v" + context.provider_version,
    );
    setText("#traceStatus", context.execution_status);
    setText("#traceFingerprint", context.payload_fingerprint_match ? "一致" : "不一致");
    setText("#traceClaimCount", String(context.used_claim_count));
    setText("#traceDiagramCount", String(context.used_diagram_request_count));
    setText("#traceReferenceCount", String(context.used_reference_count));
    setText("#traceValidation", context.validation_result ? "OK" : "NG");
    document.querySelector("#traceableResponseMessage").textContent =
      "Traceable Response Contract Version 1.0 · 医学本文をResultへ複製していません。";
    traceableResponseReason.textContent =
      "外部AI通信なし · 保存先：" + payload.output_path +
      " · 監査ログ：" + payload.audit_log_path;
    traceableResponseReason.className = context.validation_result
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    traceableResponseOutput.textContent = JSON.stringify(payload.response, null, 2);
    traceableResponsePanel.hidden = false;
    knowledgeEditorMessage.textContent = context.validation_result
      ? "Traceable Dummy Responseの検証が成功しました。"
      : "Traceable Response Validationにより停止しました。";
    traceableResponsePanel.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error
        ? error.message
        : "Traceable Dummy実行の通信に失敗しました。";
  } finally {
    executeTraceableDummyButton.disabled = false;
  }
}

async function generatePresentationPrompt() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "先に保存済みKnowledgeを開いてください。";
    return;
  }
  generatePresentationPromptButton.disabled = true;
  executeGeminiSandboxButton.disabled = true;
  presentationPromptPanel.hidden = true;
  geminiSandboxPanel.hidden = true;
  const mode = presentationRequestMode.value;
  knowledgeEditorMessage.textContent =
    "Providerに依存しないPresentation Promptを生成しています…";
  try {
    const response = await fetch(
      "/api/presentation-prompts/" + encodeURIComponent(record.knowledge_id),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_mode: mode }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message || "Presentation Promptを生成できませんでした。",
      );
    }
    const context = payload.prompt_context;
    setText("#promptId", context.prompt_id);
    setText("#promptBuilderVersion", "v" + context.prompt_builder_version);
    setText("#promptProviderNeutral", context.provider_neutral ? "OK" : "NG");
    setText(
      "#promptApprovalState",
      registryStatusLabels[context.approval_state] || context.approval_state,
    );
    setText("#promptRequestMode", context.request_mode);
    setText("#promptClaimCount", String(context.claim_count));
    setText("#promptKeyMessageCount", String(context.key_message_count));
    setText("#promptDiagramCount", String(context.diagram_request_count));
    setText("#promptReferenceCount", String(context.reference_count));
    setText("#promptValidation", payload.validation.is_valid ? "OK" : "NG");
    setText("#promptFingerprint", context.prompt_fingerprint || "未生成");
    document.querySelector("#presentationPromptMessage").textContent =
      payload.output_path
        ? "保存先：" + payload.output_path + " · Provider固有情報なし"
        : "安全確認によりPromptは生成・保存していません。";
    presentationPromptReason.textContent =
      (payload.stop_reasons.length
        ? "停止理由：" + payload.stop_reasons.join(" / ")
        : "承認・Fingerprint・Claim本文一致を確認しました。") +
      " · 監査ログ：" +
      payload.audit_log_path;
    presentationPromptReason.className = payload.validation.is_valid
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    presentationPromptOutput.textContent = payload.prompt
      ? JSON.stringify(payload.prompt, null, 2)
      : "Presentation Promptは生成されませんでした。";
    presentationPromptPanel.hidden = false;
    executeGeminiSandboxButton.disabled =
      payload.status !== "success" || mode !== "external";
    knowledgeEditorMessage.textContent = payload.validation.is_valid
      ? "Provider-neutral Presentation Promptを生成しました。"
      : "Presentation Promptの安全検証により停止しました。";
    presentationPromptPanel.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error
        ? error.message
        : "Presentation Prompt生成の通信に失敗しました。";
  } finally {
    generatePresentationPromptButton.disabled = false;
  }
}

async function prepareGeminiAcceptance() {
  prepareGeminiAcceptanceButton.disabled = true;
  executeGeminiAcceptanceButton.disabled = true;
  geminiAcceptanceResultPanel.hidden = true;
  document.querySelector("#geminiAcceptanceMessage").textContent =
    "隔離Fixtureを組み立て、送信前の安全条件を確認しています…";
  try {
    const response = await fetch("/api/gemini-acceptance/preflight", {
      method: "POST",
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message || "送信前確認を作成できませんでした。",
      );
    }
    const preflight = payload.preflight;
    const check = (value) => (value ? "OK" : "NG");
    geminiAcceptanceFingerprint = preflight.payload_fingerprint;
    geminiAcceptanceExecutionStarted = preflight.already_executed;
    setText(
      "#acceptanceProviderMode",
      preflight.provider + " / " + preflight.mode,
    );
    setText("#acceptanceModel", preflight.model);
    setText(
      "#acceptanceFixture",
      preflight.knowledge_id + " / fixture_mode=" + preflight.fixture_mode,
    );
    setText("#acceptanceApproval", preflight.approval_state);
    setText(
      "#acceptanceCounts",
      preflight.claim_count + " / " + preflight.reference_count,
    );
    setText(
      "#acceptanceLayout",
      preflight.diagram_request_count + " / " + preflight.page_count,
    );
    setText(
      "#acceptanceSafety",
      check(preflight.data_egress_policy_result) +
        " / " +
        check(preflight.secret_scan_result),
    );
    setText(
      "#acceptanceIntegrity",
      check(preflight.stale_check_result) +
        " / " +
        check(preflight.fingerprint_result),
    );
    setText("#acceptanceCharacters", String(preflight.send_character_count));
    setText("#acceptanceMaxTokens", String(preflight.max_output_tokens));
    setText(
      "#acceptanceLimits",
      preflight.retry_limit + " / " + preflight.timeout_seconds + "秒",
    );
    setText(
      "#acceptanceExternal",
      "外部通信あり / API Key " +
        (preflight.api_key_configured ? "設定済み" : "未設定"),
    );
    setText("#acceptanceFingerprint", preflight.payload_fingerprint);
    geminiAcceptancePreflight.hidden = false;
    const reason = document.querySelector("#geminiAcceptanceReason");
    reason.textContent = preflight.can_execute
      ? "全条件OKです。次のボタンを押すと、隔離FixtureをGeminiへ1回だけ送信します。"
      : "停止理由：" + preflight.stop_reasons.join(" / ");
    reason.className = preflight.can_execute
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    document.querySelector("#geminiAcceptanceMessage").textContent =
      "送信前確認が完了しました。この時点では外部通信していません。";
    executeGeminiAcceptanceButton.disabled = !preflight.can_execute;
  } catch (error) {
    document.querySelector("#geminiAcceptanceMessage").textContent =
      error instanceof Error ? error.message : "送信前確認に失敗しました。";
  } finally {
    prepareGeminiAcceptanceButton.disabled = geminiAcceptanceExecutionStarted;
  }
}

async function executeGeminiAcceptance() {
  if (!geminiAcceptanceFingerprint || geminiAcceptanceExecutionStarted) {
    return;
  }
  geminiAcceptanceExecutionStarted = true;
  executeGeminiAcceptanceButton.disabled = true;
  prepareGeminiAcceptanceButton.disabled = true;
  document.querySelector("#geminiAcceptanceMessage").textContent =
    "隔離FixtureをGeminiへ送信しています。この実行は1回だけです…";
  try {
    const response = await fetch("/api/gemini-acceptance/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        confirm_external_communication: true,
        payload_fingerprint: geminiAcceptanceFingerprint,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message || "実API受入テストを実行できませんでした。",
      );
    }
    const result = payload.result;
    const usage = result.token_usage;
    const check = (value) => (value ? "OK" : "NG");
    setText("#acceptanceResultStatus", result.status);
    setText(
      "#acceptanceResultTransport",
      (result.http_status ?? "未取得") + " / " +
        (result.provider_request_id ?? "未取得"),
    );
    setText("#acceptanceResultValidation", result.validation_result);
    setText(
      "#acceptanceResultTraceability",
      check(result.claim_traceability_result) +
        " / " +
        check(result.reference_traceability_result),
    );
    setText(
      "#acceptanceResultTokens",
      (usage.prompt_tokens ?? "?") +
        " + " +
        (usage.completion_tokens ?? "?") +
        " = " +
        (usage.total_tokens ?? "?"),
    );
    setText(
      "#acceptanceResultCost",
      usage.cost_status === "calculated"
        ? "$" + usage.estimated_cost_usd
        : "未計算",
    );
    setText(
      "#acceptanceResultTiming",
      result.duration_ms + " ms / retry " + result.retry_count,
    );
    setText(
      "#acceptanceResultRegistry",
      result.production_registry_unchanged ? "変更なし" : "変更検出",
    );
    setText(
      "#acceptanceResultStorage",
      check(result.audit_saved) + " / " + check(result.response_metadata_saved),
    );
    setText(
      "#acceptanceResultEnvironment",
      result.execution_environment + " / fixture=" + result.fixture_mode,
    );
    const reason = document.querySelector("#geminiAcceptanceResultReason");
    reason.textContent = result.error_code
      ? "結果：" + result.error_code + " · " + result.error_message
      : "実API通信とResponse Validationが完了しました。";
    reason.className = result.status === "success"
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    geminiAcceptanceResultPanel.hidden = false;
    document.querySelector("#geminiAcceptanceMessage").textContent =
      "受入テストは完了しました。再実行にはWorkbenchの再起動が必要です。";
    geminiAcceptanceResultPanel.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  } catch (error) {
    document.querySelector("#geminiAcceptanceMessage").textContent =
      error instanceof Error ? error.message : "実API受入テストに失敗しました。";
  }
}

async function executeGeminiSandbox() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "先に保存済みKnowledgeを開いてください。";
    return;
  }
  executeGeminiSandboxButton.disabled = true;
  geminiSandboxPanel.hidden = true;
  knowledgeEditorMessage.textContent =
    "Approval GateとFingerprintを確認してGemini Sandboxを実行しています…";
  try {
    const response = await fetch(
      "/api/presentation-prompts/" +
        encodeURIComponent(record.knowledge_id) +
        "/execute-gemini",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_mode: "external" }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message || "Gemini Sandboxを実行できませんでした。",
      );
    }
    const report = payload.sandbox_report;
    const validation = payload.response.validation;
    const usage = report.usage;
    setText("#geminiProvider", report.provider + " / Adapter v" + report.adapter_version);
    setText("#geminiModel", report.model);
    setText("#geminiStatus", report.status);
    setText("#geminiApiCalled", report.external_ai_called ? "実行" : "停止");
    setText("#geminiAttempts", String(report.attempt_count));
    setText("#geminiPromptTokens", usage.prompt_tokens ?? "未取得");
    setText("#geminiCompletionTokens", usage.completion_tokens ?? "未取得");
    setText("#geminiTotalTokens", usage.total_tokens ?? "未取得");
    setText(
      "#geminiEstimatedCost",
      usage.estimated_cost_usd === null
        ? "料金設定なし"
        : "$" + usage.estimated_cost_usd,
    );
    setText("#geminiDuration", report.duration_ms + " ms");
    setText("#geminiValidation", validation.is_valid ? "OK" : "NG");
    setText(
      "#geminiPromptVisibility",
      payload.gemini_prompt_visible ? "Debug表示" : "非表示",
    );
    document.querySelector("#geminiSandboxMessage").textContent =
      "Gemini固有PromptとAPIキーは通常画面・監査ログへ保存しません。";
    geminiSandboxReason.textContent =
      (report.error_code
        ? "停止理由：" + report.error_code + " · " + report.error_message
        : "Gemini Sandbox応答をTraceable Responseへ変換しました。") +
      " · 監査ログ：" +
      report.audit_log_path;
    geminiSandboxReason.className = validation.is_valid
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    geminiSandboxOutput.textContent = JSON.stringify(
      { response: payload.response, report },
      null,
      2,
    );
    const debugOutput = document.querySelector("#geminiPromptDebugOutput");
    debugOutput.hidden = !payload.gemini_prompt_visible;
    debugOutput.textContent = payload.gemini_prompt_debug || "";
    geminiSandboxPanel.hidden = false;
    knowledgeEditorMessage.textContent = validation.is_valid
      ? "Gemini SandboxとTraceable Response Validationが成功しました。"
      : "Gemini Sandboxは安全に停止し、理由を記録しました。";
    geminiSandboxPanel.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error
        ? error.message
        : "Gemini Sandbox実行の通信に失敗しました。";
  } finally {
    executeGeminiSandboxButton.disabled = false;
  }
}

async function executeDummyAdapter() {
  let record;
  try {
    record = JSON.parse(knowledgeJsonEditor.value);
  } catch {
    knowledgeEditorMessage.textContent = "先に保存済みKnowledgeを開いてください。";
    return;
  }
  executeDummyAdapterButton.disabled = true;
  presentationEnginePanel.hidden = true;
  const mode = presentationRequestMode.value;
  knowledgeEditorMessage.textContent =
    "Dummy Adapterで" + (mode === "external" ? "External" : "Preview") +
    "フローを検証しています…";
  try {
    const response = await fetch(
      "/api/presentation-engine/" + encodeURIComponent(record.knowledge_id) +
        "/execute",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_mode: mode, adapter: "dummy" }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        payload.errors?.[0]?.message || "Dummy Adapterを実行できませんでした。",
      );
    }
    const context = payload.engine_context;
    setText("#engineMode", context.mode);
    setText("#enginePreviewSupport", payload.adapter.supports_preview ? "対応" : "非対応");
    setText("#engineExternalSupport", payload.adapter.supports_external ? "対応" : "非対応");
    setText(
      "#engineAdapter",
      payload.adapter.provider_name + " v" + payload.adapter.provider_version,
    );
    setText("#engineValidation", context.validation === "passed" ? "OK" : "NG");
    setText("#engineResultStatus", payload.result.status);
    setText("#enginePages", String(context.pages));
    setText("#engineClaims", String(context.claims_used));
    setText("#engineDiagrams", String(context.diagram_requests));
    setText("#engineReferences", String(context.references));
    setText("#engineRequestFingerprint", payload.request_fingerprint);
    presentationEngineReason.textContent =
      "Approval Gate " + (payload.approval_gate.allowed ? "許可" : "確認済み") +
      " · 外部AI通信なし · 監査ログ：" + payload.audit_log_path;
    presentationEngineReason.className = payload.result.validation_result.is_valid
      ? "source-bundle-gate-reason allowed"
      : "source-bundle-gate-reason blocked";
    document.querySelector("#presentationEngineMessage").textContent =
      "Presentation Result Contract Version 1.0 · " + context.output_type +
      " · KnowledgeとRegistryは変更していません。";
    presentationResultOutput.textContent = JSON.stringify(payload.result, null, 2);
    presentationEnginePanel.hidden = false;
    knowledgeEditorMessage.textContent = payload.result.validation_result.is_valid
      ? "Dummy Adapterの全フロー検証が成功しました。"
      : "Presentation Result Validationにより停止しました。";
    presentationEnginePanel.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  } catch (error) {
    knowledgeEditorMessage.textContent =
      error instanceof Error
        ? error.message
        : "Dummy Adapter実行の通信に失敗しました。";
  } finally {
    executeDummyAdapterButton.disabled = false;
  }
}

document.querySelector("#copyButton").addEventListener("click", async (event) => {
  await navigator.clipboard.writeText(jsonOutput.textContent);
  event.currentTarget.textContent = "コピー済み";
  window.setTimeout(() => {
    event.currentTarget.textContent = "コピー";
  }, 1300);
});

function renderResult(
  data,
  knowledgeCompleteness,
  examMetadata,
  examCompleteness,
  registry,
  relations,
) {
  document.querySelector("#canonicalName").textContent = data.term.canonical_name;
  document.querySelector("#knowledgeId").textContent = data.knowledge_id;
  document.querySelector("#classification").textContent =
    termTypeLabels[data.classification.term_type] || data.classification.term_type;
  document.querySelector("#examDomain").textContent =
    examDomainLabels[data.classification.primary_exam_domain] ||
    data.classification.primary_exam_domain;

  renderClaimList("#definitions", data.core_facts.definitions);
  const templateId = data.category_content.template_id;
  if (templateId === "test_item_v1.0") {
    const content = data.category_content.test_item;
    document.querySelector("#biologicalBasisTitle").textContent = "生物学的基盤";
    document.querySelector("#analyteCharacteristicsTitle").textContent = "検査対象の特徴";
    renderClaimList("#biologicalBasis", content.biological_basis);
    renderClaimList("#analyteCharacteristics", content.analyte_characteristics);
  } else if (templateId === "staining_method_v1.0") {
    const content = data.category_content.staining_method;
    document.querySelector("#biologicalBasisTitle").textContent = "対象構造";
    document.querySelector("#analyteCharacteristicsTitle").textContent = "染色原理";
    renderClaimList("#biologicalBasis", content.target_structures);
    renderClaimList("#analyteCharacteristics", content.staining_principles);
  } else if (templateId === "specimen_v1.0") {
    const content = data.category_content.specimen;
    document.querySelector("#biologicalBasisTitle").textContent = "概要";
    document.querySelector("#analyteCharacteristicsTitle").textContent = "使用用途";
    renderClaimList("#biologicalBasis", content.overview);
    renderClaimList("#analyteCharacteristics", content.uses);
  } else if (templateId === "reagent_v1.0") {
    const content = data.category_content.reagent;
    document.querySelector("#biologicalBasisTitle").textContent = "用途";
    document.querySelector("#analyteCharacteristicsTitle").textContent = "使用工程";
    renderClaimList("#biologicalBasis", content.purposes);
    renderClaimList("#analyteCharacteristics", content.usage_steps);
  } else if (templateId === "biological_structure_v1.0") {
    const content = data.category_content.biological_structure;
    document.querySelector("#biologicalBasisTitle").textContent = "概要";
    document.querySelector("#analyteCharacteristicsTitle").textContent = "主な機能";
    renderClaimList("#biologicalBasis", content.overview);
    renderClaimList("#analyteCharacteristics", content.main_functions);
  } else if (templateId === "disease_v1.0") {
    const content = data.category_content.disease;
    document.querySelector("#biologicalBasisTitle").textContent = "病態";
    document.querySelector("#analyteCharacteristicsTitle").textContent = "主な検査所見";
    renderClaimList("#biologicalBasis", content.pathophysiology);
    renderClaimList("#analyteCharacteristics", content.main_laboratory_findings);
  } else {
    const content = data.category_content.laboratory_test_item;
    document.querySelector("#biologicalBasisTitle").textContent = "臨床的意義";
    document.querySelector("#analyteCharacteristicsTitle").textContent = "測定対象";
    renderClaimList("#biologicalBasis", content.clinical_significance);
    renderClaimList("#analyteCharacteristics", content.measured_targets);
  }
  renderSystemMetadata(data, examMetadata);
  renderCategoryContent(data);
  renderKnowledgeCompleteness(knowledgeCompleteness);
  renderExamCompleteness(examCompleteness);
  renderExamMetadata(data, examMetadata);
  renderRegistry(registry);
  renderKnowledgeRelations(relations);
  setSourceBundleAvailability(data, registry !== null);

  jsonOutput.textContent = JSON.stringify(
    {
      knowledge: data,
      exam_metadata: examMetadata,
      knowledge_registry: registry,
      knowledge_relations: relations,
    },
    null,
    2,
  );
  resultPanel.hidden = false;
  if (
    [
      "staining_method",
      "specimen",
      "reagent",
      "biological_structure",
      "disease",
      "laboratory_test_item",
    ].includes(data.classification.term_type)
  ) {
    knowledgeJsonEditor.value = JSON.stringify(data, null, 2);
    saveKnowledgeButton.disabled = false;
  }
  const scrollTarget = registry === null
    ? resultPanel
    : document.querySelector("#registryPanel");
  scrollTarget.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderRegistry(registry) {
  const panel = document.querySelector("#registryPanel");
  if (registry === null) {
    panel.hidden = true;
    knowledgeApprovalSummary.hidden = true;
    return;
  }
  currentRegistry = registry;
  const knowledge = registry.knowledge;
  knowledgeApprovalSummary.hidden = false;
  setText(
    "#knowledgeApprovalState",
    registryStatusLabels[knowledge.status] || knowledge.status,
  );
  setText("#knowledgeReviewVersion", "v" + knowledge.knowledge_version);
  setText(
    "#knowledgeExternalAiRule",
    knowledge.status === "approved" ? "送信可能" : "送信停止",
  );
  const validationBadge = document.querySelector("#registryValidationBadge");
  validationBadge.textContent = registry.validation.is_valid
    ? "Registry Validation OK"
    : "Registry要修正";
  validationBadge.className = registry.validation.is_valid
    ? "badge success"
    : "badge warning";

  const statusBadge = document.querySelector("#registryStatusBadge");
  statusBadge.textContent = registryStatusLabels[knowledge.status] || knowledge.status;
  statusBadge.className = knowledge.status === "approved"
    ? "badge success"
    : knowledge.status === "draft"
      ? "badge warning"
      : "badge neutral";

  setText("#registryKnowledgeVersion", "v" + knowledge.knowledge_version);
  setText("#registryClaimCount", registry.claims.length + "件");
  setText("#registryHistoryCount", registry.history.length + "件");
  const latestApproval = knowledge.approval.at(-1);
  setText(
    "#registryApprovalStatus",
    latestApproval
      ? registryStatusLabels[latestApproval.status] || latestApproval.status
      : "未承認",
  );
  const activeClaims = registry.claims.filter(
    (claim) => !claim.is_deleted && claim.status !== "deprecated",
  );
  setText(
    "#registryUnapprovedCount",
    activeClaims.filter((claim) => claim.status !== "approved").length + "件",
  );
  setText("#registryMergeCount", registry.merge_redirects.length + "件");
  setText(
    "#registryAliases",
    knowledge.aliases.length === 0 ? "なし" : knowledge.aliases.join("、"),
  );

  renderClaimDictionary(registry.claims);
  renderMergeCandidates(registry.merge_candidates);
  renderMergeRedirects(registry.merge_redirects);
  renderRegistryHistory(registry.history);
  updateRegistryKnowledgeOption(knowledge);
  clearRegistryOperationMessage();
  if (!registry.validation.is_valid) {
    showRegistryOperationMessage(registry.validation.errors.join(" / "), "error");
  }
  panel.hidden = false;
}

function renderKnowledgeRelations(view) {
  const container = document.querySelector("#knowledgeRelationList");
  const badge = document.querySelector("#relationValidationBadge");
  container.replaceChildren();
  if (view === null || view === undefined) {
    badge.textContent = "Relation未対応";
    badge.className = "badge neutral";
    setText("#relationCount", "0件");
    setText("#resolvedRelationCount", "0件");
    setText("#unresolvedRelationCount", "0件");
    setText("#networkCompleteness", "0.0%");
    setText("#relationHistoryCount", "0件");
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "このKnowledgeにはRelationがありません。";
    container.appendChild(empty);
    return;
  }
  badge.textContent = view.validation.is_valid
    ? "Relation Validation OK"
    : "Relation要修正";
  badge.className = view.validation.is_valid ? "badge success" : "badge warning";
  const activeRelations = view.relations.filter((item) => item.status !== "deprecated");
  const resolved = activeRelations.filter(
    (item) => item.resolution_status === "resolved",
  );
  const unresolved = activeRelations.filter(
    (item) => item.resolution_status === "unresolved_relation",
  );
  setText("#relationCount", activeRelations.length + "件");
  setText("#resolvedRelationCount", resolved.length + "件");
  setText("#unresolvedRelationCount", unresolved.length + "件");
  const networkCompleteness = view.network_summary?.network_completeness ?? (
    activeRelations.length === 0
      ? 0
      : Math.round((resolved.length / activeRelations.length) * 1000) / 10
  );
  setText("#networkCompleteness", Number(networkCompleteness).toFixed(1) + "%");
  setText("#relationHistoryCount", view.history.length + "件");
  if (activeRelations.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "このKnowledgeにはRelationがありません。";
    container.appendChild(empty);
    return;
  }
  const relationTypeLabels = {
    uses_specimen: "使用する検体",
    uses_reagent: "使用する試薬",
    targets_structure: "対象構造",
    related_method: "関連する検査法・染色法",
  };
  activeRelations.forEach((relation) => {
    const card = document.createElement("article");
    card.className = "knowledge-relation-card";
    card.dataset.resolution = relation.resolution_status;
    const heading = document.createElement("div");
    heading.className = "relation-card-heading";
    const type = document.createElement("strong");
    type.textContent = relationTypeLabels[relation.relation_type] || relation.relation_type;
    const resolution = document.createElement("span");
    resolution.className = "relation-resolution";
    resolution.textContent = relation.resolution_status === "resolved"
      ? "解決済み"
      : "未登録・未解決";
    heading.append(type, resolution);
    const target = document.createElement("p");
    target.textContent = relation.target_label;
    const details = document.createElement("code");
    details.textContent =
      "Knowledge ID: " + (relation.target_knowledge_id || "未登録") +
      " · Resolution: " + relation.resolution_status +
      " · 根拠 " + relation.claim_id +
      " · Relation v" + relation.version;
    card.append(heading, target, details);
    const contextParts = [
      ...(relation.context?.qualifiers || []),
      relation.context?.preparation || "",
    ].filter(Boolean);
    if (contextParts.length > 0) {
      const context = document.createElement("p");
      context.className = "relation-context";
      context.textContent = "Context：" + contextParts.join(" ／ ");
      card.appendChild(context);
    }
    container.appendChild(card);
  });
}

function resolutionReportMessage(report) {
  if (!report) return "";
  return (
    " · Relation再評価 " + report.evaluated_count + "件" +
    "（解決 " + report.resolved_count + "件／未解決 " + report.unresolved_count + "件）"
  );
}

function renderResolutionReport(report) {
  const panel = document.querySelector("#resolutionReportPanel");
  if (!report) {
    panel.hidden = true;
    return;
  }
  document.querySelector("#resolutionReportText").textContent =
    "再評価 " + report.evaluated_count + "件 · 解決 " + report.resolved_count +
    "件 · 未解決のまま " + report.unresolved_count + "件 · " + report.report_id;
  panel.hidden = false;
}

function renderClaimDictionary(claims) {
  const container = document.querySelector("#claimDictionary");
  container.replaceChildren();
  const ordered = [...claims].sort((left, right) => {
    const leftDeprecated = left.status === "deprecated" || left.is_deleted ? 1 : 0;
    const rightDeprecated = right.status === "deprecated" || right.is_deleted ? 1 : 0;
    return leftDeprecated - rightDeprecated || left.claim_key.localeCompare(right.claim_key);
  });
  ordered.forEach((claim) => {
    const entry = document.createElement("article");
    entry.className = "dictionary-entry";
    entry.dataset.status = claim.status;
    const header = document.createElement("div");
    header.className = "dictionary-entry-header";
    const identity = document.createElement("div");
    const claimKey = document.createElement("code");
    claimKey.className = "claim-key";
    claimKey.textContent = claim.claim_key;
    const claimId = document.createElement("code");
    claimId.className = "claim-id";
    claimId.textContent = claim.claim_id;
    identity.append(claimKey, claimId);
    const version = document.createElement("span");
    version.className = "claim-version";
    version.textContent =
      "v" + claim.claim_version + " · " +
      (registryStatusLabels[claim.status] || claim.status);
    const assertion = document.createElement("p");
    assertion.textContent = claim.assertion;
    const controls = document.createElement("div");
    controls.className = "claim-operation-controls";
    const unavailable = claim.status === "deprecated" || claim.is_deleted;
    controls.append(
      claimChoice(
        "checkbox",
        "approval-claim",
        claim.claim_id,
        "承認対象",
        unavailable,
      ),
      claimChoice(
        "radio",
        "merge-target",
        claim.claim_id,
        "統合先",
        unavailable,
      ),
      claimChoice(
        "checkbox",
        "merge-source",
        claim.claim_id,
        "統合元",
        unavailable,
      ),
    );
    header.append(identity, version);
    entry.append(header, assertion, controls);
    container.appendChild(entry);
  });
  container.querySelectorAll(".merge-target, .merge-source").forEach((control) => {
    control.addEventListener("change", updateMergeSelectionSummary);
  });
  updateMergeSelectionSummary();
}

function claimChoice(type, className, value, text, disabled) {
  const label = document.createElement("label");
  const inputElement = document.createElement("input");
  inputElement.type = type;
  inputElement.className = className;
  inputElement.value = value;
  inputElement.disabled = disabled;
  if (type === "radio") inputElement.name = "merge-target";
  const caption = document.createElement("span");
  caption.textContent = text;
  label.append(inputElement, caption);
  return label;
}

function renderMergeCandidates(candidates) {
  const container = document.querySelector("#mergeCandidateList");
  container.replaceChildren();
  if (candidates.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "現在の規則で高い類似度の候補はありません。";
    container.appendChild(empty);
    return;
  }
  candidates.forEach((candidate) => {
    const card = document.createElement("article");
    const score = document.createElement("strong");
    score.textContent = "類似度 " + candidate.similarity_score + "%";
    const route = document.createElement("code");
    route.textContent = candidate.source_claim_key + " → " + candidate.target_claim_key;
    const reason = document.createElement("span");
    reason.textContent = candidate.reason;
    const select = document.createElement("button");
    select.type = "button";
    select.className = "secondary-action compact";
    select.textContent = "この候補を選択";
    select.addEventListener("click", () => selectMergeCandidate(candidate));
    card.append(score, route, reason, select);
    container.appendChild(card);
  });
}

function selectMergeCandidate(candidate) {
  document.querySelectorAll(".merge-target").forEach((inputElement) => {
    inputElement.checked = inputElement.value === candidate.target_claim_id;
  });
  document.querySelectorAll(".merge-source").forEach((inputElement) => {
    inputElement.checked = inputElement.value === candidate.source_claim_id;
  });
  updateMergeSelectionSummary();
}

function updateMergeSelectionSummary() {
  const target = document.querySelector(".merge-target:checked");
  const sources = [...document.querySelectorAll(".merge-source:checked")];
  setText("#mergeTargetSummary", target?.value || "未選択");
  setText(
    "#mergeSourceSummary",
    sources.length === 0 ? "未選択" : sources.map((item) => item.value).join("、"),
  );
}

function renderMergeRedirects(redirects) {
  const list = document.querySelector("#registryMergeRedirectList");
  list.replaceChildren();
  if (redirects.length === 0) {
    appendSimpleListItem(list, "統合転送はありません。");
    return;
  }
  [...redirects].reverse().forEach((redirect) => {
    const item = document.createElement("li");
    const heading = document.createElement("strong");
    heading.textContent = redirect.source_claim_key + " → " + redirect.target_claim_key;
    const ids = document.createElement("code");
    ids.textContent = redirect.source_claim_id + " → " + redirect.target_claim_id;
    const detail = document.createElement("span");
    detail.textContent =
      new Date(redirect.merged_at).toLocaleString("ja-JP") + " · " +
      redirect.actor + " · " + redirect.comment;
    item.append(heading, detail, ids);
    list.appendChild(item);
  });
}

function renderRegistryHistory(history) {
  const list = document.querySelector("#registryHistoryList");
  const actionLabels = {
    add: "追加",
    update: "更新",
    delete: "削除",
    deprecated: "deprecated",
    status_change: "状態変更",
    merge: "Claim統合",
  };
  list.replaceChildren();
  [...history].reverse().forEach((event) => {
    const item = document.createElement("li");
    const heading = document.createElement("strong");
    const version = event.to_version === null ? "" : " v" + event.to_version;
    heading.textContent =
      (actionLabels[event.action] || event.action) + " · " + event.entity_type + version;
    const timestamp = document.createElement("span");
    const comment = event.details.comment || event.details.note || event.details.reason || "";
    timestamp.textContent =
      new Date(event.occurred_at).toLocaleString("ja-JP") + " · " + event.actor +
      (comment ? " · " + comment : "");
    const id = document.createElement("code");
    id.textContent = event.entity_id;
    item.append(heading, timestamp, id);
    list.appendChild(item);
  });
}

async function runExamPreview(url, requestBody = null) {
  setImportLoading(true);
  hideImportError();
  importReportPanel.hidden = true;
  currentPreviewId = null;
  currentPreviewCanCommit = false;
  commitImportButton.disabled = true;
  try {
    const options = { method: "POST" };
    if (requestBody !== null) {
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify(requestBody);
    }
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) {
      const message =
        payload.detail?.[0]?.msg || payload.errors?.[0]?.message || "取込に失敗しました。";
      throw new Error(message);
    }
    renderImportReport(payload);
    currentPreviewId = payload.preview?.preview_id || null;
    currentPreviewCanCommit = payload.preview?.can_commit === true;
    commitImportButton.disabled = !currentPreviewCanCommit;
  } catch (error) {
    showImportError(
      error instanceof Error ? error.message : "CSVの読込中に通信エラーが発生しました。",
    );
  } finally {
    setImportLoading(false);
  }
}

async function commitExamImport(previewId) {
  setImportLoading(true);
  hideImportError();
  try {
    const response = await fetch("/api/import/exam-csv/commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preview_id: previewId }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0]?.message || "Importを確定できませんでした。");
    }
    renderImportReport(payload);
    currentPreviewId = null;
    currentPreviewCanCommit = false;
    commitImportButton.disabled = true;
    await refreshRegistryList(false);
    const knowledgeId = payload.mapped_records?.[0]?.knowledge_id;
    if (knowledgeId) {
      registryKnowledgeSelect.value = knowledgeId;
      await loadSelectedRegistry();
    }
    showRegistryOperationMessage("CSV ImportをRegistryへ反映しました。", "success");
  } catch (error) {
    showImportError(
      error instanceof Error ? error.message : "Import確定中に通信エラーが発生しました。",
    );
  } finally {
    setImportLoading(false);
  }
}

function renderImportReport(payload) {
  const report = payload.report;
  const validation = report.validation;
  const badge = document.querySelector("#importStatusBadge");
  badge.textContent = payload.phase === "imported"
    ? "Import完了"
    : validation.can_import
      ? "Preview OK・未反映"
      : "要修正・未反映";
  badge.className = validation.can_import ? "badge success" : "badge warning";

  setText("#normalizedCount", report.normalized_record_count + "件");
  setText("#mappedCount", report.mapped_record_count + "件");
  setText("#metadataCount", report.metadata_record_count + "件");
  setText("#imageMappedCount", report.image_mapped_count + "件");
  setText("#imageWarningCount", report.image_warning_count + "件");
  setText("#addedRows", report.diff.added_source_row_ids.length + "件");
  setText("#removedRows", report.diff.removed_source_row_ids.length + "件");
  setText("#unchangedRows", report.diff.unchanged_source_row_ids.length + "件");
  const preview = payload.preview;
  setText("#previewNewKnowledge", (preview?.new_knowledge_ids.length || 0) + "件");
  setText(
    "#previewUpdatedKnowledge",
    (preview?.updated_knowledge_ids.length || 0) + "件",
  );
  setText("#previewUnknownTerms", (preview?.unknown_terms.length || 0) + "件");
  setText(
    "#previewMappingFailures",
    (preview?.mapping_failures.length || 0) + "件",
  );
  setText("#previewMissingImages", (preview?.missing_images.length || 0) + "件");
  setText(
    "#previewUnsupportedClaims",
    (preview?.unsupported_claims.length || 0) + "件",
  );
  setValueList("#missingColumns", validation.required_columns_missing);
  setValueList(
    "#unmappedFields",
    [...validation.optional_fields_unmapped, ...validation.ambiguous_mappings],
  );
  setValueList("#unusedColumns", validation.unused_columns);
  setValueList("#unknownColumns", validation.unknown_columns);
  setValueList("#duplicateColumns", validation.duplicate_columns);

  renderKnowledgeMappings(report.knowledge_mappings);
  renderImportIssues(validation.issues);
  renderPreviewDetails(preview);
  renderImportedMetadata(payload.exam_metadata, report.knowledge_mappings);
  importReportPanel.hidden = false;
  importReportPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderPreviewDetails(preview) {
  const list = document.querySelector("#previewDetailList");
  list.replaceChildren();
  if (!preview) {
    appendSimpleListItem(list, "Preview情報はありません。");
    return;
  }
  const groups = [
    ["新規Knowledge", preview.new_knowledge_ids],
    ["更新Knowledge", preview.updated_knowledge_ids],
    ["Unknown用語", preview.unknown_terms],
    ["Mapping不能", preview.mapping_failures],
    ["画像不足", preview.missing_images],
    ["Claim未対応", preview.unsupported_claims],
  ];
  groups.forEach(([label, values]) => {
    if (values.length === 0) return;
    values.forEach((value) => {
      const item = document.createElement("li");
      const heading = document.createElement("strong");
      heading.textContent = label;
      const detail = document.createElement("span");
      detail.textContent = value;
      item.append(heading, detail);
      list.appendChild(item);
    });
  });
  if (list.children.length === 0) {
    appendSimpleListItem(list, "Preview上の追加確認事項はありません。");
  }
}

function renderKnowledgeMappings(mappings) {
  const list = document.querySelector("#knowledgeMappingList");
  list.replaceChildren();
  if (mappings.length === 0) {
    appendSimpleListItem(list, "関連付け結果はありません。");
    return;
  }
  mappings.forEach((mapping) => {
    const item = document.createElement("li");
    const route = document.createElement("strong");
    route.textContent = mapping.source_theme + " → " + mapping.canonical_theme;
    const id = document.createElement("code");
    id.textContent = mapping.knowledge_id;
    item.append(route, id);
    list.appendChild(item);
  });
}

function renderImportIssues(issues) {
  const list = document.querySelector("#importIssueList");
  list.replaceChildren();
  if (issues.length === 0) {
    appendSimpleListItem(list, "Error・Warningはありません。");
    return;
  }
  issues.forEach((issue) => {
    const item = document.createElement("li");
    item.dataset.severity = issue.severity;
    const code = document.createElement("strong");
    code.textContent = issue.severity.toUpperCase() + " · " + issue.code;
    const message = document.createElement("span");
    const row = issue.source_row_number ? "（CSV " + issue.source_row_number + "行目）" : "";
    message.textContent = issue.message + row;
    item.append(code, message);
    list.appendChild(item);
  });
}

function renderImportedMetadata(records, mappings) {
  const container = document.querySelector("#importedMetadataList");
  container.replaceChildren();
  const names = Object.fromEntries(
    mappings.map((mapping) => [mapping.knowledge_id, mapping.canonical_theme]),
  );
  if (records.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "CSV Validationを修正するとExam Metadataが生成されます。";
    container.appendChild(empty);
    return;
  }
  records.forEach((metadata) => {
    const card = document.createElement("article");
    card.className = "imported-metadata-card";
    const heading = document.createElement("h4");
    heading.textContent = names[metadata.knowledge_id] || metadata.knowledge_id;
    const details = document.createElement("p");
    const imageCount = metadata.history.reduce(
      (total, occurrence) => total + occurrence.image_assets.length,
      0,
    );
    details.textContent =
      "出題 " + metadata.frequency.appearance_count + "件 · importance_score " +
      metadata.importance.importance_score + " · 重要claim " +
      metadata.priority_claims.length + "件 · 画像 " + imageCount + "件";
    const id = document.createElement("code");
    id.textContent = metadata.knowledge_id;
    card.append(heading, details, id);
    container.appendChild(card);
  });
}

async function refreshArtifactRegistryList(autoLoad, preferredArtifactId = null) {
  try {
    const response = await fetch("/api/artifact-registry");
    const payload = await response.json();
    if (!response.ok) throw new Error("Artifact Registry一覧を取得できませんでした。");
    const previous = preferredArtifactId || artifactRegistrySelect.value;
    const artifacts = payload.registry?.artifacts || [];
    artifactRegistrySelect.replaceChildren();
    if (artifacts.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Artifactはまだありません";
      artifactRegistrySelect.appendChild(option);
      artifactRegistryPanel.hidden = true;
      return;
    }
    for (const artifact of artifacts) {
      const option = document.createElement("option");
      option.value = artifact.artifact_id;
      option.textContent =
        artifact.knowledge_id + " · v" + artifact.artifact_version + " · " +
        (artifactApprovalLabels[artifact.approval_state] || artifact.approval_state);
      artifactRegistrySelect.appendChild(option);
    }
    if ([...artifactRegistrySelect.options].some((item) => item.value === previous)) {
      artifactRegistrySelect.value = previous;
    }
    if (autoLoad || preferredArtifactId) await loadSelectedArtifactRegistry();
  } catch (error) {
    setArtifactRegistryMessage(
      error instanceof Error ? error.message : "Artifact Registry一覧を表示できません。",
      "error",
    );
  }
}

async function loadSelectedArtifactRegistry() {
  const artifactId = artifactRegistrySelect.value;
  if (!artifactId) return;
  try {
    const response = await fetch(
      "/api/artifact-registry/" + encodeURIComponent(artifactId),
    );
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.errors?.[0] || "Artifact Registryを表示できません。");
    }
    currentArtifactRegistry = payload.registry;
    populateArtifactVersions(payload.registry.versions);
    renderArtifactRegistryVersion(
      payload.registry.current,
      payload.artifact,
      payload.completeness,
      payload.renderer_eligibility,
    );
    renderArtifactRegistryHistory(payload.registry);
    artifactRegistryPanel.hidden = false;
    setArtifactRegistryMessage(
      "保存済みArtifactを読み込みました。Completeness 100%は教育品質の保証ではありません。",
      "success",
    );
    artifactRegistryPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setArtifactRegistryMessage(
      error instanceof Error ? error.message : "Artifact Registryの通信に失敗しました。",
      "error",
    );
  }
}

function populateArtifactVersions(versions) {
  const selects = [
    artifactVersionSelect,
    document.querySelector("#artifactDiffFrom"),
    document.querySelector("#artifactDiffTo"),
  ];
  for (const select of selects) select.replaceChildren();
  for (const version of versions) {
    for (const select of selects) {
      const option = document.createElement("option");
      option.value = String(version.artifact_version);
      option.textContent =
        "v" + version.artifact_version + " · " +
        (artifactApprovalLabels[version.approval_state] || version.approval_state);
      select.appendChild(option);
    }
  }
  if (versions.length > 1) {
    document.querySelector("#artifactDiffFrom").value = String(
      versions[versions.length - 1].artifact_version,
    );
    document.querySelector("#artifactDiffTo").value = String(
      versions[0].artifact_version,
    );
  }
}

async function loadSelectedArtifactVersion() {
  const artifactId = artifactRegistrySelect.value;
  const version = artifactVersionSelect.value;
  if (!artifactId || !version) return;
  try {
    const response = await fetch(
      "/api/artifact-registry/" + encodeURIComponent(artifactId) +
        "/versions/" + encodeURIComponent(version),
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.errors?.[0] || "Versionを表示できません。");
    renderArtifactRegistryVersion(
      payload.version.entry,
      payload.version.artifact,
      payload.completeness,
      payload.renderer_eligibility,
    );
  } catch (error) {
    setArtifactRegistryMessage(
      error instanceof Error ? error.message : "Versionの通信に失敗しました。",
      "error",
    );
  }
}

function renderArtifactRegistryVersion(entry, artifact, completeness, eligibility) {
  artifactVersionSelect.value = String(entry.artifact_version);
  setText("#artifactRegistryVersion", "v" + entry.artifact_version);
  setText("#artifactRegistryKnowledgeVersion", "v" + entry.knowledge_version);
  setText("#artifactCompletenessScore", completeness.score + "%");
  setText("#artifactHistoryCount", String(currentArtifactRegistry?.history?.length || 0));
  setText("#artifactOwner", entry.owner);
  setText("#artifactRegistryFingerprint", entry.fingerprint);
  setText(
    "#artifactRendererEligibility",
    eligibility?.eligible ? "利用可能" : "停止",
  );
  setText(
    "#artifactReviewResult",
    eligibility?.artifact_review_result === "passed" ? "合格" : "停止",
  );
  setText(
    "#artifactKnowledgeApproval",
    eligibility?.source_knowledge_approval_state || "未確認",
  );
  setText(
    "#artifactKnowledgeVersionMatch",
    eligibility?.knowledge_version_matches ? "一致" : "不一致",
  );
  setText(
    "#artifactReviewVersionMatch",
    eligibility?.review_version_matches ? "一致" : "不一致",
  );
  setText(
    "#artifactSourceFingerprintMatch",
    eligibility?.source_fingerprint_matches ? "一致" : "不一致",
  );
  setText(
    "#artifactClaimApproval",
    eligibility?.claim_approval_valid ? "全件承認済み" : "未承認あり",
  );
  setText(
    "#artifactRendererBlockReasons",
    eligibility?.reasons?.length ? eligibility.reasons.join(" / ") : "なし",
  );
  const approvalBadge = document.querySelector("#artifactApprovalBadge");
  approvalBadge.textContent = artifactApprovalLabels[entry.approval_state] || entry.approval_state;
  approvalBadge.className =
    entry.approval_state === "approved" ? "badge success" : "badge warning";
  const validationBadge = document.querySelector("#artifactRegistryValidationBadge");
  validationBadge.textContent = completeness.is_complete ? "Completeness OK" : "要改善";
  validationBadge.className = completeness.is_complete ? "badge success" : "badge warning";
  artifactRegistryJson.textContent = JSON.stringify(artifact, null, 2);
}

function renderArtifactRegistryHistory(registry) {
  const versionList = document.querySelector("#artifactVersionList");
  versionList.replaceChildren();
  for (const version of registry.versions) {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent =
      "v" + version.artifact_version + " · " +
      (artifactApprovalLabels[version.approval_state] || version.approval_state);
    const detail = document.createElement("span");
    detail.textContent =
      "Knowledge v" + version.knowledge_version + " · " + version.updated_at;
    const fingerprint = document.createElement("code");
    fingerprint.textContent = version.fingerprint;
    item.append(title, detail, fingerprint);
    versionList.appendChild(item);
  }
  const historyList = document.querySelector("#artifactHistoryList");
  historyList.replaceChildren();
  for (const event of registry.history) {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent =
      "v" + event.artifact_version + " · " + event.event_type + " · " +
      event.to_approval_state;
    const detail = document.createElement("span");
    detail.textContent = event.changed_at + " · " + event.changed_by;
    const comment = document.createElement("code");
    comment.textContent = event.review_comment || "コメントなし";
    item.append(title, detail, comment);
    historyList.appendChild(item);
  }
  const auditList = document.querySelector("#artifactGateAuditList");
  auditList.replaceChildren();
  for (const audit of registry.gate_audit || []) {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent =
      "v" + audit.artifact_version + " · " + audit.action + " · " + audit.outcome;
    const detail = document.createElement("span");
    detail.textContent = audit.evaluated_at + " · " + audit.actor;
    const reasons = document.createElement("code");
    reasons.textContent = audit.reason_codes.length
      ? audit.reason_codes.join(" / ")
      : "停止理由なし";
    item.append(title, detail, reasons);
    auditList.appendChild(item);
  }
}

async function changeArtifactApproval() {
  const artifactId = artifactRegistrySelect.value;
  const version = artifactVersionSelect.value;
  const actor = document.querySelector("#artifactApprovalActor").value.trim();
  const reviewComment = document.querySelector("#artifactReviewComment").value.trim();
  const targetState = document.querySelector("#artifactApprovalTarget").value;
  if (!artifactId || !version || !actor || !reviewComment) {
    setArtifactRegistryMessage("Version、操作者、Review Commentが必要です。", "error");
    return;
  }
  try {
    const response = await fetch(
      "/api/artifact-registry/" + encodeURIComponent(artifactId) +
        "/versions/" + encodeURIComponent(version) + "/approval",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_state: targetState,
          actor,
          review_comment: reviewComment,
        }),
      },
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.errors?.[0] || "承認状態を変更できません。");
    await refreshArtifactRegistryList(false, artifactId);
    artifactVersionSelect.value = version;
    await loadSelectedArtifactVersion();
    setArtifactRegistryMessage(
      "Artifact v" + version + "を" + targetState + "へ変更し、履歴を保存しました。",
      "success",
    );
  } catch (error) {
    setArtifactRegistryMessage(
      error instanceof Error ? error.message : "承認操作に失敗しました。",
      "error",
    );
  }
}

async function compareArtifactVersions() {
  const artifactId = artifactRegistrySelect.value;
  const fromVersion = document.querySelector("#artifactDiffFrom").value;
  const toVersion = document.querySelector("#artifactDiffTo").value;
  if (!artifactId || !fromVersion || !toVersion) return;
  try {
    const response = await fetch(
      "/api/artifact-registry/" + encodeURIComponent(artifactId) +
        "/diff?from_version=" + encodeURIComponent(fromVersion) +
        "&to_version=" + encodeURIComponent(toVersion),
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.errors?.[0] || "差分を表示できません。");
    document.querySelector("#artifactDiffOutput").textContent = JSON.stringify(
      payload.diff,
      null,
      2,
    );
  } catch (error) {
    setArtifactRegistryMessage(
      error instanceof Error ? error.message : "差分比較に失敗しました。",
      "error",
    );
  }
}

async function checkRendererEligibility() {
  const artifactId = artifactRegistrySelect.value;
  const version = artifactVersionSelect.value;
  if (!artifactId || !version) return;
  try {
    const response = await fetch(
      "/api/artifact-registry/" + encodeURIComponent(artifactId) +
        "/render-source?artifact_version=" + encodeURIComponent(version),
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.errors?.[0] || "Renderer利用不可です。");
    const eligibility = payload.renderer_eligibility;
    setText("#artifactRendererEligibility", eligibility?.eligible ? "利用可能" : "停止");
    setText(
      "#artifactRendererBlockReasons",
      eligibility?.reasons?.length ? eligibility.reasons.join(" / ") : "なし",
    );
    setArtifactRegistryMessage(
      "Registry経由でapproved Artifactを取得できました。Rendererへ渡せます。",
      "success",
    );
  } catch (error) {
    setText("#artifactRendererEligibility", "停止");
    setArtifactRegistryMessage(
      error instanceof Error ? error.message : "Renderer利用判定に失敗しました。",
      "error",
    );
  }
}

function setArtifactRegistryMessage(message, kind) {
  const panel = document.querySelector("#artifactRegistryMessage");
  panel.textContent = message;
  panel.dataset.kind = kind;
}

async function refreshRegistryList(autoLoad) {
  try {
    const response = await fetch("/api/registry");
    const snapshot = await response.json();
    if (!response.ok) throw new Error("Registry一覧を取得できませんでした。");
    const selected = registryKnowledgeSelect.value;
    registryKnowledgeSelect.replaceChildren();
    if (snapshot.knowledge.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Registryはまだ空です";
      registryKnowledgeSelect.appendChild(option);
      document.querySelector("#registryPanel").hidden = true;
      return;
    }
    snapshot.knowledge.forEach((knowledge) => {
      const option = document.createElement("option");
      option.value = knowledge.knowledge_id;
      option.textContent =
        knowledge.canonical_name + " · v" + knowledge.knowledge_version + " · " +
        (registryStatusLabels[knowledge.status] || knowledge.status);
      registryKnowledgeSelect.appendChild(option);
    });
    if ([...registryKnowledgeSelect.options].some((item) => item.value === selected)) {
      registryKnowledgeSelect.value = selected;
    }
    if (autoLoad) await loadSelectedRegistry();
  } catch (error) {
    showRegistryOperationMessage(
      error instanceof Error ? error.message : "Registry一覧の通信に失敗しました。",
      "error",
    );
  }
}

function updateRegistryKnowledgeOption(knowledge) {
  const existing = [...registryKnowledgeSelect.options].find(
    (item) => item.value === knowledge.knowledge_id,
  );
  const option = existing || document.createElement("option");
  option.value = knowledge.knowledge_id;
  option.textContent =
    knowledge.canonical_name + " · v" + knowledge.knowledge_version + " · " +
    (registryStatusLabels[knowledge.status] || knowledge.status);
  if (!existing) registryKnowledgeSelect.appendChild(option);
  registryKnowledgeSelect.value = knowledge.knowledge_id;
}

async function loadSelectedRegistry() {
  const knowledgeId = registryKnowledgeSelect.value;
  if (!knowledgeId) return;
  try {
    const response = await fetch("/api/registry/" + encodeURIComponent(knowledgeId));
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.errors?.[0]?.message || "Registryを表示できません。");
    renderRegistry(payload);
    const recordResponse = await fetch(
      "/api/knowledge-records/" + encodeURIComponent(knowledgeId),
    );
    if (recordResponse.ok) {
      const recordPayload = await recordResponse.json();
      renderKnowledgeRelations(recordPayload.relations);
      knowledgeJsonEditor.value = JSON.stringify(recordPayload.data, null, 2);
      saveKnowledgeButton.disabled = false;
      setSourceBundleAvailability(recordPayload.data, true);
      knowledgeEditorMessage.textContent =
        "保存済みKnowledgeを編集画面へ読み込みました · Completeness " +
        recordPayload.knowledge_completeness.score + "%";
    } else {
      const relationResponse = await fetch(
        "/api/knowledge-relations/" + encodeURIComponent(knowledgeId),
      );
      if (relationResponse.ok) renderKnowledgeRelations(await relationResponse.json());
    }
    document.querySelector("#registryPanel").scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  } catch (error) {
    showRegistryOperationMessage(
      error instanceof Error ? error.message : "Registryの通信に失敗しました。",
      "error",
    );
  }
}

function registryCredentials() {
  const actor = document.querySelector("#registryActor").value.trim();
  const comment = document.querySelector("#registryComment").value.trim();
  if (!actor || !comment) {
    throw new Error("操作者とコメントを入力してください。");
  }
  return { actor, comment };
}

async function changeSelectedClaimStatus() {
  if (!currentRegistry) return;
  try {
    const { actor, comment } = registryCredentials();
    const claimIds = [...document.querySelectorAll(".approval-claim:checked")].map(
      (item) => item.value,
    );
    if (claimIds.length === 0) throw new Error("状態を変更するClaimを選択してください。");
    const targetStatus = document.querySelector("#claimTargetStatus").value;
    const payload = await postRegistryOperation(
      "/api/registry/" + currentRegistry.knowledge.knowledge_id + "/claims/status",
      { claim_ids: claimIds, target_status: targetStatus, actor, comment },
    );
    renderRegistry(payload.registry);
    showRegistryOperationMessage(
      claimIds.length + "件のClaimを" + targetStatus + "へ変更しました。",
      "success",
    );
  } catch (error) {
    showRegistryOperationMessage(
      error instanceof Error ? error.message : "Claim状態を変更できませんでした。",
      "error",
    );
  }
}

async function changeKnowledgeStatus() {
  if (!currentRegistry) return;
  try {
    const { actor, comment } = registryCredentials();
    const targetStatus = document.querySelector("#knowledgeTargetStatus").value;
    const payload = await postRegistryOperation(
      "/api/registry/" + currentRegistry.knowledge.knowledge_id + "/status",
      { target_status: targetStatus, actor, comment },
    );
    renderRegistry(payload.registry);
    showRegistryOperationMessage(
      "Knowledgeを" + targetStatus + "へ変更しました。",
      "success",
    );
  } catch (error) {
    showRegistryOperationMessage(
      error instanceof Error ? error.message : "Knowledge状態を変更できませんでした。",
      "error",
    );
  }
}

async function mergeSelectedClaims() {
  if (!currentRegistry) return;
  try {
    const { actor, comment } = registryCredentials();
    const target = document.querySelector(".merge-target:checked")?.value;
    const sources = [...document.querySelectorAll(".merge-source:checked")].map(
      (item) => item.value,
    );
    if (!target || sources.length === 0) {
      throw new Error("統合先を1件、統合元を1件以上選択してください。");
    }
    if (sources.includes(target)) {
      throw new Error("同じClaimを統合先と統合元の両方には選べません。");
    }
    const payload = await postRegistryOperation(
      "/api/registry/" + currentRegistry.knowledge.knowledge_id + "/claims/merge",
      {
        target_claim_id: target,
        source_claim_ids: sources,
        actor,
        comment,
      },
    );
    renderRegistry(payload.registry);
    showRegistryOperationMessage(
      sources.length + "件を統合し、統合先claim_idを維持しました。",
      "success",
    );
  } catch (error) {
    showRegistryOperationMessage(
      error instanceof Error ? error.message : "Claimを統合できませんでした。",
      "error",
    );
  }
}

async function postRegistryOperation(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.errors?.[0]?.message || "Registry操作に失敗しました。");
  }
  return payload;
}

function showRegistryOperationMessage(message, kind) {
  const panel = document.querySelector("#registryOperationMessage");
  panel.textContent = message;
  panel.dataset.kind = kind;
  panel.hidden = false;
}

function clearRegistryOperationMessage() {
  const panel = document.querySelector("#registryOperationMessage");
  panel.textContent = "";
  panel.hidden = true;
}

async function refreshBackups() {
  const select = document.querySelector("#backupSelect");
  try {
    const response = await fetch("/api/registry-backups");
    const payload = await response.json();
    select.replaceChildren();
    if (!payload.backups?.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Backupはまだありません";
      select.appendChild(option);
      return;
    }
    payload.backups.forEach((backup) => {
      const option = document.createElement("option");
      option.value = backup.filename;
      option.textContent =
        backup.filename + " · " + Math.ceil(backup.size_bytes / 1024) + " KB";
      select.appendChild(option);
    });
  } catch {
    document.querySelector("#backupMessage").textContent =
      "Backup一覧を取得できませんでした。";
  }
}

async function createRegistryBackup() {
  const message = document.querySelector("#backupMessage");
  try {
    const response = await fetch("/api/registry-backups", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.errors?.[0]?.message || "Backup失敗");
    message.textContent = "Backupを作成しました：" + payload.backup.filename;
    await refreshBackups();
  } catch (error) {
    message.textContent = error instanceof Error ? error.message : "Backupに失敗しました。";
  }
}

async function restoreRegistryBackup() {
  const select = document.querySelector("#backupSelect");
  const filename = select.value;
  const message = document.querySelector("#backupMessage");
  if (!filename) {
    message.textContent = "RestoreするBackupを選択してください。";
    return;
  }
  if (!window.confirm(filename + "へRegistryを戻します。よろしいですか？")) return;
  try {
    const response = await fetch("/api/registry-backups/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.errors?.[0]?.message || "Restore失敗");
    message.textContent =
      "Restoreしました。直前状態の安全Backup：" + payload.safety_backup.filename;
    currentRegistry = null;
    document.querySelector("#registryPanel").hidden = true;
    await refreshBackups();
    await refreshRegistryList(true);
  } catch (error) {
    message.textContent = error instanceof Error ? error.message : "Restoreに失敗しました。";
  }
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const commaIndex = result.indexOf(",");
      resolve(commaIndex >= 0 ? result.slice(commaIndex + 1) : result);
    });
    reader.addEventListener("error", () => reject(new Error("CSVを読み込めませんでした。")));
    reader.readAsDataURL(file);
  });
}

function setImportLoading(isLoading) {
  previewCsvButton.disabled = isLoading;
  samplePreviewButton.disabled = isLoading;
  commitImportButton.disabled = isLoading || !currentPreviewCanCommit;
  previewCsvButton.textContent = isLoading ? "確認中…" : "選択したCSVをPreview";
  samplePreviewButton.textContent = isLoading ? "確認中…" : "サンプルをPreview";
}

function showImportError(message) {
  importErrorMessage.textContent = message;
  importErrorPanel.hidden = false;
}

function hideImportError() {
  importErrorMessage.textContent = "";
  importErrorPanel.hidden = true;
}

function setText(selector, value) {
  document.querySelector(selector).textContent = value;
}

function setValueList(selector, values) {
  setText(selector, values.length === 0 ? "なし" : values.join("、"));
}

function appendSimpleListItem(list, text) {
  const item = document.createElement("li");
  item.textContent = text;
  list.appendChild(item);
}

function renderClaimList(selector, claims) {
  const container = document.querySelector(selector);
  container.replaceChildren();
  if (claims.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "登録なし";
    container.appendChild(empty);
    return;
  }
  claims.forEach((claim) => {
    const card = document.createElement("article");
    card.className = "claim-card";
    const assertion = document.createElement("p");
    assertion.textContent = claim.assertion;
    const id = document.createElement("code");
    id.textContent = claim.claim_id;
    card.append(assertion, id);
    container.appendChild(card);
  });
}

function renderSystemMetadata(data, examMetadata) {
  const source = examMetadata.source_dataset;
  document.querySelector("#examMetadataStatus").textContent =
    source.source_type === "manual_dummy"
      ? "ダミー " + source.source_row_count + "件"
      : "CSV " + source.source_row_count + "件";
  document.querySelector("#evidenceStatus").textContent = data.evidence.length + "件";
  const profiles = Object.values(data.publish_targets);
  const priorityCount = profiles.reduce(
    (total, profile) => total + profile.priority_claim_ids.length,
    0,
  );
  document.querySelector("#publisherStatus").textContent =
    priorityCount === 0 ? "未指定" : priorityCount + "件";
}

function renderCategoryContent(data) {
  if (data.category_content.template_id === "staining_method_v1.0") {
    renderStainingMethodContent(data);
    return;
  }
  if (data.category_content.template_id === "specimen_v1.0") {
    renderSpecimenContent(data);
    return;
  }
  if (data.category_content.template_id === "reagent_v1.0") {
    renderReagentContent(data);
    return;
  }
  if (data.category_content.template_id === "biological_structure_v1.0") {
    renderBiologicalStructureContent(data);
    return;
  }
  if (data.category_content.template_id === "disease_v1.0") {
    renderDiseaseContent(data);
    return;
  }
  if (data.category_content.template_id === "laboratory_test_item_v1.0") {
    renderLaboratoryTestItemContent(data);
    return;
  }
  renderTestItemContent(data);
}

function renderTestItemContent(data) {
  testItemSections.replaceChildren();
  const content = data.category_content.template_id === "test_item_v1.0"
    ? data.category_content.test_item
    : null;
  testItemPanel.hidden = content === null;
  if (content === null) return;
  document.querySelector("#categoryTemplateLabel").textContent = "検査項目専用";
  document.querySelector("#categoryTemplateTitle").textContent =
    "検査項目テンプレート 1.0";

  appendDetailSection("検査の目的", content.purposes.map(claimEntry));
  appendDetailSection(
    "検体",
    content.specimens.map((item) => ({
      title: item.specimen,
      body: [
        "容器・抗凝固剤：" + (item.container_or_anticoagulant || "未登録"),
        "取扱い：" + item.handling,
        "安定性：" + (item.stability || "未登録"),
        claimIdLine(item),
      ],
    })),
  );
  appendDetailSection(
    "測定方法",
    content.measurement_methods.map((item) => ({
      title: item.method_name,
      body: [
        item.method_family ? "測定法群：" + item.method_family : "",
        item.assertion,
        claimIdLine(item),
      ].filter(Boolean),
    })),
    "important",
  );
  appendDetailSection(
    "測定原理",
    content.measurement_principles.map((item) => ({
      title: item.measured_quantity,
      body: [
        "反応：" + item.reaction_sequence,
        "検出：" + item.detection_signal,
        item.wavelength_or_endpoint
          ? "波長・終点：" + item.wavelength_or_endpoint
          : "",
        claimIdLine(item),
      ].filter(Boolean),
    })),
    "important",
  );
  appendDetailSection(
    "標準化・トレーサビリティ",
    content.standardization_and_traceability.map((item) => ({
      title: item.framework_or_body,
      body: [item.traceability, item.assertion, claimIdLine(item)],
    })),
    "source-check",
    "未登録（出典確認後に追加）",
  );
  appendDetailSection(
    "報告単位・報告方式",
    content.reporting_systems.map((item) => ({
      title: item.system_name + "・" + item.unit,
      body: [item.conditions || "", item.assertion, claimIdLine(item)].filter(Boolean),
    })),
    "source-check",
    "未登録（出典確認後に追加）",
  );
  appendDetailSection(
    "基準範囲",
    content.reference_ranges.map((item) => ({
      title: referenceRangeLabel(item),
      body: [
        item.population + "・" + item.specimen,
        item.conditions,
        claimIdLine(item),
      ],
    })),
    "source-check",
    "未登録（出典確認後に追加）",
  );
  appendDetailSection(
    "臨床判断値",
    content.clinical_decision_limits.map((item) => ({
      title: clinicalDecisionLimitLabel(item),
      body: [
        item.limit_name + "・" + item.population,
        item.conditions,
        item.assertion,
        claimIdLine(item),
      ],
    })),
    "source-check",
    "未登録（適用する検査のみ出典確認後に追加）",
  );
  appendValueAssociationSections("高値", content.value_associations.high);
  appendValueAssociationSections("低値", content.value_associations.low);
  appendDetailSection(
    "他検査との組み合わせ",
    content.related_test_combinations.map((item) => ({
      title: item.related_test_names.join(" ＋ "),
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "干渉物質・分析上の影響",
    content.analytical_interferences.map((item) => ({
      title: item.interference_name,
      body: [
        "影響：" + item.effect_direction,
        item.conditions || "",
        item.assertion,
        claimIdLine(item),
      ].filter(Boolean),
    })),
    "source-check",
    "未登録（方法依存情報を出典確認後に追加）",
  );
  appendDetailSection(
    "解釈時の注意点",
    content.interpretation_cautions.map(claimEntry),
  );
  appendDetailSection(
    "経時変化",
    content.time_course.map((item) => ({
      title: item.event_or_condition,
      body: [item.time_course, item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "アイソザイム",
    content.isoenzymes.map((item) => ({
      title: item.isoenzyme_name,
      body: [item.distribution_or_property, item.assertion, claimIdLine(item)],
    })),
  );
}

function renderStainingMethodContent(data) {
  testItemSections.replaceChildren();
  const content = data.category_content.staining_method;
  testItemPanel.hidden = false;
  document.querySelector("#categoryTemplateLabel").textContent = "染色法専用";
  document.querySelector("#categoryTemplateTitle").textContent =
    "Staining Method Template 1.0";

  appendDetailSection(
    "目的",
    content.purposes.map((item) => ({
      title: item.use_case,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "対象構造",
    content.target_structures.map((item) => ({
      title: item.target_name,
      body: ["種類：" + item.target_kind, item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "適用検体・標本",
    content.applicable_specimens.map((item) => ({
      title: item.specimen,
      body: ["前処理：" + item.preparation, item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "固定法",
    content.fixation_requirements.map((item) => ({
      title: item.fixative_or_method,
      body: ["条件：" + item.conditions, item.assertion, claimIdLine(item)],
    })),
    "important",
  );
  appendDetailSection(
    "染色原理",
    content.staining_principles.map((item) => ({
      title: item.mechanism,
      body: [
        "対象：" + item.affected_target,
        "結果：" + item.resulting_effect,
        item.assertion,
        claimIdLine(item),
      ],
    })),
    "important",
  );
  appendDetailSection(
    "試薬",
    content.reagents.map((item) => ({
      title: item.reagent_name,
      body: ["役割：" + item.reagent_role, item.assertion, claimIdLine(item)],
    })),
    "important",
  );
  appendDetailSection(
    "工程",
    [...content.procedure_steps]
      .sort((left, right) => left.step_order - right.step_order)
      .map((item) => ({
        title: "Step " + item.step_order + " · " + item.action,
        body: [
          "使用試薬claim：" + (item.reagent_claim_ids.join("、") || "なし"),
          item.duration ? "時間：" + item.duration : "時間：標準作業書に従う",
          item.conditions ? "条件：" + item.conditions : "",
          item.assertion,
          claimIdLine(item),
        ].filter(Boolean),
      })),
    "important",
  );
  appendDetailSection(
    "判定",
    content.result_interpretations.map((item) => ({
      title: item.target_name + " · " + item.observed_color_or_pattern,
      body: [item.interpretation, item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "精度管理",
    content.quality_controls.map((item) => ({
      title: item.control_material,
      body: ["期待結果：" + item.expected_result, item.assertion, claimIdLine(item)],
    })),
    "source-check",
  );
  appendDetailSection(
    "誤りの原因",
    content.error_causes.map((item) => ({
      title: item.error_type,
      body: ["原因：" + item.cause, "影響：" + item.observed_effect, item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "限界",
    content.limitations.map((item) => ({
      title: item.scope_or_target,
      body: [item.limitation, item.assertion, claimIdLine(item)],
    })),
    "source-check",
  );
  appendDetailSection(
    "安全上の注意",
    content.safety_considerations.map(claimEntry),
    "source-check",
    "未登録（施設の安全手順確認後に追加）",
  );
  appendDetailSection(
    "関連する染色法",
    content.related_methods.map((item) => ({
      title: item.method_name,
      body: ["関係：" + item.relation_type, item.assertion, claimIdLine(item)],
    })),
  );
}

function renderSpecimenContent(data) {
  testItemSections.replaceChildren();
  const content = data.category_content.specimen;
  testItemPanel.hidden = false;
  document.querySelector("#categoryTemplateLabel").textContent = "検体・標本専用";
  document.querySelector("#categoryTemplateTitle").textContent =
    "Specimen Template 1.0 · " + content.specimen_kind;

  appendDetailSection("概要", content.overview.map(claimEntry));
  appendDetailSection(
    "使用用途",
    content.uses.map((item) => ({
      title: item.use_case,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "採取・作製方法",
    content.collection_methods.map((item) => ({
      title: item.source_material,
      body: [
        "方法：" + item.collection_or_preparation_method,
        "容器・器具：" + (item.container_or_device || "未登録"),
        item.assertion,
        claimIdLine(item),
      ],
    })),
    "important",
  );
  appendDetailSection(
    "保存条件",
    content.storage_conditions.map((item) => ({
      title: item.temperature || "温度は標準作業書に従う",
      body: [
        "保存時間：" + (item.maximum_duration || "未登録"),
        "条件：" + item.conditions,
        item.assertion,
        claimIdLine(item),
      ],
    })),
    "source-check",
  );
  appendDetailSection(
    "注意事項",
    content.cautions.map(claimEntry),
    "source-check",
  );
}

function renderReagentContent(data) {
  testItemSections.replaceChildren();
  const content = data.category_content.reagent;
  testItemPanel.hidden = false;
  document.querySelector("#categoryTemplateLabel").textContent = "試薬専用";
  document.querySelector("#categoryTemplateTitle").textContent =
    "Reagent Template 1.0 · " + content.reagent_kind;

  appendDetailSection(
    "用途",
    content.purposes.map((item) => ({
      title: item.use_case,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "使用対象",
    content.targets.map((item) => ({
      title: item.target_name,
      body: ["種類：" + item.target_kind, item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "使用工程",
    content.usage_steps.map((item) => ({
      title: item.usage_phase,
      body: [
        "使用方法：" + item.application,
        item.conditions ? "条件：" + item.conditions : "条件：製品添付文書と標準作業書に従う",
        item.assertion,
        claimIdLine(item),
      ],
    })),
    "important",
  );
  appendDetailSection(
    "注意事項",
    content.cautions.map(claimEntry),
    "source-check",
  );
  appendDetailSection(
    "保管条件",
    content.storage_conditions.map((item) => ({
      title: item.temperature || "温度は製品添付文書に従う",
      body: [item.conditions, item.assertion, claimIdLine(item)],
    })),
    "source-check",
  );
}

function renderBiologicalStructureContent(data) {
  testItemSections.replaceChildren();
  const content = data.category_content.biological_structure;
  testItemPanel.hidden = false;
  document.querySelector("#categoryTemplateLabel").textContent = "生体構造専用";
  document.querySelector("#categoryTemplateTitle").textContent =
    "Biological Structure Template 1.0 · MVP";

  appendDetailSection("概要", content.overview.map(claimEntry));
  appendDetailSection(
    "主な機能",
    content.main_functions.map((item) => ({
      title: item.function_name,
      body: [item.assertion, claimIdLine(item)],
    })),
    "important",
  );
  appendDetailSection(
    "主な構成要素",
    content.main_components.map((item) => ({
      title: item.component_name,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "存在する生物",
    content.organisms_present.map((item) => ({
      title: item.organism_name,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
}

function renderDiseaseContent(data) {
  testItemSections.replaceChildren();
  const content = data.category_content.disease;
  testItemPanel.hidden = false;
  document.querySelector("#categoryTemplateLabel").textContent = "疾患専用";
  document.querySelector("#categoryTemplateTitle").textContent =
    "Disease Template 1.0 · MVP";

  appendDetailSection("概要", content.overview.map(claimEntry));
  appendDetailSection(
    "病態",
    content.pathophysiology.map((item) => ({
      title: item.process_name,
      body: [item.assertion, claimIdLine(item)],
    })),
    "important",
  );
  appendDetailSection(
    "原因",
    content.causes.map((item) => ({
      title: item.cause_name,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "主な症状",
    content.main_symptoms.map((item) => ({
      title: item.finding_name,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "主な検査所見",
    content.main_laboratory_findings.map((item) => ({
      title: item.test_name + "：" + item.direction_or_result,
      body: [
        item.specimen ? "検体：" + item.specimen : "検体：未指定",
        item.conditions ? "条件：" + item.conditions : "条件：なし",
        item.assertion,
        claimIdLine(item),
      ],
    })),
    "important",
  );
  appendDetailSection(
    "鑑別のポイント",
    content.differential_points.map((item) => ({
      title: item.compared_disease_name,
      body: [item.distinguishing_feature, item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "国家試験ポイント",
    content.national_exam_point_claim_ids.map((claimId) => ({
      title: claimId,
      body: ["既存の医学的Claimを国家試験向けに優先参照"],
    })),
    "important",
  );
}

function renderLaboratoryTestItemContent(data) {
  testItemSections.replaceChildren();
  const content = data.category_content.laboratory_test_item;
  testItemPanel.hidden = false;
  document.querySelector("#categoryTemplateLabel").textContent = "臨床検査項目専用";
  document.querySelector("#categoryTemplateTitle").textContent =
    "Laboratory Test Item Template 1.0 · MVP";

  appendDetailSection("概要", content.overview.map(claimEntry));
  appendDetailSection(
    "測定対象",
    content.measured_targets.map((item) => ({
      title: item.analyte_name,
      body: [
        "代表的な検体：" + (item.typical_specimens.join("、") || "未登録"),
        item.assertion,
        claimIdLine(item),
      ],
    })),
    "important",
  );
  appendDetailSection(
    "臨床的意義",
    content.clinical_significance.map((item) => ({
      title: item.significance_name,
      body: [item.assertion, claimIdLine(item)],
    })),
    "important",
  );
  appendDetailSection(
    "高値となる主な病態",
    content.high_conditions.map((item) => ({
      title: item.condition_name,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "低値となる主な病態",
    content.low_conditions.map((item) => ({
      title: item.condition_name,
      body: [item.assertion, claimIdLine(item)],
    })),
  );
  appendDetailSection(
    "主な測定法",
    content.measurement_methods.map((item) => ({
      title: item.method_name,
      body: [
        item.method_family ? "測定法群：" + item.method_family : "",
        item.assertion,
        claimIdLine(item),
      ].filter(Boolean),
    })),
  );
}

function appendValueAssociationSections(direction, group) {
  appendDetailSection(
    direction + "：病態",
    group.pathophysiologic_states.map((item) => ({
      title: item.state_name,
      body: [item.assertion, claimIdLine(item)],
    })),
    "",
    "登録なし",
  );
  appendDetailSection(
    direction + "：代表疾患",
    group.representative_diseases.map((item) => ({
      title: item.disease_name,
      body: [item.assertion, claimIdLine(item)],
    })),
    "",
    "登録なし",
  );
  appendDetailSection(
    direction + "：解釈上の事実",
    group.interpretive_notes.map(claimEntry),
    "",
    "登録なし",
  );
}

function claimEntry(claim) {
  return { title: claim.assertion, body: [claimIdLine(claim)] };
}

function claimIdLine(item) {
  return "claim_id：" + item.claim_id;
}

function referenceRangeLabel(item) {
  if (item.lower_bound !== null || item.upper_bound !== null) {
    const lower = item.lower_bound === null ? "" : item.lower_bound;
    const upper = item.upper_bound === null ? "" : item.upper_bound;
    return lower + "〜" + upper + (item.unit ? " " + item.unit : "");
  }
  return item.qualitative_value + (item.unit ? " " + item.unit : "");
}

function clinicalDecisionLimitLabel(item) {
  const comparators = {
    less_than: "<",
    less_than_or_equal: "≤",
    greater_than: ">",
    greater_than_or_equal: "≥",
  };
  const value = item.value === null ? item.qualitative_value : item.value;
  const unit = item.unit ? " " + item.unit : "";
  return item.limit_name + "：" + comparators[item.comparator] + " " + value + unit;
}

function renderKnowledgeCompleteness(report) {
  const levelLabels = {
    complete_for_review: "医学レビューへ渡せる情報量です",
    mostly_complete: "主情報はありますが補完が必要です",
    incomplete: "重要項目の追加が必要です",
    critically_incomplete: "カテゴリ情報が大きく不足しています",
  };
  renderCompleteness(
    report,
    "#knowledgeCompletenessScore",
    "#knowledgeCompletenessBar",
    "#knowledgeCompletenessLevel",
    "#knowledgeImprovementList",
    levelLabels,
  );
}

function renderExamCompleteness(report) {
  const levelLabels = {
    ready_for_publisher: "Publisherが利用できる国家試験情報量です",
    mostly_complete: "主情報はありますがCSV取込後の再評価が必要です",
    incomplete: "国家試験情報の追加が必要です",
    critically_incomplete: "国家試験情報が大きく不足しています",
  };
  renderCompleteness(
    report,
    "#examCompletenessScore",
    "#examCompletenessBar",
    "#examCompletenessLevel",
    "#examImprovementList",
    levelLabels,
  );
}

function renderCompleteness(
  report,
  scoreSelector,
  barSelector,
  levelSelector,
  listSelector,
  levelLabels,
) {
  const score = report.score;
  const scoreElement = document.querySelector(scoreSelector);
  const bar = document.querySelector(barSelector);
  const fill = bar.querySelector("span");
  const level = document.querySelector(levelSelector);
  const list = document.querySelector(listSelector);

  scoreElement.textContent = score + "%";
  scoreElement.dataset.level = report.level;
  bar.setAttribute("aria-valuenow", String(score));
  fill.style.width = score + "%";
  level.textContent = levelLabels[report.level] || report.level;
  list.replaceChildren();

  if (report.improvement_candidates.length === 0) {
    const item = document.createElement("li");
    item.textContent = "現在の評価基準で不足項目はありません";
    list.appendChild(item);
    return;
  }

  report.improvement_candidates.forEach((candidate) => {
    const item = document.createElement("li");
    const label = document.createElement("strong");
    label.textContent = candidate.label;
    const action = document.createElement("span");
    action.textContent = candidate.action;
    item.dataset.priority = candidate.priority;
    item.append(label, action);
    list.appendChild(item);
  });
}

function renderExamMetadata(data, metadata) {
  const source = metadata.source_dataset;
  const frequency = metadata.frequency;
  const badge = document.querySelector("#examDataBadge");
  badge.textContent = source.is_production_data ? "CSV解析データ" : "試験用ダミーデータ";
  badge.className = source.is_production_data ? "badge success" : "badge warning";
  document.querySelector("#examImportanceScore").textContent =
    metadata.importance ? metadata.importance.importance_score + " / 100" : "未登録";
  document.querySelector("#examAppearanceCount").textContent =
    frequency.appearance_count + "回";
  document.querySelector("#examFirstYear").textContent =
    frequency.first_exam_year === null ? "未登録" : frequency.first_exam_year;
  document.querySelector("#examLatestYear").textContent =
    frequency.latest_exam_year === null ? "未登録" : frequency.latest_exam_year;

  const claimMap = collectClaims(data);
  const priorityLabels = {
    highest: "最優先",
    important: "重要",
    supplementary: "補足",
  };
  const priorityList = document.querySelector("#priorityClaimList");
  priorityList.replaceChildren();
  metadata.priority_claims.forEach((item) => {
    const entry = document.createElement("li");
    const priority = document.createElement("strong");
    priority.textContent = priorityLabels[item.priority] || item.priority;
    const assertion = document.createElement("span");
    assertion.textContent = claimMap[item.claim_id] || "リンク先claimを表示できません";
    const claimId = document.createElement("code");
    claimId.textContent = item.claim_id;
    entry.append(priority, assertion, claimId);
    priorityList.appendChild(entry);
  });

  const sectionLabels = { morning: "午前", afternoon: "午後", unspecified: "区分なし" };
  const patternLabels = {
    standalone_knowledge: "単独知識",
    differential: "鑑別問題",
    image: "画像問題",
    calculation: "計算問題",
    elimination: "消去法",
    combination: "組み合わせ問題",
  };
  const historyList = document.querySelector("#examHistoryList");
  historyList.replaceChildren();
  metadata.history.forEach((item) => {
    const entry = document.createElement("li");
    const heading = document.createElement("strong");
    heading.textContent =
      "第" + item.session_number + "回 " +
      sectionLabels[item.section] + " 問" + item.question_number + "（ダミー）";
    const details = document.createElement("span");
    details.textContent =
      item.exam_year + "年 · " +
      item.patterns.map((pattern) => patternLabels[pattern] || pattern).join("・");
    const rowId = document.createElement("code");
    rowId.textContent = "source_row_id: " + item.source_row_id;
    entry.append(heading, details, rowId);
    historyList.appendChild(entry);
  });
}

function collectClaims(data) {
  const claims = {};
  function visit(value) {
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (value === null || typeof value !== "object") return;
    if (typeof value.claim_id === "string") {
      claims[value.claim_id] =
        value.assertion || value.reaction_sequence || value.conditions || value.claim_id;
    }
    Object.values(value).forEach(visit);
  }
  visit(data);
  return claims;
}

function appendDetailSection(title, items, variant = "", emptyLabel = "登録なし") {
  const section = document.createElement("section");
  section.className = ("detail-section " + variant).trim();
  const heading = document.createElement("h4");
  heading.textContent = title;
  section.appendChild(heading);

  const list = document.createElement("div");
  list.className = "detail-list";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "detail-entry empty-state";
    empty.textContent = emptyLabel;
    list.appendChild(empty);
  }
  items.forEach((item) => {
    const entry = document.createElement("div");
    entry.className = "detail-entry";
    const strong = document.createElement("strong");
    strong.textContent = item.title;
    entry.appendChild(strong);
    item.body.forEach((line) => {
      const paragraph = document.createElement("p");
      paragraph.textContent = line;
      entry.appendChild(paragraph);
    });
    list.appendChild(entry);
  });
  section.appendChild(list);
  testItemSections.appendChild(section);
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  normalLabel.hidden = isLoading;
  loadingLabel.hidden = !isLoading;
}

function showError(message) {
  errorMessage.textContent = message;
  errorPanel.hidden = false;
}

function hideError() {
  errorPanel.hidden = true;
  errorMessage.textContent = "";
}

async function loadDiseaseRelationVocabulary() {
  try {
    const response = await fetch("/api/relation-vocabulary/disease");
    if (!response.ok) {
      throw new Error("Vocabulary APIを読み込めませんでした。");
    }
    const catalog = await response.json();
    diseaseVocabularyList.replaceChildren();
    catalog.entries.forEach((entry) => {
      const card = document.createElement("article");
      card.className = "relation-vocabulary-card";

      const heading = document.createElement("div");
      heading.className = "vocabulary-card-heading";
      const relationType = document.createElement("code");
      relationType.textContent = entry.relation_type;
      const direction = document.createElement("span");
      direction.textContent =
        entry.direction.value === "symmetric" ? "対称" : "疾患 → 関係先";
      heading.append(relationType, direction);

      const meaning = document.createElement("p");
      meaning.textContent = entry.meaning;

      const categories = document.createElement("small");
      categories.textContent = `${entry.source_categories.join(" / ")} → ${entry.target_categories.join(" / ")}`;

      const example = document.createElement("strong");
      example.textContent = `例：${entry.example.source_label} → ${entry.example.target_label}`;

      const reading = document.createElement("small");
      reading.textContent = entry.example.reading;

      card.append(heading, meaning, categories, example, reading);
      diseaseVocabularyList.appendChild(card);
    });
    diseaseVocabularyBadge.textContent = `${catalog.entries.length} types · v${catalog.schema_version}`;
    diseaseVocabularyBadge.className = "badge success";
  } catch (error) {
    diseaseVocabularyBadge.textContent = "読込エラー";
    diseaseVocabularyBadge.className = "badge warning";
    const message = document.createElement("p");
    message.className = "empty-state";
    message.textContent = error instanceof Error ? error.message : "Vocabularyを表示できません。";
    diseaseVocabularyList.replaceChildren(message);
  }
}

const aiKnowledgeWizardForm = document.querySelector("#aiKnowledgeWizardForm");
const aiKnowledgeTheme = document.querySelector("#aiKnowledgeTheme");
const aiKnowledgeMessage = document.querySelector("#aiKnowledgeMessage");
const aiKnowledgePreview = document.querySelector("#aiKnowledgePreview");
const generateAiKnowledgeButton = document.querySelector("#generateAiKnowledgeButton");
const saveAiKnowledgeDraftButton = document.querySelector("#saveAiKnowledgeDraftButton");
const runGroundedEvidenceSearchButton = document.querySelector(
  "#runGroundedEvidenceSearchButton",
);
const groundedSearchMessage = document.querySelector("#groundedSearchMessage");
const groundedSearchPreview = document.querySelector("#groundedSearchPreview");
let currentAiKnowledgePreview = null;

function renderAiPipelineItems(targetSelector, items, renderItem) {
  const target = document.querySelector(targetSelector);
  target.replaceChildren();
  items.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "authoring-item";
    const rendered = renderItem(entry);
    const title = document.createElement("strong");
    title.textContent = rendered.title;
    const detail = document.createElement("small");
    detail.textContent = rendered.detail;
    card.append(title, detail);
    target.appendChild(card);
  });
}

function renderAiKnowledgePreview(preview) {
  currentAiKnowledgePreview = preview;
  const bundle = preview.evidence_bundle;
  aiKnowledgePreview.hidden = false;
  document.querySelector("#aiPipelineSubject").textContent =
    bundle.subject.canonical_name;
  document.querySelector("#aiPipelineCategory").textContent =
    termTypeLabels[bundle.subject.category] || bundle.subject.category;
  document.querySelector("#aiPipelineInputCount").textContent =
    bundle.input_record_count;
  document.querySelector("#aiPipelineEvidenceCount").textContent =
    bundle.accepted_evidence_count;
  document.querySelector("#aiPipelineExcludedCount").textContent =
    bundle.excluded_evidence_count;
  document.querySelector("#aiPipelineClaimCount").textContent =
    preview.claim_build.claims.length;
  document.querySelector("#aiPipelineReferenceCount").textContent =
    preview.references.length;
  document.querySelector("#aiPipelineProvider").textContent =
    bundle.providers.join(", ") || "--";
  document.querySelector("#aiPipelineSearchAudit").textContent =
    preview.search_audit_recorded ? "Recorded" : "Not recorded";
  document.querySelector("#aiPipelineExternal").textContent =
    `${preview.external_search_called ? "Yes" : "No"} / ${preview.external_ai_called ? "Yes" : "No"}`;
  document.querySelector("#aiPipelineFingerprint").textContent = preview.fingerprint;
  document.querySelector("#aiPipelineBundleFingerprint").textContent = bundle.fingerprint;
  document.querySelector("#aiPipelineBundleJson").textContent =
    JSON.stringify(bundle, null, 2);
  document.querySelector("#aiPipelineDraftJson").textContent =
    JSON.stringify(preview.authoring_draft, null, 2);
  saveAiKnowledgeDraftButton.disabled = false;

  renderAiPipelineItems(
    "#aiPipelineEvidenceList",
    bundle.evidence,
    (entry) => ({
      title: entry.evidence.title,
      detail: `${entry.evidence.publisher} · ${entry.evidence.evidence_type} · ${entry.evidence.publication_date || "発行日未登録"}`,
    }),
  );
  renderAiPipelineItems(
    "#aiPipelineRankingList",
    bundle.evidence,
    (entry) => ({
      title: `${entry.rank}. Evidence Level ${entry.evidence.evidence_level}`,
      detail: `${entry.evidence.title} · Information Priority ${entry.information_priority_rank}（同Level内補助）`,
    }),
  );
  renderAiPipelineItems(
    "#aiPipelineClaimList",
    preview.claim_build.claims,
    (claim) => ({
      title: claim.assertion,
      detail: `${claim.claim_type} · ${claim.semantic_slot} · Evidence ${claim.evidence_ids.length}件 · 抽出信頼度 ${Math.round(claim.confidence * 100)}%`,
    }),
  );
  renderAiPipelineItems(
    "#aiPipelineReferenceList",
    preview.references,
    (reference) => ({
      title: reference.title,
      detail: `${reference.issuing_organization || "発行団体未登録"} · Claim ${reference.supported_claim_ids.length}件`,
    }),
  );
}

function renderGroundedEvidencePreview(preview) {
  const bundle = preview.evidence_bundle;
  const audit = preview.search_audit;
  const policyByEvidenceId = new Map(
    preview.policy_decisions.map((item) => [item.evidence_id, item]),
  );
  groundedSearchPreview.hidden = false;
  document.querySelector("#groundedProvider").textContent = preview.provider;
  document.querySelector("#groundedModel").textContent = preview.model;
  document.querySelector("#groundedSourceCount").textContent =
    audit.raw_source_count;
  document.querySelector("#groundedAccepted").textContent =
    `${audit.accepted_count} / ${audit.excluded_count}`;
  document.querySelector("#groundedDeduplicated").textContent =
    audit.deduplicated_count;
  document.querySelector("#groundedLevels").textContent =
    `${audit.evidence_level_counts.A} / ${audit.evidence_level_counts.B} / ${audit.evidence_level_counts.C}`;
  document.querySelector("#groundedAuditStatus").textContent =
    `${audit.status} · ${audit.duration_ms}ms`;
  document.querySelector("#groundedBundleJson").textContent =
    JSON.stringify(bundle, null, 2);

  renderAiPipelineItems(
    "#groundedQueryList",
    preview.generated_queries,
    (query) => ({
      title: query.intent,
      detail: query.query,
    }),
  );

  const target = document.querySelector("#groundedEvidenceList");
  target.replaceChildren();
  bundle.evidence.forEach((ranked) => {
    const evidence = ranked.evidence;
    const policy = policyByEvidenceId.get(evidence.evidence_id);
    const card = document.createElement("article");
    card.className = "authoring-item";
    const title = document.createElement("strong");
    title.textContent = `${ranked.rank}. ${evidence.title}`;
    const detail = document.createElement("small");
    detail.textContent = `${evidence.publisher} · ${policy?.domain || "unknown"} · ${policy?.domain_class || "other"} · Evidence ${evidence.evidence_level} · ${evidence.retrieved_at}`;
    const link = document.createElement("a");
    link.href = evidence.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = evidence.url;
    card.append(title, detail, link);
    target.appendChild(card);
  });
}

runGroundedEvidenceSearchButton.addEventListener("click", async () => {
  const theme = aiKnowledgeTheme.value.trim();
  if (!theme) {
    groundedSearchMessage.textContent = "先に医療用語を入力してください。";
    aiKnowledgeTheme.focus();
    return;
  }
  runGroundedEvidenceSearchButton.disabled = true;
  groundedSearchPreview.hidden = true;
  groundedSearchMessage.textContent =
    "Google Search Groundingから外部Source Citationを取得しています…";
  try {
    const payload = await authoringApi(
      "/api/evidence-search/gemini/previews",
      authoringJsonOptions("POST", { theme }),
    );
    renderGroundedEvidencePreview(payload.preview);
    groundedSearchMessage.textContent =
      "Evidence候補を取得しました。医学的承認ではありません。Gemini回答本文・Claim・Knowledge Draftは保存していません。";
  } catch (error) {
    groundedSearchPreview.hidden = true;
    groundedSearchMessage.textContent =
      error instanceof Error ? error.message : "実Evidence検索に失敗しました。";
  } finally {
    runGroundedEvidenceSearchButton.disabled = false;
  }
});

aiKnowledgeWizardForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  generateAiKnowledgeButton.disabled = true;
  aiKnowledgeMessage.textContent = "EvidenceからDraft Previewを組み立てています…";
  try {
    const payload = await authoringApi(
      "/api/ai-knowledge-pipeline/previews",
      authoringJsonOptions("POST", { theme: aiKnowledgeTheme.value.trim() }),
    );
    renderAiKnowledgePreview(payload.preview);
    aiKnowledgeMessage.textContent =
      "Evidence BundleとDraft Previewを生成しました。Raw Evidenceは画面へ渡していません。外部検索・LLM・Registry・Promotionは動作していません。";
  } catch (error) {
    currentAiKnowledgePreview = null;
    aiKnowledgePreview.hidden = true;
    aiKnowledgeMessage.textContent =
      error instanceof Error ? error.message : "Draft Previewを生成できませんでした。";
  } finally {
    generateAiKnowledgeButton.disabled = false;
  }
});

document.querySelectorAll("[data-ai-theme]").forEach((button) => {
  button.addEventListener("click", () => {
    aiKnowledgeTheme.value = button.dataset.aiTheme;
    aiKnowledgeTheme.focus();
  });
});

saveAiKnowledgeDraftButton.addEventListener("click", async () => {
  if (!currentAiKnowledgePreview) return;
  saveAiKnowledgeDraftButton.disabled = true;
  try {
    const payload = await authoringApi(
      `/api/ai-knowledge-pipeline/previews/${currentAiKnowledgePreview.pipeline_id}/save`,
      { method: "POST" },
    );
    const draftId = payload.result.draft.draft_id;
    await refreshAuthoringDrafts(draftId);
    await openAuthoringDraft(draftId);
    aiKnowledgeMessage.textContent =
      "Authoring Draftへ保存しました。正式RegistryとPromotionは変更していません。";
  } catch (error) {
    saveAiKnowledgeDraftButton.disabled = false;
    aiKnowledgeMessage.textContent =
      error instanceof Error ? error.message : "Authoring Draftへ保存できませんでした。";
  }
});

const authoringWizardForm = document.querySelector("#authoringWizardForm");
const authoringDraftSelect = document.querySelector("#authoringDraftSelect");
const authoringEditor = document.querySelector("#authoringEditor");
const authoringMessage = document.querySelector("#authoringMessage");
const authoringClaimList = document.querySelector("#authoringClaimList");
const authoringReferenceList = document.querySelector("#authoringReferenceList");
const authoringReferenceClaims = document.querySelector("#authoringReferenceClaims");
let currentAuthoringDraft = null;
let currentAuthoringValidation = null;
let editingAuthoringReferenceId = null;
let currentPromotionPreview = null;
let promotionSemanticSlots = {};

const promotionSlotLabels = {
  definition: "定義",
  overview: "概要",
  biological_basis: "生物学的基盤",
  analyte_characteristic: "測定対象の特徴",
  purpose: "検査目的",
  interpretation_caution: "解釈上の注意",
  safety_consideration: "安全上の注意",
  caution: "注意事項",
  unassigned: "未指定（Promotion不可）",
};

async function authoringApi(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.errors?.[0]?.message || "Authoring操作に失敗しました。");
  }
  return payload;
}

function authoringJsonOptions(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

async function refreshAuthoringDrafts(preferredId = null) {
  const payload = await authoringApi("/api/authoring/drafts");
  const selected = preferredId || currentAuthoringDraft?.draft_id || "";
  authoringDraftSelect.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = payload.drafts.length ? "下書きを選択" : "下書きはありません";
  authoringDraftSelect.appendChild(placeholder);
  payload.drafts.forEach((draft) => {
    const option = document.createElement("option");
    option.value = draft.draft_id;
    option.textContent = `${draft.title} · ${termTypeLabels[draft.category] || draft.category} · Claim ${draft.claim_count} · ${draft.lifecycle_state}`;
    option.selected = draft.draft_id === selected;
    authoringDraftSelect.appendChild(option);
  });
}

async function openAuthoringDraft(draftId) {
  if (!draftId) return;
  const payload = await authoringApi(`/api/authoring/drafts/${draftId}`);
  currentAuthoringDraft = payload.draft;
  currentAuthoringValidation = payload.validation;
  renderAuthoringDraft();
  resetPromotionPreview();
  authoringMessage.textContent = `${payload.draft.metadata.title} の下書きを開きました。正式Registryは変更していません。`;
}

function renderAuthoringDraft() {
  const draft = currentAuthoringDraft;
  const validation = currentAuthoringValidation;
  if (!draft || !validation) return;
  authoringEditor.hidden = false;
  document.querySelector("#authoringSchemaStatus").textContent =
    validation.schema_valid && validation.knowledge_schema_valid ? "OK" : "要修正";
  document.querySelector("#authoringCompleteness").textContent = `${validation.completeness_score}%`;
  document.querySelector("#authoringClaimCount").textContent = draft.claims.length;
  document.querySelector("#authoringReferenceCount").textContent = draft.references.length;
  document.querySelector("#authoringReviewState").textContent = draft.review.state;
  renderNewClaimSlotOptions();
  renderAuthoringClaims();
  renderAuthoringReferences();
  renderAuthoringValidation();
}

function renderAuthoringClaims() {
  authoringClaimList.replaceChildren();
  authoringReferenceClaims.replaceChildren();
  if (!currentAuthoringDraft.claims.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Claimはまだありません。";
    authoringClaimList.appendChild(empty);
  }
  currentAuthoringDraft.claims.forEach((claim, index) => {
    const card = document.createElement("article");
    card.className = "authoring-item";
    const id = document.createElement("code");
    id.textContent = `${claim.position}. ${claim.claim_id}`;
    const textarea = document.createElement("textarea");
    textarea.rows = 3;
    textarea.maxLength = 800;
    textarea.value = claim.assertion;
    const slot = document.createElement("select");
    appendPromotionSlotOptions(slot, claim.semantic_slot);
    const actions = document.createElement("div");
    actions.className = "authoring-item-actions";
    const save = authoringButton("保存", async () => {
      await mutateAuthoring(`/claims/${claim.claim_id}`, "PUT", {
        assertion: textarea.value,
        semantic_slot: slot.value,
      });
    });
    const up = authoringButton("↑", () => reorderAuthoringClaim(index, -1));
    const down = authoringButton("↓", () => reorderAuthoringClaim(index, 1));
    up.disabled = index === 0;
    down.disabled = index === currentAuthoringDraft.claims.length - 1;
    const remove = authoringButton("削除", async () => {
      await mutateAuthoring(`/claims/${claim.claim_id}`, "DELETE");
    }, "danger-action");
    actions.append(save, up, down, remove);
    card.append(id, textarea, slot, actions);
    authoringClaimList.appendChild(card);

    const option = document.createElement("option");
    option.value = claim.claim_id;
    option.textContent = `${claim.position}. ${claim.assertion}`;
    authoringReferenceClaims.appendChild(option);
  });
}

function appendPromotionSlotOptions(select, selected = "unassigned") {
  const category = currentAuthoringDraft?.metadata?.category;
  const values = ["unassigned", ...(promotionSemanticSlots[category] || [])];
  select.replaceChildren();
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = promotionSlotLabels[value] || value;
    option.selected = value === selected;
    select.appendChild(option);
  });
}

function renderNewClaimSlotOptions() {
  appendPromotionSlotOptions(document.querySelector("#authoringClaimSlot"), "unassigned");
}

function authoringButton(label, handler, className = "secondary-action") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `${className} compact`;
  button.textContent = label;
  button.addEventListener("click", async () => {
    try {
      await handler();
    } catch (error) {
      authoringMessage.textContent = error instanceof Error ? error.message : "操作に失敗しました。";
    }
  });
  return button;
}

async function reorderAuthoringClaim(index, offset) {
  const ids = currentAuthoringDraft.claims.map((item) => item.claim_id);
  const target = index + offset;
  if (target < 0 || target >= ids.length) return;
  [ids[index], ids[target]] = [ids[target], ids[index]];
  await mutateAuthoring("/claims/reorder", "POST", { claim_ids: ids });
}

function renderAuthoringReferences() {
  authoringReferenceList.replaceChildren();
  if (!currentAuthoringDraft.references.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Referenceはまだありません。";
    authoringReferenceList.appendChild(empty);
    return;
  }
  currentAuthoringDraft.references.forEach((reference) => {
    const card = document.createElement("article");
    card.className = "authoring-item";
    const title = document.createElement("strong");
    title.textContent = `[${reference.evidence_level}] ${reference.title}`;
    const detail = document.createElement("small");
    detail.textContent = `${reference.source_id} · Claim ${reference.supported_claim_ids.length}件`;
    const actions = document.createElement("div");
    actions.className = "authoring-item-actions";
    actions.append(
      authoringButton("編集", () => beginAuthoringReferenceEdit(reference)),
      authoringButton("削除", async () => {
        await mutateAuthoring(`/references/${reference.source_id}`, "DELETE");
      }, "danger-action"),
    );
    card.append(title, detail, actions);
    authoringReferenceList.appendChild(card);
  });
}

function beginAuthoringReferenceEdit(reference) {
  editingAuthoringReferenceId = reference.source_id;
  document.querySelector("#authoringEvidenceLevel").value = reference.evidence_level;
  document.querySelector("#authoringEvidenceRole").value = reference.evidence_role;
  document.querySelector("#authoringSourcePriorityRank").value = reference.source_priority_rank || "";
  document.querySelector("#authoringReferenceTitle").value = reference.title;
  document.querySelector("#authoringReferenceOrganization").value = reference.issuing_organization || "";
  document.querySelector("#authoringReferenceYear").value = reference.publication_year || "";
  document.querySelector("#authoringReferenceEdition").value = reference.edition || "";
  document.querySelector("#authoringReferenceUrl").value = reference.url || "";
  document.querySelector("#authoringReferenceDoi").value = reference.doi || "";
  document.querySelector("#authoringReferencePmid").value = reference.pmid || "";
  document.querySelector("#authoringReferenceChapter").value = reference.chapter || "";
  document.querySelector("#authoringReferencePages").value = reference.pages || "";
  [...authoringReferenceClaims.options].forEach((option) => {
    option.selected = reference.supported_claim_ids.includes(option.value);
  });
  document.querySelector("#saveAuthoringReferenceButton").textContent = "Reference更新";
  document.querySelector("#cancelAuthoringReferenceButton").hidden = false;
}

function clearAuthoringReferenceForm() {
  editingAuthoringReferenceId = null;
  ["Title", "Organization", "Year", "Edition", "Url", "Doi", "Pmid", "Chapter", "Pages"].forEach((name) => {
    document.querySelector(`#authoringReference${name}`).value = "";
  });
  [...authoringReferenceClaims.options].forEach((option) => { option.selected = false; });
  document.querySelector("#authoringSourcePriorityRank").value = "";
  document.querySelector("#saveAuthoringReferenceButton").textContent = "＋ Reference追加";
  document.querySelector("#cancelAuthoringReferenceButton").hidden = true;
}

function authoringReferencePayload() {
  const optional = (selector) => document.querySelector(selector).value.trim() || null;
  const year = document.querySelector("#authoringReferenceYear").value;
  const sourcePriorityRank = document.querySelector("#authoringSourcePriorityRank").value;
  return {
    evidence_level: document.querySelector("#authoringEvidenceLevel").value,
    evidence_role: document.querySelector("#authoringEvidenceRole").value,
    source_priority_rank: sourcePriorityRank ? Number(sourcePriorityRank) : null,
    title: document.querySelector("#authoringReferenceTitle").value.trim(),
    issuing_organization: optional("#authoringReferenceOrganization"),
    publication_year: year ? Number(year) : null,
    edition: optional("#authoringReferenceEdition"),
    url: optional("#authoringReferenceUrl"),
    doi: optional("#authoringReferenceDoi"),
    pmid: optional("#authoringReferencePmid"),
    accessed_at: null,
    chapter: optional("#authoringReferenceChapter"),
    pages: optional("#authoringReferencePages"),
    supported_claim_ids: [...authoringReferenceClaims.selectedOptions].map((option) => option.value),
  };
}

function renderAuthoringValidation() {
  const list = document.querySelector("#authoringValidationIssues");
  list.replaceChildren();
  currentAuthoringValidation.issues.forEach((issue) => {
    const item = document.createElement("li");
    item.dataset.severity = issue.severity;
    const title = document.createElement("strong");
    title.textContent = issue.code;
    const message = document.createElement("span");
    message.textContent = issue.message;
    item.append(title, message);
    list.appendChild(item);
  });
  if (!currentAuthoringValidation.issues.length) {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = "Validation OK";
    item.appendChild(title);
    list.appendChild(item);
  }
}

async function mutateAuthoring(suffix, method, body = null) {
  if (!currentAuthoringDraft) throw new Error("先に下書きを開いてください。");
  const options = body === null ? { method } : authoringJsonOptions(method, body);
  const payload = await authoringApi(`/api/authoring/drafts/${currentAuthoringDraft.draft_id}${suffix}`, options);
  currentAuthoringDraft = payload.draft;
  currentAuthoringValidation = payload.validation;
  renderAuthoringDraft();
  resetPromotionPreview();
  await refreshAuthoringDrafts(currentAuthoringDraft.draft_id);
  authoringMessage.textContent = "下書きを保存しました。正式Registryは変更していません。";
}

authoringWizardForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const aliases = document.querySelector("#authoringAliases").value
      .split(/[、,\n]/).map((item) => item.trim()).filter(Boolean);
    const payload = await authoringApi("/api/authoring/drafts", authoringJsonOptions("POST", {
      category: document.querySelector("#authoringCategory").value,
      title: document.querySelector("#authoringTitle").value.trim(),
      aliases,
      difficulty: document.querySelector("#authoringDifficulty").value,
      exam_importance: document.querySelector("#authoringImportance").value,
    }));
    currentAuthoringDraft = payload.draft;
    currentAuthoringValidation = payload.validation;
    renderAuthoringDraft();
    await refreshAuthoringDrafts(payload.draft.draft_id);
    authoringMessage.textContent = "Skeletonを作成しました。ClaimとReferenceを追加できます。";
  } catch (error) {
    authoringMessage.textContent = error instanceof Error ? error.message : "Skeletonを作成できませんでした。";
  }
});

document.querySelector("#loadAuthoringDraftButton").addEventListener("click", async () => {
  try { await openAuthoringDraft(authoringDraftSelect.value); }
  catch (error) { authoringMessage.textContent = error instanceof Error ? error.message : "開けませんでした。"; }
});

document.querySelector("#addAuthoringClaimButton").addEventListener("click", async () => {
  const field = document.querySelector("#authoringClaimText");
  if (!field.value.trim()) { authoringMessage.textContent = "Claim本文を入力してください。"; return; }
  try {
    await mutateAuthoring("/claims", "POST", {
      assertion: field.value.trim(),
      semantic_slot: document.querySelector("#authoringClaimSlot").value,
    });
    field.value = "";
  }
  catch (error) { authoringMessage.textContent = error instanceof Error ? error.message : "追加できませんでした。"; }
});

document.querySelector("#saveAuthoringReferenceButton").addEventListener("click", async () => {
  try {
    const suffix = editingAuthoringReferenceId ? `/references/${editingAuthoringReferenceId}` : "/references";
    const method = editingAuthoringReferenceId ? "PUT" : "POST";
    await mutateAuthoring(suffix, method, authoringReferencePayload());
    clearAuthoringReferenceForm();
  } catch (error) { authoringMessage.textContent = error instanceof Error ? error.message : "Referenceを保存できませんでした。"; }
});

document.querySelector("#cancelAuthoringReferenceButton").addEventListener("click", clearAuthoringReferenceForm);

document.querySelector("#authoringImportFile").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const draft = JSON.parse(await file.text());
    const payload = await authoringApi("/api/authoring/import", authoringJsonOptions("POST", { draft }));
    currentAuthoringDraft = payload.draft;
    currentAuthoringValidation = payload.validation;
    renderAuthoringDraft();
    await refreshAuthoringDrafts(payload.draft.draft_id);
    authoringMessage.textContent = "JSONを新しい下書きとしてImportしました。";
  } catch (error) { authoringMessage.textContent = error instanceof Error ? error.message : "Importできませんでした。"; }
  event.target.value = "";
});

function exportAuthoring(format) {
  if (!currentAuthoringDraft) { authoringMessage.textContent = "先に下書きを開いてください。"; return; }
  window.location.assign(`/api/authoring/drafts/${currentAuthoringDraft.draft_id}/export?format=${format}`);
}

document.querySelector("#exportAuthoringJsonButton").addEventListener("click", () => exportAuthoring("json"));
document.querySelector("#exportAuthoringMarkdownButton").addEventListener("click", () => exportAuthoring("markdown"));

function resetPromotionPreview() {
  currentPromotionPreview = null;
  document.querySelector("#promotionPreview").hidden = true;
  document.querySelector("#commitPromotionButton").disabled = true;
  document.querySelector("#promotionSavedResult").hidden = true;
  document.querySelector("#promotionMessage").textContent = "";
}

function renderPromotionPreview(preview) {
  currentPromotionPreview = preview;
  document.querySelector("#promotionPreview").hidden = false;
  document.querySelector("#promotionKnowledgeName").textContent = preview.knowledge_name;
  document.querySelector("#promotionCategory").textContent = termTypeLabels[preview.category] || preview.category;
  document.querySelector("#promotionCounts").textContent = `${preview.claim_count} / ${preview.reference_count}`;
  document.querySelector("#promotionCompleteness").textContent = `${preview.completeness_score}%`;
  document.querySelector("#promotionRegistryKey").textContent = preview.registry_key;
  document.querySelector("#promotionOperation").textContent =
    preview.operation === "create" ? "新規作成" : "Version更新";
  document.querySelector("#promotionKnowledgeId").textContent = preview.target_knowledge_id;
  document.querySelector("#promotionVersion").textContent = `v${preview.target_version} / draft`;
  const list = document.querySelector("#promotionValidationChecks");
  list.replaceChildren();
  preview.validation.checks.forEach((check) => {
    const item = document.createElement("li");
    item.dataset.severity = check.passed ? "info" : "error";
    const title = document.createElement("strong");
    title.textContent = `${check.passed ? "✓" : "×"} ${check.code}`;
    const message = document.createElement("span");
    message.textContent = check.message;
    item.append(title, message);
    list.appendChild(item);
  });
  document.querySelector("#commitPromotionButton").disabled = !preview.validation.promotion_allowed;
  document.querySelector("#promotionMessage").textContent = preview.validation.promotion_allowed
    ? "Promotion可能です。確定するまでRegistryは変更されません。"
    : "不足項目を修正して、もう一度Previewしてください。Registryは変更されていません。";
}

async function previewPromotion() {
  if (!currentAuthoringDraft) throw new Error("先に下書きを開いてください。");
  const payload = await authoringApi(
    `/api/authoring/drafts/${currentAuthoringDraft.draft_id}/promotion/preview`,
    { method: "POST" },
  );
  renderPromotionPreview(payload.preview);
  await refreshPromotionLogs();
}

async function commitPromotion() {
  if (!currentPromotionPreview) throw new Error("先にPromotion Previewを実行してください。");
  const payload = await authoringApi("/api/authoring/promotions", authoringJsonOptions("POST", {
    preview_id: currentPromotionPreview.preview_id,
    draft_disposition: document.querySelector("#promotionDraftDisposition").value,
    actor: document.querySelector("#promotionActor").value.trim() || "knowledge_author",
    comment: document.querySelector("#promotionComment").value.trim(),
  }));
  const result = payload.result;
  const output = document.querySelector("#promotionSavedResult");
  output.hidden = false;
  output.textContent = `Registry保存完了：${result.knowledge_id} / Version ${result.knowledge_version} / Approval ${result.approval_state} / Draft ${result.draft_lifecycle_state}`;
  document.querySelector("#promotionMessage").textContent = "正式KnowledgeへPromotionしました。自動承認は行っていません。";
  document.querySelector("#commitPromotionButton").disabled = true;
  await refreshAuthoringDrafts(currentAuthoringDraft.draft_id);
  await refreshPromotionLogs();
  await refreshRegistryList(true);
}

async function refreshPromotionLogs() {
  const payload = await authoringApi("/api/authoring/promotion/logs?limit=20");
  const list = document.querySelector("#promotionLogList");
  list.replaceChildren();
  if (!payload.logs.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Promotion履歴はまだありません。";
    list.appendChild(empty);
    return;
  }
  payload.logs.forEach((event) => {
    const card = document.createElement("article");
    card.className = "authoring-item";
    const title = document.createElement("strong");
    title.textContent = `${event.event_type === "preview" ? "Preview" : "Promotion"} · ${event.status}`;
    const detail = document.createElement("small");
    detail.textContent = `${event.knowledge_id} · v${event.knowledge_version} · ${new Date(event.occurred_at).toLocaleString("ja-JP")}`;
    card.append(title, detail);
    list.appendChild(card);
  });
}

document.querySelector("#previewPromotionButton").addEventListener("click", async () => {
  try { await previewPromotion(); }
  catch (error) { document.querySelector("#promotionMessage").textContent = error instanceof Error ? error.message : "Previewできませんでした。"; }
});

document.querySelector("#commitPromotionButton").addEventListener("click", async () => {
  try { await commitPromotion(); }
  catch (error) { document.querySelector("#promotionMessage").textContent = error instanceof Error ? error.message : "Promotionできませんでした。"; }
});

document.querySelector("#refreshPromotionLogButton").addEventListener("click", async () => {
  try { await refreshPromotionLogs(); }
  catch (error) { document.querySelector("#promotionMessage").textContent = error instanceof Error ? error.message : "Promotion Logを読み込めませんでした。"; }
});

fetch("/api/status")
  .then((response) => response.json())
  .then((status) => {
    const badge = document.querySelector("#providerBadge");
    const geminiBadge = document.querySelector("#geminiBadge");
    if (status.provider === "fixture") {
      badge.textContent = "固定テストモード";
    } else if (status.openai_key_configured) {
      badge.textContent = "OpenAI 接続準備OK";
      badge.className = "badge success";
    } else {
      badge.textContent = "OpenAI APIキー未設定";
      badge.className = "badge warning";
    }
    if (status.gemini_sandbox_api_key_configured) {
      geminiBadge.textContent = "Gemini Sandbox準備OK";
      geminiBadge.className = "badge success";
    } else {
      geminiBadge.textContent = "Gemini APIキー未設定";
      geminiBadge.className = "badge warning";
    }
  })
  .catch(() => {});

refreshRegistryList(true);
refreshArtifactRegistryList(true);
refreshBackups();
loadDiseaseRelationVocabulary();
authoringApi("/api/authoring/promotion/semantic-slots")
  .then((payload) => { promotionSemanticSlots = payload.semantic_slots; })
  .then(() => refreshAuthoringDrafts())
  .catch(() => { authoringMessage.textContent = "保存済み下書きを読み込めませんでした。"; });
refreshPromotionLogs().catch(() => {
  document.querySelector("#promotionMessage").textContent = "Promotion Logを読み込めませんでした。";
});
