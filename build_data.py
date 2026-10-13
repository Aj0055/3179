# Builds data/ and specs/ from the raw files. Run: python3 build_data.py
import re,json,subprocess,glob,os,pandas as pd
U='/mnt/user-data/uploads/'; os.makedirs('data',exist_ok=True); os.makedirs('specs',exist_ok=True)
norm=lambda s:re.sub(r'[^a-z]','',re.sub(r'\(.*?\)|shire|regional|city|town authority|aboriginal|council','',s.lower()))
# 1 bulletin summary table (page 1 of the State Library of Queensland bulletin)
txt=subprocess.run(['pdftotext','-layout',glob.glob(U+'2024-25_Statistical*.pdf')[0],'-'],capture_output=True,text=True).stdout
N=r'([\d,.]+)'
pat=re.compile(r'^\s*(.+?)\s+(Rural Libraries Queensland \(RLQ\)|Independent \(IND\))\s+'+r'\s+'.join([N,N,N+'%',N,N,N,N,N+'%',N+'%',N,N,N])+r'\s*$')
rows={}
for l in txt.splitlines():
    m=pat.match(l)
    if m:
        g=[x.replace(',','') for x in m.groups()]
        rows[norm(g[0])]=dict(svc='RLQ' if 'RLQ' in g[1] else 'IND',pop=float(g[2]),members=float(g[3]),members_pct=float(g[4]),visits=float(g[5]),visits_pc=float(g[7]),usage=float(g[11]),usage_pc=float(g[12]))
print('bulletin councils parsed:',len(rows))
# 2 SEIFA
s=pd.read_excel(U+'Local_Government_Area__Indexes__SEIFA_2021.xlsx',sheet_name='Table 1',header=None).iloc[6:]
s=s[s[0].astype(str).str.match(r'^3\d{4}$')]
sf={str(r[0]):(int(r[3]),int(r[2])) for _,r in s.iterrows()}
# 3 simplify boundaries (Douglas-Peucker) and join
def dp(p,e):
    k=[False]*len(p);k[0]=k[-1]=True;st=[(0,len(p)-1)]
    while st:
        a,b=st.pop();x1,y1=p[a];x2,y2=p[b];dx,dy=x2-x1,y2-y1;n=(dx*dx+dy*dy)**.5 or 1e-12;m=0;j=-1
        for i in range(a+1,b):
            d=abs(dy*(p[i][0]-x1)-dx*(p[i][1]-y1))/n
            if d>m:m=d;j=i
        if m>e:k[j]=True;st+=[(a,j),(j,b)]
    return [[round(q[0],3),round(q[1],3)] for q,f in zip(p,k) if f]
def ring(r):
    h=len(r)//2; a=dp(r[:h+1],0.012); b=dp(r[h:],0.012)
    return a[:-1]+b
def poly(rs):
    out=[ring(r) for r in rs]; out=[r for r in out if len(r)>=4]
    return out if out and len(out[0])>=4 else None
g=json.load(open(U+'qld_lga.geojson')); feats=[]; miss=[]
for f in g['features']:
    if not f['geometry']: continue
    c=f['properties']['lga_code_2021']; nm=f['properties']['lga_name_2021']
    ps=[poly(f['geometry']['coordinates'])] if f['geometry']['type']=='Polygon' else [poly(p) for p in f['geometry']['coordinates']]
    ps=[p for p in ps if p]
    if not ps: continue
    d,sc=sf[c]; b=rows.get(norm(nm))
    if not b: miss.append(nm)
    pr=dict(code=c,name=re.sub(r' \(Qld\)','',nm),irsd_decile=d,irsd_score=sc,**(b or {}))
    feats.append(dict(type='Feature',properties=pr,geometry=dict(type='MultiPolygon',coordinates=ps)))
print('councils without bulletin stats (shown as no data):',miss)
# bivariate classes: usage tercile x disadvantage group
u=pd.Series({i:f['properties'].get('usage_pc') for i,f in enumerate(feats)}).dropna()
q1,q2=u.quantile([1/3,2/3])
for f in feats:
    p=f['properties']
    if 'usage_pc' in p:
        a=0 if p['usage_pc']<=q1 else 1 if p['usage_pc']<=q2 else 2
        d=0 if p['irsd_decile']<=3 else 1 if p['irsd_decile']<=7 else 2
        p['bi']=f'{a}{d}'
json.dump(dict(type='FeatureCollection',features=feats),open('data/qld_lga.geojson','w'),separators=(',',':'))
print('geojson KB:',os.path.getsize('data/qld_lga.geojson')//1024)
# 4 library directory
L=pd.read_csv(U+'opendata_2026_public_library_directory_.csv',encoding='utf-8-sig')
L=L[L['Branch Type'].isin(['Branch','Community'])]
t={'Independent Library Service':'Independent','Rural Libraries Queensland':'Rural Libraries Queensland','Indigenous Knowledge Centre':'Indigenous Knowledge Centre','State Library of Queensland':'Independent'}
out=pd.DataFrame(dict(name=L['Branch Name'],council=L['Name of Library Service'],type=L['Library Service Type'].map(t),wifi=L['WiFi Availability'],lat=L['Latitude (Decimal)'],lon=L['Longitude (Decimal)']))
out.to_csv('data/libraries.csv',index=False); print('libraries:',len(out))
# 5 specs
S='https://vega.github.io/schema/vega-lite/v5.json'
P={'type':'conicEqualArea','parallels':[-12,-28],'rotate':[-145,0]}
base={'data':{'url':'data/qld_lga.geojson','format':{'type':'json','property':'features'}},'mark':{'type':'geoshape','fill':'#e4e7e2','stroke':'#ffffff','strokeWidth':0.5}}
def spec(title,sub,layers):
    return {'$schema':S,'title':{'text':title,'subtitle':sub,'anchor':'start','font':'Newsreader','fontSize':18,'subtitleFont':'IBM Plex Sans','subtitleColor':'#5b6660'},'width':'container','height':520,'projection':P,'layer':layers,'config':{'view':{'stroke':None},'font':'IBM Plex Sans'}}
dom=['Independent','Rural Libraries Queensland','Indigenous Knowledge Centre']
json.dump(spec('Where Queensland\'s libraries are','Each dot is one branch or community library (mobile libraries and offices excluded)',[base,{'data':{'url':'data/libraries.csv'},'mark':{'type':'circle','size':34,'opacity':0.85,'stroke':'#fff','strokeWidth':0.4},'encoding':{'longitude':{'field':'lon','type':'quantitative'},'latitude':{'field':'lat','type':'quantitative'},'color':{'field':'type','type':'nominal','scale':{'domain':dom,'range':['#2f5d62','#c08a3e','#8b4a6b']},'legend':{'title':'Service type','orient':'bottom'}},'tooltip':[{'field':'name','title':'Library'},{'field':'council','title':'Council'},{'field':'wifi','title':'Wi-Fi'}]}}]),open('specs/map_library_locations.json','w'),indent=2)
json.dump(spec('How often people borrow','Items borrowed per resident, 2024-25. Grey councils have no figures in the bulletin',[base,{'transform':[{'filter':'isValid(datum.properties.usage_pc)'}],'mark':{'type':'geoshape','stroke':'#fff','strokeWidth':0.5},'encoding':{'color':{'field':'properties.usage_pc','type':'quantitative','scale':{'type':'quantile','scheme':'tealblues'},'legend':{'title':'Loans per resident','orient':'bottom'}},'tooltip':[{'field':'properties.name','title':'Council'},{'field':'properties.usage_pc','title':'Loans per resident'},{'field':'properties.members_pct','title':'Members % of population'}]}}]),open('specs/map_loans_per_resident.json','w'),indent=2)
cols={'00':'#e8e8e8','10':'#ace4e4','20':'#5ac8c8','01':'#dfb0d6','11':'#a5add3','21':'#5698b9','02':'#be64ac','12':'#8c62aa','22':'#3b4994'}
json.dump(spec('Library use and disadvantage together','Borrowing level (low to high) against socio-economic disadvantage (SEIFA 2021)',[base,{'transform':[{'filter':'isValid(datum.properties.bi)'}],'mark':{'type':'geoshape','stroke':'#fff','strokeWidth':0.5},'encoding':{'color':{'field':'properties.bi','type':'nominal','scale':{'domain':list(cols),'range':list(cols.values())},'legend':None},'tooltip':[{'field':'properties.name','title':'Council'},{'field':'properties.usage_pc','title':'Loans per resident'},{'field':'properties.irsd_decile','title':'Disadvantage decile (1 = most disadvantaged)'}]}}]),open('specs/map_bivariate.json','w'),indent=2)
hi=max(feats,key=lambda f:f['properties'].get('usage_pc',0))['properties']; lo=min((f for f in feats if 'usage_pc' in f['properties']),key=lambda f:f['properties']['usage_pc'])['properties']
json.dump(dict(hi=hi['name'],hi_v=hi['usage_pc'],lo=lo['name'],lo_v=lo['usage_pc'],n=len(out),q1=round(q1,1),q2=round(q2,1)),open('/tmp/facts.json','w'))
