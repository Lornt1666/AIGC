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

def test_identical_inputs_produce_identical_decisions():
    args=dict(expected_repository="Lornt1666/AIGC",expected_revision=VALID["exact_repository_revision"],known_surfaces=KNOWN,authority_evidence=AUTH,emergency_evidence=STOP)
    a=evaluate(VALID,BUNDLE,**args); b=evaluate(VALID,BUNDLE,**args)
    assert a==b and a["decision"]=="ALLOW"
def test_emergency_stop_overrides_allow():
    d=evaluate(VALID,BUNDLE,expected_repository="Lornt1666/AIGC",expected_revision=VALID["exact_repository_revision"],known_surfaces=KNOWN,authority_evidence=AUTH,emergency_evidence={"state":"LOCKED","epoch":1})
    assert d["decision"]=="EMERGENCY_STOP_LOCKED"
def test_missing_authority_never_allows():
    d=evaluate(VALID,BUNDLE,expected_repository="Lornt1666/AIGC",expected_revision=VALID["exact_repository_revision"],known_surfaces=KNOWN,authority_evidence=None,emergency_evidence=STOP)
    assert d["decision"]=="INSUFFICIENT_EVIDENCE"
