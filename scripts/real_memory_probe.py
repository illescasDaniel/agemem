"""Local-only source-grounded memory probe; never constructs a hosted backend."""
import hashlib
import json
import time
from pathlib import Path
from agemem.deciders import QSIVDecider
from agemem.notes.decider import ChoiceQ

root = Path('/home/daniel/Projects/Code/Python')
specs = [
    ('srxy', 'src/srxy/adapters/inbound/gui/controller.py', 'def setBrowsedPath', 6,
     'Should the Browse handler decode a selected local URL twice?',
     {'a':'Yes, unquote the converted path again.', 'b':'No. Use the typed QUrl and call toLocalFile once.'}, 'b'),
    ('srxy', 'src/srxy/adapters/inbound/cli/cli.py', 'print("Search cancelled."', 2,
     'Where is cancellation reported and what exit code is returned?',
     {'a':'stderr; exit 130', 'b':'stdout; exit 1'}, 'a'),
    ('SpaceMaker', 'CLAUDE.md', '@AGENTS.md', 1,
     'Which file supplies the shared Claude project instructions?',
     {'a':'A duplicated instruction body in CLAUDE.md', 'b':'Imported AGENTS.md'}, 'b'),
    ('SpaceMaker', 'tests/unit/test_agent_context.py', 'AGENTS_MD_LINE_BUDGET =', 1,
     'What line budget should shared agent instructions stay within?',
     {'a':'130', 'b':'200'}, 'a'),
]
if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-dir', required=True)
    p.add_argument('--output', required=True)
    args=p.parse_args()
    decider=QSIVDecider.load(args.model_dir)
    rows=[]
    for project, relative, marker, count, query, options, gold in specs:
        path=root/project/relative
        text=path.read_text()
        lines=text.splitlines()
        start=next(i for i,line in enumerate(lines) if marker in line)
        excerpt='\n'.join(lines[start:start+count])
        t=time.perf_counter()
        answer=decider.ask({'project':project, 'query':query, 'source':str(path), 'excerpt':excerpt},
                          {'answer':ChoiceQ('Select the answer supported by this current source excerpt.', options)})['answer']
        rows.append(dict(project=project, path=str(path), line=start+1,
                         source_sha256=hashlib.sha256(text.encode()).hexdigest(), query=query,
                         expected=gold, choice=answer.choice, confidence=answer.confidence,
                         correct=gold==answer.choice, seconds=time.perf_counter()-t))
    result=dict(scope='Local-only source-grounded narrow selection probe, author-selected questions; not end-to-end coding',
                rows=rows, correct=sum(r['correct'] for r in rows), total=len(rows), hosted_calls=0)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
