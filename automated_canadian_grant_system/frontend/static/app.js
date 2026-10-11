const result = document.querySelector("#result");
const portalSelect = document.querySelector("#portal-id");
const grantName = document.querySelector("#grant-name");
const templateStatus = document.querySelector("#template-status");
const reviewSection = document.querySelector("#operator-review-section");
const reviewForm = document.querySelector("#operator-review-form");
const reviewResult = document.querySelector("#operator-review-result");
const exportButton = document.querySelector("#local-export-button");

let selectedDraftTemplate = null;
let currentApplication = null;

function appendDefinition(target, label, value) {
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = String(value);
  target.append(term, description);
}

function nonEmptyLines(value) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function numberOrNull(form, name) {
  const value = form.get(name);
  return value === "" ? null : Number(value);
}

function clearReviewState() {
  currentApplication = null;
  reviewForm.reset();
  reviewSection.hidden = true;
  exportButton.disabled = true;
  reviewResult.textContent = "No local review recorded.";
}

function displayError(target, body, fallback) {
  target.textContent = body?.detail?.message || fallback;
}

async function loadPortal() {
  const [identityResponse, portalsResponse, healthResponse] = await Promise.all([
    fetch("/api/identity"),
    fetch("/api/portals"),
    fetch("/health")
  ]);
  const identity = await identityResponse.json();
  const portalData = await portalsResponse.json();
  const health = await healthResponse.json();

  if (!identityResponse.ok || !portalsResponse.ok || !healthResponse.ok) {
    throw new Error("Unable to load the governed local portal.");
  }

  document.querySelector("#mode").textContent =
    `${health.mode}; external actions performed: ${health.external_action_performed}.`;
  const identityTarget = document.querySelector("#identity");
  appendDefinition(identityTarget, "Entity", identity.entity_name);
  appendDefinition(identityTarget, "Headquarters", identity.headquarters);
  appendDefinition(identityTarget, "Sector", identity.primary_sector);
  appendDefinition(identityTarget, "Verification", identity.verification_status);

  document.querySelector("#portal-recommendation").textContent =
    portalData.recommendation_basis;
  const portalsTarget = document.querySelector("#portals");
  for (const portal of portalData.portals) {
    const item = document.createElement("li");
    item.textContent =
      `${portal.organization}: local template ${portal.local_draft_template_available ? "available" : "unavailable"}; ` +
      `live ingestion ${portalData.live_ingestion_enabled ? "enabled" : "disabled"}.`;
    portalsTarget.append(item);
    const option = document.createElement("option");
    option.value = portal.portal_id;
    option.textContent =
      `${portal.organization} (${portal.local_draft_template_available ? "template available" : "template unavailable"})`;
    option.disabled = !portal.local_draft_template_available;
    portalSelect.append(option);
  }
  await loadDraftTemplate(portalSelect.value);
}

async function loadDraftTemplate(portalId) {
  selectedDraftTemplate = null;
  templateStatus.textContent = "Loading local draft template…";
  const response = await fetch(
    `/api/draft-payloads/${encodeURIComponent(portalId)}`
  );
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(
      payload.detail?.message || "Local draft template is unavailable."
    );
  }
  selectedDraftTemplate = payload;
  grantName.value = payload.grant.grant_name;
  document.querySelector("#review-program-name").value =
    payload.grant.grant_name;
  document.querySelector("#review-source-guideline-url").value =
    payload.source_attribution.official_portal_url;
  document.querySelector("#review-source-evidence").value =
    payload.source_attribution.official_portal_url;
  templateStatus.textContent =
    `${payload.template_id}: local template only. The official source was not fetched or verified; ` +
    `${payload.required_operator_inputs.length} operator inputs remain required.`;
}

document.querySelector("#draft-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedDraftTemplate) {
    result.textContent =
      "Select an available local draft template before generating a draft.";
    return;
  }
  const form = new FormData(event.currentTarget);
  const grant = {
    ...selectedDraftTemplate.grant,
    grant_name: form.get("grant_name"),
    eligibility: {
      ...selectedDraftTemplate.grant.eligibility,
      funding_ceiling_cad: numberOrNull(form, "funding_ceiling_cad"),
      required_matching_ratio: numberOrNull(form, "required_matching_ratio")
    }
  };
  const payload = {
    grant,
    project: {
      project_title: form.get("project_title"),
      project_summary: form.get("project_summary"),
      requested_funding_cad: numberOrNull(form, "requested_funding_cad"),
      matching_contribution_cad: numberOrNull(
        form,
        "matching_contribution_cad"
      ),
      duration_months: 12
    }
  };
  result.textContent = "Generating and persisting local draft…";
  const response = await fetch("/api/generate_application", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const body = await response.json();
  if (!response.ok) {
    displayError(result, body, "Local draft generation was blocked.");
    return;
  }
  currentApplication = body.persistence;
  document.querySelector("#review-application-id").value =
    currentApplication.application_id;
  document.querySelector("#review-expected-revision").value =
    currentApplication.revision;
  document.querySelector("#review-source-reviewed-at").value =
    new Date().toISOString().slice(0, 10);
  reviewSection.hidden = false;
  exportButton.disabled = true;
  reviewResult.textContent =
    "Draft persisted. Complete the operator review before a local export can be viewed.";
  result.textContent = JSON.stringify(body, null, 2);
});

reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentApplication) {
    reviewResult.textContent =
      "Generate a local draft before recording an operator review.";
    return;
  }
  const form = new FormData(event.currentTarget);
  const payload = {
    expected_revision: Number(form.get("expected_revision")),
    decision: form.get("decision"),
    operator_role: form.get("operator_role"),
    program_name: form.get("program_name"),
    source_guideline_url: form.get("source_guideline_url"),
    source_version: form.get("source_version"),
    source_reviewed_at: form.get("source_reviewed_at"),
    operator_attested_criteria: {
      eligibility_criteria_summary: form.get("eligibility_criteria_summary"),
      financial_criteria_summary: form.get("financial_criteria_summary"),
      eligible_regions: nonEmptyLines(form.get("eligible_regions")),
      min_trl: numberOrNull(form, "min_trl"),
      max_trl: numberOrNull(form, "max_trl"),
      min_headcount: numberOrNull(form, "min_headcount"),
      max_headcount: numberOrNull(form, "max_headcount"),
      funding_ceiling_cad: numberOrNull(form, "funding_ceiling_cad"),
      required_matching_ratio: numberOrNull(form, "required_matching_ratio")
    },
    source_evidence_references: nonEmptyLines(
      form.get("source_evidence_references")
    ),
    budget_evidence_references: nonEmptyLines(
      form.get("budget_evidence_references")
    ),
    review_notes: form.get("review_notes"),
    operator_attests_current_source:
      form.get("operator_attests_current_source") === "on",
    operator_attests_evidence_complete:
      form.get("operator_attests_evidence_complete") === "on",
    ai_use_disclosure_acknowledged:
      form.get("ai_use_disclosure_acknowledged") === "on"
  };
  reviewResult.textContent = "Recording local operator review…";
  const response = await fetch(
    `/api/applications/${encodeURIComponent(currentApplication.application_id)}/review`,
    {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    }
  );
  const body = await response.json();
  if (!response.ok) {
    displayError(reviewResult, body, "Local operator review was blocked.");
    return;
  }
  currentApplication = {
    application_id: body.application_id,
    revision: body.revision,
    lifecycle_state: body.lifecycle_state
  };
  document.querySelector("#review-expected-revision").value =
    currentApplication.revision;
  exportButton.disabled =
    currentApplication.lifecycle_state !== "LOCAL_EXPORT_APPROVED";
  reviewResult.textContent = JSON.stringify(body, null, 2);
});

exportButton.addEventListener("click", async () => {
  if (!currentApplication) {
    return;
  }
  reviewResult.textContent = "Loading local export artifact…";
  const response = await fetch(
    `/api/applications/${encodeURIComponent(currentApplication.application_id)}/export`
  );
  const body = await response.json();
  if (!response.ok) {
    displayError(reviewResult, body, "Local export remains blocked.");
    return;
  }
  reviewResult.textContent = JSON.stringify(body, null, 2);
});

portalSelect.addEventListener("change", () => {
  clearReviewState();
  loadDraftTemplate(portalSelect.value).catch((error) => {
    templateStatus.textContent = `Unable to load local template: ${error.message}`;
    result.textContent = templateStatus.textContent;
  });
});

loadPortal().catch((error) => {
  result.textContent = `Unable to load local portal: ${error.message}`;
});
