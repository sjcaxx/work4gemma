"""Fetch this private run's artifacts; never persist or print signed URLs."""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest

OUT = (Path(__file__).resolve().parent / 'remote-v2').resolve()


def main():
    api=KaggleApi(); api.authenticate()
    files=[]; token=None; log=''
    with api.build_kaggle_client() as client:
        while True:
            req=ApiListKernelSessionOutputRequest()
            req.user_name='yeaowohe'; req.kernel_slug='codearch-real-gemma-context-abcd'
            req.version_label=api._kernel_version_label('2')
            api._set_paging(req,200,token)
            result=client.kernels.kernels_api_client.list_kernel_session_output(req)
            files.extend(result.files or [])
            log=result.log or log
            token=result.next_page_token
            if not token: break
    assert files, 'No output artifacts published yet'
    OUT.mkdir(parents=True,exist_ok=True)
    def fetch(item):
        target=(OUT/item.file_name).resolve()
        if not target.is_relative_to(OUT): raise ValueError('Unsafe artifact path')
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            for attempt in range(3):
                try:
                    response=requests.get(item.url,timeout=90)
                    if response.status_code!=200: raise RuntimeError('Artifact fetch failed')
                    target.write_bytes(response.content)
                    break
                except Exception:
                    if attempt==2: raise RuntimeError('Failed artifact: '+item.file_name) from None
                    time.sleep(1)
        return {'file':item.file_name,'bytes':target.stat().st_size,
                'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    rows=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(fetch,item) for item in files]
        for future in as_completed(futures):
            rows.append(future.result())
            if len(rows)%50==0: print('Downloaded',len(rows),'/',len(files),flush=True)
    (OUT/'kernel-log.json').write_text(log,encoding='utf-8')
    (OUT/'download-manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print('COMPLETE:',len(rows),'files,',sum(r['bytes'] for r in rows),'bytes',flush=True)


if __name__=='__main__': main()
