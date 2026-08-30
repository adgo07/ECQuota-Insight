from __future__ import annotations

import json
import re
from pathlib import Path

ROOT=Path(r'G:\Python Project\能耗限额')
SCOPE=set(json.loads((ROOT/'data/scope-44.json').read_text(encoding='utf8'))['standards'])
# Longest first: these are the metric terms allowed in the indicator-name column.
METRICS=(
    '单位产品综合电耗', '单位产品综合能耗', '单位产品能源消耗', '单位产品电耗',
    '单位产品能耗', '单位产品焦耗', '单位产品煤耗', '单位产品天然气耗',
    '单位产品油耗', '单位产品水耗', '单位产品热耗', '吨酸电耗',
)
TABLE_PREFIX=re.compile(r'^\s*表\s*\d+\s*')

def split_metric(text: str):
    text=TABLE_PREFIX.sub('', ' '.join(str(text).split())).strip()
    for metric in METRICS:
        pos=text.find(metric)
        if pos>=0:
            prefix=text[:pos].strip()
            suffix=text[pos+len(metric):].strip()
            # A parenthetical qualifier after the metric belongs to the product/condition,
            # not to the generic indicator label.
            product=(prefix + suffix).strip()
            return product, metric
    return text, None

changed_files=[]
all_mappings={}
overrides_path=ROOT/'data/indicator-name-overrides.json'
overrides=json.loads(overrides_path.read_text(encoding='utf8'))
all_mappings.update(overrides.get('mappings',{}))
for path in sorted((ROOT/'data/definitions').glob('*.json')):
    data=json.loads(path.read_text(encoding='utf8'))
    if data.get('number') not in SCOPE:
        continue
    changed=False
    for product in data.get('products',[]):
        old_product=product.get('name','')
        # Derive each row from the indicator text when it contains a metric. This
        # keeps duplicate product names valid when their indicators differ.
        for indicator in product.get('indicators',[]):
            old_indicator=indicator.get('name','')
            product_candidate, metric=split_metric(old_indicator)
            if metric is None:
                product_candidate, metric2=split_metric(old_product)
                metric=metric2
            if metric is None:
                continue
            if not product_candidate:
                product_candidate=TABLE_PREFIX.sub('', old_product).strip()
            if product.get('name') != product_candidate:
                # Only replace names that contain an explicit metric; conditions and
                # product qualifiers remain in the product name.
                product['name']=product_candidate
                changed=True
            if indicator.get('name') != metric:
                indicator['name']=metric
                changed=True
            all_mappings[indicator['id']]={'product':product['name'],'indicator':metric}
        # If one indicator was normalized, synchronize the product name for remaining
        # indicators in this row only when their names are already the same family.
    if changed:
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        changed_files.append(str(path.relative_to(ROOT)))
# Keep mappings for all existing IDs and update only normalized rows.
overrides['mappings']=dict(sorted(all_mappings.items()))
overrides['mapping_count']=len(overrides['mappings'])
overrides['generated_at']='2026-08-30'
overrides_path.write_text(json.dumps(overrides,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('changed definition files',len(changed_files))
for f in changed_files: print(f)
print('mapping_count',overrides['mapping_count'])
