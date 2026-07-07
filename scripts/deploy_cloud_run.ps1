param(
    [Parameter(Mandatory=$true)] [string] $ProjectId,
    [string] $Region = "us-central1",
    [string] $ServiceName = "aigc-governed-worker",
    [string] $CommandCenterTokenSecret = "aigc-command-center-token"
)

$ErrorActionPreference = "Stop"

Write-Host "Building and deploying $ServiceName to Google Cloud Run..."

gcloud config set project $ProjectId

gcloud builds submit --tag "gcr.io/$ProjectId/$ServiceName"

gcloud run deploy $ServiceName `
    --image "gcr.io/$ProjectId/$ServiceName" `
    --platform managed `
    --region $Region `
    --no-allow-unauthenticated `
    --set-env-vars "AIGC_ENV=production,PORT=8000" `
    --set-secrets "AIGC_COMMAND_CENTER_TOKEN=$CommandCenterTokenSecret:latest"

Write-Host "Deployment command completed with authenticated invoker required and command-center token loaded from Secret Manager."
