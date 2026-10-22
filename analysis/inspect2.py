import json,sys
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
d=json.load(open(PACKET))
r=d['readme']
for k in ['what_this_is','truth_and_mistakes','no_page_images','engine_and_recomputing','where_now_is']: print(k,':',r[k],'\n')
for k in ['documents','extracted_values','return_versions[]','return_versions[].lines[]','timeline','firm','tax_agency_records']: print('SEC',k,':',r['sections'][k],'\n')
print('== DOCS')
for x in d['documents']: print(x['id'],x['document_type'],'|',x['title'],'|',x['received_at'][:10],'|',x['extraction'].get('status') if isinstance(x['extraction'],dict) else x['extraction'])
print('== doc sample'); print(json.dumps(d['documents'][10],indent=1)[:1500])
print('== EV sample'); print(json.dumps(d['extracted_values'][100],indent=1))
print('== TIMELINE')
for t in d['timeline']: print(t['id'],t['at'][:10],t['event'],t['actor'],'|',(t['detail'] or '')[:110])
for v in d['return_versions']:
  print('== VERSION',v['version'],v['computed_at'][:10],v['trigger']); print(' summary',json.dumps(v['summary'])[:400])
  for g in v['diagnostics']: print('  DIAG',json.dumps(g)[:230])
  for c in v['changes_from_previous'][:6]: print('  CHG',json.dumps(c)[:230])
print('== LINE sample'); print(json.dumps(d['return_versions'][2]['lines'][40],indent=1))
print('== standards'); print(json.dumps(d['firm']['starter_standards'],indent=1)[:2500])
print('== staff'); print(json.dumps(d['firm']['staff'])[:900])
print('== prior preparer'); print(json.dumps(d['prior_years']['prior_preparer_workpaper'],indent=1)[:1800])
print('== call'); print(json.dumps(d['client']['call_notes'],indent=1)[:1500])
print('== msgs'); 
for m in d['client']['messages']: print(m['id'],m['from'],':',m['text'][:160])
