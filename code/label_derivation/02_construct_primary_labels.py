"""Current primary 140/90 label derivation; all outputs remain local.
Source functions and source-spine processing retained from executed derivation.
Historical alternative-threshold and strict-T event branches excluded.
This is a reproduction adapter, not the original prospective lock artifact.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'analysis'))
from public_paths import PROJECT_ROOT,source_path,REPOSITORY_ROOT
import pandas as pd,numpy as np,duckdb,json,hashlib,datetime,zipfile,io,re,ast,math
from scipy.stats import t as student_t
O=PROJECT_ROOT/'preflight/LABELBIAS_PF01'
assert not (O/'00_lock/PF01_PROTOCOL_LOCK.json').exists(),'Use a fresh reproduction workspace'
for name in ['00_lock','01_label_contract','02_cross_sectional','04_sensitivity','09_code','10_manifests']:(O/name).mkdir(parents=True,exist_ok=True)
L=json.loads((REPOSITORY_ROOT/'documentation/primary_label_contract.json').read_text())
for b in L['blocks']:
 for k in ['health_path','physical_path','weight_path','status_path']:
  if k in b:b[k]=str(source_path(b[k]))
L['timestamp_UTC']=datetime.datetime.now(datetime.timezone.utc).isoformat()
L['artifact_identity']='Local reproduction contract; not original study lock'
MD=json.loads((REPOSITORY_ROOT/'documentation/bp_missing_code_keys.json').read_text())
for name,payload in [('PF01_PROTOCOL_LOCK.json',json.dumps(L,indent=2)),('PF01_PROTOCOL_LOCK.md','# Local reproduction contract\nPrimary 140/90 rules only. Not the original prospective study lock.\n')]:
 (O/'00_lock'/name).write_text(payload)
(O/'00_lock/PF01_PREOUTCOME_LOCK_SHA256.txt').write_text(''.join(hashlib.sha256((O/'00_lock'/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in ['PF01_PROTOCOL_LOCK.md','PF01_PROTOCOL_LOCK.json']))
QC=[];DEN=[];MR=[];MRT=[];WE=[];AGR=[];ONE=[];EXCL=[];RFLAGS=[];frames={};input_paths=set();weighted_universes={};statusframes={};derived=[]
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8388608), b''):
            h.update(b)
    return h.hexdigest()

def verify_lock():
    text = (O / '00_lock/PF01_PREOUTCOME_LOCK_SHA256.txt').read_text()
    for name in ['PF01_PROTOCOL_LOCK.md', 'PF01_PROTOCOL_LOCK.json']:
        assert sha(O / '00_lock' / name) + '  ' + name in text, 'Pre-outcome lock changed'

def save(rows, name):
    pd.DataFrame(rows).to_csv(O / name, index=False)

def number(x):
    return pd.to_numeric(x, errors='coerce')

def id_text(x):
    if pd.api.types.is_numeric_dtype(x):
        assert x.dropna().eq(np.floor(x.dropna())).all(), 'Noninteger source identity'
        return x.astype('Int64').astype('string')
    return x.astype('string')

def unique(d, key, ds, w, src):
    n = len(d)
    dup = int(d.duplicated(key).sum())
    null = int(d[key].isna().any(axis=1).sum())
    QC.append(dict(dataset=ds, wave=w, operation='KEY_UNIQUENESS', source=src, pre_join_N=n, post_join_N=n, duplicate_keys=dup, missing_keys=null, status='PASS' if not dup and (not null) else 'FAIL'))
    assert not dup and (not null), (ds, w, src, dup, null)
    return d

def merge(left, right, ds, w, src):
    unique(right, ['id'], ds, w, src)
    n = len(left)
    out = left.merge(right, on='id', how='left', validate='one_to_one')
    QC.append(dict(dataset=ds, wave=w, operation='LEFT_JOIN', source=src, pre_join_N=n, post_join_N=len(out), duplicate_keys=int(out.id.duplicated().sum()), missing_keys=int(out.id.isna().sum()), status='PASS'))
    assert len(out) == n
    return out

def sread(p, fields):
    verify_lock()
    input_paths.add(p)
    d = pd.read_stata(p, columns=list(dict.fromkeys(fields)), convert_categoricals=False, convert_missing=True)
    return d

def hrs_read(b, module, fields):
    verify_lock()
    p = b['health_path']
    input_paths.add(p)
    z = zipfile.ZipFile(p)
    sta = next((n for n in z.namelist() if n.lower().endswith('sta.zip')))
    st = zipfile.ZipFile(io.BytesIO(z.read(sta)))
    dct = next((n for n in st.namelist() if Path(n).stem.upper() == module and n.lower().endswith('.dct')))
    text = st.read(dct).decode('latin1')
    dta = next((n for n in st.namelist() if Path(n).stem.upper() == module and n.lower().endswith('.dta')), None)
    if dta:
        payload = st.read(dta)
        with pd.io.stata.StataReader(io.BytesIO(payload), convert_categoricals=False) as r:
            names = {v.upper(): v for v in r.variable_labels()}
        d = pd.read_stata(io.BytesIO(payload), columns=[names[v] for v in fields], convert_categoricals=False, convert_missing=True)
        d.columns = d.columns.str.upper()
    else:
        dan = next((n for n in z.namelist() if n.lower().endswith('da.zip')))
        da = zipfile.ZipFile(io.BytesIO(z.read(dan)))
        m = next((n for n in da.namelist() if Path(n).stem.upper() == module))
        cs = {v: (int(a) - 1, int(a) - 1 + int(c)) for a, t, v, c, l in re.findall('_column\\((\\d+)\\)\\s+(\\w+)\\s+(\\w+)\\s+%(\\d+)(?:\\.\\d+)?[fgs]\\s+"([^"]*)"', text)}
        d = pd.read_fwf(io.BytesIO(da.read(m)), colspecs=[cs[v] for v in fields], names=fields, dtype=str)
    d['id'] = d.HHID.astype('string').str.zfill(6) + d.PN.astype('string').str.zfill(3)
    assert d.id.str.fullmatch('\\d{9}').all()
    return d.drop(columns=['HHID', 'PN'])

def rt_reason(d, fields, b, construct):
    cs = [d[f].astype(str).str.strip() for f in fields]
    all_blank = pd.concat([number(d[f]).isna() for f in fields], axis=1).all(axis=1)
    reason = pd.Series('UNRESOLVED_SOURCE_RESPONSE_OR_ROUTING', index=d.index)
    reason[all_blank] = 'SOURCE_BLANK_OR_TAGGED_MISSING_ROUTING_UNKNOWN'
    if b['dataset'] == 'ELSA':
        refusal = pd.concat([number(d[f]).eq(-9) for f in fields], axis=1).any(axis=1)
        dk = pd.concat([number(d[f]).eq(-8) for f in fields], axis=1).any(axis=1)
    elif b['dataset'] == 'HRS':
        refusal = number(d[fields[0]]).eq(9)
        dk = number(d[fields[0]]).eq(8)
    elif b['dataset'] == 'NHANES':
        refusal = number(d[fields[0]]).eq(7)
        dk = number(d[fields[0]]).eq(9)
    else:
        refusal = pd.Series(False, index=d.index)
        dk = pd.Series(False, index=d.index)
    reason[dk] = 'DONT_KNOW'
    reason[refusal] = 'REFUSED'
    return reason

def construct_rt(d, b):
    ds = b['dataset']
    R = pd.Series(np.nan, index=d.index)
    T = R.copy()
    rflag = pd.Series(False, index=d.index)
    tflag = rflag.copy()
    n = {v: number(d[v]) for v in b['R_fields'] + b['T_fields']}
    if ds == 'CHARLS':
        direct = n['da007_1_'].map({1: 1.0, 2: 0.0})
        update = n['da007_w2_2_1_'].map({1: 1.0, 2: 0.0})
        R = direct.copy()
        confirm = n['zda007_1_'].eq(1) & n['da007_w2_1_1_'].eq(1)
        R[confirm] = 1
        R[update.notna()] = update[update.notna()]
        contradictory = direct.notna() & update.notna() & direct.ne(update)
        R[contradictory] = np.nan
        rflag = n['da007_w2_1_1_'].eq(2)
        tv = pd.concat([n[v] for v in b['T_fields']], axis=1)
        yes = tv.isin([1, 2]).any(axis=1)
        no = tv.eq(3).any(axis=1)
        T[no & ~yes] = 0
        T[yes] = 1
        tflag = yes & no
    elif ds == 'ELSA':
        new = n['hediabp'].eq(1) | n['hedimbp'].eq(1)
        fed = n['hedawbp'].eq(1)
        conf = n['hedacbp'].eq(1)
        prior_yes = fed & (conf | n['hedanbp'].isin([2, 3]))
        retracted = n['hedacbp'].eq(2) & n['hedanbp'].eq(1)
        explicit_none = (n['hedia96'].eq(1) | n['hedim96'].eq(1)) & (n['hediabp'].eq(0) | n['hedimbp'].eq(0)) & n['hedawbp'].eq(-1)
        R[explicit_none | retracted] = 0
        R[prior_yes | new] = 1
        rflag = n['hedacbp'].eq(2)
        R[n['hedanbp'].eq(4) & ~new] = np.nan
        tv = pd.concat([n[v] for v in b['T_fields']], axis=1)
        yes = tv.eq(1).any(axis=1)
        no = tv.eq(2).any(axis=1)
        T[no & ~yes] = 0
        T[yes] = 1
        tflag = yes & no
    elif ds == 'HRS':
        R = n[b['R_fields'][0]].map({1: 1.0, 3: 1.0, 4: 0.0, 5: 0.0})
        rflag = n[b['R_fields'][0]].isin([3, 4])
        T = n[b['T_fields'][0]].map({1: 1.0, 5: 0.0})
    else:
        R = n['BPQ020'].map({1: 1.0, 2: 0.0})
        T = n['BPQ050A'].map({1: 1.0, 2: 0.0})
    d['R'] = R
    d['T'] = T
    d['R_dispute_retraction'] = rflag
    d['T_response_contradiction'] = tflag
    for typ in ['R', 'T']:
        reason = rt_reason(d, b[typ + '_fields'], b, typ)
        reason[d[typ].eq(1)] = 'EXPLICIT_AFFIRMATIVE_SOURCE_OR_CONFIRMED_DOCTOR_HISTORY'
        reason[d[typ].eq(0)] = 'EXPLICIT_NEGATIVE_SOURCE_WITH_NATIVE_LOOKBACK'
        d[typ + '_status'] = reason
        for f in b[typ + '_fields']:
            d['source_' + f] = d[f].astype(str)
    return d

def bp_construct(d, b):
    sv = []
    dv = []
    rawvalid = []
    protocol = []
    ds = b['dataset']
    extras = set(b['BP_extra_fields'])
    for i, (s, t) in enumerate(zip(b['SBP'], b['DBP'])):
        x = number(d[s])
        y = number(d[t])
        bad = set(b['BP_missing'])
        for v in [s, t]:
            md = next((r for r in MD if r['dataset'] == ds and r['wave'] == b['wave'] and (r['variable'] == v)))
            if ds == 'HRS':
                for k in md['codes']:
                    try:
                        bad.add(float(k))
                    except ValueError:
                        pass
        ok = np.isfinite(x) & np.isfinite(y) & x.gt(0) & (y.ge(0) if b['DBP_zero_valid'] else y.gt(0)) & x.gt(y) & ~x.isin(bad) & ~y.isin(bad)
        if ds == 'NHANES':
            ok &= x.le(300) & x.mod(2).eq(0) & y.mod(2).eq(0)
        rawvalid.append(ok)
        q = ok.copy()
        if ds == 'ELSA':
            q &= number(d.bpconst).eq(1)
            if b['wave'] == '4':
                q &= number(d.bprespc).eq(1)
            else:
                no_context = number(d.consubno).eq(1) | pd.concat([number(d[v]).eq(0) for v in ['consubea', 'consubsm', 'consubdr', 'consubex']], axis=1).all(axis=1)
                q &= number(d['full' + str(i + 1)]).eq(1) & no_context
        protocol.append(q)
        sv.append(x.where(q))
        dv.append(y.where(q))
    raw = pd.concat(rawvalid, axis=1)
    ok = pd.concat(protocol, axis=1)
    n = ok.sum(axis=1)
    d['N_numeric_valid_pairs'] = raw.sum(axis=1)
    d['N_protocol_valid_pairs'] = n
    xs = pd.concat(sv, axis=1)
    ys = pd.concat(dv, axis=1)
    if ds == 'ELSA' and b['wave'] == '4':
        eligible = n.eq(3)
        ms = xs.iloc[:, 1:3].mean(axis=1).where(eligible)
        mt = ys.iloc[:, 1:3].mean(axis=1).where(eligible)
        for variable, calc in [('sysval', ms), ('diaval', mt)]:
            a = number(d[variable])
            compare = eligible & a.gt(0)
            mismatch = int(((a - calc).abs().gt(1e-06) & compare).sum())
            QC.append(dict(dataset=ds, wave=b['wave'], operation='OFFICIAL_MEAN_REDERIVATION', source=variable, pre_join_N=int(compare.sum()), post_join_N=int(compare.sum()), duplicate_keys=0, missing_keys=0, N_mean_mismatch=mismatch, status='PASS' if not mismatch else 'FAIL'))
            assert mismatch == 0, 'Source official mean discrepancy'
    else:
        eligible = n.ge(2)
        ms = xs.mean(axis=1).where(eligible)
        mt = ys.mean(axis=1).where(eligible)
    d['mean_SBP_primary'] = ms
    d['mean_DBP_primary'] = mt
    d['M'] = np.where(eligible, (ms.ge(140) | mt.ge(90)).astype(float), np.nan)
    d['M_status'] = np.select([eligible, n.eq(1), n.eq(0)], ['VALID_PRIMARY', 'ONE_PROTOCOL_VALID_PAIR_PRIMARY_EXCLUDED', 'NO_PROTOCOL_VALID_PAIRED_READING'], default='SOURCE_OFFICIAL_SUMMARY_ELIGIBILITY_NOT_MET')
    return d

def proxy_status(d, b):
    ds = b['dataset']
    p = pd.Series('UNRESOLVED', index=d.index)
    if ds == 'CHARLS':
        if 'proxy' in b['proxy_fields']:
            p[number(d.proxy).eq(1)] = 'PROXY'
            p[number(d.proxy).eq(2)] = 'SELF'
        else:
            p[number(d.db034).isin([1, 2, 3, 4])] = 'PROXY'
    elif ds == 'ELSA':
        p[number(d.askpx).eq(1)] = 'PROXY'
        p[number(d.askpx).eq(0)] = 'SELF'
    elif ds == 'HRS':
        x = number(d[b['proxy_fields'][0]])
        p[x.isin([1, 2])] = 'PROXY'
        p[x.eq(5)] = 'SELF'
    return p

def survey_estimate(universe, labels, domain_col, event_col, b):
    z = universe.merge(labels[['id', domain_col, event_col]], on='id', how='left', validate='one_to_one')
    QC.append(dict(dataset=b['dataset'], wave=b['wave'], operation='SURVEY_UNIVERSE_DOMAIN_LEFT_JOIN', source=domain_col + ':' + event_col, pre_join_N=len(universe), post_join_N=len(z), duplicate_keys=int(z.id.duplicated().sum()), missing_keys=int(z.id.isna().sum()), status='PASS'))
    assert len(z) == len(universe)
    w = number(z[b['weight']])
    domain = z[domain_col].fillna(False).astype(bool)
    event = z[event_col].fillna(False).astype(bool)
    usable = w.gt(0) & np.isfinite(w)
    weighted_domain = usable & domain
    den = float(w[weighted_domain].sum())
    num = float(w[weighted_domain & event].sum())
    p = num / den if den else np.nan
    out = dict(weight=b['weight'], weight_target=b['weight_status'], N_positive_weight_domain=int(weighted_domain.sum()), sum_weight_domain=den, weighted_percentage=100 * p if den else np.nan, CI95_low_percentage=np.nan, CI95_high_percentage=np.nan, design_df=np.nan, variance_method='NOT_ESTIMABLE_SOURCE_DESIGN_UNRESOLVED', strata=b['strata'], PSU=b['PSU'])
    if not den:
        return dict(out, estimate_status='NO_POSITIVE_AUTHORIZED_WEIGHT_DOMAIN')
    if not b['strata'] or not b['PSU']:
        return dict(out, estimate_status='WEIGHTED_POINT_ONLY_DESIGN_CI_NOT_ESTIMABLE')
    if z.loc[usable, [b['strata'], b['PSU']]].isna().any().any():
        return dict(out, estimate_status='DESIGN_VALUES_MISSING_CI_NOT_ESTIMABLE')
    influence = (w.fillna(0) * domain.astype(float) * (event.astype(float) - p) / den).where(usable, 0)
    ps = pd.DataFrame({'h': z[b['strata']], 'j': z[b['PSU']], 'u': influence})[usable].groupby(['h', 'j'], dropna=False).u.sum()
    var = 0.0
    df = 0
    for h, a in ps.groupby(level=0):
        n = len(a)
        if n < 2:
            return dict(out, estimate_status='SINGLETON_DESIGN_STRATUM_CI_NOT_ESTIMABLE')
        var += n / (n - 1) * float(((a - a.mean()) ** 2).sum())
        df += n - 1
    se = math.sqrt(max(0, var))
    q = float(student_t.ppf(0.975, df))
    if 0 < p < 1:
        se_l = se / (p * (1 - p))
        l = math.log(p / (1 - p))
        lo = 1 / (1 + math.exp(min(700, -(l - q * se_l))))
        hi = 1 / (1 + math.exp(min(700, -(l + q * se_l))))
        method = 'TAYLOR_RATIO_FULL_DESIGN_LOGIT_T95'
    else:
        lo = np.nan
        hi = np.nan
        method = 'BOUNDARY_CELL_DESIGN_95CI_NOT_IDENTIFIED_BY_LINEARIZATION'
    out.update(CI95_low_percentage=100 * lo, CI95_high_percentage=100 * hi, design_df=df, variance_method=method, estimate_status='DESIGN_ESTIMABLE' if 0 < p < 1 else 'BOUNDARY_CELL_CI_NOT_ESTIMABLE', SE_percentage=100 * se)
    return out

tracker=None
for b in L['blocks']:
 ds=b['dataset'];w=b['wave'];key=(ds,w);rawkeys=['ID'] if ds=='CHARLS' else ['idauniq'] if ds=='ELSA' else ['HHID','PN'] if ds=='HRS' else ['SEQN'];wanted=b['R_fields']+b['T_fields']+b['proxy_fields']
 if ds=='CHARLS':
  d=sread(b['health_path'],rawkeys+wanted);d['id']=id_text(d.ID);p=sread(b['physical_path'],rawkeys+b['SBP']+b['DBP']+b['BP_extra_fields']);p['id']=id_text(p.ID);weight=sread(b['weight_path'],['ID',b['weight']]);weight['id']=id_text(weight.ID)
  if 'status_path' in b:
   sf=sread(b['status_path'],['ID']+b['status_fields']);sf['id']=id_text(sf.ID);statusframes[ds]=unique(sf[['id']+b['status_fields']],['id'],ds,w,'Sample_Infor')
 elif ds=='ELSA':
  verify_lock();input_paths.update([b['health_path'],b['physical_path']]);d=pd.read_parquet(b['health_path'],columns=rawkeys+wanted);p=pd.read_parquet(b['physical_path'],columns=rawkeys+b['SBP']+b['DBP']+b['BP_extra_fields']+[b['weight']]);d['id']=id_text(d.idauniq);p['id']=id_text(p.idauniq);weight=p[['id',b['weight']]].copy()
 elif ds=='HRS':
  d=hrs_read(b,b['health_module'],rawkeys+b['R_fields']+b['T_fields']);p=hrs_read(b,b['physical_module'],rawkeys+b['SBP']+b['DBP'])
  if tracker is None:
   input_paths.add(b['weight_path']);z=zipfile.ZipFile(b['weight_path']);selected=['HHID','PN','STRATUM','SECU','OPMWGTR','QPMWGTR','OPROXY','QPROXY','OALIVE','QALIVE']
   with z.open('trk2022tr_r.csv') as f:tracker=pd.read_csv(f,usecols=lambda x:x.upper() in selected,dtype=str)
   tracker.columns=tracker.columns.str.upper();tracker['id']=tracker.HHID.str.zfill(6)+tracker.PN.str.zfill(3);unique(tracker,['id'],'HRS','TRACKER','trk2022v1')
  weight=tracker[['id',b['weight'],'STRATUM','SECU']].copy();d=merge(d,tracker[['id']+b['proxy_fields']],ds,w,'Tracker proxy attachment without future filtering');statusframes[ds]=tracker[['id','QALIVE','QPROXY']].copy()
 else:
  input_paths.add(b['health_path']);con=duckdb.connect(b['health_path'],read_only=True);fields=rawkeys+wanted+b['SBP']+b['DBP']+b['BP_extra_fields']+[b['weight'],b['strata'],b['PSU']]
  d=con.execute('select '+','.join('"'+f+'"' for f in fields)+' from '+b['view']).fetchdf();d['id']=id_text(d.SEQN);p=d[['id']+b['SBP']+b['DBP']].copy();weight=d[['id',b['weight'],b['strata'],b['PSU']]].copy()
 if ds=='CHARLS':
  before=len(weight);weight['_source_weight_token']=weight[b['weight']].astype(str);weight=weight.drop_duplicates(['id','_source_weight_token']).copy();QC.append(dict(dataset=ds,wave=w,operation='COLLAPSE_IDENTICAL_WEIGHT_PROJECTION_ONLY',source=b['weight_path'],pre_join_N=before,post_join_N=len(weight),N_identical_projection_duplicates=before-len(weight),duplicate_keys=int(weight.id.duplicated().sum()),missing_keys=0,status='PASS' if weight.id.is_unique else 'FAIL'));assert weight.id.is_unique,'Conflicting source weight authority'
 unique(d,['id'],ds,w,'Native health spine');unique(p,['id'],ds,w,'Native physical visit');unique(weight,['id'],ds,w,'Source measurement weight universe')
 if ds!='NHANES':d=merge(d,p.drop(columns=rawkeys,errors='ignore'),ds,w,'Physical same-visit source fields')
 d['eligible']=number(d.RIDAGEYR).ge(16) if ds=='NHANES' else True
 d=construct_rt(d,b);d=bp_construct(d,b);d['proxy_status']=proxy_status(d,b)
 # Preserve complete source spine in the local derived artifact; no future eligibility constraint.
 d['valid_MR']=d.eligible&d.M.notna()&d.R.notna();d['valid_MRT']=d.valid_MR&d['T'].notna()
 d['state_MR']=np.select([d.valid_MR&d.M.eq(0)&d.R.eq(0),d.valid_MR&d.M.eq(1)&d.R.eq(0),d.valid_MR&d.M.eq(1)&d.R.eq(1),d.valid_MR&d.M.eq(0)&d.R.eq(1)],['S1','S2','S3','S4'],default='UNRESOLVED')
 d['state_MRT']=pd.Series('UNRESOLVED',index=d.index)
 for a in [0,1]:
  for r in [0,1]:
   for t in [0,1]:d.loc[d.valid_MRT&d.M.eq(a)&d.R.eq(r)&d['T'].eq(t),'state_MRT']=f'M{a}R{r}T{t}'
 z=d[d.eligible];den=dict(dataset=ds,wave=w,N_source_spine=len(d),N_eligible_source_population=len(z),N_two_or_more_protocol_valid_BP=int(z.N_protocol_valid_pairs.ge(2).sum()),N_primary_M=int(z.M.notna().sum()),N_valid_R=int(z.R.notna().sum()),N_valid_T=int(z['T'].notna().sum()),N_valid_MR=int(z.valid_MR.sum()),N_valid_MRT=int(z.valid_MRT.sum()),N_M_unknown=int(z.M.isna().sum()),N_R_unknown=int(z.R.isna().sum()),N_T_unknown=int(z['T'].isna().sum()),N_proxy=int(z.proxy_status.eq('PROXY').sum()),N_proxy_mode_unknown=int(z.proxy_status.eq('UNRESOLVED').sum()),T_qualification='QUALIFIED_SOURCE_ROUTING_OR_REPORTED_TREATMENT_NOT_ADHERENCE',population=b['population']);DEN.append(den)
 c={s:int(z.state_MR.eq(s).sum()) for s in ['S1','S2','S3','S4']};assert sum(c.values())==den['N_valid_MR']
 for s,label in zip(['S1','S2','S3','S4'],L['policies']['state_labels']):MR.append(dict(den,state=s,state_label=label,N=c[s],unweighted_proportion=c[s]/den['N_valid_MR'] if den['N_valid_MR'] else np.nan,unweighted_CI_status='RAW_SAMPLE_DESCRIPTIVE_NO_NAIVE_POPULATION_CI'))
 for a in [0,1]:
  for r in [0,1]:
   for t in [0,1]:
    state=f'M{a}R{r}T{t}';n=int(z.state_MRT.eq(state).sum());MRT.append(dict(den,state=state,N=n,unweighted_proportion=n/den['N_valid_MRT'] if den['N_valid_MRT'] else np.nan,T_tables_status='QUALIFIED' if ds=='HRS' else 'SOURCE_ROUTING_QUALIFIED'))
 assert sum(x['N'] for x in MRT if x['dataset']==ds and x['wave']==w)==den['N_valid_MRT']
 for family,domain,states in [('MR','valid_MR',['S1','S2','S3','S4']),('MRT','valid_MRT',[f'M{a}R{r}T{t}' for a in [0,1] for r in [0,1] for t in [0,1]])]:
  for s in states:
   d['event']=d['state_'+family].eq(s);res=survey_estimate(weight,d,domain,'event',b);WE.append(dict(dataset=ds,wave=w,family=family,state=s,raw_N=int(z['state_'+family].eq(s).sum()),raw_valid_denominator=int(z[domain].sum()),**res))
 n=sum(c.values());disc=c['S2']+c['S4'];obs=(c['S1']+c['S3'])/n if n else np.nan;pe=((c['S3']+c['S2'])*(c['S3']+c['S4'])+(c['S1']+c['S4'])*(c['S1']+c['S2']))/n**2 if n else np.nan
 AGR.append(dict(dataset=ds,wave=w,N_valid_MR=n,symmetric_discordance=disc/n if n else np.nan,positive_agreement=2*c['S3']/(2*c['S3']+disc) if 2*c['S3']+disc else np.nan,negative_agreement=2*c['S1']/(2*c['S1']+disc) if 2*c['S1']+disc else np.nan,Cohen_kappa_secondary=(obs-pe)/(1-pe) if n and pe<1 else np.nan,interpretation='SECONDARY_MEASUREMENT_AGREEMENT_NO_GOLD_STANDARD_OR_CLINICAL_ACCURACY'))

 ONE.append(dict(dataset=ds,wave=w,N_exactly_one_numeric_pair=int(z.N_numeric_valid_pairs.eq(1).sum()),N_exactly_one_protocol_valid_pair=int(z.N_protocol_valid_pairs.eq(1).sum()),primary_M_included=False,interpretation='SENSITIVITY_INVENTORY_ONLY; aggregate complete-set source flags may leave single numeric pair validity unresolved'))
 for typ in ['M','R','T']:
  for reason,n in z[typ+'_status'].value_counts(dropna=False).items():EXCL.append(dict(dataset=ds,wave=w,label=typ,reason=reason,N=int(n)))
 RFLAGS.append(dict(dataset=ds,wave=w,N_R_dispute_retraction=int(z.R_dispute_retraction.sum()),N_T_response_contradiction=int(z.T_response_contradiction.sum()),N_T_positive_R_negative=int((z['T'].eq(1)&z.R.eq(0)).sum()),negative_R_does_not_prove_never_recognized=True))
 keep=['id','eligible','M','R','T','M_status','R_status','T_status','mean_SBP_primary','mean_DBP_primary','N_numeric_valid_pairs','N_protocol_valid_pairs','proxy_status','R_dispute_retraction','T_response_contradiction','state_MR','state_MRT']+['source_'+x for x in b['R_fields']+b['T_fields']]
 file=O/'01_label_contract'/f'DERIVED_LABELS_{ds}_{w.replace("-","_")}.parquet';d[keep].to_parquet(file,index=False);derived.append(str(file));frames[key]=d[keep].copy();weighted_universes[key]=weight
 print('Constructed',ds,w,'sourceN',len(z),'validMR',den['N_valid_MR'],'validMRT',den['N_valid_MRT'],flush=True)

save(MR,'02_cross_sectional/PF01_MR_FOUR_STATE_COUNTS.csv')
save(WE,'02_cross_sectional/PF01_SURVEY_WEIGHTED_STATE_ESTIMATES.csv')
save(QC,'10_manifests/PF01_PRIMARY_REPRODUCTION_QC.csv')
save(DEN,'02_cross_sectional/PF01_LABEL_AVAILABILITY.csv')
S=PROJECT_ROOT/'protocol/LABELBIAS_SAP01_R1'
for name in ['02_predictors','03_events','10_manifests']:(S/name).mkdir(parents=True,exist_ok=True)
# The production reader loads this metadata table but does not use it for selection.
pd.DataFrame([{'dataset':b['dataset'],'wave':b['wave'],'construct':'PRIMARY_LABEL_INTERFACE'} for b in L['blocks']]).to_csv(S/'02_predictors/SAP01_PREDICTOR_DOMAIN_MATRIX.csv',index=False)
# Exact treatment-context counting expression from the executed protocol census.
tctx=[]
for pair in L['primary_pairs']:
 ds=pair['dataset'];w0=pair['baseline'];b=frames[(ds,w0)]
 for aim,m in [('AIM2',1),('AIM3',0)]:
  risk=b[b.eligible&b.M.eq(m)&b.R.eq(0)].copy();N=len(risk)
  tctx.append(dict(dataset=ds,baseline_wave=w0,aim=aim,baseline_N=N,explicit_T_positive=int(risk['T'].eq(1).sum()),explicit_T_negative=int(risk['T'].eq(0).sum()),T_unknown_or_routed=int(risk['T'].isna().sum()),T_used_for_eligibility=False))
  assert sum(tctx[-1][x] for x in ['explicit_T_positive','explicit_T_negative','T_unknown_or_routed'])==N
pd.DataFrame(tctx).to_csv(S/'03_events/SAP01_T_CONTEXT_COUNTS.csv',index=False)
for root,name in [(O,'PF01'),(S,'SAP01')]:
 rs=[dict(absolute_path=str(p),sha256=sha(p)) for p in sorted(root.rglob('*')) if p.is_file() and 'OUTPUT_SHA256_MANIFEST' not in p.name]
 pd.DataFrame(rs).to_csv(root/f'10_manifests/{name}_OUTPUT_SHA256_MANIFEST.csv',index=False)
print('Primary interfaces created locally. Participant-level outputs must not be committed or uploaded.')
