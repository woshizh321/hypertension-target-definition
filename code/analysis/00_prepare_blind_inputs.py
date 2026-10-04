from public_paths import PROJECT_ROOT, source_path
"""Pre-lock outcome-blind predictor preparation; no associations or models."""
from pathlib import Path
import pandas as pd,numpy as np,json,zipfile,io,re,hashlib,datetime
O=Path(str(PROJECT_ROOT / 'analysis/LABELBIAS_PROD01'));P=Path(str(PROJECT_ROOT / 'preflight/LABELBIAS_PF01'));S=Path(str(PROJECT_ROOT / 'protocol/LABELBIAS_SAP01_R1'))
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
for d in ['00_lock','01_aim1','02_aim2','03_aim3','04_integration','05_figures','06_tables','07_report','09_code','10_manifests','08_analytic_inputs']: (O/d).mkdir(parents=True,exist_ok=True)
assert not (O/'00_lock/PROD01_ANALYSIS_LOCK.json').exists(),'No preparation after lock without explicit repair artifact'
inputs=set();joins=[];profiles=[];source=[];frames={}
for root in [Path(str(PROJECT_ROOT / 'preflight')),Path(str(PROJECT_ROOT / 'governance')),Path(str(PROJECT_ROOT / 'protocol'))]:
 for f in root.rglob('*'):
  if f.is_file() and '__pycache__' not in str(f):inputs.add(str(f))
for root,name in [(P,'PF01'),(S,'SAP01')]:
 for r in pd.read_csv(root/f'10_manifests/{name}_OUTPUT_SHA256_MANIFEST.csv').to_dict('records'):assert sha(r['absolute_path'])==r['sha256']
L=json.loads((P/'00_lock/PF01_PROTOCOL_LOCK.json').read_text());matrix=pd.read_csv(S/'02_predictors/SAP01_PREDICTOR_DOMAIN_MATRIX.csv')
num=lambda s:pd.to_numeric(s,errors='coerce')
def merge(a,b,ds,tag):
 assert a.id.is_unique and b.id.is_unique and a.id.notna().all() and b.id.notna().all(),(ds,tag,'key error')
 n=len(a);z=a.merge(b,on='id',how='left',validate='one_to_one');assert len(z)==n
 joins.append(dict(dataset=ds,operation=tag,left_N=n,right_N=len(b),post_N=len(z),duplicates=0,status='PASS'));return z

def readstata(p,fields):
 inputs.add(str(p));d=pd.read_stata(p,columns=fields,convert_categoricals=False,convert_missing=True);d['id']=d.ID.astype('string');return d.drop(columns='ID')
def hrs(module,fields):
 p=str(source_path('hrs_2014'));inputs.add(p)
 with zipfile.ZipFile(p) as z:
  st=zipfile.ZipFile(io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith('sta.zip')))));da=zipfile.ZipFile(io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith('da.zip')))))
  dc=next(n for n in st.namelist() if Path(n).stem.upper()==module and n.endswith('.dct'));text=st.read(dc).decode('latin1');spec={v:(int(a)-1,int(a)-1+int(c)) for a,t,v,c,l in re.findall(r'_column\((\d+)\)\s+(\w+)\s+(\w+)\s+%(\d+)(?:\.\d+)?[fgs]\s+"([^"]*)"',text)}
  data=next(n for n in da.namelist() if Path(n).stem.upper()==module);d=pd.read_fwf(io.BytesIO(da.read(data)),colspecs=[spec[v] for v in ['HHID','PN']+fields],names=['HHID','PN']+fields,dtype=str)
 d['id']=d.HHID.str.zfill(6)+d.PN.str.zfill(3);return d.drop(columns=['HHID','PN'])
for pair in L['primary_pairs']:
 ds=pair['dataset'];w0=pair['baseline'];w1=pair['followup']
 f0=P/f'01_label_contract/DERIVED_LABELS_{ds}_{w0}.parquet';f1=P/f'01_label_contract/DERIVED_LABELS_{ds}_{w1}.parquet';inputs.update([str(f0),str(f1)])
 b=pd.read_parquet(f0,columns=['id','eligible','M','R','T','proxy_status','mean_SBP_primary','mean_DBP_primary']);f=pd.read_parquet(f1,columns=['id','M','R','proxy_status']);b=b.rename(columns={'M':'M0','R':'R0','T':'T0','proxy_status':'proxy0','mean_SBP_primary':'sbp','mean_DBP_primary':'dbp'})
 pred=b[['id','sbp','dbp']].copy()
 if ds=='CHARLS':
  root=Path(str(source_path('charls_2013')));d=readstata(root/'Demographic_Background.dta',['ID','householdID','communityID','ba002_1','zba002_1','ba001_w2_1','ba000_w2_3','bd001','zbd001','bd001_w2_1','bd001_w2_2','bd001_w2_3','bd001_w2_4']);h=readstata(root/'Health_Status_and_Functioning.dta',['ID','xrgender']);a=readstata(root/'Health_Care_and_Insurance.dta',['ID','ed001'])
  raw=merge(merge(d,h,ds,'demographic_health'),a,ds,'demographic_access')
  y=num(raw.ba002_1);fy=num(raw.zba002_1);confirm=num(raw.ba001_w2_1).eq(1)
  raw['age']=2013-y.where(y.between(1850,2013),fy.where(confirm&fy.between(1850,2013)));raw['female']=num(raw.ba000_w2_3).map({1:0.,2:1.})
  # Both sex routes are SAP core; deterministic direct interviewer -> health recorded fallback, conflicts unknown.
  sex2=num(raw.xrgender).map({1:0.,2:1.});conflict=raw.female.notna()&sex2.notna()&raw.female.ne(sex2);raw['female']=raw.female.fillna(sex2);raw.loc[conflict,'female']=np.nan
  direct=num(raw.bd001).where(num(raw.bd001).between(1,11));change=num(raw.bd001_w2_4);corrected=num(raw.bd001_w2_3).where(num(raw.bd001_w2_3).between(1,11));fed=num(raw.zbd001).where(num(raw.bd001_w2_1).eq(1)&num(raw.bd001_w2_2).eq(2)&num(raw.zbd001).between(1,11));prior=corrected.combine_first(fed);current=change.where(change.between(1,11),prior.where(change.eq(12)));ed=direct.combine_first(current);raw['education']=np.select([ed.between(1,5),ed.between(6,11)],['LOW','HIGH'],default='UNOBSERVED')
  raw['access']=num(raw.ed001).map({1:'CONTACT',2:'NO_CONTACT'}).fillna('UNOBSERVED')
  raw['cluster']=raw.communityID.astype('string');raw['household']=raw.householdID.astype('string')
  meta=dict(age='2013 minus direct birthyear, or affirmative source-confirmed fed birthyear; approximate calendar-year age, not exact birthday age',education='Same SAP education construct: direct bd001 > explicit bd001_w2_4 update; no-change12 uses corrected bd001_w2_3 or confirmed zbd001 with adult-education exclusion flag2. Codes6-11HIGH,1-5LOW; unsupported skip remains UNOBSERVED',access='ed001 source last-month hospital/outpatient contact1yes2no; mediator candidate in upstream SES specification, exposure in contact model',cluster='Native communityID for sample-conditional cluster uncertainty/group splits, not asserted surveyPSU')
 elif ds=='ELSA':
  root=Path(str(source_path('elsa_wave4_predictors')));mp=next(root.glob('module=MAIN_INTERVIEW/*/data.parquet'));dp=next(root.glob('module=DERIVED/*/data.parquet'));inputs.update([str(mp),str(dp)])
  d=pd.read_parquet(mp,columns=['idauniq','idahhw4','indager','indsex','scedgp']);d['id']=num(d.idauniq).astype('Int64').astype('string');d=d.drop(columns='idauniq');e=pd.read_parquet(dp,columns=['idauniq','edqual']);e['id']=num(e.idauniq).astype('Int64').astype('string');e=e.drop(columns='idauniq');raw=merge(d,e,ds,'main_derived')
  ag=num(raw.indager);raw['age']=ag.where(ag.gt(0));raw.loc[ag.eq(-7),'age']=90.;raw['female']=num(raw.indsex).map({1:0.,2:1.})
  ed=num(raw.edqual);raw['education']=np.select([ed.isin([4,5,7]),ed.isin([1,2,3]),ed.eq(6)],['LOW','HIGH','FOREIGN_OTHER'],default='UNOBSERVED')
  ac=num(raw.scedgp);raw['access']=np.select([ac.isin([1,2]),ac.isin([3,4,5]),ac.eq(6)],['EASY','DIFFICULT','PREFERENCE_NOT_TO_GO'],default='UNOBSERVED')
  # No authoritative household public key found in selected source scope. Exact-person resampling only, qualified.
  raw['cluster']=num(raw.idahhw4).astype('Int64').astype('string');raw['household']=raw['cluster'];assert raw.cluster.notna().all(),'Missing authoritative baseline household key'
  meta=dict(age='indager positive age; source -7 top-coded90+ represented lowerbound90, sensitivity exclude collapsed records if separately needed',education='edqual1-3 upper-secondary+ HIGH;4/5/7 LOW;6 FOREIGN_OTHER distinct; negativecodes UNOBSERVED',access='scedgp1/2 EASY;3/4/5 DIFFICULT;6 preference distinct; negative routed/selfcompletion missing UNOBSERVED',cluster='Native idahhw4 baseline household grouping; sample-conditional cluster uncertainty, nationalPSU/strata unresolved')
 elif ds=='HRS':
  raw=merge(merge(merge(hrs('H14A_R',['OA019']),hrs('H14B_R',['OB014']),ds,'A_B'),hrs('H14N_R',['ON147','ON290']),ds,'A_B_N'),hrs('H14PR_R',['OZ216','OX060_R']),ds,'baseline_preload_education_sex_same_construct')
  tp=str(source_path('hrs_tracker'));inputs.add(tp)
  with zipfile.ZipFile(tp).open('trk2022tr_r.csv') as zz:t=pd.read_csv(zz,usecols=lambda x:x.upper() in ['HHID','PN','SEX','STRATUM','SECU'],dtype=str)
  t.columns=t.columns.str.upper();t['id']=t.HHID.str.zfill(6)+t.PN.str.zfill(3);raw=merge(raw,t[['id','SEX','STRATUM','SECU']],ds,'Tracker_historical_sex_design_no_membership_filter')
  ag=num(raw.OA019);raw['age']=ag.where(ag.between(0,120));raw['female']=num(raw.OX060_R).map({1:0.,2:1.});ed=num(raw.OB014).where(num(raw.OB014).between(0,17),num(raw.OZ216).where(num(raw.OZ216).between(0,17)));raw['education']=np.select([ed.between(0,11),ed.between(12,17)],['LOW','HIGH'],default='UNOBSERVED')
  ac=num(raw.ON147);raw['access']=np.select([ac.eq(0),ac.between(1,997)],['NO_CONTACT','CONTACT'],default='UNOBSERVED');raw['barrier']=num(raw.ON290).map({1:1.,5:0.})
  raw['cluster']=raw.STRATUM.astype('string')+'_'+raw.SECU.astype('string');raw['household']=raw.id.str[:6];raw['stratum']=raw.STRATUM;raw['psu']=raw.SECU
  meta=dict(age='OA019 native age at baseline; missing codes/no valid age remain missing',education='Same SAP attained-education construct: valid contemporaneous OB0140-17, else baseline native preloaded OZ2160-17;0-11LOW,12-17HIGH; no future wave values',access='ON147 exact nonnegative count:0 NO_CONTACT,1-997 CONTACT;998/999/blank UNOBSERVED; windows include ER/home/supervised testing',cluster='Native STRATUM/SECU cluster with strata retained for sandwich; sex from baseline OX060_R, not laterTrackerSEX; historical design coverage qualification')
  # Source mean/female direct allbaseline beforeendpointlinkage. No tests or associations.
 selected=['id','age','female','education','access','cluster','household']+(['barrier','stratum','psu'] if ds=='HRS' else [])
 pred=merge(pred,raw[selected],ds,'PF01_baseline_predictor_left_join');b=merge(b,pred.drop(columns=['sbp','dbp']),ds,'baseline_fields')
 f=f.rename(columns={'M':'M1','R':'R1','proxy_status':'proxy1'});z=b.merge(f,on='id',how='left',validate='one_to_one',indicator=True);assert len(z)==len(b) and z.id.is_unique
 z['linked']=z._merge.eq('both');z['validM1']=z.linked&z.M1.notna()&~z.proxy1.eq('PROXY');z['validR1']=z.linked&z.R1.notna()&~z.proxy1.eq('PROXY');z['aim2_base']=z.eligible&z.M0.eq(1)&z.R0.eq(0);z['aim3_base']=z.eligible&z.M0.eq(0)&z.R0.eq(0);z['aim2_observed']=z.aim2_base&z.validR1;z['aim3_common']=z.aim3_base&z.validM1&z.validR1
 for flag in ['aim2_observed','aim3_common']:
  domain=z[z[flag]]
  for v in ['age','female','sbp','dbp','education','access']:
   s=domain[v];isn=s.isna()|s.eq('UNOBSERVED') if s.dtype.kind not in 'iuf' else s.isna();row=dict(dataset=ds,domain=flag,variable=v,N=len(s),missing_N=int(isn.sum()),missing_fraction=float(isn.mean()))
   if v in ['age','sbp','dbp']:
    q=num(s).dropna();row.update(min=float(q.min()),q25=float(q.quantile(.25)),median=float(q.median()),q75=float(q.quantile(.75)),max=float(q.max()))
   else:row['distribution']=json.dumps(s.fillna('UNOBSERVED').value_counts().to_dict())
   profiles.append(row)
  # Allowed prelock aggregate event counts; never outcome stratification of predictors.
  nrec=dict(dataset=ds,domain=flag,N=len(domain),M_event_N=int(domain.M1.eq(1).sum()),R_event_N=int(domain.R1.eq(1).sum()))
  source.append(dict(dataset=ds,baseline_wave=w0,followup_wave=w1,**meta,scope='Only SAP candidate predictors; identifiers/timing auxiliary not predictors'))
 file=O/'08_analytic_inputs'/f'BASELINE_LABEL_PREDICTORS_{ds}.parquet';z.drop(columns='_merge').to_parquet(file,index=False);frames[ds]=z
pd.DataFrame(profiles).to_csv(O/'00_lock/PROD01_PRELOCK_UNIVARIATE_PROFILES.csv',index=False);pd.DataFrame(joins).to_csv(O/'10_manifests/PROD01_PRELOCK_JOIN_QC.csv',index=False);pd.DataFrame(source).drop_duplicates('dataset').to_csv(O/'00_lock/PROD01_SOURCE_DERIVATION_CLOSURE.csv',index=False)
pd.DataFrame([dict(path=p,sha256=sha(p),size_bytes=Path(p).stat().st_size,scope='Authoritative prior or baseline source read only') for p in sorted(inputs)]).to_csv(O/'10_manifests/PROD01_PRELOCK_INPUT_MANIFEST.csv',index=False)
(O/'00_lock/PROD01_PRELOCK_STATUS.json').write_text(json.dumps(dict(timestamp_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),predictor_outcome_associations_inspected=False,models_fit=False,profile_fields='Missingness and marginal baseline distribution only',source_temporal_scope='Native baseline2013/2008-09/2014 modules precede nominal followup2015/2012-13/2018; exact within-wave main/physical date equality not claimed'),indent=2))
print(pd.DataFrame(profiles)[['dataset','domain','variable','N','missing_N','distribution']].fillna('').to_string(index=False))
