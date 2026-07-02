param(
  [string]$ProjectId = "YOUR_PROJECT_ID",
  [string]$Member = "user:YOUR_EMAIL@example.com"
)

python .\src\security\google_secret_manager_provisioning.py --project-id $ProjectId --member $Member
