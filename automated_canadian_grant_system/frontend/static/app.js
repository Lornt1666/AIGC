const result = document.querySelector("#result");
const portalSelect = document.querySelector("#portal-id");

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
    item.textContent = `${portal.organization}: ${portal.ingestion_mode}`;
    portalsTarget.append(item);
    const option = document.createElement("option");
    option.value = portal.portal_id;
    option.textContent = portal.organization;
    portalSelect.append(option);
  }
}

document.querySelector("#draft-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const numberOrNull = (name) => {
    const value = form.get(name);
    return value === "" ? null : Number(value);
  };
  const payload = {
    grant: {
      grant_id: `manual_${Date.now()}`,
      portal_id: form.get("portal_id"),
      grant_name: form.get("grant_name"),
      guideline_url: "https://operator-supplied.local/review-required",
      summary: "Operator-supplied program information requires official guideline review.",
      eligibility: {
        eligible_regions: ["Alberta"],
        funding_ceiling_cad: numberOrNull("funding_ceiling_cad"),
        required_matching_ratio: numberOrNull("required_matching_ratio"),
        source_verification_status: "operator_review_required"
      }
    },
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

loadPortal().catch((error) => {
  result.textContent = `Unable to load local portal: ${error.message}`;
});
