import json,sys,re
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
d=json.load(open(PACKET))
docs={x['id']:x for x in d['documents']}
v3=d['return_versions'][2]
print('D31 p32:',docs['D31']['pages'][31]['printed_content'])
print('D30 p32:',docs['D30']['pages'][31]['printed_content'][:400])
# D74 reconcile lots in return vs summary
import collections
tot=collections.defaultdict(lambda:[0,0,0])
for l in v3['lines']:
    k=l['key']
    if re.match(r'F8949\.[AD]\.X',k):
        m=re.search(r'proceeds ([\d,.]+), basis ([\d,.]+)(?:, adjustment W ([\d,.]+))?',l['label'])
        b=k.split('.')[1]
        if m:
            tot[b][0]+=float(m.group(1).replace(',',''));tot[b][1]+=float(m.group(2).replace(',',''));tot[b][2]+=float((m.group(3) or '0').replace(',',''))
print('D74 lots in return by box (proceeds,basis,wash):',{k:[round(x,2) for x in v] for k,v in tot.items()})
ex=[l for l in v3['lines'] if re.match(r'F8949\.[AD]\.X',l['key'])][:2]; print([e['label'] for e in ex])
# printed D74 lots totals
txt=' '.join(p['printed_content'] for p in docs['D74']['pages'])
lots=re.findall(r'(X\d+) .*? proceeds ([\d,.]+) basis ([\d,.]+) wash sale loss disallowed ([\d,.]+) (short|long)-term',txt)
agg=collections.defaultdict(lambda:[0,0,0,0])
for x in lots:
    a=agg[x[4]]; a[0]+=float(x[1].replace(',',''));a[1]+=float(x[2].replace(',',''));a[2]+=float(x[3].replace(',',''));a[3]+=1
print('D74 printed lots:',{k:[round(v,2) for v in a] for k,a in agg.items()}, 'unique ids',len(set(x[0] for x in lots)))
