"""Locally authorized STAB01 execution; see documentation and private input requirements."""

def main():
    #!/usr/bin/env python3
    """STAB01 historical execution adaptation. Restricted inputs and outputs stay local."""
    import os
    os.umask(0o077)
    import ast, hashlib, json, math, platform, sys, time, traceback, warnings
    from pathlib import Path
    import numpy as np
    import pandas as pd
    import scipy, sklearn, pyarrow, joblib
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning

    # PUBLIC ADAPTER: locally trusted private authority, reference and input manifest.
    # Paths, scientific input digests and the output directory are never distributed.
    if sys.flags.optimize:
     raise SystemExit('Optimized Python is unsupported because the original fit uses assertions.')
    if os.environ.get('STAB01_RUN_AUTHORIZED') != 'YES':
     raise SystemExit('Explicit local authorization is required; no data have been read.')
    manifest_path = Path(os.environ['STAB01_PRIVATE_INPUT_MANIFEST']).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text())
    if set(manifest) != {'inputs', 'output_dir'}:
     raise ValueError('Invalid private manifest keys')
    from identity_guard import verify_frozen_inputs
    inputs = verify_frozen_inputs(os.environ['STAB01_TRUSTED_REFERENCE'], manifest['inputs'])
    R = Path(manifest['output_dir']).resolve()
    if R.exists():
     raise FileExistsError('Output directory must not already exist')
    R.mkdir(mode=0o700, parents=False, exist_ok=False)
    PRIVATE=R/'restricted'; PRIVATE.mkdir(mode=0o700)

    def sha(p):
     h=hashlib.sha256()
     with open(p,'rb') as f:
      for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
     return h.hexdigest()
    def write_json(name,obj):
     p=PRIVATE/name
     with p.open('x') as f: json.dump(obj,f,indent=2,sort_keys=True,default=str)
    def gate(x,msg):
     if not x: raise AssertionError(msg)
    def stop(status,reason):
     p=R/'STAB01_EXECUTION_REPORT.md'
     p.write_text(f'# STAB01 execution report\n\n**{status}**\n\n{reason}\n\nNo perturbation analysis was started. Original outputs remain unchanged. See reproducibility QC.\n')
     (R/'STAB01_REPRODUCIBILITY_QC.md').write_text('# STAB01 reproducibility QC\n\n'+reason+'\n\nRestricted execution details are in `restricted/`.\n')
     print(status+': '+reason,flush=True)
     sys.exit(2)

    expected={'python':'3.14.4','numpy':'2.4.4','pandas':'3.0.2','scipy':'1.17.1','scikit-learn':'1.8.0','pyarrow':'24.0.0','joblib':'1.5.3'}
    env={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'scikit-learn':sklearn.__version__,'pyarrow':pyarrow.__version__,'joblib':joblib.__version__,'platform':platform.platform(),'OPENBLAS_NUM_THREADS':os.environ.get('OPENBLAS_NUM_THREADS'),'OMP_NUM_THREADS':os.environ.get('OMP_NUM_THREADS')}
    try:
     for name,(p,h) in inputs.items():gate(sha(p)==h,'Input hash mismatch: '+name)
     gate(all(env[k]==v for k,v in expected.items()),'Recorded Python or package version mismatch')
     gate(env['OPENBLAS_NUM_THREADS']=='1' and env['OMP_NUM_THREADS']=='1','Thread environment mismatch')
     write_json('frozen_provenance.json',{'inputs':{k:{'path':str(p),'sha256':sha(p)} for k,(p,_) in inputs.items()},'environment':env,'script_sha256':sha(__file__),'seed':2026111901,'draw_streams':200,'qc_amendment':'2026-11-19'})
    except Exception as e:stop('STAB01_INTEGRITY_HOLD','Pre-execution authority/environment gate failed: '+str(e))

    # Extract only unmodified, hash-verified Phase I function definitions; never execute its top level.
    source=inputs['model_code'][0].read_text(); tree=ast.parse(source)
    names={'Xframe','template','pairedfit','highmask'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    gate(len(nodes)==len(names) and {x.name for x in nodes}==names,'Missing original function definition or duplicate')
    blocks={'BASE':[],'BASE_SES':['education'],'BASE_ACCESS':['access'],'FULL':['education','access']}
    # Use one explicit namespace for extracted definitions and their global dependencies.
    model_scope={'np':np,'Pipeline':Pipeline,'ColumnTransformer':ColumnTransformer,
                 'SimpleImputer':SimpleImputer,'StandardScaler':StandardScaler,
                 'OneHotEncoder':OneHotEncoder,'LogisticRegression':LogisticRegression,
                 'blocks':blocks}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(inputs['model_code'][0]),'exec'),model_scope)
    Xframe,template,pairedfit,highmask=(model_scope[name] for name in ('Xframe','template','pairedfit','highmask'))
    gate(all(callable(fn) for fn in (Xframe,template,pairedfit,highmask)),'Invalid original function definition')
    def fit(train, held):
     gate(set(train.M1.unique())=={0,1} and set(train.R1.unique())=={0,1},'Training target not binary with both classes')
     with warnings.catch_warnings(record=True) as w:
      warnings.simplefilter('always',ConvergenceWarning)
      pair=pairedfit(train,'FULL')
      gate(not any(issubclass(x.category,ConvergenceWarning) for x in w),'Convergence warning')
     p={t:pair[t].predict_proba(Xframe(held))[:,1] for t in ('M','R')}
     for t in p:gate(np.isfinite(p[t]).all() and ((p[t]>=0)&(p[t]<=1)).all(),'Invalid probabilities')
     return p

    try:
     df=pd.read_parquet(inputs['analytic'][0]); d=df.loc[df.aim3_common].copy().reset_index(drop=True)
     gate(len(d)==5303 and d.id.notna().all() and d.id.astype(str).is_unique and d.cluster.notna().all(),'Cohort N/ID/cluster integrity')
     ids=d.id.astype(str); communities=d.cluster.astype(str).to_numpy()
     key=hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest()
     lock=json.loads(inputs['lock'][0].read_text()); contract=next(x for x in lock['samples'] if x['dataset']=='CHARLS' and x['aim']=='AIM3_COMMON')
     gate(key==contract['ordered_native_key_sha256'],'Original sorted person-key hash mismatch')
     f=pd.read_csv(inputs['folds'][0],dtype={'id':str,'cluster':str})
     gate(len(f)==10606 and set(f.columns)=={'id','cluster','repeat','fold'},'Fold schema/row count mismatch')
     gate(not f[['id','repeat']].duplicated().any() and set(f.repeat)=={0,1} and set(f.fold)==set(range(5)),'Fold duplicates/repeat/fold mismatch')
     gate(set(f.id)==set(ids),'Fold/cohort ID set mismatch')
     id_index=pd.Index(ids); f['idx']=id_index.get_indexer(f.id);gate((f.idx>=0).all(),'Fold unmatched ID')
     gate(np.array_equal(f.cluster.to_numpy(),communities[f.idx.to_numpy()]),'Fold community mismatch')
     foldmap=np.full((2,len(d)),-1,dtype=int)
     for row in f.itertuples(index=False):foldmap[int(row.repeat),int(row.idx)]=int(row.fold)
     gate((foldmap>=0).all(),'Fold assignments incomplete')
     parts={}
     for r in range(2):
      for fold in range(5):
       te=np.flatnonzero(foldmap[r]==fold);tr=np.flatnonzero(foldmap[r]!=fold)
       gate(len(te)>0 and not set(communities[te])&set(communities[tr]),'Community leakage')
       gate(not set(ids.iloc[te])&set(ids.iloc[tr]),'Person leakage')
       groups=sorted(set(communities[tr])); members={g:tr[communities[tr]==g] for g in groups}
       parts[r,fold]=(tr,te,groups,members)
     saved=pd.read_parquet(inputs['oof'][0]);gate(len(saved)==5303 and saved.id.astype(str).is_unique,'OOF ID integrity')
     gate(np.array_equal(saved.id.astype(str).to_numpy(),ids.to_numpy()),'OOF original cohort order mismatch')
     gate(np.array_equal(saved.cluster.astype(str).to_numpy(),communities),'OOF cluster mismatch')
     gate(all(np.array_equal(saved[c].to_numpy(),d[c].to_numpy()) for c in ['M1','R1']),'OOF target mismatch')
     original={t:saved['FULL_'+t].to_numpy() for t in ('M','R')}
     base={t:np.zeros(len(d)) for t in ('M','R')};cover=np.zeros(len(d),int); nfits=0
     for r in range(2):
      for fold in range(5):
       tr,te,_,_=parts[r,fold];p=fit(d.iloc[tr],d.iloc[te]);nfits+=2
       for t in base:base[t][te]+=p[t]/2
       cover[te]+=1
     gate(np.all(cover==2) and nfits==20,'Baseline coverage or fit count')
     delta={t:float(np.max(np.abs(base[t]-original[t]))) for t in base}
     gate(all(v<=1e-10 for v in delta.values()),'Baseline OOF numerical tolerance failed')
     origmask={t:highmask(original[t],d,.1) for t in original}
     gate(all(np.array_equal(highmask(base[t],d,.1),origmask[t]) for t in base),'Baseline top-list mismatch')
     gate(all(int(origmask[t].sum())==531 for t in origmask),'Baseline capacity mismatch')
     shared=int((origmask['M']&origmask['R']).sum());gate(shared==354,'Baseline cross-target overlap mismatch')
     baseline={'N':len(d),'fold_rows':len(f),'n_fits':nfits,'max_abs_difference':delta,'equal_top_lists':True,'original_shared':shared,'community_leakage':0,'sorted_id_sha256':key}
     write_json('baseline_qc.json',baseline)
     print('BASELINE PASS: all 20 fits and required provenance, fold and list gates passed',flush=True)
    except Exception as e:
     write_json('baseline_failure.json',{'error':str(e),'type':type(e).__name__,'trace':traceback.format_exc()})
     stop('STAB01_BASELINE_REPRODUCTION_FAIL','Baseline gate failed: '+str(e))

    children=np.random.SeedSequence(2026111901).spawn(200); selection=np.zeros((200,2,len(d)),dtype=bool)
    am=np.full((200,2),np.nan);cross=np.full(200,np.nan); qa=np.full((200,2,5,2),np.nan); qb=np.full_like(qa,np.nan)
    fail=[]; draw_records=[];valid=np.zeros(200,bool);fit_attempts=0;start=time.monotonic()
    for b,child in enumerate(children):
     rng=np.random.Generator(np.random.PCG64(child)); pred=np.zeros((2,len(d))); counts=np.zeros(len(d),dtype=int); localqa=np.zeros((2,5,2)); reason=None
     try:
      for r in range(2):
       for fold in range(5):
        tr,te,groups,members=parts[r,fold]; draws=rng.integers(0,len(groups),size=len(groups)); picked=[groups[j] for j in draws]
        ix=np.concatenate([members[g] for g in picked]);gate(len(picked)==len(groups) and not set(picked)&set(communities[te]),'Draw size or held-out community violation')
        expected_n=sum(len(members[g]) for g in picked);gate(len(ix)==expected_n,'Training multiplicity mismatch')
        draw_records.append({'replicate':b+1,'repeat':r,'fold':fold,'groups':len(groups),'sample_rows':len(ix),'draw_hash':hashlib.sha256('\n'.join(picked).encode()).hexdigest(),'spawn_key':list(child.spawn_key)})
        p=fit(d.iloc[ix],d.iloc[te]);fit_attempts+=2
        for ti,t in enumerate(('M','R')):pred[ti,te]+=p[t]/2;localqa[r,fold,ti]=float(np.mean(p[t]))
        counts[te]+=1
      gate(np.all(counts==2),'Replicate prediction coverage')
      for ti,t in enumerate(('M','R')):
       mask=highmask(pred[ti],d,.1);gate(mask.sum()==531,'Replicate list size');selection[b,ti]=mask
       am[b,ti]=int((mask&origmask[t]).sum())/531
       for r in range(2):
        for fold in range(5):qb[b,r,fold,ti]=int(mask[parts[r,fold][1]].sum())
        gate(qb[b,r,:,ti].sum()==531,'Fold contribution mismatch')
      cross[b]=int((selection[b,0]&selection[b,1]).sum())/531;qa[b]=localqa;valid[b]=True
     except (AssertionError,ValueError,FloatingPointError) as e:
      reason={'replicate':b+1,'error':str(e),'type':type(e).__name__,'repeat':r,'fold':fold};fail.append(reason);selection[b]=False;am[b]=np.nan;cross[b]=np.nan;qa[b]=np.nan;qb[b]=np.nan
     if (b+1)%20==0:print(f'Completed {b+1}/200; valid={int(valid.sum())}; elapsed={time.monotonic()-start:.1f}s',flush=True)

    write_json('draw_log.json',draw_records);write_json('failures.json',fail)
    write_json('execution_qc.json',{'valid_replicates':int(valid.sum()),'failed_replicates':len(fail),'fits_completed':fit_attempts,'planned_fits':4000,'elapsed_seconds':time.monotonic()-start,'baseline':baseline,'protocol_sha256_after':sha(inputs['protocol'][0]),'input_hashes_after':{k:sha(v[0]) for k,v in inputs.items()}})
    if sha(inputs['protocol'][0])!=inputs['protocol'][1] or any(sha(p)!=h for p,h in inputs.values()):
     stop('STAB01_INTEGRITY_HOLD','Input or frozen protocol changed during execution; no result interpretation.')
    if not valid.all():
     (R/'STAB01_EXECUTION_REPORT.md').write_text(f'# STAB01 execution report\n\n**STAB01_INCOMPLETE_REPLICATES**\n\nAttempted 200; complete {valid.sum()}; failed {len(fail)}. No success-selected stability conclusions. See restricted failure log.\n')
     (R/'STAB01_REPRODUCIBILITY_QC.md').write_text(f'# Reproducibility QC\n\nBaseline passed. Paired replicates complete: {valid.sum()}/200; no draws replaced.\n')
     print('STAB01_INCOMPLETE_REPLICATES',flush=True);sys.exit(2)

    gate(fit_attempts==4000,'Perturbation fit count mismatch')
    freq=selection.mean(axis=0);gate(np.allclose(freq.sum(axis=1),531,atol=1e-10),'Frequency accounting mismatch')
    def summary(x):
     x=np.asarray(x,dtype=float);q=np.quantile(x,[.05,.25,.5,.75,.95]);return {'n':len(x),'mean':float(x.mean()),'sd':float(x.std(ddof=1)),'median':float(q[2]),'p05':float(q[0]),'p25':float(q[1]),'p75':float(q[3]),'p95':float(q[4]),'min':float(x.min()),'max':float(x.max()),'mcse_mean':float(x.std(ddof=1)/np.sqrt(len(x)))}
    rows=[]
    def add(family,target,x,unit='fraction_of_531'):
     rows.append({'family':family,'target_or_contrast':target,'unit':unit,**summary(x)})
    for t,label in enumerate(('M','R')):add('original_retention',label,am[:,t])
    ind=np.stack([(selection[0::2,t]&selection[1::2,t]).sum(axis=1)/531 for t in range(2)],axis=1)
    for t,label in enumerate(('M','R')):add('independent_refit_overlap',label,ind[:,t])
    add('matched_cross_target_overlap','M_vs_R',cross)
    add('paired_retention_difference','M_minus_R',am[:,0]-am[:,1]);add('paired_independent_overlap_difference','M_minus_R',ind[:,0]-ind[:,1])
    for t,label in enumerate(('M','R')):
     q=freq[t];ss=summary(q);ss['mcse_mean']=np.nan
     rows.append({'family':'selection_frequency_across_people','target_or_contrast':label,'unit':'frequency',**ss})
     edges=[0,.1,.25,.5,.75,.9,1.0000001]; hist=np.histogram(q,bins=edges)[0]
     for name,count in zip(['[0,0.1)','[0.1,0.25)','[0.25,0.5)','[0.5,0.75)','[0.75,0.9)','[0.9,1]'],hist):rows.append({'family':'selection_frequency_bin','target_or_contrast':label,'unit':name,'n':int(count)})
    pd.DataFrame(rows).to_csv(R/'STAB01_STABILITY_RESULTS.csv',index=False)
    foldrows=[]
    for kind,arr in [('QC_A_mean_heldout_probability',qa),('QC_B_global_selected_count',qb)]:
     for r in range(2):
      for fold in range(5):
       for ti,t in enumerate(('M','R')):foldrows.append({'diagnostic':kind,'repeat':r,'fold':fold,'target':t,**summary(arr[:,r,fold,ti])})
    pd.DataFrame(foldrows).to_csv(R/'STAB01_FOLD_QC_SUMMARY.csv',index=False)
    write_json('complete.json',{'verdict':'STAB01_EXECUTION_PASS','valid':200,'baseline_fits':20,'perturbation_fits':4000,'failure_count':0,'selection_frequency_sums':freq.sum(axis=1).tolist(),'original_shared':shared})
    print('STAB01_EXECUTION_PASS: numerical execution and accounting gates passed',flush=True)

if __name__ == "__main__":
    main()
