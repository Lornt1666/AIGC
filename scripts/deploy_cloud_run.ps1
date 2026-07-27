param(
    [Parameter(Mandatory=$true)] [string] $ProjectId,
    [Parameter(Mandatory=$true)] [string] $Region,
    [Parameter(Mandatory=$true)] [string] $VertexLocation,
    [Parameter(Mandatory=$true)] [string] $GeminiModel,
    [Parameter(Mandatory=$true)] [string] $EvidenceBucket,
    [Parameter(Mandatory=$true)] [string] $ServiceAccount,
    [Parameter(Mandatory=$true)] [string] $ArtifactRegistryRepository,
    [string] $ServiceName = "aigc-governed-worker",
    [string] $CommandCenterTokenSecret = "aigc-command-center-token",
    [Parameter(Mandatory=$true)] [string] $CommandCenterTokenSecretVersion
)

$ErrorActionPreference = "Stop"
$ImageUri = "${Region}-docker.pkg.dev/$ProjectId/$ArtifactRegistryRepository/$ServiceName"

Write-Host "Building and deploying $ServiceName to Google Cloud Run..."

gcloud config set project $ProjectId

gcloud artifacts repositories describe $ArtifactRegistryRepository `
    --location $Region `
    --project $ProjectId

gcloud builds submit --tag $ImageUri

gcloud run deploy $ServiceName `
    --image $ImageUri `
    --platform managed `
    --region $Region `
    --no-allow-unauthenticated `
    --service-account $ServiceAccount `
    --min-instances 0 `
    --max-instances 3 `
    --concurrency 8 `
    --timeout 60 `
    --set-env-vars "AIGC_ENV=production,PORT=8000,AIGC_GEMINI_ENABLED=true,GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_LOCATION=$VertexLocation,AIGC_GEMINI_MODEL=$GeminiModel,AIGC_GEMINI_EVIDENCE_BACKEND=gcs,AIGC_GEMINI_EVIDENCE_BUCKET=$EvidenceBucket,AIGC_GEMINI_EVIDENCE_PREFIX=product-evidence/gemini" `
    --set-secrets "AIGC_COMMAND_CENTER_TOKEN=$CommandCenterTokenSecret`:$CommandCenterTokenSecretVersion"

Write-Host "Deployment command completed with authenticated invoker, dedicated service identity, Artifact Registry image, bounded scaling, Vertex AI Gemini configuration, durable evidence storage, and a pinned Secret Manager version."
