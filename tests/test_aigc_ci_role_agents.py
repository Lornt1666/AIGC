import base64,hashlib,io,json,time,unittest,zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from aigc_ci_role_agents import CanonicalRunnerOutcomeAgent,CurrentDispositionAgent,Ed25519ReviewerAuthenticator,EvidenceError,FailClosedTestAgent,LiveMonitoringService
SHA="a"*40
def archive(sha=SHA):
 b=io.BytesIO()
 with zipfile.ZipFile(b,"w") as z:
  z.writestr("exact_head_admission_receipt.json",json.dumps({"requested_head_sha":sha,"observed_head_sha":sha}))
  z.writestr("stage_canonical_runner.json",json.dumps({"stage_id":"canonical_validation_runner","status":"PASS","target_sha":sha}))
 return b.getvalue()
class RoleAgentTests(unittest.TestCase):
 def test_runner_pass_not_workflow_pass(self):
  r=CanonicalRunnerOutcomeAgent.evaluate({"head_sha":SHA,"status":"completed","conclusion":"failure"},[{"status":"completed","conclusion":"failure"}],{"canonical_runner":{"status":"PASS","target_sha":SHA}},expected_sha=SHA)
  self.assertTrue(r["canonical_runner_success"]); self.assertFalse(r["overall_workflow_success"]); self.assertEqual(r["decision"],"BLOCK")
 def test_failed_job_blocks(self):
  r=CanonicalRunnerOutcomeAgent.evaluate({"head_sha":SHA,"status":"completed","conclusion":"success"},[{"status":"completed","conclusion":"failure"}],{"canonical_runner":{"status":"PASS","target_sha":SHA}},expected_sha=SHA)
  self.assertFalse(r["overall_workflow_success"])
 def test_required_fail_closed_cases(self):
  self.assertGreaterEqual(len(FailClosedTestAgent.required_cases()),9)
  self.assertEqual(FailClosedTestAgent.disposition(exact_sha=True,workflow_success=True,artifact_verified=True,reviewer_authenticated=True,independent_review_approved=False),"BLOCK")
 def test_artifact_digest_receipt(self):
  b=archive(); d=hashlib.sha256(b).hexdigest(); a={"id":1,"name":"evidence-"+SHA,"digest":"sha256:"+d,"expired":False,"workflow_run":{"head_sha":SHA}}
  self.assertEqual(LiveMonitoringService.verify_artifact(a,b,expected_sha=SHA)["computed_digest"],"sha256:"+d)
 def test_bad_digest(self):
  b=archive(); a={"id":1,"name":"evidence-"+SHA,"digest":"sha256:"+"0"*64,"expired":False,"workflow_run":{"head_sha":SHA}}
  with self.assertRaises(EvidenceError): LiveMonitoringService.verify_artifact(a,b,expected_sha=SHA)
 def test_stale_receipt(self):
  b=archive("c"*40); a={"id":1,"name":"evidence-"+SHA,"digest":"sha256:"+hashlib.sha256(b).hexdigest(),"expired":False,"workflow_run":{"head_sha":SHA}}
  with self.assertRaises(EvidenceError): LiveMonitoringService.verify_artifact(a,b,expected_sha=SHA)
 def test_zip_traversal(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,"w") as z: z.writestr("../bad.json","{}"); z.writestr("exact_head_admission_receipt.json",json.dumps({"requested_head_sha":SHA,"observed_head_sha":SHA}))
  data=b.getvalue(); a={"id":1,"name":"evidence-"+SHA,"digest":"sha256:"+hashlib.sha256(data).hexdigest(),"expired":False,"workflow_run":{"head_sha":SHA}}
  with self.assertRaises(EvidenceError): LiveMonitoringService.verify_artifact(a,data,expected_sha=SHA)
 def test_ed25519_review(self):
  sk=Ed25519PrivateKey.generate(); pk=sk.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw); now=int(time.time())
  r={"reviewer_id":"independent","approved":True,"subject_sha":SHA,"artifact_digest":"sha256:"+"d"*64,"issued_at":now-1,"expires_at":now+60}
  r["signature"]=base64.b64encode(sk.sign(json.dumps(r,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())).decode()
  self.assertTrue(Ed25519ReviewerAuthenticator({"independent":pk}).verify(r,expected_sha=SHA,artifact_digest=r["artifact_digest"])["authenticated"])
 def test_bad_signature(self):
  sk=Ed25519PrivateKey.generate(); pk=sk.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw); now=int(time.time())
  r={"reviewer_id":"r","approved":True,"subject_sha":SHA,"artifact_digest":"sha256:"+"d"*64,"issued_at":now-1,"expires_at":now+60,"signature":base64.b64encode(b"x"*64).decode()}
  with self.assertRaises(EvidenceError): Ed25519ReviewerAuthenticator({"r":pk}).verify(r,expected_sha=SHA,artifact_digest=r["artifact_digest"])
 def test_expired_review(self):
  sk=Ed25519PrivateKey.generate(); pk=sk.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw); now=int(time.time())
  r={"reviewer_id":"r","approved":True,"subject_sha":SHA,"artifact_digest":"sha256:"+"d"*64,"issued_at":now-100,"expires_at":now-1}
  r["signature"]=base64.b64encode(sk.sign(json.dumps(r,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())).decode()
  with self.assertRaises(EvidenceError): Ed25519ReviewerAuthenticator({"r":pk}).verify(r,expected_sha=SHA,artifact_digest=r["artifact_digest"])
 def test_disposition_blocks(self): self.assertEqual(CurrentDispositionAgent.evaluate({"status":"VALIDATED"},{"eligible":False})["release_decision"],"BLOCK")
if __name__=="__main__": unittest.main()
