from pathlib import Path
import argparse,hashlib,json
import numpy as np
import openpyxl
from scipy.interpolate import PchipInterpolator
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent.parent
p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,default=PACKAGE/'data')
p.add_argument('--book',type=Path,default=PACKAGE/'results'/'q4'/'result4.xlsx')
a=p.parse_args()
s=json.loads((PACKAGE/'results'/'q4'/'validation.json').read_text(encoding='utf-8'))
data=json.loads((PACKAGE/'results'/'q4'/'result4_data.json').read_text(encoding='utf-8'))
for f,k in [('附件1.xlsx','environment_sha256'),('附件2.xlsx','radius_sha256')]:
    assert hashlib.sha256((PACKAGE/'data'/f).read_bytes()).hexdigest()==s[k]
with np.load(PACKAGE/'results'/'q4'/'result4_full_precision.npz') as full:
    assert np.all(np.diff(full['t'][:-1])==60)
    assert full['t'][-2]<s['event_s']<full['t'][-1]
    assert np.nanmax(full['C'][-1])<.15 and np.nanmax(full['C'][-2])>.15
    assert np.all(np.diff(full['R'])<=1e-12)
    outside=(np.arange(20)*.001)[None,:]>full['R'][:,None]
    assert np.array_equal(np.isnan(full['C'][:,:20]),outside)
    assert np.isfinite(full['C'][:,-1]).all()
    expected=np.round(full['C'][1:],4)
    data_array=np.array([[np.nan if v is None else v for v in row] for row in data['C']])
    assert np.array_equal(expected,data_array,equal_nan=True)
    assert np.array_equal(np.round(full['t'][1:],4),data['t_s'])
    assert np.array_equal(full['R'][1:]*100,data['R_cm'])
    for t,c in zip(s['table_t_s'],s['table_C']):
        i=int(np.argmin(abs(full['t']-t)))
        assert np.array_equal(full['C'][i,[0,5,10,20]],c)
    assert full['C'][-1,12]==full['C'][-1,-1]
book=a.book
w=openpyxl.load_workbook(book,data_only=True,read_only=True)
assert w.sheetnames==['Sheet1']
rows=iter(w.active.iter_rows())
head=next(rows)
assert [c.value for c in head[1:]]==data['fixed_r_cm']+['药材表面']
count=0;blanks=0;numeric=0
for i,row in enumerate(rows):
    assert len(row)==22
    assert row[0].value==data['t_s'][i]
    for cell,target in zip(row[1:],data['C'][i]):
        assert cell.value==target
        assert cell.number_format=='0.0000'
        if target is None:blanks+=1
        else:numeric+=1
    count+=1
w.close()
assert count==s['output_rows'] and blanks==s['outside_blank_count']
table=(PACKAGE/'results'/'q4'/'结果表.md').read_text(encoding='utf-8')
assert '{{' not in table
r={'time_rows':count,'numeric_C_cells':numeric,'outside_blank_cells':blanks,
   'all_values_and_masks_match':True,'strict_terminal_check':True,'surface_column_present':True,
   'input_files_unchanged':True,'markdown_tables_match':True}
(PACKAGE/'results'/'q4'/'validation_export.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(r,ensure_ascii=False))
