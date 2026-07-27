param(
    [Parameter(Mandatory=$true)] [string] $ProjectId,
    [Parameter(Mandatory=$true)] [string] $Region,
    [Parameter(Mandatory=$true)] [string] $VertexLocation,
    [Parameter(Mandatory=$true)] [string] $GeminiModel,
    [Parameter(Mandatory=$true)] [string] $EvidenceBucket,
    [Parameter(Mandatory=$true)] [string] $ServiceAccount,
    [Parameter(Mandatory=$true)] [string] $ArtifactRegistryRepository,
    [Parameter(Mandatory=$true)] [string] $ReleaseRevision,
    [string] $ServiceName = "aigc-governed-worker",
    [string] $CommandCenterTokenSecret = "aigc-command-center-token",
    [Parameter(Mandatory=$true)] [string] $CommandCenterTokenSecretVersion,
    [string] $OperatorSubjectKeySecret = "aigc-operator-subject-key",
    [Parameter(Mandatory=$true)] [string] $OperatorSubjectKeySecretVersion,
    [Parameter(Mandatory=$true)] [string] $DeploymentPermitPath,
    [string] $EnvironmentDecisionPath = "config/production_environment_decision.json",
    [string] $DeploymentBaselinePath = "config/production_deployment_baseline.json",
    [string] $ReleaseGatePath = "config/production_release_gate.json"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

function Assert-NativeSuccess {
    param([Parameter(Mandatory=$true)] [string] $Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

foreach ($PolicyPath in @(
    $EnvironmentDecisionPath,
    $DeploymentBaselinePath,
    $ReleaseGatePath,
    $DeploymentPermitPath
)) {
    if (-not (Test-Path -LiteralPath $PolicyPath -PathType Leaf)) {
        throw "Required deployment authority file is missing: $PolicyPath"
    }
}

$EnvironmentDecision = Get-Content -Raw -LiteralPath $EnvironmentDecisionPath |
    ConvertFrom-Json
$DeploymentBaseline = Get-Content -Raw -LiteralPath $DeploymentBaselinePath |
    ConvertFrom-Json
$ReleaseGate = Get-Content -Raw -LiteralPath $ReleaseGatePath |
    ConvertFrom-Json
$DeploymentPermit = Get-Content -Raw -LiteralPath $DeploymentPermitPath |
    ConvertFrom-Json

if ($EnvironmentDecision.authority.production_deployment_authorized -ne $true) {
    throw "The accepted environment decision does not authorize production deployment."
}
if (
    $DeploymentBaseline.authority.production_resource_creation_authorized -ne $true -or
    $DeploymentBaseline.authority.production_apply_authorized -ne $true -or
    $DeploymentBaseline.authority.production_deployment_authorized -ne $true
) {
    throw "The production deployment baseline does not authorize resource creation, apply, and deployment."
}
if ($ReleaseGate.deployment_default_authorized -ne $false) {
    throw "The release-gate policy must retain a default-deny deployment posture."
}
if (
    $DeploymentPermit.deployment_authorized -ne $true -or
    $DeploymentPermit.operator_approval_recorded -ne $true -or
    $DeploymentPermit.environment -ne "production"
) {
    throw "The supplied deployment permit is not an approved production permit."
}
if (
    $DeploymentPermit.release_revision -ne $ReleaseRevision -or
    $DeploymentPermit.project_id -ne $ProjectId -or
    $DeploymentPermit.region -ne $Region -or
    $DeploymentPermit.service_name -ne $ServiceName
) {
    throw "The deployment permit does not match the exact release target."
}
$PermitExpiry = [DateTimeOffset]::Parse(
    [string] $DeploymentPermit.expires_at,
    [Globalization.CultureInfo]::InvariantCulture
)
if ($PermitExpiry -le [DateTimeOffset]::UtcNow) {
    throw "The deployment permit is expired."
}
if (
    $Region -ne [string] $EnvironmentDecision.cloud.primary_region -or
    $Region -ne [string] $DeploymentBaseline.cloud.primary_region
) {
    throw "Region must match the accepted production primary region."
}

if ($ReleaseRevision -notmatch '^[a-f0-9]{40}$') {
    throw "ReleaseRevision must be the exact 40-character lowercase Git SHA."
}

$HeadRevision = (git rev-parse HEAD).Trim()
Assert-NativeSuccess "Resolve repository HEAD"
if ($HeadRevision -ne $ReleaseRevision) {
    throw "ReleaseRevision does not match the checked-out repository HEAD."
}
$WorkingTreeState = [string]::Join(
    [Environment]::NewLine,
    @(git status --porcelain --untracked-files=all)
).Trim()
Assert-NativeSuccess "Inspect repository working tree"
if ($WorkingTreeState) {
    throw "Deployment requires a clean tracked and untracked working tree."
}

$ImageBase = "${Region}-docker.pkg.dev/$ProjectId/$ArtifactRegistryRepository/$ServiceName"
$TaggedImageUri = "${ImageBase}:$ReleaseRevision"

Write-Host "Building and deploying $ServiceName to Google Cloud Run..."

gcloud config set project $ProjectId
Assert-NativeSuccess "Select Google Cloud project"

gcloud artifacts repositories describe $ArtifactRegistryRepository `
    --location $Region `
    --project $ProjectId
Assert-NativeSuccess "Verify Artifact Registry repository"

gcloud builds submit --tag $TaggedImageUri
Assert-NativeSuccess "Build release image"

$ImageDigest = (
    gcloud artifacts docker images describe $TaggedImageUri `
        --project $ProjectId `
        --format "value(image_summary.digest)"
).Trim()
Assert-NativeSuccess "Resolve release image digest"
if ($ImageDigest -notmatch '^sha256:[a-f0-9]{64}$') {
    throw "Artifact Registry did not return an immutable sha256 image digest."
}
$ImmutableImageUri = "${ImageBase}@$ImageDigest"

gcloud run deploy $ServiceName `
    --image $ImmutableImageUri `
    --platform managed `
    --region $Region `
    --no-allow-unauthenticated `
    --service-account $ServiceAccount `
    --min-instances 0 `
    --max-instances $DeploymentBaseline.runtime.max_instances `
    --concurrency $DeploymentBaseline.runtime.concurrency `
    --timeout $DeploymentBaseline.runtime.request_timeout_seconds `
    --set-env-vars "AIGC_ENV=production,PORT=$($DeploymentBaseline.runtime.port),AIGC_RELEASE_REVISION=$ReleaseRevision,AIGC_GEMINI_ENABLED=true,GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_LOCATION=$VertexLocation,AIGC_GEMINI_MODEL=$GeminiModel,AIGC_GEMINI_EVIDENCE_BACKEND=gcs,AIGC_GEMINI_EVIDENCE_BUCKET=$EvidenceBucket,AIGC_GEMINI_EVIDENCE_PREFIX=product-evidence/gemini" `
    --set-secrets "AIGC_COMMAND_CENTER_TOKEN=$CommandCenterTokenSecret`:$CommandCenterTokenSecretVersion,AIGC_OPERATOR_SUBJECT_KEY=$OperatorSubjectKeySecret`:$OperatorSubjectKeySecretVersion"
Assert-NativeSuccess "Deploy Cloud Run release"

Write-Host "Deployment command completed only after repository authority and exact-target permit checks, with authenticated invoker, dedicated service identity, immutable Artifact Registry digest $ImageDigest, exact release revision, bounded scaling, Vertex AI Gemini configuration, durable evidence storage, and pinned command-token and operator-subject-key Secret Manager versions."
