"""Presentation only. Reads frozen aggregate outputs; no estimation or model fitting."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--output',required=True);ap.add_argument('--private-charls-oof');a=ap.parse_args()
P=Path(a.source);O=Path(a.output);O.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':8,'pdf.fonttype':42,'ps.fonttype':42,'axes.linewidth':.6,'lines.linewidth':1,'savefig.dpi':300})
M='#0072B2';R='#D55E00';states=['#D9D9D9',M,'#009E73',R];hatches=['','///','xx','...']
def load(d,n):return pd.read_csv(P/d/f'PROD01_{n}.csv',dtype={'wave':str})
W=load('01_aim1','AIM1_WEIGHTED_ESTIMATES');S=load('01_aim1','AIM1_STATE_TABLE');A=load('02_aim2','AIM2_PRIMARY_ESTIMATES');I=load('03_aim3','AIM3_BLOCK_INCREMENT');K=load('03_aim3','AIM3_RISK_RANK_COMPARISON');E=load('03_aim3','AIM3_EXTERNAL_TRANSPORT')
F=A[A.model.isin(['BASE_SES','BASE_ACCESS'])].copy();F['risk_difference_pp']=F.risk_difference*100;F['CI95_low_pp']=F.RD_CI95_low*100;F['CI95_high_pp']=F.RD_CI95_high*100
G=I[(I.dataset=='CHARLS')&(I.target=='R_MINUS_M')&I.block.isin(['BASE_SES','BASE_ACCESS'])&I.metric.isin(['AUROC','Brier','log_loss'])].copy()
H=K[(K.dataset=='CHARLS')&(K.fraction=='0.1')].copy();X=E[(E.block=='BASE')&(E.domain=='EXTERNAL_FULL_COMMON_PAIR')&E.metric.isin(['AUROC','calibration_intercept','calibration_slope'])].copy()
assert len(G)==6 and ((G.CI95_low<=0)&(G.CI95_high>=0)).all()
for i,d in [(2,W),(3,F),(4,pd.concat([G,H],ignore_index=True)),(5,X)]:d.to_csv(O/f'FIGURE_{i}_SOURCE_DATA.csv',index=False)
concept=pd.DataFrame([['M','Current BP physiology; survey protocol; current treatment/state'],['R','BP-related history; assessment/contact; professional recognition; reporting; treatment/history'],['CHARLS','Development and longitudinal discovery; 2013–2015'],['ELSA','External longitudinal evaluation; waves 4–6'],['HRS','External longitudinal evaluation; 2014–2018'],['NHANES','Cross-sectional benchmark; 2015–2016']],columns=['element','description']);concept.to_csv(O/'FIGURE_1_SOURCE_DATA.csv',index=False)
S.drop_duplicates(['dataset','wave'])[['dataset','wave','N_eligible_source_population','N_valid_MR','unresolved_MR_fraction']].to_csv(O/'FIGURE_2_AVAILABILITY_SOURCE_DATA.csv',index=False)
K.to_csv(O/'FIGURE_4B_AGGREGATE_RANK_SOURCE_DATA.csv',index=False)
def fig(mm):return plt.figure(figsize=(170/25.4,mm/25.4),layout='constrained')
def save(f,i,height):
 f.savefig(O/f'FIGURE_{i}_FINAL.pdf');f.savefig(O/f'FIGURE_{i}_FINAL.png',dpi=300)
 (O/f'FIGURE_{i}_QC.md').write_text(f'# Figure {i} production QC\n\nPresentation-only transformation of frozen outputs. Dimensions 170 × {height} mm. PDF vector output; TrueType fonts embedded; 300-dpi PNG. No model fit, inference or scientific statistic recalculation. CI segments and point estimates are drawn independently to preserve percentile intervals. Minimum specified line width 0.6 pt. Visual review is recorded in the final technical QC.\n')
 plt.close(f)
def style(ax):
 ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',color='#eeeeee',lw=.6);ax.set_axisbelow(True)
f=fig(123); gs=f.add_gridspec(3,2,height_ratios=[2.2,.5,1.7]);ax=f.add_subplot(gs[0,0]);bx=f.add_subplot(gs[0,1]);cx=f.add_subplot(gs[1,:]);dx=f.add_subplot(gs[2,:])
for q,title,color,items in [(ax,'A  Measurement-defined phenotype M',M,['Current BP physiology','Survey measurement protocol','Current treatment/state']),(bx,'B  Clinically recognized hypertension R',R,['BP-related history','Clinical assessment/contact','Professional recognition','Communication/reporting','Treatment/history'])]:
 q.axis('off');q.set_title(title,loc='left',fontweight='bold',fontsize=8.6)
 for j,t in enumerate(items):
  y=.9-j*(.72/(len(items)-1));q.text(.05,y,t,ha='left',va='center',bbox={'boxstyle':'round,pad=.35','fc':'white','ec':color,'lw':.8},transform=q.transAxes)
 q.text(.05,.01,'Conceptual contributors; dashed connections',fontsize=7,transform=q.transAxes)
 q.plot([.02,.02],[.17,.88],ls='--',color=color,lw=.8,transform=q.transAxes)
cx.axis('off');cx.text(.5,.5,'OVERLAPPING INFORMATION  •  NON-EQUIVALENT OBSERVATIONS',ha='center',va='center',fontweight='bold',fontsize=8.4)
dx.axis('off');dx.set_title('C  Population studies and analysis aims',loc='left',fontweight='bold')
for j,(c,t) in enumerate([('CHARLS','Development / longitudinal discovery'),('ELSA','External longitudinal evaluation'),('HRS','External longitudinal evaluation'),('NHANES','Cross-sectional benchmark')]):dx.text(.01,.84-j*.21,f'{c:8s}  {t}',fontsize=8)
dx.text(.63,.84,'Aim 1  Joint M/R states\n\nAim 2  Subsequent recognition\n\nAim 3  Paired target comparison',fontsize=8,va='top');save(f,1,123)
f=fig(135);gs=f.add_gridspec(2,1,height_ratios=[4,1.4]);ax=f.add_subplot(gs[0]);bx=f.add_subplot(gs[1]);keys=list(W[['dataset','wave']].drop_duplicates().itertuples(index=False,name=None));ys=np.arange(len(keys));left=np.zeros(len(keys))
for j,st in enumerate(['S1','S2','S3','S4']):
 vals=np.array([W[(W.dataset==c)&(W.wave==w)&(W.state==st)].weighted_percentage.iloc[0] for c,w in keys]);ax.barh(ys,vals,left=left,color=states[j],hatch=hatches[j],edgecolor='white',lw=.7,label=['M− / R−','M+ / R−','M+ / R+','M− / R+'][j]);left+=vals
ax.set_yticks(ys,[f'{c} {w}' for c,w in keys]);ax.invert_yaxis();ax.set_xlim(0,100);ax.set_xlabel('Weighted percentage in valid M/R positive-weight domain');ax.legend(ncol=2,loc='lower left',bbox_to_anchor=(0,1.01),frameon=False);style(ax)
avail=S.drop_duplicates(['dataset','wave']).set_index(['dataset','wave']);bx.axis('off');bx.text(0,1,'Availability in eligible respondent population (separate denominator)',fontweight='bold',fontsize=8)
for j,(c,w) in enumerate(keys):
 r=avail.loc[(c,w)];xx=(j%4)*.25;yy=.63-(j//4)*.45;bx.text(xx,yy,f'{c} {w}\nUnresolved {r.unresolved_MR_fraction*100:.1f}%',fontsize=7.5)
save(f,2,135)
f=fig(135);gs=f.add_gridspec(2,1);axs=[f.add_subplot(gs[j]) for j in range(2)]
for j,(ax,block) in enumerate(zip(axs,['BASE_SES','BASE_ACCESS'])):
 labs=[]
 for y,c in enumerate(['CHARLS','ELSA','HRS']):
  r=F[(F.dataset==c)&(F.model==block)].iloc[0];ax.plot([r.CI95_low_pp,r.CI95_high_pp],[y,y],color='#333333',lw=1.2);ax.plot(r.risk_difference_pp,y,'o' if j==0 else 's',color=M if j==0 else R,ms=4.5)
  labs.append(c if j==0 else c+'\n'+{'CHARLS':'Prior-month healthcare contact','ELSA':'GP access difficulty','HRS':'Doctor contact since prior interview'}[c])
 ax.set_yticks(range(3),labs);ax.invert_yaxis();ax.axvline(0,color='#777777',ls='--',lw=.8);ax.set_xlabel('Adjusted standardized risk difference (percentage points)');ax.set_title(['A  Higher versus lower attained education','B  Source-native contact/access contrasts'][j],loc='left',fontweight='bold');style(ax)
axs[1].text(.98,.98,'SOURCE-NATIVE MEASURES\nNOT DIRECTLY HARMONIZED',transform=axs[1].transAxes,ha='right',va='top',fontsize=7);save(f,3,135)
f=fig(179);gs=f.add_gridspec(2,3,height_ratios=[1,2.1]);axes=[f.add_subplot(gs[0,j]) for j in range(3)]
for j,(ax,metric) in enumerate(zip(axes,['AUROC','Brier','log_loss'])):
 for y,b in enumerate(['BASE_SES','BASE_ACCESS']):
  r=G[(G.block==b)&(G.metric==metric)].iloc[0];ax.plot([r.CI95_low,r.CI95_high],[y,y],color='#333333',lw=1.2);ax.plot(r.gain,y,'o' if y==0 else 's',color=M if y==0 else R,ms=4)
 ax.axvline(0,ls='--',color='#777777',lw=.8);ax.set_yticks([0,1],['Education','Contact'] if j==0 else []);ax.set_ylim(1.6,-.6);ax.set_title(('A  ' if j==0 else '')+metric.replace('_',' '),loc='left',fontweight='bold');ax.set_xlabel('R-minus-M gain');ax.ticklabel_format(axis='x',style='sci',scilimits=(-3,-3));style(ax)
bx=f.add_subplot(gs[1,:2]);cx=f.add_subplot(gs[1,2]);bx.set_title('B  Overall rank agreement (FULL)',loc='left',fontweight='bold')
if a.private_charls_oof:
 # Only explicitly authorized probability columns; no identifiers or outcomes loaded.
 z=pd.read_parquet(a.private_charls_oof,columns=['FULL_M','FULL_R']);assert len(z)==5303
 u=z.FULL_M.rank(method='average',pct=True)*100;v=z.FULL_R.rank(method='average',pct=True)*100
 hb=bx.hexbin(u,v,gridsize=28,mincnt=1,cmap='Greys',linewidths=.3);cb=f.colorbar(hb,ax=bx,orientation='horizontal',fraction=.07,pad=.15);cb.set_label('Participants per display bin')
else:
 bx.axis('off');bx.text(.1,.5,'Participant predictions require controlled access.\nSee frozen aggregate rank summaries.')
bx.set_xlabel('M-target risk percentile');bx.set_ylabel('R-target risk percentile');bx.text(.04,.96,'Spearman ρ = 0.917\n95% CI 0.783–0.950',transform=bx.transAxes,va='top',bbox={'facecolor':'white','edgecolor':'none','alpha':.9});bx.plot([0,100],[0,100],ls='--',color='#999999',lw=.7);style(bx)
cx.set_title('C  Top-decile membership',loc='left',fontweight='bold',fontsize=8)
cx.bar([0,1,2],[177,354,177],color=[M,'#009E73',R],hatch=['///','xx','...'],edgecolor='#555555',lw=.6);cx.set_xticks([0,1,2],['M only','Shared','R only'],rotation=35,ha='right');cx.set_ylabel('Participants');cx.set_ylim(0,440)
for j,n in enumerate([177,354,177]):cx.text(j,n+12,str(n),ha='center',fontweight='bold')
cx.text(.5,.97,'531 per target\n354/531 shared\n66.7% overlap',transform=cx.transAxes,ha='center',va='top',fontsize=7.5);style(cx);save(f,4,179)
f=fig(166);gs=f.add_gridspec(3,2,height_ratios=[1.2,1.2,1]);ax=f.add_subplot(gs[0,:]);bx=f.add_subplot(gs[1,0]);cx=f.add_subplot(gs[1,1]);dx=f.add_subplot(gs[2,:])
for axis,metric,title,ideal in [(ax,'AUROC','A  Discrimination',None),(bx,'calibration_intercept','B  Calibration intercept',0),(cx,'calibration_slope','Calibration slope',1)]:
 for y,(c,t) in enumerate([(c,t) for c in ['ELSA','HRS'] for t in ['M','R']]):
  r=X[(X.dataset==c)&(X.target==t)&(X.metric==metric)].iloc[0];co=M if t=='M' else R;axis.plot([r.CI95_low,r.CI95_high],[y,y],color=co,lw=1.2);axis.plot(r.value,y,'o' if t=='M' else 's',color=co,ms=4)
 axis.set_yticks(range(4),['ELSA M','ELSA R','HRS M','HRS R']);axis.invert_yaxis();axis.set_title(title,loc='left',fontweight='bold');style(axis)
 if ideal is not None:axis.axvline(ideal,color='#777777',lw=.8,ls='--')
dx.axis('off');dx.set_title('C  Transport boundaries',loc='left',fontweight='bold');dx.text(.01,.82,'CHARLS: ~2 years\nELSA / HRS: ~4 years',va='top');dx.text(.43,.82,'BASE: portable mapping\nEducation: qualified mapping\nContact / FULL: not defensibly mapped',va='top');dx.text(.43,.08,'NOT MAPPABLE ≠ MODEL FAILED',fontweight='bold',fontsize=8);save(f,5,166)
print('Produced five figures; new scientific analyses = 0')
