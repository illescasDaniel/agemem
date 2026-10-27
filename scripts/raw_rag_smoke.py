"""Real offline RAW-RAG + SQLite + bank + optional QSIV/MCP smoke test.

Python HTTP/socket clients are blocked during inference. Preparation is separate.
"""
import argparse
import asyncio
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from agemem.engine import Engine
from agemem.project import initialize
from agemem.evidence import TOKEN


@contextlib.contextmanager
def no_network():
    import httpx
    import requests
    import urllib.request
    def blocked(*args, **kwargs):
        raise AssertionError('Network attempt during offline RAW-RAG inference')
    with contextlib.ExitStack() as stack:
        for target in ('socket.socket.connect','socket.create_connection',
                       'urllib.request.urlopen','requests.sessions.Session.request',
                       'httpx.Client.send','httpx.AsyncClient.send'):
            stack.enter_context(patch(target, side_effect=blocked))
        yield


def seed(root, raw, qsiv):
    subprocess.run(['git','init','-b','main',str(root)],check=True,capture_output=True)
    initialize(root, 'raw-rag')
    path=root/'.agemem/config.json'
    config=json.loads(path.read_text())
    config.update(raw_rag_directory=str(raw), decision_backend='qsiv' if qsiv else 'jev',
                  qsiv_directory=str(qsiv) if qsiv else None)
    path.write_text(json.dumps(config))
    (root/'memory/activeContext.md').write_text('Current blocker: staging signature mismatch.')
    (root/'README.md').write_text('Atlas deploys with Fabric. This is the old deployment tool.')
    subprocess.run(['git','-C',str(root),'add','README.md'],check=True)
    engine=Engine(root,offline=True)
    engine.index()
    (root/'README.md').write_text('Atlas deploys with Ansible because failed runs must resume.')
    engine.index()  # Old snapshot must not enter the current upstream corpus.
    source=engine.capture('Atlas serializes settlement jobs because the upstream API rejects concurrent writes.', 'incident')
    write=engine.remember('Atlas serializes settlement jobs because the upstream API rejects concurrent writes.', source['source_id']) if qsiv else None
    engine.close()
    return write


def verify(packet, notes):
    assert packet['retrieval']=='raw-rag' and packet['offline']
    assert packet['retrieval_details']['local_providers']
    assert packet['retrieval_details']['answer_generation'] is False
    assert packet['layers']['bank'] and packet['layers']['sources']
    assert 'Ansible' in packet['context'] and 'Fabric' not in packet['context']
    assert 'rejects concurrent writes' in packet['context']
    assert 'signature mismatch' in packet['context']
    assert len(TOKEN.findall(packet['context'])) <= 1800
    assert all(h['ids'] and all(i.startswith('src:') for i in h['ids']) for h in packet['layers']['sources'])
    if notes:
        assert packet['layers']['notes']


async def mcp_probe(folder):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    # The child installs the same socket/HTTP guard before starting the MCP server.
    code="from scripts.raw_rag_smoke import no_network; from agemem.mcp import serve; import sys\nwith no_network(): serve(sys.argv[1], offline=True)"
    env={k:v for k,v in os.environ.items() if not any(s in k for s in ('API_KEY','TOKEN','SECRET'))}
    # TIKTOKEN_CACHE_DIR contains TOKEN but is a path, not a credential.
    env['TIKTOKEN_CACHE_DIR']=os.environ['TIKTOKEN_CACHE_DIR']
    params=StdioServerParameters(command=sys.executable,args=['-c',code,folder],env=env)
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools()
            result=await session.call_tool('project_memory_recall',{'query':'How does Atlas deploy, why serialize settlements and what is blocked?'})
            assert not result.is_error, result
            packet=result.structured_content
            verify(packet, True)
            return dict(tool_names=[t.name for t in tools.tools],packet=packet)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-checkout',type=Path,help='Deprecated: ignored by the bundled adapter')
    p.add_argument('--model-dir',type=Path)
    p.add_argument('--mcp',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    assert not args.mcp or args.model_dir, 'MCP layered test requires --model-dir'
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='agemem-raw-offline-') as folder:
        root=Path(folder)
        with no_network(), contextlib.redirect_stdout(sys.stderr):
            write=seed(root,args.raw_checkout.resolve() if args.raw_checkout else None,args.model_dir.resolve() if args.model_dir else None)
            engine=Engine(root,offline=True)
            packet=engine.recall('How does Atlas deploy, why serialize settlements and what is blocked?')
            verify(packet, bool(args.model_dir))
            engine.close()
            # Branch switch: previous branch evidence must disappear from RAW-RAG.
            subprocess.run(['git','-C',folder,'symbolic-ref','HEAD','refs/heads/feature'],check=True)
            engine=Engine(root,offline=True)
            engine.capture('Feature branch deploys with Terraform.', 'feature-event')
            feature=engine.recall('How does Atlas deploy?')
            assert 'Ansible' not in feature['context'] and 'Terraform' in feature['context']
            engine.close()
            subprocess.run(['git','-C',folder,'symbolic-ref','HEAD','refs/heads/main'],check=True)
        mcp=asyncio.run(mcp_probe(folder)) if args.mcp else None
        report=dict(status='passed',retrieval='raw-rag',offline=True,network_clients_blocked=True,
                    paid_api_calls=0,qsiv=bool(args.model_dir),write=write,recall=packet,
                    branch_scope_verified=True,stale_snapshot_excluded=True,mcp=mcp,
                    seconds=time.perf_counter()-started)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('write','recall','mcp')}))


if __name__=='__main__':
    main()
