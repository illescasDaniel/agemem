"""Offline MCP handshake and recall in a disposable project."""
import asyncio,json,subprocess,tempfile,sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from agemem.project import initialize
from agemem.engine import Engine
async def main():
 with tempfile.TemporaryDirectory(prefix='agemem-installed-') as folder:
  root=Path(folder)
  subprocess.run(['git','init','-b','main',folder],check=True,capture_output=True)
  initialize(root,'bm25','hash')
  (root/'README.md').write_text('Atlas deploys with Ansible because failed runs must resume.')
  subprocess.run(['git','-C',folder,'add','README.md'],check=True)
  engine=Engine(root,offline=True);engine.index();engine.close()
  params=StdioServerParameters(command=sys.executable,args=['-m','agemem.cli','--project',folder,'--offline','mcp'])
  async with stdio_client(params) as (read,write):
   async with ClientSession(read,write) as session:
    await session.initialize()
    tools=await session.list_tools()
    result=await session.call_tool('project_memory_recall',{'query':'How does Atlas deploy?'})
    assert not result.is_error
    assert 'Ansible' in str(result)
    print(json.dumps({'status':'passed','installed_location':True,'tools':[t.name for t in tools.tools],'offline_recall':True}))
asyncio.run(main())
