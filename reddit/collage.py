import pandas as pd, numpy as np, json, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from pyproj import Transformer
F='/tmp/claude-0/-home-claude/c232619d-81e0-53f3-9de6-41e973630753/scratchpad/fonts/'
for f in ['FrauncesVar.ttf','IBMPlexMono-Regular.ttf','IBMPlexMono-Medium.ttf','SourceSerif4-Regular.ttf','SourceSerif4-Semibold.ttf','SourceSerif4-It.ttf']: fm.fontManager.addfont(F+f)
DISP=fm.FontProperties(fname=F+'FrauncesVar.ttf',weight=900)
SER='Source Serif 4'; MONO='IBM Plex Mono'
BG='#F3EEE2'; FG='#1D1A15'; MUT='#6B6457'; LAND='#D9D1BF'
tr=Transformer.from_crs(4326,27700,always_xy=True)
d=pd.read_csv('../data/landscape_words.csv'); d['x'],d['y']=tr.transform(d.lon.values,d.lat.values)
base=pd.read_csv('/home/claude/hist/osnames_gb.tsv',sep='\t',usecols=['x','y'])
base=base.sample(140000,random_state=1)
B=json.load(open('../data/boundaries.geojson'))
def proj_lines(pairs):
    L=[]
    for f in B['features']:
        p=f['properties']
        if p.get('kind')=='word_boundary' and p.get('pair') in pairs:
            g=f['geometry']; cs=g['coordinates'] if g['type']=='MultiLineString' else [g['coordinates']]
            for c in cs:
                c=np.array(c); X,Y=tr.transform(c[:,0],c[:,1]); L.append((p['pair'],X,Y))
    return L
def basemap(ax,ext=None,s=0.25):
    ax.scatter(base.x,base.y,s=s,c=LAND,lw=0,rasterized=True)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_xlim(60000,660000); ax.set_ylim(5000,980000)
fig=plt.figure(figsize=(12,15),dpi=200,facecolor=BG)
# title
fig.text(0.04,0.965,'Beck, brook or burn?',fontproperties=DISP,fontsize=50,color=FG,va='top')
fig.text(0.04,0.918,'What Britain calls its streams, valleys and hills. Every named feature on the Ordnance Survey map,\nsorted by its landscape word: 74,934 features, including 29,677 named streams.',family=SER,fontsize=15.5,color=FG,va='top',linespacing=1.35)
# big stream map
ax=fig.add_axes([0.0,0.255,0.56,0.60]); basemap(ax,s=0.35)
S=[('brook','#D9480F','brook  (Old English)'),('beck','#2763A8','beck  (Old Norse)'),('burn','#A87400','burn  (Old English / Scots)'),('allt','#4D7A2E','allt  (Gaelic)'),('nant','#8E3E9E','nant / afon  (Welsh)')]
for w,c,lab in S:
    q=d[(d.family=='stream')&(d.word.isin(['nant','afon']) if w=='nant' else d.word.eq(w))]
    ax.scatter(q.x,q.y,s=2.2,c=c,lw=0,alpha=.85,rasterized=True,label=f'{lab}   {len(q):,}')
for pair,X,Y in proj_lines({'beck_brook','burn_beck'}):
    ax.plot(X,Y,color=FG,lw=2.6,solid_capstyle='round')
h,l=ax.get_legend_handles_labels(); lg=fig.legend(h,l,loc='upper left',bbox_to_anchor=(0.585,0.855),frameon=False,markerscale=6,prop={'family':MONO,'size':11},handletextpad=.3,labelcolor=FG,labelspacing=.55)
ax.text(395000,180000,'',)
# annotations of lines
ax.annotate('beck | brook\n80% to 20% in 11 km',xy=(472000,393000),xytext=(535000,445000),family=MONO,fontsize=10,color=FG,arrowprops=dict(arrowstyle='-',color=FG,lw=.8))
ax.annotate('burn | beck\n40 km inside England',xy=(430000,575000),xytext=(455000,700000),family=MONO,fontsize=10,color=FG,arrowprops=dict(arrowstyle='-',color=FG,lw=.8))
# right column text
tx=fig.add_axes([0.6,0.30,0.38,0.42]); tx.axis('off')
notes=[('11 km','to go from 80% becks to 80% brooks.\nOne of the sharpest dialect lines in Britain.'),
       ('0.63','correlation between becks and Norse\nplace names (-by, -thorpe, -thwaite).'),
       ('84 km','The beck/brook line runs this far north\nof the old Danelaw boundary. The -by and\n-thorpe names follow the Danelaw; the\nstream names do not.'),
       ('10.6 km','median distance from the Welsh words\nnant and afon to the Welsh border.\nThe Scottish border is no word line at all.')]
for (big,small),y in zip(notes,[1.0,0.77,0.55,0.21]):
    tx.text(0,y,big,fontproperties=DISP,fontsize=27,color='#D9480F',va='top',transform=tx.transAxes)
    tx.text(0,y-0.075,small,family=SER,fontsize=12,color=FG,va='top',transform=tx.transAxes,linespacing=1.25)
# small multiples
SM=[('dale','dale','#2763A8','valley'),('clough','clough / cleugh','#4D7A2E','valley'),('combe','combe / bottom','#D9480F','valley'),
    ('fell','fell','#2763A8','hill'),('down','down','#D9480F','hill'),('law','law','#A87400','hill')]
for i,(w,lab,c,fam) in enumerate(SM):
    a=fig.add_axes([0.02+i*0.163,0.06,0.16,0.19]); basemap(a,s=0.08)
    ws={'clough':['clough','cleugh'],'combe':['combe','bottom']}.get(w,[w])
    q=d[(d.family==fam)&d.word.isin(ws)]
    a.scatter(q.x,q.y,s=3.5,c=c,lw=0,alpha=.9,rasterized=True)
    a.set_title(f'{lab}\n{len(q):,}',family=MONO,fontsize=11,color=FG,pad=2)
fig.text(0.04,0.283,'VALLEYS',family=MONO,fontsize=11,color=MUT); fig.text(0.53,0.283,'HILLS',family=MONO,fontsize=11,color=MUT)
fig.text(0.04,0.018,'Data: Ordnance Survey OS Open Names and OS Open Rivers. Contains OS data © Crown copyright and database right 2026 (OGL v3).\nAnalysis and chart: Tristan Hotham, with Python and matplotlib. Lines: where two words are equally common (kernel smoothing).',family=MONO,fontsize=9,color=MUT,linespacing=1.4)
fig.savefig('beck_brook_burn.png',facecolor=BG,dpi=200)
print('ok')
