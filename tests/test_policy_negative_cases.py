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

import pytest
@pytest.mark.parametrize("action",["direct_main_write","merge","automatic_merge","self_approval","arbitrary_shell","gmail_send","financial_commitment","raw_secret_output","terraform_apply","opentofu_apply","provider_mutation_outside_bridge_setup","aigc_deployment","production_activation"])
def test_dangerous_actions_denied(action):
    r=dict(VALID); r.update({"request_id":f"REQ-{action}","idempotency_key":f"idem-{action}","action_class":action})
    d=evaluate(r,BUNDLE,expected_repository="Lornt1666/AIGC",expected_revision=VALID["exact_repository_revision"],known_surfaces=KNOWN,authority_evidence=AUTH,emergency_evidence=STOP)
    assert d["decision"]=="DENY"
def test_unknown_surface_denied():
    r=dict(VALID); r["execution_surface"]="unknown"
    d=evaluate(r,BUNDLE,expected_repository="Lornt1666/AIGC",expected_revision=VALID["exact_repository_revision"],known_surfaces=KNOWN,authority_evidence=AUTH,emergency_evidence=STOP)
    assert d["decision"]=="DENY"
def test_self_approval_rejected():
    r=dict(VALID); r.update({"request_id":"REQ-BRANCH","idempotency_key":"idem-branch","action_class":"branch_create","approval_reference":{"approver":"operator-1","expired":False}})
    d=evaluate(r,BUNDLE,expected_repository="Lornt1666/AIGC",expected_revision=VALID["exact_repository_revision"],known_surfaces=KNOWN,authority_evidence=AUTH,emergency_evidence=STOP)
    assert d["decision"]=="DENY" and "SELF_APPROVAL_PROHIBITED" in d["reasons"]
