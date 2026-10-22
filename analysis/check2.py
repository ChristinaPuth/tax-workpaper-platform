import json,sys,re
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
from collections import defaultdict
d=json.load(open(PACKET))
docs={x['id']:x for x in d['documents']}
def page_text(did,p):
    for pg in docs[did]['pages']:
        if pg['page']==p: return pg['printed_content']
def nums(t):
    out=set()
    for m in re.findall(r'\(?-?\$?\d[\d,]*\.?\d*\)?',t):
        s=m.replace(',','').replace('$','')
        neg=s.startswith('(') or s.startswith('-')
        s=s.strip('()-').rstrip('.')
        try:
            v=float(s); out.add(round(v,2)); out.add(round(-v,2))
        except: pass
    return out
bad=defaultdict(list)
for e in d['extracted_values']:
    if e['value_type'] not in ('money','integer','quantity','percent'): continue
    if e['value'] is None: continue
    t=page_text(e['document_id'],e['page']) or ''
    v=round(float(e['value']),2)
    ns=nums(t)
    if v in ns or (e['value_type']=='percent' and (round(v*100,2) in ns)): continue
    bad[e['document_id']].append((e['id'],e['field'],e['value'],e['text_as_read'],e['confidence']))
tot=sum(len(v) for v in bad.values()); print('numeric values not present on page:',tot)
for k,v in bad.items():
    print(k,docs[k]['title'][:60],len(v))
    for x in v[:8]: print('   ',x)
