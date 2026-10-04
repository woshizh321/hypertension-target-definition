"""Locked paired-label prediction and full-pipeline paired cluster bootstrap."""
from prod01_common import *
import warnings,time,joblib,copy
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.base import clone
from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss,log_loss
from scipy.special import logit
from scipy.stats import spearmanr,rankdata
import statsmodels.api as sm
warnings.filterwarnings('ignore',category=FutureWarning)
L=start(__file__);blocks={'BASE':[],'BASE_SES':['education'],'BASE_ACCESS':['access'],'FULL':['education','access']};bootn=200
D={ds:data(ds).loc[lambda x:x.aim3_common].copy().reset_index(drop=True) for ds in ['CHARLS','ELSA','HRS']};train=D['CHARLS']
assert [len(D[d]) for d in ['CHARLS','ELSA','HRS']]==[5303,2075,1619]
QC=[];folds=[];bootlog=[]

def Xframe(d):
 x=d[['age','sbp','dbp','education','access']].copy();x['sex']=np.select([d.female.eq(0),d.female.eq(1)],['MALE','FEMALE'],default='UNOBSERVED');return x

def template(block):
 categorical=['sex']+blocks[block];levels={'sex':['MALE','FEMALE','UNOBSERVED'],'education':['LOW','HIGH','UNOBSERVED'],'access':['NO_CONTACT','CONTACT','UNOBSERVED']}
 pre=ColumnTransformer([('num',Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]),['age','sbp','dbp']),('cat',OneHotEncoder(categories=[levels[v] for v in categorical],drop='first',handle_unknown='error',sparse_output=False),categorical)],sparse_threshold=0)
 return Pipeline([('preprocess',pre),('model',LogisticRegression(C=1.0,penalty='l2',solver='lbfgs',max_iter=3000,random_state=20261002))])

def pairedfit(a,block):
 x=Xframe(a);pair={}
 for target in ['M','R']:
  pipe=template(block);pipe.fit(x,a[target+'1'].astype(int));assert pipe.named_steps['model'].n_iter_.max()<3000;pair[target]=pipe
 A=pair['M'].named_steps['preprocess'].transform(x.iloc[:min(12,len(x))]);B=pair['R'].named_steps['preprocess'].transform(x.iloc[:min(12,len(x))]);assert np.allclose(A,B),'Target-specific preprocessing'
 return pair

def pairedCV(a,record=False):
 n=len(a);joint=(a.M1.astype(int)*2+a.R1.astype(int)).to_numpy();groups=a.cluster.astype(str).to_numpy();x=Xframe(a);pred={b:{t:np.zeros(n) for t in ['M','R']} for b in blocks};cnt=np.zeros(n,int)
 for repeat,seed in enumerate([20261002,20261003]):
  cv=StratifiedGroupKFold(5,shuffle=True,random_state=seed)
  for fold,(tr,te) in enumerate(cv.split(x,joint,groups)):
   assert not set(groups[tr])&set(groups[te]);assert not set(a.id.iloc[tr])&set(a.id.iloc[te]),'Repeated person leakage'
   for block in blocks:
    pp=pairedfit(a.iloc[tr],block)
    for target in ['M','R']:pred[block][target][te]+=pp[target].predict_proba(x.iloc[te])[:,1]
   cnt[te]+=1
   if record:
    for i in te:folds.append(dict(id=str(a.id.iloc[i]),cluster=str(a.cluster.iloc[i]),repeat=repeat,fold=fold))
    QC.append(dict(dataset='CHARLS',check='SAME_PERSON_TARGET_FOLDS_TRAIN_ONLY_TRANSFORM',repeat=repeat,fold=fold,N_train=len(tr),N_test=len(te),overlap_person_N=0,overlap_group_N=0,status='PASS'))
 assert np.all(cnt==2)
 for block in blocks:
  for target in ['M','R']:pred[block][target]/=2;assert np.isfinite(pred[block][target]).all()
 return pred

metricnames=['AUROC','AUPRC','Brier','log_loss','calibration_intercept','calibration_slope']
def met(y,p):
 y=np.asarray(y,dtype=int);p=np.clip(np.asarray(p,float),1e-9,1-1e-9)
 if len(np.unique(y))<2:return {k:np.nan for k in metricnames}
 lp=logit(p)
 try:ci=sm.GLM(y,np.ones((len(y),1)),family=sm.families.Binomial(),offset=lp).fit(maxiter=60,tol=1e-8).params[0];cs=sm.GLM(y,sm.add_constant(lp),family=sm.families.Binomial()).fit(maxiter=60,tol=1e-8).params[1]
 except Exception:ci=cs=np.nan
 return dict(AUROC=float(roc_auc_score(y,p)),AUPRC=float(average_precision_score(y,p)),Brier=float(brier_score_loss(y,p)),log_loss=float(log_loss(y,p,labels=[0,1])),calibration_intercept=float(ci),calibration_slope=float(cs))

def scalarrecords(a,preds,dataset,domain):
 rows=[]
 for block,pr in preds.items():
  for target in ['M','R']:
   y=a[target+'1'].to_numpy(int);m=met(y,pr[target])
   for metric,value in m.items():rows.append(dict(dataset=dataset,domain=domain,block=block,target=target,metric=metric,value=value,N=len(a),events=int(y.sum()),non_events=int(len(y)-y.sum())))
 return rows

def increments(a,preds,dataset,domain):
 mm={b:{t:met(a[t+'1'],preds[b][t]) for t in ['M','R']} for b in preds};out=[]
 for block in preds:
  if block=='BASE':continue
  for metric in ['AUROC','AUPRC','Brier','log_loss']:
   gains={t:(mm['BASE'][t][metric]-mm[block][t][metric] if metric in ['Brier','log_loss'] else mm[block][t][metric]-mm['BASE'][t][metric]) for t in ['M','R']}
   for t in ['M','R']:out.append(dict(dataset=dataset,domain=domain,block=block,target=t,metric=metric,gain=gains[t],N=len(a),contrast='NewminusBASE forAUROC/AP;BASEminusnew forlosses'))
   out.append(dict(dataset=dataset,domain=domain,block=block,target='R_MINUS_M',metric=metric,gain=gains['R']-gains['M'],N=len(a),contrast='Paired difference of within-target gain; not difficulty-free causal effect'))
 return out

def highmask(p,a,fraction):
 n=len(a);k=int(np.ceil(fraction*n));ix=np.lexsort((np.arange(n),a.id.astype(str).to_numpy(),-np.asarray(p)));h=np.zeros(n,bool);h[ix[:k]]=True;return h

def ranks(a,preds,dataset,domain,block):
 pm=preds[block]['M'];pr=preds[block]['R'];move=rankdata(pr,method='average')/len(a)-rankdata(pm,method='average')/len(a);rho=spearmanr(pm,pr).statistic;rows=[dict(dataset=dataset,domain=domain,block=block,metric='Spearman',fraction='ALL',value=float(rho),N=len(a))]
 for q in [.05,.25,.5,.75,.95]:rows.append(dict(dataset=dataset,domain=domain,block=block,metric='rank_percentile_movement_q'+str(q),fraction='ALL',value=float(np.quantile(move,q)),N=len(a)))
 for f in [.1,.2]:
  hm=highmask(pm,a,f);hr=highmask(pr,a,f);inter=int((hm&hr).sum());k=int(hm.sum());counts={'concordant_high_N':inter,'M_high_only_N':int((hm&~hr).sum()),'R_high_only_N':int((hr&~hm).sum()),'concordant_low_N':int((~hm&~hr).sum()),'overlap_fraction':inter/k,'overlap_N':inter,'top_N':k}
  assert sum(counts[x] for x in ['concordant_high_N','M_high_only_N','R_high_only_N','concordant_low_N'])==len(a)
  for metric,value in counts.items():rows.append(dict(dataset=dataset,domain=domain,block=block,metric=metric,fraction=f,value=float(value),N=len(a)))
 return rows

bins=np.array([0,.02,.05,.1,.2,.4,1])
def calibration(a,preds,dataset,domain):
 out=[]
 for block,pr in preds.items():
  for target in ['M','R']:
   p=pr[target];y=a[target+'1'].to_numpy();ix=np.clip(np.searchsorted(bins,p,side='right')-1,0,len(bins)-2)
   for b in range(len(bins)-1):
    m=ix==b;n=int(m.sum());out.append(dict(dataset=dataset,domain=domain,block=block,target=target,bin=b,bin_low=bins[b],bin_high=bins[b+1],N=n,events=int(y[m].sum()),mean_predicted=float(p[m].mean()) if n else np.nan,observed_fraction=float(y[m].mean()) if n else np.nan))
 return out

def subgroups(a,preds,dataset,domain,block):
 out=[]
 for group,mask in [('SEX_MALE',a.female.eq(0)),('SEX_FEMALE',a.female.eq(1)),('AGE_LT65',a.age.lt(65)),('AGE_GE65',a.age.ge(65))]:
  ix=np.flatnonzero(mask.to_numpy());n=len(ix)
  for target in ['M','R']:
   y=a[target+'1'].to_numpy(int)[ix];e=int(y.sum());p=preds[block][target][ix];m=met(y,p) if e>=20 and n-e>=20 else {k:np.nan for k in metricnames};hm=highmask(preds[block][target],a,.1)[ix];m['sensitivity_at_global_top10']=float(hm[y==1].mean()) if e else np.nan
   for metric,value in m.items():out.append(dict(dataset=dataset,domain=domain,block=block,target=target,subgroup=group,metric=metric,value=value,N=n,events=e,non_events=n-e,precision_status='ESTIMABLE_SECONDARY' if e>=20 and n-e>=20 else 'DESCRIPTIVE_LOW_SUPPORT_NO_PRECISION_CLAIM'))
 return out

# Bootstrap resampling preserves all members of a source cluster; repeat copies stay in the same CV fold.
def draw(a,rng,ds):
 pieces=[]
 if ds=='HRS':
  for _,st in a.groupby('stratum',dropna=False):
   gs=list(st.cluster.astype(str).unique());sample=rng.choice(gs,len(gs),replace=True)
   for g in sample:pieces.append(st[st.cluster.astype(str).eq(g)])
 else:
  gs=list(a.cluster.astype(str).unique());sample=rng.choice(gs,len(gs),replace=True)
  for g in sample:pieces.append(a[a.cluster.astype(str).eq(g)])
 return pd.concat(pieces,ignore_index=True)

point=pairedCV(train,True);main=scalarrecords(train,point,'CHARLS','INTERNAL_COMMON_PAIR');inc=increments(train,point,'CHARLS','INTERNAL_COMMON_PAIR');ranking=ranks(train,point,'CHARLS','INTERNAL_COMMON_PAIR','FULL');cal=calibration(train,point,'CHARLS','INTERNAL_COMMON_PAIR');sub=subgroups(train,point,'CHARLS','INTERNAL_COMMON_PAIR','FULL')
# Freeze CHARLS-only full-data models, never refit in external cohorts.
final={b:pairedfit(train,b) for b in blocks};joblib.dump(final,O/'03_aim3/PROD01_CHARLS_FROZEN_MODELS.joblib',compress=3)
external={};extmain=[];extinc=[];extrank=[];extcal=[];extsub=[]
for ds in ['ELSA','HRS']:
 a=D[ds];x=Xframe(a);base={'BASE':{t:final['BASE'][t].predict_proba(x)[:,1] for t in ['M','R']}}
 extmain+=scalarrecords(a,base,ds,'EXTERNAL_FULL_COMMON_PAIR');extcal+=calibration(a,base,ds,'EXTERNAL_FULL_COMMON_PAIR')
 eligible=a.education.isin(['LOW','HIGH']);z=a[eligible].reset_index(drop=True);x=Xframe(z);pp={b:{t:final[b][t].predict_proba(x)[:,1] for t in ['M','R']} for b in ['BASE','BASE_SES']};external[ds]=(z,pp)
 extmain+=scalarrecords(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR');extinc+=increments(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR');extrank+=ranks(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR','BASE_SES');extcal+=calibration(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR');extsub+=subgroups(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR','BASE_SES')
 pd.DataFrame(dict(id=z.id,M1=z.M1,R1=z.R1,BASE_M=pp['BASE']['M'],BASE_R=pp['BASE']['R'],BASE_SES_M=pp['BASE_SES']['M'],BASE_SES_R=pp['BASE_SES']['R'])).to_parquet(O/f'03_aim3/PROD01_EXTERNAL_PREDICTIONS_{ds}.parquet',index=False)
print('Primary paired CV and unchanged external application finished; starting full-pipeline bootstrap',flush=True)
for ds,pp in [('CHARLS',point)]:
 out=train[['id','cluster','M1','R1']].copy()
 for b in blocks:
  for t in ['M','R']:out[b+'_'+t]=pp[b][t]
 out.to_parquet(O/'03_aim3/PROD01_CHARLS_OOF_PREDICTIONS.parquet',index=False)
save(folds,'03_aim3/PROD01_PAIRED_FOLD_ASSIGNMENTS.csv')
# Point values are retained before bootstrap; interruption can resume using recorded checkpoint, not change the lock.
Bmain=[];Binc=[];Brank=[];Bcal=[];Bsub=[];Bext=[];Bextinc=[];Bextrank=[];Bextcal=[];Bextsub=[]
clock0=time.monotonic();rng=np.random.default_rng(20261004)
for b in range(bootn):
 a=draw(train,rng,'CHARLS');pp=pairedCV(a);vals=[scalarrecords(a,pp,'CHARLS','INTERNAL_COMMON_PAIR'),increments(a,pp,'CHARLS','INTERNAL_COMMON_PAIR'),ranks(a,pp,'CHARLS','INTERNAL_COMMON_PAIR','FULL'),calibration(a,pp,'CHARLS','INTERNAL_COMMON_PAIR'),subgroups(a,pp,'CHARLS','INTERNAL_COMMON_PAIR','FULL')]
 for dest,rr in zip([Bmain,Binc,Brank,Bcal,Bsub],vals):
  for r in rr:r['bootstrap']=b;dest.append(r)
 # Full-data bootstrap models for external variability are CHARLS-only.
 bb={block:pairedfit(a,block) for block in ['BASE','BASE_SES']}
 for ds in ['ELSA','HRS']:
  d=draw(D[ds],rng,ds);x=Xframe(d);bp={'BASE':{t:bb['BASE'][t].predict_proba(x)[:,1] for t in ['M','R']}};rr=scalarrecords(d,bp,ds,'EXTERNAL_FULL_COMMON_PAIR')
  for r in rr:r['bootstrap']=b;Bext.append(r)
  rr=calibration(d,bp,ds,'EXTERNAL_FULL_COMMON_PAIR')
  for r in rr:r['bootstrap']=b;Bextcal.append(r)
  z=d[d.education.isin(['LOW','HIGH'])].reset_index(drop=True);x=Xframe(z);bp={block:{t:bb[block][t].predict_proba(x)[:,1] for t in ['M','R']} for block in ['BASE','BASE_SES']}
  vals=[scalarrecords(z,bp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR'),increments(z,bp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR'),ranks(z,bp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR','BASE_SES'),calibration(z,bp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR'),subgroups(z,bp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR','BASE_SES')]
  for dest,rr in zip([Bext,Bextinc,Bextrank,Bextcal,Bextsub],vals):
   for r in rr:r['bootstrap']=b;dest.append(r)
 bootlog.append(dict(bootstrap=b,N_CHARLS=len(a),events_M=int(a.M1.sum()),events_R=int(a.R1.sum()),resampled_cluster_hash=hashlib.sha256('\n'.join(a.cluster.astype(str)).encode()).hexdigest(),full_pipeline_refit=True,status='PASS'))
 if (b+1)%10==0:
  print('Full pipeline bootstrap',b+1,'/',bootn,'elapsed_seconds',round(time.monotonic()-clock0),flush=True)
  (O/'10_manifests/PROD01_PREDICTION_PROGRESS.json').write_text(json.dumps(dict(completed_bootstrap=b+1,total=bootn,elapsed_seconds=time.monotonic()-clock0),indent=2))
 # Full deterministic RNG/model output checkpoint only; not a source/result-selection mechanism.
 if (b+1)%25==0:joblib.dump(dict(completed=b+1,RNG=rng.bit_generator.state,Bmain=Bmain,Binc=Binc,Brank=Brank,Bcal=Bcal,Bsub=Bsub,Bext=Bext,Bextinc=Bextinc,Bextrank=Bextrank,Bextcal=Bextcal,Bextsub=Bextsub,bootlog=bootlog),O/'03_aim3/PROD01_BOOTSTRAP_CHECKPOINT.joblib',compress=3)

# Attach 95% paired full-procedure percentile intervals using identical keys.
def attach(points,boots,keys,value='value'):
 p=pd.DataFrame(points);b=pd.DataFrame(boots);stats=b.groupby(keys,dropna=False)[value].agg(CI95_low=lambda x:x.quantile(.025),CI95_high=lambda x:x.quantile(.975),valid_bootstrap_N='count').reset_index();o=p.merge(stats,on=keys,how='left',validate='one_to_one');o['uncertainty']='200 full-pipeline paired cluster-bootstrap percentile95%; source conditional domain';return o
keys=['dataset','domain','block','target','metric'];kRank=['dataset','domain','block','metric','fraction'];kCal=['dataset','domain','block','target','bin'];kSub=['dataset','domain','block','target','subgroup','metric']
internal=attach(main,Bmain,keys);eperformance=attach(extmain,Bext,keys);increments_df=attach(inc+extinc,Binc+Bextinc,keys,'gain');rank_df=attach(ranking+extrank,Brank+Bextrank,kRank);cal_df=attach(cal+extcal,Bcal+Bextcal,kCal,'observed_fraction');sub_df=attach(sub+extsub,Bsub+Bextsub,kSub)
internal.to_csv(O/'03_aim3/PROD01_AIM3_INTERNAL_PERFORMANCE.csv',index=False);eperformance['transport_boundary']='UNCHANGED_CHARLS2YEAR_MODELS_VS_EXTERNAL4YEAR_WAVE_TARGETS_NOT_VALIDATED_2YEAR_TRANSPORT';eperformance.to_csv(O/'03_aim3/PROD01_AIM3_EXTERNAL_TRANSPORT.csv',index=False);increments_df.to_csv(O/'03_aim3/PROD01_AIM3_BLOCK_INCREMENT.csv',index=False);rank_df.to_csv(O/'03_aim3/PROD01_AIM3_RISK_RANK_COMPARISON.csv',index=False);cal_df.to_csv(O/'03_aim3/PROD01_AIM3_CALIBRATION.csv',index=False);sub_df.to_csv(O/'03_aim3/PROD01_AIM3_SUBGROUP_PERFORMANCE.csv',index=False)
# Preserve all bootstrap scalar outputs for audit.
for name,rows in [('PERFORMANCE',Bmain+Bext),('INCREMENTS',Binc+Bextinc),('RANKS',Brank+Bextrank),('CALIBRATION',Bcal+Bextcal),('SUBGROUPS',Bsub+Bextsub)]:pd.DataFrame(rows).to_parquet(O/f'03_aim3/PROD01_BOOTSTRAP_{name}.parquet',index=False)
save(bootlog,'10_manifests/PROD01_PREDICTION_BOOTSTRAP_QC.csv');save(QC,'10_manifests/PROD01_PREDICTION_FOLD_QC.csv')
flow=[];spec=[]
for ds in ['CHARLS','ELSA','HRS']:
 d=data(ds);z=D[ds];flow.append(dict(dataset=ds,baseline_N=int(d.aim3_base.sum()),common_pair_N=len(z),Y_M_events=int(z.M1.sum()),Y_R_events=int(z.R1.sum()),education_mappable_N=int(z.education.isin(['LOW','HIGH']).sum()),no_outcome_imputation=True,source='Frozen SAP/PF01 labels'))
 for block in blocks:
  spec.append(dict(dataset=ds,block=block,model_family='FIXED_C1_RIDGE_LOGISTIC',training='CHARLS_ONLY',predictors=','.join(L['blocks'][block]),pair_same_people=True,status='INTERNAL_PAIRED_CV' if ds=='CHARLS' else 'UNCHANGED_HORIZON_QUALIFIED_TRANSPORT' if block in ['BASE','BASE_SES'] else 'NOT_ESTIMABLE_SOURCE_ACCESS_CONSTRUCT_MAPPING',reason='Exact access/contact windows and ELSA GP-ease differ; no forced mapping' if ds!='CHARLS' and block in ['BASE_ACCESS','FULL'] else 'No external refit or recalibration'))
save(flow,'03_aim3/PROD01_AIM3_COHORT_FLOW.csv');save(spec,'03_aim3/PROD01_AIM3_MODEL_SPECIFICATIONS.csv')
# Locked complete-source-information sensitivity: identical target/domain/folds; no threshold or wave change.
cc=train[['age','female','sbp','dbp']].notna().all(axis=1)&train.education.isin(['LOW','HIGH'])&train.access.isin(['NO_CONTACT','CONTACT']);z=train[cc].reset_index(drop=True);pp=pairedCV(z);sens=scalarrecords(z,pp,'CHARLS','FULLY_OBSERVED_SOURCE_INFORMATION_SENSITIVITY')+increments(z,pp,'CHARLS','FULLY_OBSERVED_SOURCE_INFORMATION_SENSITIVITY');save(sens,'03_aim3/PROD01_AIM3_MISSINGNESS_SENSITIVITY.csv')
save([dict(model='NONLINEAR_COMPARATOR',status='NOT_RUN_NO_LOCKED_SAP_SUPPORT',reason='Parsimonious primary retained; no algorithm zoo or result rescue'),dict(model='UNPENALIZED_ALTERNATIVE',status='NOT_RUN_NOT_PRESPECIFIED',reason='Fixed ridge family unchanged')],'03_aim3/PROD01_AIM3_SECONDARY_MODEL.csv')
print('AIM3 finished; bootstrap intervals from full refitting',flush=True)
print(internal[internal.metric.isin(['AUROC','Brier'])][['block','target','metric','value','CI95_low','CI95_high']].to_string(index=False))
