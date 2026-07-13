#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw
import csv, math
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'analysis-out/xray_optical_missing'
rows=[]
with (OUT/'cell_scores.csv').open() as f:
    for r in csv.DictReader(f):
        if r['bumpbond_missing_candidate']=='True': rows.append(r)
thumbs=[]
for r in rows:
    xray=Image.open(ROOT/r['xray'].lstrip('/')).convert('RGB')
    montage=Image.open(ROOT/r['montage'].lstrip('/')).convert('RGB')
    x=int(float(r['x'])); y=int(float(r['y']))
    xr=xray.crop((max(0,x-35),max(0,y-35),min(xray.width,x+36),min(xray.height,y+36))).resize((142,142))
    tw,th=montage.width/16,montage.height/16
    c=int(r['col']); rr=int(r['row'])
    op=montage.crop((int(c*tw),int(rr*th),int((c+1)*tw),int((rr+1)*th))).resize((180,142))
    panel=Image.new('RGB',(342,178),'white')
    panel.paste(xr,(0,22)); panel.paste(op,(150,22))
    d=ImageDraw.Draw(panel)
    title=f"{r['etroc']} pos {r['pos']} r{r['row']}c{r['col']} opt {r['optical_label']} z {float(r['weak_z']):.1f}"
    d.text((4,4),title,fill=(0,0,0))
    d.rectangle((0,22,141,163),outline=(255,0,0),width=2)
    thumbs.append(panel)
cols=2; w=342*cols; h=178*math.ceil(len(thumbs)/cols)
sheet=Image.new('RGB',(w,h),(240,240,240))
for i,p in enumerate(thumbs): sheet.paste(p,((i%cols)*342,(i//cols)*178))
out=OUT/'candidate_contact_sheet.jpg'
sheet.save(out,quality=92)
print(out, 'candidates', len(rows))
