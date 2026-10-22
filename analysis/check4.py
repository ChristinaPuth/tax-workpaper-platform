import json,sys,re
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
d=json.load(open(PACKET))
docs={x['id']:x for x in d['documents']}
pages=docs['D23']['pages']
for pg in pages:
    t=pg['printed_content']
    trips=re.findall(r'(\d{4}-\d{2}-\d{2}) ([^;]*?) (\d[\d,]*) mi',t)
    print('page',pg['page'],'trips',len(trips),'printed sum',sum(int(m[2].replace(',','')) for m in trips),'| header:',t[:160])
    m=re.search(r'Page total ([\d,]+)',t); print('   printed page total',m.group(1) if m else None)
p2=[x[:2] for x in re.findall(r'(\d{4}-\d{2}-\d{2}) ([^;]*?) (\d[\d,]*) mi',pages[1]['printed_content'])]
p3=[x[:2] for x in re.findall(r'(\d{4}-\d{2}-\d{2}) ([^;]*?) (\d[\d,]*) mi',pages[2]['printed_content'])]
print('p2==p3 trips identical:',p2==p3, 'overlap',len(set(p2)&set(p3)))
print('p2 dates',p2[0][0],p2[-1][0],'p3 dates',p3[0][0],p3[-1][0])
qa=[q for q in d['client']['questionnaire']]
for q in qa: print(q['id'],q['question'][:90],'=>',str(q['answer'])[:120])
