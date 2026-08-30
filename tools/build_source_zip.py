from pathlib import Path
import zipfile
root=Path(r'G:\Python Project\能耗限额')
out=root/'dist/release/UEBench-source-0.1.0.zip'
exclude_top={'dist','build','work','outputs','.git','.venv','.pytest_cache'}
include_roots=['src','tests','tools','scripts','packaging','migrations','data','docs']
files=[]
for name in include_roots:
    base=root/name
    if not base.exists(): continue
    for p in base.rglob('*'):
        if p.is_file() and not ({'__pycache__','node_modules'} & set(p.parts)) and p.suffix not in {'.pyc','.pyo'}:
            files.append(p)
for name in ['README.md','pyproject.toml','requirements.txt','requirements.lock','run_uebench.py','uebench.spec','alembic.ini','.gitignore']:
    p=root/name
    if p.exists(): files.append(p)
files=sorted(set(files))
out.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files:
        z.write(p,p.relative_to(root).as_posix())
print('wrote',out,'files',len(files),'bytes',out.stat().st_size)

