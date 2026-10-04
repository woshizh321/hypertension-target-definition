from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import argparse
ap=argparse.ArgumentParser(description='Display frozen calibration bins without estimation')
ap.add_argument('--source',type=Path,required=True,help='Frozen PROD01_AIM3_CALIBRATION.csv')
ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();P=args.source;O=args.output;O.mkdir(parents=True,exist_ok=True)
d=pd.read_csv(P);groups=list(d.groupby(['dataset','domain','block'],sort=False));plt.rcParams.update({'font.size':7,'font.family':'DejaVu Sans','axes.linewidth':.6,'pdf.fonttype':42})
f,axs=plt.subplots(5,2,figsize=(170/25.4,230/25.4),layout='constrained')
for ax,((study,domain,block),z) in zip(axs.flat,groups):
 for target in ['M','R']:
  t=z[z.target==target];co='#0072B2' if target=='M' else '#D55E00';ax.plot(t.mean_predicted,t.observed_fraction,color=co,marker='o' if target=='M' else 's',ms=2,lw=.8,label=target)
  for _,r in t.iterrows():ax.plot([r.mean_predicted,r.mean_predicted],[r.CI95_low,r.CI95_high],color=co,lw=.7)
 ax.plot([0,1],[0,1],ls='--',color='#aaaaaa',lw=.6);ax.set_xlim(0,.65);ax.set_ylim(0,.8);ax.set_title(f'{study} {block}\n'+('Education-mapped domain' if 'MAPPABLE' in domain else 'Original paired domain'),fontsize=7);ax.set_xlabel('Mean predicted');ax.set_ylabel('Observed fraction');ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False,fontsize=6)
f.savefig(O/'SUPPLEMENT_CALIBRATION.png',dpi=300);plt.close(f)
d.to_csv(O/'SUPPLEMENT_CALIBRATION_SOURCE.csv',index=False)
print('Ten original block/domain calibration displays; no new estimation')
