import json,sys,re
PACKET = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json")
d=json.load(open(PACKET))
docs={x['id']:x for x in d['documents']}
ev={e['id']:e for e in d['extracted_values']}
def pt(did,p): return next(pg['printed_content'] for pg in docs[did]['pages'] if pg['page']==p)
print('== text/code/ein/ssn/account values whose text_as_read not on page')
for e in d['extracted_values']:
    if e['value_type'] in ('ein','ssn','account_number','code','text') and e['text_as_read']:
        t=pt(e['document_id'],e['page'])
        if e['text_as_read'] not in t and str(e['value']) not in t:
            print(' ',e['id'],e['document_id'],e['field'],repr(e['value']),repr(e['text_as_read']),e['confidence'])
print('== household people'); 
for p in d['household']['people']: print(' ',{k:p.get(k) for k in ('id','role','name','ssn','dob','full_time_student','months_lived_with_you')})
print('== mileage D23')
for pg in docs['D23']['pages']:
    evs=[e for e in d['extracted_values'] if e['document_id']=='D23' and e['page']==pg['page']]
    miles=[e for e in evs if e['field'].endswith('_miles') or e['field'].endswith('miles')]
    tot=[e for e in evs if e['field']=='page_total']
    print(' page',pg['page'],'n trips',len(miles),'sum',sum(float(e['value']) for e in miles if e['field'].startswith('trip')),'page_total ev',[(e['value'],e['text_as_read']) for e in tot])
    print('   fields sample',sorted(set(re.sub(r'trip\d+_','trip_',e['field']) for e in evs)))
print(pt('D23',4)[-700:])
print('== rules'); 
for r in ['R-8949-LOT','R-ESTIMATED-PAYMENTS','R-MILEAGE-PAGE-TOTALS','R-CA-WAGES-SOURCE','R-SALT-PROPERTY','R-MORTGAGE-INTEREST','R-NONCASH-GIFT','R-CHARITY-CASH','R-SCHC-GROSS','R-CA-ESTIMATED-PAYMENTS']: print(' ',r,':',d['engine_reference']['rules'].get(r))
print('== agency'); print(json.dumps(d['tax_agency_records']['irs_account_transcript_2025'],indent=0)); print(json.dumps(d['tax_agency_records']['ftb_account'],indent=0))
