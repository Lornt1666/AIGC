"""Read-only CI role agents. No repository mutation or release authority."""
from __future__ import annotations
import base64,hashlib,io,json,re,time,zipfile
from typing import Any,Mapping,Protocol
from urllib.parse import urlparse
import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aigc_ci_validation_agent import diagnose_failure,normalize_observation
SHA=re.compile(r"^[0-9a-f]{40}$"); DIGEST=re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
class EvidenceError(ValueError): pass
class CanonicalRunnerOutcomeAgent:
 @staticmethod
 def evaluate(run,jobs,stages,*,expected_sha):
  run=run if isinstance(run,Mapping) else {}; jobs=jobs if isinstance(jobs,list) else []; stages=stages if isinstance(stages,Mapping) else {}
  s=stages.get("canonical_validation_runner",stages.get("canonical_runner",{})); s=s if isinstance(s,Mapping) else {}
  runner=s.get("status") in {"PASS","pass","passed","success"} and s.get("target_sha",s.get("subject_sha",""))==expected_sha
  alljobs=bool(jobs) and all(j.get("status")=="completed" and j.get("conclusion")=="success" for j in jobs)
  overall=bool(SHA.fullmatch(expected_sha)) and run.get("head_sha")==expected_sha and run.get("status")=="completed" and run.get("conclusion")=="success" and alljobs
  return {"schema_version":"aigc-canonical-outcome/1.0","canonical_runner_success":runner,"overall_workflow_success":overall,"runner_success_is_not_workflow_success":runner and not overall,"decision":"PASS" if runner and overall else "BLOCK","release_decision":"BLOCK"}
class ReadOnlyObserverAgent:
 def observe(self,**kwargs): return normalize_observation(**kwargs)
class FailClosedTestAgent:
 @staticmethod
 def required_cases(): return ("missing_run","missing_artifact","stale_commit","forged_success","failed_independent_review","expired_artifact","bad_artifact_digest","invalid_reviewer_signature","expired_reviewer_approval")
 @staticmethod
 def disposition(**checks): return "ELIGIBLE_FOR_INDEPENDENT_ACCEPTANCE" if all(checks.get(k) is True for k in ("exact_sha","workflow_success","artifact_verified","reviewer_authenticated","independent_review_approved")) else "BLOCK"
class OperatingSpecificationAgent:
 @staticmethod
 def specification(): return {"mode":"read_only","automatic_repairs":False,"protected_controls_may_be_changed":False,"workflow_reruns":False,"merge_authority":False,"deployment_authority":False,"release_decision_authority":False,"canonical_release_authority":"Release Assurance Agent"}
class FailureDiagnosisAgent:
 def propose(self,observation,logs=""):
  r=diagnose_failure(observation,logs); r.update({"approval_required":True,"patch_applied":False,"protected_controls_changed":False}); return r
class ValidationStatusAgent:
 @staticmethod
 def summarize(outcome,observation):
  reasons=sorted(set(observation.get("reasons",[]))); ok=outcome.get("canonical_runner_success") is True and outcome.get("overall_workflow_success") is True and not reasons
  return {"status":"VALIDATED" if ok else "VALIDATION_PENDING_OR_FAILED","canonical_runner_success":outcome.get("canonical_runner_success") is True,"overall_workflow_success":outcome.get("overall_workflow_success") is True,"blocking_reasons":reasons,"release_decision":"BLOCK"}
class CurrentDispositionAgent:
 @staticmethod
 def evaluate(status,acceptance=None):
  ok=status.get("status")=="VALIDATED" and isinstance(acceptance,Mapping) and acceptance.get("eligible") is True
  return {"disposition":"READY_FOR_RELEASE_ASSURANCE_REVIEW" if ok else "VALIDATION_PENDING_RELEASE_BLOCKED","release_decision":"BLOCK","production_authority":False,"merge_authority":False,"deployment_authority":False}
class ReviewerAuthenticator(Protocol):
 def verify(self,review:Mapping[str,Any],*,expected_sha:str,artifact_digest:str)->dict[str,Any]: ...
class Ed25519ReviewerAuthenticator:
 def __init__(self,trusted_public_keys:Mapping[str,bytes],*,clock_skew_seconds=60): self.keys=dict(trusted_public_keys); self.skew=clock_skew_seconds
 def verify(self,review,*,expected_sha,artifact_digest):
  if not isinstance(review,Mapping): raise EvidenceError("review_missing")
  rid=review.get("reviewer_id")
  if not isinstance(rid,str) or rid not in self.keys: raise EvidenceError("reviewer_not_trusted")
  if review.get("approved") is not True or review.get("subject_sha")!=expected_sha: raise EvidenceError("review_subject_or_approval_invalid")
  if review.get("artifact_digest")!=artifact_digest: raise EvidenceError("review_artifact_digest_mismatch")
  issued,expires=review.get("issued_at"),review.get("expires_at"); now=int(time.time())
  if not isinstance(issued,int) or not isinstance(expires,int) or issued>now+self.skew or expires<=now or expires<=issued: raise EvidenceError("review_expired")
  if not isinstance(review.get("signature"),str): raise EvidenceError("review_signature_missing")
  payload={k:v for k,v in review.items() if k!="signature"}; canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
  try: Ed25519PublicKey.from_public_bytes(self.keys[rid]).verify(base64.b64decode(review["signature"],validate=True),canonical)
  except (ValueError,InvalidSignature) as exc: raise EvidenceError("review_signature_invalid") from exc
  return {"authenticated":True,"approved":True,"reviewer_id":rid,"subject_sha":expected_sha,"artifact_digest":artifact_digest}
class GitHubActionsReadOnlyClient:
 def __init__(self,token,*,client=None,timeout=20):
  if not token or "\r" in token or "\n" in token: raise ValueError("runtime read token required")
  self.token=token; self.client=client or httpx.Client(timeout=timeout,follow_redirects=False)
 def _api(self,url):
  p=urlparse(url)
  if p.scheme!="https" or p.hostname!="api.github.com": raise EvidenceError("untrusted_api_url")
  r=self.client.get(url,headers={"Authorization":f"Bearer {self.token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}); r.raise_for_status(); return r.json()
 def get_run(self,repo,rid): return self._api(f"https://api.github.com/repos/{repo}/actions/runs/{int(rid)}")
 def get_jobs(self,repo,rid): return self._api(f"https://api.github.com/repos/{repo}/actions/runs/{int(rid)}/jobs").get("jobs",[])
 def get_artifacts(self,repo,rid): return self._api(f"https://api.github.com/repos/{repo}/actions/runs/{int(rid)}/artifacts").get("artifacts",[])
 def download_artifact(self,repo,aid):
  r=self.client.get(f"https://api.github.com/repos/{repo}/actions/artifacts/{int(aid)}/zip",headers={"Authorization":f"Bearer {self.token}","Accept":"application/vnd.github+json"})
  for _ in range(4):
   if r.status_code not in (301,302,303,307,308):
    r.raise_for_status()
    if len(r.content)>25*1024*1024: raise EvidenceError("artifact_too_large")
    return r.content
   target=r.headers.get("location",""); p=urlparse(target); host=p.hostname or ""
   if p.scheme!="https" or not (host in {"github.com","objects.githubusercontent.com"} or host.endswith(".blob.core.windows.net") or host.endswith(".amazonaws.com") or host.endswith(".githubusercontent.com")): raise EvidenceError("artifact_redirect_host_rejected")
   r=self.client.get(target,headers={"Accept":"application/zip"})
  raise EvidenceError("artifact_redirect_limit")
class LiveMonitoringService:
 def __init__(self,client:GitHubActionsReadOnlyClient,reviewer_authenticator:ReviewerAuthenticator): self.client=client; self.auth=reviewer_authenticator
 @staticmethod
 def verify_artifact(artifact,data,*,expected_sha):
  if artifact.get("expired") is True: raise EvidenceError("artifact_expired")
  if not isinstance(artifact.get("name"),str) or expected_sha not in artifact["name"]: raise EvidenceError("artifact_name_sha_mismatch")
  binding=artifact.get("workflow_run")
  if not isinstance(binding,Mapping) or binding.get("head_sha")!=expected_sha: raise EvidenceError("artifact_run_sha_mismatch")
  advertised=str(artifact.get("digest",""))
  if not DIGEST.fullmatch(advertised) or hashlib.sha256(data).hexdigest()!=advertised.removeprefix("sha256:"): raise EvidenceError("artifact_digest_mismatch")
  if len(data)>25*1024*1024: raise EvidenceError("artifact_too_large")
  parsed={}
  try:
   with zipfile.ZipFile(io.BytesIO(data)) as z:
    infos=z.infolist()
    if len(infos)>200: raise EvidenceError("artifact_member_count_exceeded")
    total=0
    for i in infos:
     if i.is_dir(): continue
     path=i.filename.replace("\\","/")
     if path.startswith("/") or any(p in ("",".","..") for p in path.split("/")): raise EvidenceError("unsafe_artifact_member_path")
     if i.file_size>2*1024*1024: raise EvidenceError("artifact_member_too_large")
     total+=i.file_size
     if total>25*1024*1024: raise EvidenceError("artifact_expanded_size_exceeded")
     if path.endswith(".json"):
      try: obj=json.loads(z.read(i).decode())
      except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise EvidenceError("artifact_json_invalid") from exc
      if isinstance(obj,dict): parsed[path]=obj
  except zipfile.BadZipFile as exc: raise EvidenceError("artifact_zip_invalid") from exc
  receipts=[v for k,v in parsed.items() if k.endswith("exact_head_admission_receipt.json")]
  if not receipts or not any(x.get("requested_head_sha")==expected_sha and x.get("observed_head_sha")==expected_sha for x in receipts): raise EvidenceError("exact_head_receipt_mismatch")
  return {"artifact_id":int(artifact.get("id",0)),"name":artifact["name"],"advertised_digest":advertised,"computed_digest":"sha256:"+hashlib.sha256(data).hexdigest(),"parsed_json":parsed}
 def monitor(self,repo,rid,expected_sha,independent_review=None):
  if not SHA.fullmatch(expected_sha): raise EvidenceError("invalid_expected_sha")
  run=self.client.get_run(repo,rid); jobs=self.client.get_jobs(repo,rid); artifacts=self.client.get_artifacts(repo,rid); verified=None; last="missing"
  for a in artifacts:
   if expected_sha not in str(a.get("name","")) or a.get("expired") is True: continue
   try: verified=self.verify_artifact(a,self.client.download_artifact(repo,int(a["id"])),expected_sha=expected_sha); break
   except (EvidenceError,KeyError,ValueError) as exc: last=str(exc)
  if verified is None: raise EvidenceError("no_verified_artifact:"+last)
  review=self.auth.verify(independent_review or {},expected_sha=expected_sha,artifact_digest=verified["computed_digest"])
  stages={}
  for path,obj in verified["parsed_json"].items():
   if isinstance(obj.get("stage_id"),str): stages[obj["stage_id"]]=obj
  obs=normalize_observation(repository=repo,expected_sha=expected_sha,run=run,jobs=jobs,artifacts=artifacts,stage_records=stages,independent_review={"approved":True,"subject_sha":expected_sha,"reviewer_identity":review["reviewer_id"],"authenticated":True})
  outcome=CanonicalRunnerOutcomeAgent.evaluate(run,jobs,stages,expected_sha=expected_sha); status=ValidationStatusAgent.summarize(outcome,obs)
  gate=AcceptanceGateAgent.evaluate(expected_sha=expected_sha,run=run,jobs=jobs,artifact=verified,review=review,outcome=outcome,observation=obs)
  return {"run_id":rid,"expected_sha":expected_sha,"artifact":verified,"review":review,"outcome":outcome,"observation":obs,"validation_status":status,"acceptance_gate":gate,"disposition":CurrentDispositionAgent.evaluate(status,gate)}
class AcceptanceGateAgent:
 @staticmethod
 def evaluate(*,expected_sha,run,jobs,artifact,review,outcome,observation):
  reasons=[]
  if not SHA.fullmatch(expected_sha) or run.get("head_sha")!=expected_sha: reasons.append("exact_head_mismatch")
  if run.get("status")!="completed" or run.get("conclusion")!="success": reasons.append("overall_workflow_not_successful")
  if not jobs or any(j.get("status")!="completed" or j.get("conclusion")!="success" for j in jobs): reasons.append("job_not_successful")
  if outcome.get("canonical_runner_success") is not True: reasons.append("canonical_runner_not_confirmed")
  if outcome.get("overall_workflow_success") is not True: reasons.append("overall_workflow_not_confirmed")
  if artifact.get("computed_digest","").removeprefix("sha256:")!=artifact.get("advertised_digest","").removeprefix("sha256:"): reasons.append("artifact_digest_not_verified")
  if review.get("authenticated") is not True or review.get("approved") is not True: reasons.append("review_not_authenticated")
  if observation.get("decision")!="OBSERVATION_COMPLETE": reasons.append("observation_has_blockers")
  reasons=sorted(set(reasons)); ok=not reasons
  return {"schema_version":"aigc-acceptance-gate/1.0","eligible":ok,"status":"ELIGIBLE_FOR_RELEASE_ASSURANCE_REVIEW" if ok else "BLOCK","reasons":reasons,"release_decision":"BLOCK","automatic_changes_performed":False}
