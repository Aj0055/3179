# Follows the Week 8 studio: TopoJSON base map + CSV joined with "lookup". Run after build_data.py.
import json,csv
g=json.load(open('data/qld_lga.geojson'))
def centroid(geom):  # centre of the council's largest polygon (shoelace formula)
    best=None
    for p in (geom['coordinates'] if geom['type']=='MultiPolygon' else [geom['coordinates']]):
        r=p[0];a=cx=cy=0
        for (x1,y1),(x2,y2) in zip(r,r[1:]):
            w=x1*y2-x2*y1;a+=w;cx+=(x1+x2)*w;cy+=(y1+y2)*w
        if a and (best is None or abs(a)>best[0]): best=(abs(a),cx/(3*a),cy/(3*a))
    return round(best[1],3),round(best[2],3)
F=['lga_code_2021','name','svc','pop','members','members_pct','visits','visits_pc','usage','usage_pc','irsd_decile','irsd_score','bi']
with open('data/library_stats.csv','w',newline='') as f, open('data/council_points.csv','w',newline='') as f2:
    w=csv.writer(f);w.writerow(F);w2=csv.writer(f2);w2.writerow(['name','lon','lat','visits','svc'])
    for ft in g['features']:
        p=ft['properties'];p['lga_code_2021']=p['code']
        w.writerow([p.get(k,'') for k in F])
        if 'visits' in p: w2.writerow([p['name'],*centroid(ft['geometry']),int(p['visits']),p['svc']])
S='https://vega.github.io/schema/vega-lite/v5.json'
P={'type':'conicEqualArea','parallels':[-12,-28],'rotate':[-145,0]}
TOPO={'url':'data/qld_lga.topojson','format':{'type':'topojson','feature':'qld_lga'}}
base={'data':TOPO,'mark':{'type':'geoshape','fill':'#e4e7e2','stroke':'#ffffff','strokeWidth':0.5}}
def lookup(fields):  # code is parsed as a string so it matches the TopoJSON property
    return {'lookup':'properties.lga_code_2021','from':{'data':{'url':'data/library_stats.csv','format':{'type':'csv','parse':{'lga_code_2021':'string'}}},'key':'lga_code_2021','fields':fields}}
def spec(title,sub,layers):
    return {'$schema':S,'title':{'text':title,'subtitle':sub,'anchor':'start','font':'Newsreader','fontSize':18,'subtitleFont':'IBM Plex Sans','subtitleColor':'#5b6660'},'width':'container','height':520,'projection':P,'layer':layers,'config':{'view':{'stroke':None},'font':'IBM Plex Sans'}}
def dump(n,s): json.dump(s,open(f'specs/{n}.json','w'),indent=2)
dom=['Independent','Rural Libraries Queensland','Indigenous Knowledge Centre']
dump('map_library_locations',spec("Where Queensland's libraries are",'Each dot is one branch or community library (mobile libraries and offices excluded)',[base,{'data':{'url':'data/libraries.csv'},'mark':{'type':'circle','size':34,'opacity':0.85,'stroke':'#fff','strokeWidth':0.4},'encoding':{'longitude':{'field':'lon','type':'quantitative'},'latitude':{'field':'lat','type':'quantitative'},'color':{'field':'type','type':'nominal','scale':{'domain':dom,'range':['#2f5d62','#c08a3e','#8b4a6b']},'legend':{'title':'Service type','orient':'bottom'}},'tooltip':[{'field':'name','title':'Library'},{'field':'council','title':'Council'},{'field':'wifi','title':'Wi-Fi'}]}}]))
dump('map_visits_symbol',spec('How many people walk through the door','Physical visits in 2024-25. Each circle sits at the centre of its council',[base,{'data':{'url':'data/council_points.csv'},'mark':{'type':'circle','opacity':0.6,'stroke':'#1f5559','strokeWidth':0.8,'fill':'#46888b'},'encoding':{'longitude':{'field':'lon','type':'quantitative'},'latitude':{'field':'lat','type':'quantitative'},'size':{'field':'visits','type':'quantitative','title':'Visits a year','scale':{'type':'sqrt','range':[10,2500]},'legend':{'orient':'bottom'}},'tooltip':[{'field':'name','title':'Council'},{'field':'visits','type':'quantitative','title':'Visits','format':','}]}}]))
dump('map_loans_per_resident',spec('How often people borrow','Items borrowed per resident, 2024-25. Grey councils have no figures in the bulletin',[base,{'data':TOPO,'transform':[lookup(['name','usage_pc','members_pct']),{'filter':'isValid(datum.usage_pc)'}],'mark':{'type':'geoshape','stroke':'#fff','strokeWidth':0.5},'encoding':{'color':{'field':'usage_pc','type':'quantitative','title':'Loans per resident','scale':{'type':'threshold','domain':[2,4,6,8],'range':['#e3efee','#b7d6d4','#7fb3b2','#46888b','#1f5559']},'legend':{'orient':'bottom'}},'tooltip':[{'field':'name','title':'Council'},{'field':'usage_pc','type':'quantitative','title':'Loans per resident'},{'field':'members_pct','type':'quantitative','title':'Members % of population'}]}}]))
cols={'00':'#e8e8e8','10':'#ace4e4','20':'#5ac8c8','01':'#dfb0d6','11':'#a5add3','21':'#5698b9','02':'#be64ac','12':'#8c62aa','22':'#3b4994'}
dump('map_bivariate',spec('Library use and disadvantage together','Borrowing level (low to high) against socio-economic disadvantage (SEIFA 2021)',[base,{'data':TOPO,'transform':[lookup(['name','usage_pc','irsd_decile','bi']),{'filter':'isValid(datum.bi)'}],'mark':{'type':'geoshape','stroke':'#fff','strokeWidth':0.5},'encoding':{'color':{'field':'bi','type':'nominal','scale':{'domain':list(cols),'range':list(cols.values())},'legend':None},'tooltip':[{'field':'name','title':'Council'},{'field':'usage_pc','type':'quantitative','title':'Loans per resident'},{'field':'irsd_decile','type':'quantitative','title':'Disadvantage decile (1 = most disadvantaged)'}]}}]))
h=open('index.html').read()
sec='''<section><div class="col">
<h2>Busy doors, big and small</h2>
<p>Visits tell a different story from loans. Brisbane and the Gold Coast draw millions of visits a year, but many libraries are places to use computers, meet people and get help, not only to borrow books.</p>
</div>
<div class="wide fig" id="m4" data-spec="specs/map_visits_symbol.json"></div>
<div class="col"><p class="note">Source: Queensland Public Libraries Statistical Bulletin 2024-25, State Library of Queensland.</p></div>
</section>

'''
k='<section><div class="col">\n<h2>Borrowing is far'
if 'm4' not in h: h=h.replace(k,sec+k)
open('index.html','w').write(h)
