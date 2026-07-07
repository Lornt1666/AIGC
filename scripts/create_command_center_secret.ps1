param(
    [Parameter(Mandatory=$true)] [string] $ProjectId,
    [string] $SecretName = "aigc-command-center-token",
    [string] $ReplicationPolicy = "automatic",
    [string] $CloudRunServiceAccountEmail = ""
)

$ErrorActionPreference = "Stop"

Write-Host "Configuring Google Secret Manager secret '$SecretName' in project '$ProjectId'."
Write-Host "The token value will be entered locally, written to a temporary file without a trailing newline, uploaded as a secret version, then deleted."

gcloud config set project $ProjectId | Out-Null

gcloud services enable secretmanager.googleapis.com run.googleapis.com cloudbuild.googleapis.com | Out-Null

$secretExists = $true
try {
    gcloud secrets describe $SecretName --project $ProjectId | Out-Null
} catch {
    $secretExists = $false
}

if (-not $secretExists) {
    Write-Host "Creating secret container '$SecretName'."
    gcloud secrets create $SecretName --project $ProjectId --replication-policy $ReplicationPolicy | Out-Null
} else {
    Write-Host "Secret container already exists; adding a new version."
}

$secureToken = Read-Host "Enter AIGC command center token" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
$tempPath = [System.IO.Path]::GetTempFileName()

try {
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    [System.IO.File]::WriteAllText($tempPath, $plainToken, [System.Text.UTF8Encoding]::new($false))
    gcloud secrets versions add $SecretName --project $ProjectId --data-file $tempPath | Out-Null
    Write-Host "Uploaded new secret version for '$SecretName'."
} finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    if (Test-Path $tempPath) {
        Remove-Item $tempPath -Force
    }
}

if ($CloudRunServiceAccountEmail) {
    Write-Host "Granting Secret Manager Secret Accessor to service account '$CloudRunServiceAccountEmail'."
    gcloud secrets add-iam-policy-binding $SecretName `
        --project $ProjectId `
        --member "serviceAccount:$CloudRunServiceAccountEmail" `
        --role "roles/secretmanager.secretAccessor" | Out-Null
} else {
    Write-Host "No service account grant requested. If Cloud Run uses a runtime service account, grant it roles/secretmanager.secretAccessor on this secret."
}

Write-Host "Secret Manager token setup complete. Deploy with scripts/deploy_cloud_run.ps1, which maps this secret to AIGC_COMMAND_CENTER_TOKEN."
