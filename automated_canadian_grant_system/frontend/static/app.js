const result = document.querySelector("#result");
const portalSelect = document.querySelector("#portal-id");
const grantName = document.querySelector("#grant-name");
const templateStatus = document.querySelector("#template-status");
let selectedDraftTemplate = null;

function appendDefinition(target, label, value) {
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = String(value);
  target.append(term, description);
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
    option.textContent = `${portal.organization} (${portal.local_draft_template_available ? "template available" : "template unavailable"})`;
    option.disabled = !portal.local_draft_template_available;
    portalSelect.append(option);
  }
  await loadDraftTemplate(portalSelect.value);
}

async function loadDraftTemplate(portalId) {
  selectedDraftTemplate = null;
  templateStatus.textContent = "Loading local draft template…";
  const response = await fetch(`/api/draft-payloads/${encodeURIComponent(portalId)}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail?.message || "Local draft template is unavailable.");
  }
  selectedDraftTemplate = payload;
  grantName.value = payload.grant.grant_name;
  templateStatus.textContent =
    `${payload.template_id}: local template only. The official source was not fetched or verified; ` +
    `${payload.required_operator_inputs.length} operator inputs remain required.`;
}

document.querySelector("#draft-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedDraftTemplate) {
    result.textContent = "Select an available local draft template before generating a draft.";
    return;
  }
  const form = new FormData(event.currentTarget);
  const numberOrNull = (name) => {
    const value = form.get(name);
    return value === "" ? null : Number(value);
  };
  const grant = {
    ...selectedDraftTemplate.grant,
    grant_name: form.get("grant_name"),
    eligibility: {
      ...selectedDraftTemplate.grant.eligibility,
      funding_ceiling_cad: numberOrNull("funding_ceiling_cad"),
      required_matching_ratio: numberOrNull("required_matching_ratio")
    }
  };
  const payload = {
    grant,
    project: {
      project_title: form.get("project_title"),
      project_summary: form.get("project_summary"),
      requested_funding_cad: numberOrNull("requested_funding_cad"),
      matching_contribution_cad: numberOrNull("matching_contribution_cad"),
      duration_months: 12
    }
  };
  result.textContent = "Generating local draft…";
  const response = await fetch("/api/generate_application", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const body = await response.json();
  result.textContent = JSON.stringify(body, null, 2);
});

portalSelect.addEventListener("change", () => {
  loadDraftTemplate(portalSelect.value).catch((error) => {
    templateStatus.textContent = `Unable to load local template: ${error.message}`;
    result.textContent = templateStatus.textContent;
  });
});

loadPortal().catch((error) => {
  result.textContent = `Unable to load local portal: ${error.message}`;
});
