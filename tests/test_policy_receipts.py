import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mission_os.policy import evaluate,make_receipt,verify_receipt
BUNDLE=json.loads((ROOT/"governance/policy/omega_policy_bundle.json").read_text())
VALID=json.loads((ROOT/"tests/fixtures/policy/valid/read_request.json").read_text())
AUTH={"decision":"PERMIT","expired":False,"revoked":False,"exact_repository_revision":VALID["exact_repository_revision"]}
STOP={"state":"UNLOCKED","epoch":1}
KNOWN={"chatgpt_github_connector","replit_execution_bridge","github_actions"}

def test_receipt_tamper_evident():
    d=evaluate(VALID,BUNDLE,expected_repository="Lornt1666/AIGC",expected_revision=VALID["exact_repository_revision"],known_surfaces=KNOWN,authority_evidence=AUTH,emergency_evidence=STOP)
    r=make_receipt(d,"Lornt1666/AIGC",VALID["exact_repository_revision"],BUNDLE["bundle_sha256"])
    assert verify_receipt(r)
    r["decision"]["decision"]="DENY"
    assert not verify_receipt(r)
def test_receipt_no_external_action_or_credentials():
    d=evaluate(VALID,BUNDLE,expected_repository="Lornt1666/AIGC",expected_revision=VALID["exact_repository_revision"],known_surfaces=KNOWN,authority_evidence=AUTH,emergency_evidence=STOP)
    r=make_receipt(d,"Lornt1666/AIGC",VALID["exact_repository_revision"],BUNDLE["bundle_sha256"])
    assert r["external_action_performed"] is False and r["credential_material_included"] is False
