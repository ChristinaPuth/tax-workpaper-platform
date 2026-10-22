import json,sys,re
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
d=json.load(open(PACKET))
docs={x['id']:x for x in d['documents']}
def page_text(did,p):
    for pg in docs[did]['pages']:
        if pg['page']==p: return pg['printed_content']
    return None
def norm(s): return re.sub(r'\s+',' ',str(s)).strip()
def num(s):
    s=str(s).replace(',','').replace('$','').strip()
    neg=s.startswith('(') and s.endswith(')')
    s=s.strip('()')
    try: v=float(s); return -v if neg else v
    except: return None
notin=[];valmis=[]
for e in d['extracted_values']:
    t=page_text(e['document_id'],e['page'])
    ta=e['text_as_read']
    if t is None: notin.append((e['id'],'NO PAGE')); continue
    if ta and ta not in t: notin.append((e['id'],e['document_id'],e['page'],e['field'],ta,e['confidence']))
    if e['value_type']=='money' and ta:
        n=num(ta)
        if n is not None and e['value'] is not None and abs(n-float(e['value']))>0.005: valmis.append((e['id'],e['document_id'],e['field'],ta,e['value'],e['confidence']))
print('text_as_read not found in printed page:',len(notin))
for x in notin: print(' ',x)
print('value != text_as_read:',len(valmis))
for x in valmis: print(' ',x)
