import json,sys,re
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
from collections import Counter
d=json.load(open(PACKET))
docs={x['id']:x for x in d['documents']}
ev={e['id']:e for e in d['extracted_values']}
v3=d['return_versions'][2]
lots=[l for l in v3['lines'] if l['key'].startswith('F8949.') and not l['key'].endswith('total')]
print('8949 lots',len(lots),Counter(l['key'].split('.')[1]+'.'+re.sub(r'\d+','',l['key'].split('.')[2]) for l in lots))
srcdocs=Counter(ev[s]['document_id'] for l in lots for s in l['sources'] if s in ev); print('lot source docs',srcdocs)
for l in lots:
    if any(x in l['key'] for x in ('.N','.C6','SCORP')): print(' ',l['key'],l['label'][:150],l['value'],l.get('note'))
print('D74 in documents_used:', 'D74' in v3['documents_used'])
print('D74 p1:',docs['D74']['pages'][0]['printed_content'][:900])
print('D74 last:',docs['D74']['pages'][-1]['printed_content'][-900:])
print('D74 ev count',sum(1 for e in d['extracted_values'] if e['document_id']=='D74'))
print('D31 p1:',docs['D31']['pages'][0]['printed_content'][:900])
print('D31 extraction',docs['D31']['extraction'])
