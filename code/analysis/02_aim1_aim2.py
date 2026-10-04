from public_paths import PROJECT_ROOT, source_path
"""Locked Aim1 source-preserving estimates and Aim2 cohort-specific associations."""
from prod01_common import *
import statsmodels.api as sm
from scipy.special import expit,logit
from scipy.stats import t
from statsmodels.stats.multitest import multipletests
import zipfile
L=start(__file__)
# Existing label computations are numerical authority; no rebuilding of BP/R/T infrastructure.
r=pd.read_csv(P/'02_cross_sectional/PF01_MR_FOUR_STATE_COUNTS.csv');r['unresolved_MR_N']=r.N_eligible_source_population-r.N_valid_MR;r['unresolved_MR_fraction']=r.unresolved_MR_N/r.N_eligible_source_population
r['evidence_boundary']='Source eligible complete-label distribution; no diagnostic-error interpretation';r.to_csv(O/'01_aim1/PROD01_AIM1_STATE_TABLE.csv',index=False)
w=pd.read_csv(P/'02_cross_sectional/PF01_SURVEY_WEIGHTED_STATE_ESTIMATES.csv');w=w[w.family.eq('MR')].copy();w['production_status']='PF01_AUTHORITY_REUSED_NO_NEW_SURVEY_ASSUMPTION';w.to_csv(O/'01_aim1/PROD01_AIM1_WEIGHTED_ESTIMATES.csv',index=False)
r.merge(w[['dataset','wave','state','weighted_percentage','CI95_low_percentage','CI95_high_percentage','estimate_status']],on=['dataset','wave','state'],validate='one_to_one').to_csv(O/'01_aim1/PROD01_AIM1_FIGURE_DATA.csv',index=False)
flows=[];est=[];risks=[];coef=[];sens=[];fitqc=[]
with zipfile.ZipFile(str(source_path('hrs_tracker'))).open('trk2022tr_r.csv') as f:design=pd.read_csv(f,usecols=lambda v:v.upper() in ['STRATUM','SECU','OPMWGTR'],dtype=str)
design.columns=design.columns.str.upper();design=design[pd.to_numeric(design.OPMWGTR,errors='coerce').gt(0)].dropna(subset=['STRATUM','SECU'])[['STRATUM','SECU']].drop_duplicates();design['cluster']=design.STRATUM+'_'+design.SECU
assert design.cluster.is_unique

def prepare(z,ds,terms,common=False):
 keep=z[['age','female','sbp','dbp']].notna().all(axis=1)
 if 'education_high' in terms or common:keep &= z.education.isin(['LOW','HIGH'])
 ac=['EASY','DIFFICULT'] if ds=='ELSA' else ['NO_CONTACT','CONTACT']
 if 'access_positive' in terms or common:keep &= z.access.isin(ac)
 if 'barrier' in terms:keep &= z.barrier.notna()
 d=z[keep].copy().reset_index(drop=True);d['education_high']=d.education.eq('HIGH').astype(float);d['access_positive']=d.access.eq('DIFFICULT' if ds=='ELSA' else 'CONTACT').astype(float)
 X=pd.DataFrame(dict(intercept=np.ones(len(d)),age=d.age/10,female=d.female,sbp=d.sbp/10,dbp=d.dbp/10))
 for v in terms:X[v]=d[v].astype(float)
 return d,X

def robust_cov(d,X,y,p,ds):
 A=X.to_numpy(float);bread=np.linalg.inv((A.T*(p*(1-p)))@A);scores=A*(y-p)[:,None];cols=list(X.columns)
 u=pd.DataFrame(scores,columns=cols);u['cluster']=d.cluster.astype(str).to_numpy();U=u.groupby('cluster')[cols].sum()
 if ds=='HRS':
  assert set(U.index)<=set(design.cluster),'Model PSUs absent from frozen baseline design universe'
  allu=design.merge(U.reset_index(),on='cluster',how='left',validate='one_to_one').fillna({c:0 for c in cols});meat=np.zeros((A.shape[1],A.shape[1]));df=0
  for _,g in allu.groupby('STRATUM'):
   m=len(g);assert m>1,'Singleton in full source design';a=g[cols].to_numpy();a-=a.mean(axis=0);meat+=m/(m-1)*(a.T@a);df+=m-1
  method='STRATIFIED_PSU_SANDWICH_UNWEIGHTED_SAMPLE_CONDITIONAL_POINT'
 else:
  G=len(U);assert G>1;meat=U.to_numpy().T@U.to_numpy()*G/(G-1)*(len(d)-1)/(len(d)-A.shape[1]);df=G-1;method='COMMUNITY_CLUSTER_SANDWICH_SAMPLE_CONDITIONAL' if ds=='CHARLS' else 'HOUSEHOLD_CLUSTER_SANDWICH_SAMPLE_CONDITIONAL'
 V=bread@meat@bread;assert np.isfinite(V).all();return (V+V.T)/2,df,method,len(U)

def fit(z,ds,model,terms,kind='PRIMARY',common=False):
 d,X=prepare(z,ds,terms,common);y=d.R1.to_numpy(float);N=len(d);e=int(y.sum());k=X.shape[1]
 assert d.id.is_unique and d.cluster.notna().all();assert N>k and e>0 and e<N
 res=sm.GLM(y,X,family=sm.families.Binomial()).fit(maxiter=150,tol=1e-9);assert res.converged;beta=res.params.to_numpy();p=expit(X.to_numpy()@beta);V,df,method,G=robust_cov(d,X,y,p,ds);crit=t.ppf(.975,df)
 assert np.linalg.matrix_rank(X)==k
 base=dict(dataset=ds,model=model,analysis_role=kind,N=N,events=e,non_events=N-e,df_parameters=k-1,cluster_N=G,uncertainty_df=df,variance=method,estimand='OBSERVED_VALID_FOLLOWUP_AND_MODELED_PREDICTOR_DOMAIN_SAMPLE_CONDITIONAL',missingness='Complete core and actual modeled exposure; routed missing not imputed')
 fitqc.append(dict(**base,check='CONVERGENCE_RANK_GRAIN',converged=True,design_rank=k,max_abs_score=float(np.abs(X.to_numpy().T@(y-p)).max()),status='PASS'))
 flows.append(dict(**base,baseline_risk_N=int(data(ds).aim2_base.sum()),valid_R1_before_predictors=len(z),predictor_exclusion_N=len(z)-N))
 cr=[];rr=[];pr=[]
 for j,c in enumerate(X.columns):
  se=np.sqrt(max(V[j,j],0));ci=beta[j]+np.array([-1,1])*crit*se
  cr.append(dict(**base,term=c,log_odds_coefficient=float(beta[j]),SE=float(se),CI95_low_log_odds=float(ci[0]),CI95_high_log_odds=float(ci[1]),odds_ratio_secondary=float(np.exp(beta[j])),OR_CI95_low=float(np.exp(ci[0])),OR_CI95_high=float(np.exp(ci[1])),unit='per10years' if c=='age' else 'per10mmHg' if c in ['sbp','dbp'] else 'binary/reference'))
 for c in terms:
  X0=X.copy();X1=X.copy();X0[c]=0.;X1[c]=1.;A0=X0.to_numpy();A1=X1.to_numpy();p0=expit(A0@beta);p1=expit(A1@beta);r0=float(p0.mean());r1=float(p1.mean());g0=(A0*(p0*(1-p0))[:,None]).mean(axis=0);g1=(A1*(p1*(1-p1))[:,None]).mean(axis=0);g=g1-g0;rd=r1-r0;serd=np.sqrt(max(g@V@g,0));lr=np.log(r1/r0);gr=g1/r1-g0/r0;selr=np.sqrt(max(gr@V@gr,0));pv=float(2*t.sf(abs(rd/serd),df)) if serd>0 else np.nan
  row=dict(**base,exposure=c,contrast='HIGH_vs_LOW' if c=='education_high' else 'DIFFICULT_vs_EASY' if ds=='ELSA' and c=='access_positive' else 'CONTACT_vs_NO_CONTACT' if c=='access_positive' else 'AFFORDABILITY_BARRIER_YES_vs_NO',standardized_risk_reference=r0,standardized_risk_exposed=r1,risk_difference=rd,RD_CI95_low=float(rd-crit*serd),RD_CI95_high=float(rd+crit*serd),risk_ratio=float(np.exp(lr)),RR_CI95_low=float(np.exp(lr-crit*selr)),RR_CI95_high=float(np.exp(lr+crit*selr)),p_RD_secondary=pv,causal=False)
  pr.append(row)
  for level,r,g in [(0,r0,g0),(1,r1,g1)]:
   se=np.sqrt(max(g@V@g,0));cise=se/(r*(1-r));ci=expit(logit(r)+np.array([-1,1])*crit*cise);rr.append(dict(**base,exposure=c,level=level,standardized_probability=r,CI95_low=float(ci[0]),CI95_high=float(ci[1]),contrast=row['contrast']))
 if not terms:
  r=float(p.mean());g=(X.to_numpy()*(p*(1-p))[:,None]).mean(0);se=np.sqrt(max(g@V@g,0));ci=expit(logit(r)+np.array([-1,1])*crit*se/(r*(1-r)));rr.append(dict(**base,exposure='NONE_CORE',level='observed',standardized_probability=r,CI95_low=float(ci[0]),CI95_high=float(ci[1]),contrast='Observed cohort reference'))
 return pr,rr,cr

for ds in ['CHARLS','ELSA','HRS']:
 d=data(ds);z=d[d.aim2_observed].copy()
 for model,terms in [('CORE',[]),('BASE_SES',['education_high']),('BASE_ACCESS',['access_positive']),('FULL',['education_high','access_positive'])]:
  pr,rr,cr=fit(z,ds,model,terms,'SECONDARY_CONDITIONAL_COMPONENTS' if model=='FULL' else 'PRIMARY');est+=pr;risks+=rr;coef+=cr
  if terms:
   sp,_,_=fit(z,ds,model,terms,'COMMON_COMPLETE_CASE_SENSITIVITY',True);sens+=sp
 if ds=='HRS':
  sp,_,_=fit(z,ds,'CORE_PLUS_AFFORDABILITY',['barrier'],'PRESPECIFIED_HRS_SECONDARY_COMPONENT');sens+=sp
 print('AIM2 completed',ds,'models and marginal standardization',flush=True)
res=pd.DataFrame(est);primary=res[res.model.isin(['BASE_SES','BASE_ACCESS'])].index;res['BH_FDR_q_secondary']=np.nan;res.loc[primary,'BH_FDR_q_secondary']=multipletests(res.loc[primary,'p_RD_secondary'],method='fdr_bh')[1];res.to_csv(O/'02_aim2/PROD01_AIM2_PRIMARY_ESTIMATES.csv',index=False);res.to_csv(O/'02_aim2/PROD01_AIM2_DOMAIN_RESULTS.csv',index=False)
pd.DataFrame(risks).to_csv(O/'02_aim2/PROD01_AIM2_STANDARDIZED_RISKS.csv',index=False);pd.DataFrame(coef).to_csv(O/'02_aim2/PROD01_AIM2_REGRESSION_TECHNICAL.csv',index=False);pd.DataFrame(flows).to_csv(O/'02_aim2/PROD01_AIM2_COHORT_FLOW.csv',index=False);pd.DataFrame(sens).to_csv(O/'02_aim2/PROD01_AIM2_SENSITIVITY_RESULTS.csv',index=False);pd.DataFrame(fitqc).to_csv(O/'10_manifests/PROD01_AIM2_NUMERICAL_QC.csv',index=False)
rep=res[res.model.isin(['BASE_SES','BASE_ACCESS'])].copy();rep['direction']=np.where(rep.risk_difference.gt(0),'POSITIVE','NEGATIVE');rep['CI95_excludes_zero']=(rep.RD_CI95_low.gt(0)|rep.RD_CI95_high.lt(0));rep['comparison_boundary']=np.where(rep.exposure.eq('education_high'),'Qualified upper-secondary/attained-education construct','Cohort-specific contact vs GP-accessibility; not exact measurement equivalence');rep.to_csv(O/'02_aim2/PROD01_AIM2_REPLICATION_MATRIX.csv',index=False)
tc=pd.read_csv(S/'03_events/SAP01_T_CONTEXT_COUNTS.csv');tc=tc[tc.aim.eq('AIM2')];tc.to_csv(O/'02_aim2/PROD01_AIM2_T_CONTEXT.csv',index=False)
print(res[res.model.isin(['BASE_SES','BASE_ACCESS'])][['dataset','model','N','risk_difference','RD_CI95_low','RD_CI95_high']].to_string(index=False))
