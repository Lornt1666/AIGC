# Google Cloud Secret Manager Setup

This runbook is intentionally non-executing. It documents the commands needed after the operator chooses a Google Cloud project and confirms that real secrets should be connected.

Google Cloud Secret Manager stores secret values such as API keys, passwords, OAuth client secrets, webhook signing secrets, certificates, and database passwords.

Google Cloud KMS manages cryptographic encryption keys. Use KMS for encryption key material and local archive encryption workflows, not as the general API-key/password vault.

Avoid long-lived downloaded Google service account key JSON files where possible. Prefer Google-managed identity or user Application Default Credentials. Do not store raw service account key JSON in this repo, AIGC_MEMORY_CORE, Google Secret Manager, prompts, logs, or employer packets.

## 1. Select Or Create A Project

```powershell
gcloud projects create YOUR_PROJECT_ID
gcloud config set project YOUR_PROJECT_ID
```

## 2. Enable Secret Manager

```powershell
gcloud services enable secretmanager.googleapis.com
```

## 3. Create Secrets

```powershell
gcloud secrets create aigc-openai-api-key --replication-policy="automatic"
gcloud secrets create aigc-github-token --replication-policy="automatic"
gcloud secrets create aigc-adzuna-api-key --replication-policy="automatic"
```

## 4. Add Secret Versions

Do not paste real values into chat or logs. Run this locally in a trusted terminal.

```powershell
Set-Content -NoNewline -Path .\secret_value.tmp -Value "REAL_SECRET_VALUE"
gcloud secrets versions add aigc-openai-api-key --data-file=.\secret_value.tmp
Remove-Item .\secret_value.tmp
```

## 5. Grant Least-Privilege Access

Grant `roles/secretmanager.secretAccessor` only to the runtime identity that needs the secret.

```powershell
gcloud secrets add-iam-policy-binding aigc-openai-api-key `
  --member="serviceAccount:YOUR_RUNTIME_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor"
```

## 6. Update Manifests

Replace `YOUR_PROJECT_ID` in:

- `config/secret_manifest.json`
- `C:\Users\Justice Gray Macioch\AIGC_MEMORY_CORE\config\secret_manifest.json`

The manifest stores only resource references, never raw secret values.

## Safety Rule

The 2TB drive remembers the map. Google Secret Manager holds the keys. Omega-X decides who may ask for them. The Secret Broker retrieves them only after policy approval. The audit ledger records the event without exposing the value.
