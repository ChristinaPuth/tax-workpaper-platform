import json,sys
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
d=json.load(open(PACKET))
v3=d['return_versions'][2]; L={l['key']:l for l in v3['lines']}
ev={e['id']:e for e in d['extracted_values']}
for k in ['F1040.1a','SchC.1','SchC.9','SchC.18','SchC.27a','SchE.1.14','SchA.12','F7203.1','F8949.A.total']:
  l=L.get(k); 
  if l: print(k,l['label'],l['value'],l['rule'],'inputs',l['inputs'][:6],'src',[(s,ev[s]['document_id'],ev[s]['value']) for s in l['sources'][:6] if s in ev], l.get('note'))
print('confidence<0.7:',sum(1 for e in d['extracted_values'] if e['confidence']<0.7))
print('docs not used in v3:',sorted(set(x['id'] for x in d['documents'])-set(v3['documents_used'])))
print('superseded:',v3['documents_superseded'])
print('lines total per version',[len(v['lines']) for v in d['return_versions']])
print('what_if:',[a['id'] for a in d['what_if']['alternatives']])
print('efile:',json.dumps(d['tax_agency_records']['efile'])[:600])
print('notices:',json.dumps(d['tax_agency_records']['notices'][1])[:600])
