from build_notebook import smoke_completed


def test_call_counter_without_real_usage_does_not_unlock_more_runs():
    row={'variant':'A','task':'rich_3063','llm_calls':1,'tool_calls':1,
         'patch_characters':100,'test_exit_code':0}
    assert not smoke_completed(row,[])
    assert not smoke_completed(row,[{'event':'response','run':'A__rich_3063','usage':None}])


def test_both_groups_need_tools_patch_and_executed_verification():
    events=[{'event':'response','run':v+'__rich_3063','usage':{'prompt_token_count':100}} for v in 'AD']
    a={'variant':'A','task':'rich_3063','tool_calls':1,'patch_characters':100,'test_exit_code':0}
    d={**a,'variant':'D'}
    assert smoke_completed(a,events) and smoke_completed(d,events)
    for key,value in [('tool_calls',0),('patch_characters',0),('test_exit_code',-1)]:
        assert not smoke_completed({**a,key:value},events)
    # A failed assertion is still executed verification; accuracy is reported separately.
    assert smoke_completed({**a,'test_exit_code':1},events)


def test_error_response_cannot_count_as_successful_inference():
    row={'variant':'A','task':'rich_3063','tool_calls':1,'patch_characters':100,'test_exit_code':0}
    event={'event':'response','run':'A__rich_3063','usage':{'prompt_token_count':100},'error_code':'400'}
    assert not smoke_completed(row,[event])
