import collections
import csv
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'remote-v2/codearch-real-gemma'


def role_from_request(data):
    value=data.get('system')
    if isinstance(value,str): text=value
    elif isinstance(value,dict): text='\n'.join(p.get('text','') for p in value.get('parts',[]))
    elif isinstance(value,list): text='\n'.join(p if isinstance(p,str) else p.get('text','') for p in value)
    else: text=str(value)
    match=re.search(r'# Role:\s*([^\n]+)',text)
    return match.group(1) if match else data.get('role','unknown')


def main():
    results=json.loads((DATA/'results.json').read_text(encoding='utf-8'))
    events=[json.loads(line) for line in (DATA/'model-calls.jsonl').read_text(encoding='utf-8').splitlines()]
    requests={int(p.stem.split('-')[-1]):json.loads(p.read_text(encoding='utf-8')) for p in DATA.glob('request-*.json')}
    assert len(results)==12
    by_run=collections.defaultdict(list)
    for e in events: by_run[e['run']].append(e)
    rows=[]; failures=[]
    for result in results:
        run=result['variant']+'__'+result['task']
        es=by_run[run]
        responses={e['call_id']:e for e in es if e.get('event')=='response' and isinstance(e.get('usage'),dict)}
        errors=[e for e in es if e.get('event')=='error']
        context_errors=[e for e in errors if 'ContextWindowExceeded' in e.get('error','')]
        roles=collections.Counter(role_from_request(j) for j in requests.values() if j['run']==run)
        patch=(DATA/'results'/run/'agent.patch').read_text(encoding='utf-8')
        paths=re.findall(r'^diff --git a/(.*?) b/',patch,re.MULTILINE)
        product_paths=[p for p in paths if p.startswith(('rich/','fastapi/','requests/'))]
        row={**result,'successful_model_responses':len(responses),
             'max_successful_input_tokens':max([e['usage'].get('prompt_token_count',0) for e in responses.values()] or [0]),
             'total_reported_input_tokens':sum(e['usage'].get('prompt_token_count',0) for e in responses.values()),
             'total_reported_output_tokens':sum(e['usage'].get('candidates_token_count',0) for e in responses.values()),
             'context_error_count':len(context_errors),'roles':dict(roles),
             'patch_files':paths,'product_source_files_modified':product_paths}
        rows.append(row)
        for e in context_errors:
            failures.append({**e,'derived_role':role_from_request(requests[e['call_id']]),
                             'request_file':f'request-{e["call_id"]:05d}.json'})
    # Verify real model evidence for both first-stage chains, independent of harness counters.
    from build_notebook import smoke_completed
    assert all(smoke_completed(row,events) for row in results if row['task']=='rich_3063' and row['variant'] in 'AD')
    groups=[]
    for variant in 'ABCD':
        subset=[r for r in rows if r['variant']==variant]
        groups.append({'variant':variant,'runs':len(subset),'resolved':sum(r['resolved'] for r in subset),
                       'context_errors':sum(r['context_error_count'] for r in subset),
                       'max_successful_input_tokens':max(r['max_successful_input_tokens'] for r in subset),
                       'successful_model_responses':sum(r['successful_model_responses'] for r in subset)})
    report={'real_model':'gemma-4-31b-it-qat-w4a16-ct','hardware':'4x NVIDIA L4',
            'notebook_version':2,'runs':rows,'groups':groups,'context_failures':failures,
            'model_requests':len(requests),'successful_model_responses':sum(r['successful_model_responses'] for r in rows),
            'run_finished':json.loads((DATA/'run-finished.json').read_text(encoding='utf-8')),
            'limits':['three tasks, one stochastic run per variant; no statistical claim',
                      'successful usage excludes requests rejected before inference',
                      'requests_6629 verification has 185 httpbin fixture setup errors in every variant',
                      'no product source files changed; fallback patches contain scratch and sometimes state files',
                      'Kaggle AgentTool child runners do not automatically inherit parent App compaction',
                      '8192 output ceiling mitigated observed overflow; does not enforce a universal input limit'],
            'new_competition_submission':False}
    (ROOT/'real-gemma-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'real-gemma-results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['variant','task','resolved','context_error_count','max_successful_input_tokens',
                'successful_model_responses','tool_calls','patch_characters','wall_seconds','error']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    text='''CodeArch 真实 Gemma 测试结果（2026-11-21）

模型：gemma-4-31b-it-qat-w4a16-ct，4 张 NVIDIA L4。
Notebook：yeaowohe/codearch-real-gemma-context-abcd，版本 2，私有、离线。
执行时间约 73 分钟，12 次运行完成，VllmServer.stop() 已执行，Kaggle 状态 COMPLETE。
另一次启动检查在推理前因测试脚本漏导入 re 失败，修正后重新运行；未新增比赛提交。

四组：A 原始配置；B 仅关闭思考历史；C 在 B 上将输出上限降到 8192；D 再增加精简交接提示。
共同保持 31B、原角色/工具、每次 Agent 5 分钟/60 次工具调用/100 轮。
题目：rich_3063、fastapi_11194、requests_6629。

已复现上下文错误：A、B 在 fastapi_11194 的 Architect 调用中分别出现一次。
服务端错误原文指出：输入至少 16385 tokens，申请输出 16384 tokens，超过 32768 窗口。
C、D 的这三次运行均未观察到同类错误。FastAPI 的成功请求最大输入分别达到
18918 和 20568 tokens；配合 8192 输出额度仍处于窗口内。
这说明关闭思考历史本身不足以解决问题，降低输出额度是这次可验证的直接缓解措施。
它不代表历史不会继续增长，也不保证换一道长任务仍然安全。

四组均 0/3 通过；12 次都达到 Agent 的 5 分钟超时。这不等于本地保护逻辑无效，
因为本次运行使用的是官方多 Agent 配置，没有将本地 Ollama 历史保护代码注入官方工具。

进一步核对补丁：12 份均未修改 rich/、fastapi/、requests/ 下的产品源码。
主要产物是复现/调试脚本，部分 Rich 补丁还混入 .agent_state。
请求记录显示绝大多数调用停留在 PM 和 Architect，只有 C/FastAPI 出现 1 次 Worker 请求。
因此这套流程在当前 5 分钟预算内大多停留在调查阶段，不能把“产生了补丁”当作完成修复。
Rich 与 FastAPI 的目标断言仍失败；Requests 还存在 httpbin fixture 递归依赖导致的
185 个 setup errors，因此其整组验证失败不能单独归因于模型修复能力。

官方 ADK 1.36.1 源码还显示：AgentTool 创建单独 Runner，没有传入父 App 的
events_compaction_config。主 Runner 的自动压缩配置不等于各子 Runner 都有保护。
这提供了 Architect 内部累积历史的机制解释；不能把问题笼统归为所有 Agent 共用上下文。

建议先采用 C 的最小配置改动作为上下文溢出的缓解，不宣称整个 Agent 已修好。
下一轮应单独调整 Architect 调查轮数和返回条件，让 Worker 更早获得明确修复任务；
同时处理临时文件不进入补丁，并修正 Requests 验证环境。需要另外安排真实任务回归。
本轮只是 3 道题的单次实验，组间速度差异可能受采样、运行顺序和缓存影响。

全部原始记录保存在 remote-v2/，共 438 个文件。逐轮模型输入、真实 usage、异常、
官方 trace、补丁和测试输出均可核对。real-gemma-results.json/CSV 为汇总数据。
run-v2.ipynb 是实际执行的 Notebook；其截止时间针对本次批准会话，重新运行需重新设定。
'''
    text+='\n分组摘要：\n'+json.dumps(groups,ensure_ascii=False,indent=2)+'\n'
    (ROOT/'真实Gemma测试结果.txt').write_text(text,encoding='utf-8')
    print(json.dumps(groups,indent=2))
    print('requests',len(requests),'successful responses',report['successful_model_responses'],'context failures',len(failures))


if __name__=='__main__': main()
