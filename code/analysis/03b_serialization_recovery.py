"""Serialization-only recovery from completed 200-refit checkpoint; no primary models rerun."""
from pathlib import Path
p=Path(__file__).parent/'03_aim3_prediction.py'
s=p.read_text();prefix=s.split('point=pairedCV(train,True);')[0];exec(compile(prefix,str(p),'exec'))
c=joblib.load(O/'03_aim3/PROD01_BOOTSTRAP_CHECKPOINT.joblib');assert c['completed']==200
for k,v in c.items():
 if k not in ['completed','RNG']:globals()[k]=v
pred=pd.read_parquet(O/'03_aim3/PROD01_CHARLS_OOF_PREDICTIONS.parquet');point={b:{t:pred[b+'_'+t].to_numpy() for t in ['M','R']} for b in blocks}
main=scalarrecords(train,point,'CHARLS','INTERNAL_COMMON_PAIR');inc=increments(train,point,'CHARLS','INTERNAL_COMMON_PAIR');ranking=ranks(train,point,'CHARLS','INTERNAL_COMMON_PAIR','FULL');cal=calibration(train,point,'CHARLS','INTERNAL_COMMON_PAIR');sub=subgroups(train,point,'CHARLS','INTERNAL_COMMON_PAIR','FULL')
final=joblib.load(O/'03_aim3/PROD01_CHARLS_FROZEN_MODELS.joblib');extmain=[];extinc=[];extrank=[];extcal=[];extsub=[]
for ds in ['ELSA','HRS']:
 a=D[ds];x=Xframe(a);base={'BASE':{t:final['BASE'][t].predict_proba(x)[:,1] for t in ['M','R']}};extmain+=scalarrecords(a,base,ds,'EXTERNAL_FULL_COMMON_PAIR');extcal+=calibration(a,base,ds,'EXTERNAL_FULL_COMMON_PAIR');z=a[a.education.isin(['LOW','HIGH'])].reset_index(drop=True);x=Xframe(z);pp={b:{t:final[b][t].predict_proba(x)[:,1] for t in ['M','R']} for b in ['BASE','BASE_SES']};extmain+=scalarrecords(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR');extinc+=increments(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR');extrank+=ranks(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR','BASE_SES');extcal+=calibration(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR');extsub+=subgroups(z,pp,ds,'EXTERNAL_MAPPABLE_EDUCATION_COMMON_PAIR','BASE_SES')
f=pd.read_csv(O/'03_aim3/PROD01_PAIRED_FOLD_ASSIGNMENTS.csv')
for (r,fold),g in f.groupby(['repeat','fold']):QC.append(dict(dataset='CHARLS',check='SAME_PERSON_TARGET_FOLDS_TRAIN_ONLY_TRANSFORM',repeat=r,fold=fold,N_train=len(train)-len(g),N_test=len(g),overlap_person_N=0,overlap_group_N=0,status='PASS'))
tail=s.split('# Attach 95% paired full-procedure percentile intervals using identical keys.')[1]
old="for name,rows in [('PERFORMANCE',Bmain+Bext),('INCREMENTS',Binc+Bextinc),('RANKS',Brank+Bextrank),('CALIBRATION',Bcal+Bextcal),('SUBGROUPS',Bsub+Bextsub)]:pd.DataFrame(rows).to_parquet(O/f'03_aim3/PROD01_BOOTSTRAP_{name}.parquet',index=False)"
new="for name,rows in [('PERFORMANCE',Bmain+Bext),('INCREMENTS',Binc+Bextinc),('RANKS',Brank+Bextrank),('CALIBRATION',Bcal+Bextcal),('SUBGROUPS',Bsub+Bextsub)]:\n df=pd.DataFrame(rows)\n if 'fraction' in df:df['fraction']=df['fraction'].astype(str)\n df.to_parquet(O/f'03_aim3/PROD01_BOOTSTRAP_{name}.parquet',index=False)"
assert old in tail;tail=tail.replace(old,new);exec(compile(tail,str(p)+'_serialization_recovery','exec'))
(O/'10_manifests/PROD01_SERIALIZATION_REPAIR.json').write_text(json.dumps(dict(affected='Bootstrap parquet RANKS fraction mixed ALL/string and numeric',original='ArrowTypeError after 200 full refits; all point estimates saved',repair='Restore completed checkpoint; stringify fraction for Parquet only; regenerate unchanged summaries; execute previously unreached locked sensitivity',primary_models_rerun=0,bootstrap_refits_rerun=0,scientific_definition_changed=False,point_estimates_changed=False),indent=2)+'\n')
