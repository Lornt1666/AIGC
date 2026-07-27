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
    [Parameter(Mandatory=$true)] [string] $OperatorSubjectKeySecretVersion
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

function Assert-NativeSuccess {
    param([Parameter(Mandatory=$true)] [string] $Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
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
    --max-instances 3 `
    --concurrency 8 `
    --timeout 60 `
    --set-env-vars "AIGC_ENV=production,PORT=8000,AIGC_RELEASE_REVISION=$ReleaseRevision,AIGC_GEMINI_ENABLED=true,GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_LOCATION=$VertexLocation,AIGC_GEMINI_MODEL=$GeminiModel,AIGC_GEMINI_EVIDENCE_BACKEND=gcs,AIGC_GEMINI_EVIDENCE_BUCKET=$EvidenceBucket,AIGC_GEMINI_EVIDENCE_PREFIX=product-evidence/gemini" `
    --set-secrets "AIGC_COMMAND_CENTER_TOKEN=$CommandCenterTokenSecret`:$CommandCenterTokenSecretVersion,AIGC_OPERATOR_SUBJECT_KEY=$OperatorSubjectKeySecret`:$OperatorSubjectKeySecretVersion"
Assert-NativeSuccess "Deploy Cloud Run release"

Write-Host "Deployment command completed with authenticated invoker, dedicated service identity, immutable Artifact Registry digest $ImageDigest, exact release revision, bounded scaling, Vertex AI Gemini configuration, durable evidence storage, and pinned command-token and operator-subject-key Secret Manager versions."
