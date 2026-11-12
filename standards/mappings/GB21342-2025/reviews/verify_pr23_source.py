import hashlib,json,re,subprocess,sys
from pathlib import Path
import pdfplumber
if len(sys.argv)!=3: raise SystemExit('Usage: python verify_pr23_source.py <repo> <authorized-pdf>')
repo=Path(sys.argv[1]); sha='18dd79af74476372e8b6b337df119ce04d9d9198'
pdf=Path(sys.argv[2])
def git(path):return subprocess.check_output(['git','-C',str(repo),'show',sha+':'+path]).decode('utf-8')
md=git('standards/mappings/GB21342-2025/标准映射表_V1.0_草稿.md')
def mdrows(label,end):
 s=md.split(label,1)[1].split(end,1)[0]
 return [[x.strip() for x in ln.strip('|').split('|')] for ln in s.splitlines() if re.match(r'^\|\s*\d',ln)]
a3=[];a4=[]
with pdfplumber.open(pdf) as p:
 for i in [8,9,10,11]:
  mode='A3' if i in [8,9] else 'A4';temp=None
  for table in p.pages[i].extract_tables():
   if i==8 and len(table[0])!=4:continue
   for row in table:
    if row[0] and row[0].startswith('温度'):mode='A4';continue
    if row[0] and not re.match(r'^\d',row[0]):continue
    row=[re.sub(r'\s','',c) if c else None for c in row]
    if mode=='A4':
     temp=row[0] or temp;row[0]=temp;a4.append(row)
    else:a3.append(row)
report={'commit':sha,'pdf_path':str(pdf),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'tables':{}}
for name,actual,expected in [('A3',a3,mdrows('表A.3（p5—6/PDF9—10）：','表A.4（p6—8/PDF10—12）：')),('A4',a4,mdrows('表A.4（p6—8/PDF10—12）：','### 5.6'))]:
 pairs=[{'row':n,'pdf':a,'mapping':b,'equal':a==b} for n,(a,b) in enumerate(zip(actual,expected),1)]
 report['tables'][name]={'columns':['pressure_MPa','temperature_C','enthalpy_kJ_per_kg','coefficient_kgce_per_kg'] if name=='A3' else ['temperature_C','pressure_MPa','enthalpy_kJ_per_kg','coefficient_kgce_per_kg'],'pdf_rows':len(actual),'mapping_rows':len(expected),'compared_cells':4*len(pairs),'mismatch_rows':sum(not x['equal'] for x in pairs),'pairs':pairs}
report['json_facts']=[]
for path in ['data/definitions/gb-21342-2025.json','standards/development/scope-63/definitions/gb-21342-2025.json']:
 d=json.loads(git(path));report['json_facts'].append({'path':path,'supersedes':d['supersedes'],'detail_formula':[p['indicators'][0]['detail_formula'] for p in d['products']]})
print(json.dumps(report,ensure_ascii=False,indent=2))
assert report['pdf_sha256']=='00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0'
assert all(t['pdf_rows']==t['mapping_rows'] and not t['mismatch_rows'] for t in report['tables'].values())
