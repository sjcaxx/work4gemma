"""Build the approved private, offline, real-Gemma A/B/C/D evaluation."""
import ast
import argparse
import base64
import hashlib
import io
import json
import textwrap
import zipfile
from pathlib import Path

import yaml

EXPERIMENT = Path(__file__).resolve().parents[1]
REPO = EXPERIMENT.parents[1]
OUT = Path(__file__).resolve().parent / 'generated'


def smoke_completed(row, events):
    run = row['variant'] + '__' + row['task']
    inferred = any(e.get('event') == 'response' and e.get('run') == run
                   and not e.get('error_code')
                   and (e.get('usage') or {}).get('prompt_token_count', 0) > 0
                   for e in events)
    return (inferred and (row.get('tool_calls') or 0) > 0
            and row.get('patch_characters', 0) > 0
            and row.get('test_exit_code', -1) >= 0)


def variants():
    result = {name: (EXPERIMENT / f'submission-{name}.zip').read_bytes() for name in 'ABCD'}
    expected = json.loads((EXPERIMENT / 'plan-and-manifest.json').read_text(encoding='utf-8'))['variants']
    for name, data in result.items():
        assert hashlib.sha256(data).hexdigest() == expected[name], f'Archive changed: {name}'
    return result


def build(kaggle_user):
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((EXPERIMENT / 'reference/getting-started-gemma-4-developer-agent.ipynb').read_text(encoding='utf-8'))
    blobs = variants()
    manifest = {k: hashlib.sha256(v).hexdigest() for k, v in blobs.items()}
    for name, data in blobs.items():
        (OUT / f'submission-{name}.zip').write_bytes(data)
    codes = []
    codes.append('''
import os, time, json, threading, sys, traceback, hashlib, base64, io, zipfile, re
from pathlib import Path
START = time.monotonic()
REMAINING = 7200  # Per explicitly started session; retries also consume GPU quota.
DEADLINE = START + REMAINING - 100
WORK = Path('/kaggle/working/codearch-real-gemma')
WORK.mkdir(parents=True, exist_ok=True)
server_instance = None
def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
def emergency_stop():
    save_json(WORK/'time-limit.json', {'status':'stopped_at_session_time_limit'})
    if server_instance is not None:
        cleanup = threading.Thread(target=server_instance.stop, daemon=True)
        cleanup.start()
        cleanup.join(timeout=15)
    os._exit(124)
watchdog = threading.Timer(REMAINING - 50, emergency_stop)
watchdog.daemon = True
watchdog.start()
import torch
gpu = [{'name':torch.cuda.get_device_name(i), 'bytes':torch.cuda.get_device_properties(i).total_memory}
       for i in range(torch.cuda.device_count())]
save_json(WORK/'hardware.json', {'gpus':gpu, 'real_model_inference':False})
print('Hardware:', gpu, flush=True)
assert len(gpu) >= 4 and all('L4' in g['name'] for g in gpu), 'Approved L4 x4 hardware unavailable; stopping without switching models.'
''')
    codes.append(''.join(baseline['cells'][2]['source']))
    payloads = {k: base64.b64encode(v).decode() for k, v in blobs.items()}
    unpack = '''
import yaml
MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
DATA_DIR = Path('/kaggle/input/competitions/gemma-4-developer-agent')
MODEL_PATH = Path('/kaggle/input/models/google/gemma-4/other') / MODEL_NAME / '2'
assert MODEL_PATH.is_dir(), 'Approved model weights unavailable; stopping without switching models.'
TASKS_PATH = DATA_DIR/'tasks.jsonl'
GRAPH_DIR, EMBEDDINGS_DIR = str(DATA_DIR/'graphs'), str(DATA_DIR/'embeddings')
from swegemma.models import load_tasks
task_map = {t.instance_id:t for t in load_tasks(TASKS_PATH)}
TASK_IDS = ['rich_3063', 'fastapi_11194', 'requests_6629']
assert all(t in task_map for t in TASK_IDS), 'Published test task missing'
VARIANTS = {}
for name, encoded in PAYLOADS.items():
    content = base64.b64decode(encoded)
    assert hashlib.sha256(content).hexdigest() == EXPECTED_SHA[name]
    folder = WORK/'variants'/name
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        assert z.testzip() is None
        for info in z.infolist():
            assert not Path(info.filename).is_absolute() and '..' not in Path(info.filename).parts
        z.extractall(folder)
    VARIANTS[name] = folder
save_json(WORK/'variant-manifest.json', EXPECTED_SHA)
print('All four variants and published tasks ready', flush=True)
'''
    codes.append('PAYLOADS = ' + repr(payloads) + '\nEXPECTED_SHA = ' + repr(manifest) + '\n' + textwrap.dedent(unpack))
    funcs = ast.parse((REPO/'scripts/validate_submission.py').read_text(encoding='utf-8'))
    stubs = '\n\n'.join(ast.unparse(n) for n in funcs.body if isinstance(n, ast.FunctionDef))
    codes.append('''
from adk_submission import compile_submission, ModelRegistry
from swegemma.config import build_submission_limits
limits, gen_constraints = build_submission_limits()
''' + stubs + '''
compile_models = ModelRegistry()
compile_models.register(MODEL_NAME, MODEL_NAME)
compile_tools = {f.__name__:f for f in [run_command, read_file, edit_file, write_file,
    get_code_neighbors, search_similar_code, get_code_subgraph, get_status, submit_patch]}
compiled = []
for name, folder in VARIANTS.items():
    agent = compile_submission(folder, tool_registry=compile_tools, model_registry=compile_models,
                               limits=limits, generation_constraints=gen_constraints)
    compiled.append({'variant':name, 'agent':agent.name, 'stage':'compile_only'})
save_json(WORK/'full-compilation.json', compiled)
print('Official ADK full compilation passed for A/B/C/D (no inference yet)', flush=True)
''')
    # Use the organizer's model loader without replacing the model or inference backend.
    start = ''.join(baseline['cells'][8]['source'])
    start = "AGENT_DIR = VARIANTS['A']\n" + start
    codes.append(start + "\nsave_json(WORK/'model-started.json', {'model':MODEL_NAME,'gpu_count':torch.cuda.device_count(),'base_url':server_instance.base_url})\n")
    codes.append('''
import asyncio, concurrent.futures, itertools
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig
from swegemma.evaluate import Evaluator
CURRENT = {'run':None}
counter = itertools.count(1)
original_generate = LiteLlm.generate_content_async
def dump_content(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json', exclude_none=True)
    return value
def append_event(record):
    with (WORK/'model-calls.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(record,ensure_ascii=False,default=str)+'\\n')
async def observed_generate(self, llm_request, stream=False):
    call_id = next(counter)
    run = CURRENT['run'] or 'setup'
    system = getattr(getattr(llm_request,'config',None),'system_instruction',None)
    system_text = system if isinstance(system,str) else str(system)
    role = next((line for line in system_text.splitlines() if line.startswith('# Role:')), 'unknown')
    contents = [dump_content(c) for c in llm_request.contents]
    save_json(WORK/f'request-{call_id:05d}.json', {'run':run,'role':role,'system':dump_content(system),'contents':contents})
    append_event({'event':'request','run':run,'role':role,'call_id':call_id,
                  'input_characters':len(json.dumps(contents,ensure_ascii=False,default=str)),
                  'time':time.time()})
    try:
        async for response in original_generate(self,llm_request,stream=stream):
            usage = getattr(response,'usage_metadata',None)
            append_event({'event':'response','run':run,'role':role,'call_id':call_id,
                          'usage':dump_content(usage),'error_code':getattr(response,'error_code',None),
                          'error_message':getattr(response,'error_message',None),'time':time.time()})
            yield response
    except Exception as error:
        append_event({'event':'error','run':run,'role':role,'call_id':call_id,
                      'error_type':type(error).__name__,'error':str(error),'time':time.time()})
        raise
LiteLlm.generate_content_async = observed_generate

def run_sync(factory):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda:asyncio.run(factory())).result()

results=[]
def execute(variant, task_id):
    run = variant+'__'+task_id
    folder = WORK/'results'/run
    folder.mkdir(parents=True,exist_ok=True)
    CURRENT['run'] = run
    cfg = EvalConfig(tasks_path=TASKS_PATH,snapshots_dir=DATA_DIR/'snapshots',results_dir=folder,
        submission_dir=VARIANTS[variant],models=models,sandbox='subprocess',
        timeout_seconds=300,verification_timeout_seconds=300,max_time_minutes=5,
        max_tool_calls=60,max_turns=100,limits=limits,generation_constraints=gen_constraints,
        adapter_manifest=adapters,
        context_cache_config=ContextCacheConfig(min_tokens=2048,ttl_seconds=1800,cache_intervals=10),
        events_compaction_config=EventsCompactionConfig(compaction_interval=15,overlap_size=2,
                                                       token_threshold=14336,event_retention_size=5),
        graph_dir=GRAPH_DIR,embeddings_dir=EMBEDDINGS_DIR,wheels_dir=DATA_DIR/'wheels',verbose=False)
    evaluator=Evaluator(cfg)
    print('START',run,flush=True)
    t0=time.monotonic()
    async def evaluate():
        # Includes sandbox setup and verification. Agent's own budget stays 5 min.
        return await asyncio.wait_for(evaluator.evaluate_task(task=task_map[task_id],task_index=1,total_tasks=1),
                                      timeout=min(1000,max(1,DEADLINE-time.monotonic()-30)))
    try:
        result=run_sync(evaluate)
        row={'variant':variant,'task':task_id,'resolved':bool(result.resolved),
             'error':getattr(result,'error',None),'test_exit_code':result.test_exit_code,
             'patch_characters':len(result.agent_patch or ''),'tool_calls':result.tool_calls,
             'llm_calls':getattr(result,'total_llm_calls',None),'wall_seconds':time.monotonic()-t0}
        (folder/'agent.patch').write_text(result.agent_patch or '',encoding='utf-8')
        (folder/'test-output.txt').write_text(result.test_output or '',encoding='utf-8')
    except Exception as error:
        row={'variant':variant,'task':task_id,'error':str(error),'error_type':type(error).__name__,
             'resolved':False,'wall_seconds':time.monotonic()-t0}
        (folder/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
    results.append(row)
    save_json(WORK/'results.json',results)
    print('RESULT',json.dumps(row,default=str),flush=True)
    return row

try:
    smoke_a=execute('A',TASK_IDS[0])
    smoke_d=execute('D',TASK_IDS[0])
    # Do not spend more GPU quota if the actual model/tool/patch chain did not run.
    events=[json.loads(line) for line in (WORK/'model-calls.jsonl').read_text(encoding='utf-8').splitlines()] if (WORK/'model-calls.jsonl').exists() else []
    smoke_ok=smoke_completed(smoke_a,events) and smoke_completed(smoke_d,events)
    if smoke_ok:
        schedule=[('B',TASK_IDS[0]),('C',TASK_IDS[0])]+[(v,t) for t in TASK_IDS[1:] for v in ['A','B','C','D']]
        for variant,task_id in schedule:
            if time.monotonic()+1050>DEADLINE:
                save_json(WORK/'stopped-early.json',{'reason':'session time budget','remaining_runs':12-len(results)})
                break
            execute(variant,task_id)
    else:
        save_json(WORK/'stopped-early.json',{'reason':'real-model smoke did not complete model/tool/patch/test chain'})
finally:
    LiteLlm.generate_content_async=original_generate
    if server_instance is not None:
        server_instance.stop()
    watchdog.cancel()
    save_json(WORK/'run-finished.json',{'real_model_requested':True,'runs_completed':len(results),
        'elapsed_seconds':time.monotonic()-START,'note':'Inspect response usage to confirm actual model inference; empty fields are not zero tokens.'})
    print('FINISHED',len(results),'runs; inference server stopped',flush=True)
''')
    # Include the same tested smoke predicate used by the local gate tests.
    predicate=next(n for n in ast.parse(Path(__file__).read_text(encoding='utf-8')).body
                   if isinstance(n,ast.FunctionDef) and n.name=='smoke_completed')
    codes[-1]=ast.unparse(predicate)+'\n'+codes[-1]
    cells=[{'cell_type':'markdown','metadata':{},'id':'approved-plan','source':[
        '# CodeArch real Gemma context test\n',
        'Private offline 31B experiment. Approved maximum session: 2 hours. No competition submission.\n',
        'A original; B hide thought history; C B + 8192 output; D C + concise handoffs.\n',
        'Published tasks only. Model usage, errors, traces, patches and tests are saved.\n']}]
    for i, code in enumerate(codes):
        code=textwrap.dedent(code).strip()+'\n'
        ast.parse(code)
        cells.append({'cell_type':'code','id':f'run-{i}','metadata':{},'execution_count':None,'outputs':[],
                      'source':code.splitlines(keepends=True)})
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':baseline['metadata'],'cells':cells}
    (OUT/'CodeArch_Real_Gemma.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,indent=1),encoding='utf-8')
    meta=json.loads((EXPERIMENT/'reference/kernel-metadata.json').read_text(encoding='utf-8'))
    meta.pop('id_no',None)
    meta.update(id=kaggle_user+'/codearch-context-abcd-retest',title='CodeArch Context ABCD Retest',
                code_file='CodeArch_Real_Gemma.ipynb',is_private=True,
                model_sources=['google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2'])
    (OUT/'kernel-metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    (OUT/'plan-and-manifest.json').write_text(json.dumps({'source_commit':'eeebfef','variants':manifest,
        'tasks':['rich_3063','fastapi_11194','requests_6629'],'max_runtime_seconds':7200,
        'real_model_inference_yet':False},indent=2),encoding='utf-8')
    print('Built private official 31B notebook:',OUT/'CodeArch_Real_Gemma.ipynb')


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kaggle-user', required=True)
    build(parser.parse_args().kaggle_user)
