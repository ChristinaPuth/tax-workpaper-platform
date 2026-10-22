import json,sys
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
d=json.load(open(PACKET))
def shape(x,depth=0,maxd=3):
    p='  '*depth
    if isinstance(x,dict):
        for k,v in list(x.items())[:40]:
            t=type(v).__name__
            n=len(v) if isinstance(v,(list,dict,str)) else ''
            print(f"{p}{k}: {t} {n}" + (f" = {v!r}"[:120] if not isinstance(v,(list,dict)) else ''))
            if depth<maxd and isinstance(v,(dict,list)): shape(v,depth+1,maxd)
    elif isinstance(x,list) and x:
        print(f"{p}[0]:"); shape(x[0],depth+1,maxd)
shape(d,0,2)
