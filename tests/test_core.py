from oce.oce_core import run_oce

def test_end_to_end():
    out = run_oce("Tarvitsen strategiaa ja riskiarvion.", {"project_id":"TEST"})
    js = out["json_summary"]
    assert js["applied_modules"], "No modules applied"
    assert "policy_decision" in js
