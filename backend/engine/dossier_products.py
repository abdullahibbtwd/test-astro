"""Deterministic dossier producers. Models must never be called from this module."""
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import tempfile
from profile_dossier import ROOT, digest, file_hash

REPO = ROOT.parent.parent  # astrology-app root (Chart_wheel stays here)


def versions(*files):
    return {
        'code': file_hash(*(
            (REPO / f if str(f).startswith('Chart_wheel/') else ROOT / f)
            for f in files
        ))
    }


def get_product(dossier, key, name, anchor=None):
    chart = dossier.get(key, 'chart')
    def get(product, context=None):
        return dossier.get(key, product, context)
    def memo(deps, fn, *, codec=None, tier='a1'):
        return dossier.memo(key, name, anchor, deps, fn, codec=codec, tier=tier)
    if name == 'wheel_svg':
        def wheel():
            import run
            with tempfile.TemporaryDirectory(prefix='dossier-wheel-') as folder:
                files = run.render_chart_wheels(str(dossier.folder(key)/'a0/chart.json'), folder, 'wheel')
                return {theme: Path(path).read_text(encoding='utf-8') for theme, path in zip(('light', 'dark'), files)}
        return memo(versions('Chart_wheel/cli.js', 'run.py'), wheel)
    if name in ('acg', 'acg_geojson'):
        import compute_acg as ca
        deps = versions('Astrocartography/compute_acg.py', 'Astrocartography/acg_constants.py')
        if name == 'acg':
            return memo(deps, lambda: ca.compute_acg(chart))
        acg = get('acg')
        return memo({**deps, 'acg': digest(acg)}, lambda: ca.to_geojson(acg))
    if name in ('parans', 'parans_geojson'):
        import compute_parans as cp
        acg = get('acg')
        deps = {**versions('Astrocartography/compute_parans.py'), 'acg': digest(acg)}
        if name == 'parans':
            return memo(deps, lambda: cp.compute_parans(acg))
        parans = get('parans')
        return memo({**deps, 'parans':digest(parans)}, lambda: cp.to_geojson(parans))
    if name == 'city_scan':
        import acg_locate as al
        acg = get('acg')
        deps = {**versions('Astrocartography/acg_locate.py'), 'acg': digest(acg), 'gazetteer':file_hash(ROOT/'Astrocartography/gazetteer.json')}
        return memo(deps, lambda: al.city_scan(acg))
    if name in ('goal_scan', 'goal_heat'):
        import acg_goals as ag
        import acg_locate as al
        import run_acg
        acg, parans = get('acg'), get('parans')
        deps = {**versions('Astrocartography/acg_goals.py', 'Astrocartography/acg_constants.py'), 'acg':digest(acg), 'parans':digest(parans), 'affinity':ag.affinity_sha256(), 'gazetteer':file_hash(ROOT/'Astrocartography/gazetteer.json')}
        grid_path = ROOT/'Astrocartography/geo_grid.npz'
        deps['grid'] = file_hash(grid_path) if grid_path.exists() else 'absent'
        if acg.get('status') != 'ok' or not deps['affinity']:
            return memo(deps, lambda: {'status':'absent', 'absence':{'reason':'acg_absent' if acg.get('status') != 'ok' else 'affinity_missing'}})
        if name == 'goal_scan':
            return memo(deps, lambda: ag.goal_scan(acg, ag.load_affinity(), al.load_gazetteer(), run_acg._load_grid(), parans), codec=(ag.load_scan, ag.save_scan))
        if anchor not in ag.GOAL_ORDER:
            raise ValueError('Invalid heat goal')
        scan = get('goal_scan')
        return memo({**deps, 'scan':dossier.product_sha(key,'goal_scan')}, lambda: ag.heat_geojson(scan,anchor))

    if name in ('calendar', 'personal_events', 'day_scores', 'score_components', 'periods', 'best_days', 'collective_events', 'notification_candidates'):
        import run_calendar as rc
        import cal_corpus, build_transit_affinity as ba, best_days as bd, collective_events as ce
        if not isinstance(anchor, dict) or not anchor.get('tz'):
            raise ValueError('Calendar requires a local date and timezone')
        tz = anchor['tz']
        today = date.fromisoformat(anchor['date']) if anchor.get('date') else date.fromisoformat(anchor['start']) + timedelta(days=7)
        start = date.fromisoformat(anchor['start']) if anchor.get('start') else today - timedelta(days=7)
        if name != 'best_days':
            anchor = {'start':start.isoformat(), 'tz':tz}
        else:
            anchor = {'date':today.isoformat(), 'tz':tz}
        deps = {**versions('run_calendar.py','Calendar/cal_constants.py'), 'corpus':cal_corpus.corpus_sha()}
        if name == 'personal_events':
            deps['producer'] = file_hash(ROOT/'Calendar/personal_events.py', ROOT/'Calendar/cal_astro.py')
            return memo(deps, lambda: rc.ensure_events(chart,tz,start)[0],tier='b')
        if name == 'best_days':
            deps['producer'] = file_hash(ROOT/'Calendar/best_days.py', ROOT/'Calendar/cal_astro.py')
            deps['catalogue'] = file_hash(bd.CATALOGUE)
            return memo(deps,lambda:rc.ensure_best_days(chart,tz,today)[0],tier='b')
        if name == 'collective_events':
            first,last,jd0,jd1=rc.P.horizon(start,tz)
            years=sorted({rc.A.jd_to_utc(jd0-2).year,rc.A.jd_to_utc(jd1+2).year}|set(range(first.year,last.year+1)))
            # ensure_year is the existing shared read-through store, not a personal copy.
            from profile_dossier import locked
            docs=[]
            for year in years:
                with locked(dossier.root/'.locks'/f'collective-{year}.lock'):
                    docs.append(ce.ensure_year(year))
            return {'years':years,'events':[e for doc in docs for e in doc['events']]}
        events=get('personal_events',anchor)
        deps['events']=digest(events)
        deps['affinity']=file_hash(ba.OUT)
        deps['scoring'] = file_hash(ROOT/'Calendar/cal_scoring.py')
        if name == 'score_components':
            return memo(deps,lambda:rc.S.day_scores(events,chart,ba.load()),tier='b')
        if name in ('day_scores', 'periods'):
            full = get('score_components', anchor)
            deps['components'] = digest(full)
            return memo(deps,lambda:rc.S.public_scores(full) if name == 'day_scores' else rc.S.periods(full,events),tier='b')
        scores, periods=get('day_scores',anchor),get('periods',anchor)
        if name == 'calendar':
            return {'events':events,'scores':scores,'periods':periods,'best':None,'status':{'events':'dossier','scores':'dossier','best_days':'skipped'}}
        collective=get('collective_events',anchor)
        best=get('best_days',{'date':today.isoformat(),'tz':tz})
        deps.update(periods=digest(periods),collective=digest(collective),best=digest(best),templates=digest(rc.S.load_templates()))
        return memo(deps,lambda:rc.S.notifications(periods,events,collective['events'],rc.S.load_templates(),windows=bd.all_windows(best)),tier='b')
    if name.startswith('forecast_'):
        import compute_forecast as cf
        import ground_forecast as gf
        from profile_dossier import load_corpus
        horizon=name.rsplit('_',1)[-1]
        if horizon not in ('day','month','year') or not isinstance(anchor,dict):
            raise ValueError('Invalid forecast product')
        target=date.fromisoformat(anchor['date'])
        if horizon!='day':
            target=target.replace(day=1)
            anchor={'date':target.isoformat(),'tz':anchor['tz']}
        else:
            anchor={'date':target.isoformat(),'tz':anchor['tz'],'lat':anchor['lat'],'lon':anchor['lon']}
        deps=versions('Forecast_compute/compute_forecast.py','d_layer/compute_chart.py')
        if name.startswith('forecast_grounding_'):
            forecast=get('forecast_'+horizon,anchor)
            corpus=ROOT/'principles_grounding/all_principles_grounded.with_predictive.json'
            deps.update(forecast=digest(forecast),corpus=file_hash(corpus),grounding=file_hash(ROOT/'principles_grounding/ground_forecast.py'))
            return memo(deps,lambda:gf.ground_forecast(forecast,chart,load_corpus(str(corpus),deps['corpus']),cap=6,sim_floor=.35).forecast,tier='b')
        fixed=datetime(target.year,target.month,target.day,tzinfo=timezone.utc)
        return memo(deps,lambda:cf.compute_forecast(chart,target,horizon,window_tz=anchor['tz'],latitude=anchor.get('lat'),longitude=anchor.get('lon'),now=fixed,run_id='dossier-'+digest([key,name,anchor])[:16]),tier='b')
    if name == 'relationship_grounding':
        from ground_relationship import ground_relationship
        from profile_dossier import load_corpus
        other=anchor['other_chart_key']
        other_chart=dossier.get(other,'chart')
        corpus=ROOT/'principles_grounding/combined_relationship_principles_tagged.json'
        deps={**versions('principles_grounding/ground_relationship.py'),'corpus':file_hash(corpus),'other_chart':digest(other_chart)}
        # Orientation is a dependency: preserve the approved producer's A/B semantics.
        return memo(deps,lambda:ground_relationship(load_corpus(str(corpus),deps['corpus']),chart,other_chart).payload(),tier='c')
    raise ValueError('Unknown dossier product')
