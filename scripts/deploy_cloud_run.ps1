param(
    [Parameter(Mandatory=$true)] [string] $ProjectId,
    [string] $Region = "us-central1",
    [string] $ServiceName = "aigc-governed-worker"
)

$ErrorActionPreference = "Stop"

Write-Host "Building and deploying $ServiceName to Google Cloud Run..."

gcloud config set project $ProjectId

gcloud builds submit --tag "gcr.io/$ProjectId/$ServiceName"

gcloud run deploy $ServiceName `
    --image "gcr.io/$ProjectId/$ServiceName" `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --set-env-vars "AIGC_ENV=production,PORT=8000"

Write-Host "Deployment command completed. Review Cloud Run IAM and authentication policy before sharing the URL."
