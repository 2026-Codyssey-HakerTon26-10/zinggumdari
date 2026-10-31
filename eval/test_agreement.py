import json
from datetime import date

import pandas as pd

from eval.agreement import build


def test_agreement_uses_pool_only_and_does_not_invent_parents(tmp_path, monkeypatch):
    from backend import engine
    pd.DataFrame([{'user_id':'virtual:pool','split':'pool','birth_year':1999,'source_uuid':'not-for-judge','from_text':'not-for-judge'},
                  {'user_id':'virtual:holdout','split':'holdout','birth_year':1999,'source_uuid':'x','from_text':'x'}]).to_parquet(tmp_path/'population.parquet')
    for name, subject in [('self','self'),('parent','parent')]:
        (tmp_path/(name+'.json')).write_text(json.dumps({'id':'manual:'+name,'subject':subject}))
    def judge(profile, rules, **kwargs):
        assert profile['user_id'] == 'virtual:pool'
        assert 'source_uuid' not in profile['self'] and 'from_text' not in profile['self']
        assert profile['parents'] == []
        return {r['id']:{'verdict':'needs_check'} for r in rules}
    monkeypatch.setattr(engine,'judge',judge)
    d={'extraction':[{'rule_id':'manual:'+n,'gold':[],'extracted':[]} for n in ('self','parent')]}
    result=build(d,tmp_path/'population.parquet',tmp_path,today=date(2026,11,1))
    assert len(result['verdicts']) == 1
    assert result['skipped_parent_rules'] == ['manual:parent']
