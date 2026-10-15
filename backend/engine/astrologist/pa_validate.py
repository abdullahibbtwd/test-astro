"""Validate structured answers against only this turn's deterministic evidence."""
from datetime import date
import re
import jsonschema
import pa_catalogue as C
from pa_planner import obj, enum
from pa_lexicon import fold, matches, astro_terms
from ar_validate import AV2_TR, AV2_EN, AV8_TR, AV8_EN, FORBIDDEN_READER_TOKENS
from acg_views import RV4_TR, RV4_EN
ANSWER_SCHEMA=obj({'segments':{'type':'array','minItems':1,'maxItems':10,'items':obj({'text':{'type':'string','minLength':1,'maxLength':4000,'pattern':r'^[^\r\n]*$'},'para':{'type':'integer','minimum':0,'maximum':2},'kind':enum(['astro','meta']),'trace':{'type':'array','items':{'type':'string'},'maxItems':40}})},'card_refs':{'type':'array','items':{'type':'string'},'maxItems':3},'link_refs':{'type':'array','items':{'type':'string'},'maxItems':3}})
BOUNDS={'fact':((20,60),(40,90)),'interpretive':((90,180),(150,260)),'timing':((80,170),(140,240)),'place':((80,160),(140,240)),'compatibility':((100,200),(160,260)),'mixed':((120,220),(180,280))}
def bounds(plan):
    kind={'chart_fact':'fact','natal_topic':'interpretive','basics':'interpretive','place':'place','recommend':'place','compatibility':'compatibility','mixed':'mixed'}.get(plan['intent'],'timing')
    return BOUNDS[kind][plan.get('depth')=='more']
EXTRA_TR=['kaderiniz','kaderinizde','yıldızlar böyle istiyor','evleneceksiniz','boşanacaksınız','hamile kalacaksınız','zengin olacaksınız','işten çıkarılacaksınız','ayrılacaksınız','mutlaka olacak','yatırım yapın','hisse alın','hisselerinizi satın','ilacı bırakın','teşhis','dava açın','hastalık','kanser','ameliyat']
EXTRA_EN=['destined','your fate','the stars say','you will marry','you will divorce','you will get pregnant','you will be rich','you will be fired','you will break up','will definitely','invest in','buy shares','sell your shares','stop taking','diagnos','you should sue','illness','disease','surgery']
MASK=FORBIDDEN_READER_TOKENS+['Hellenistic','Ottoman','Arabic','classical astrology','traditional astrology','modern astrology','decan','dignity','sect','Helenistik','Osmanlı','Arap','klasik astroloji','geleneksel astroloji','modern astroloji','dekan']
INTERNAL=['principle','record','corpus','evidence','trace','tool','JSON','ilke','kayıt','kanıt','araç']
MONTHS={'en':'January February March April May June July August September October November December'.split(),'tr':'Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık'.split()}

def phrase(text,term,lang,prefix=False):
    return re.search(r'(?<!\w)'+re.escape(fold(term,lang))+(r'' if prefix else r'(?!\w)'),fold(text,lang))

def claims(raw):
    result={k:set() for k in ('sign','house','aspect')}
    def visit(x):
        if isinstance(x,list):
            for row in x: visit(row)
        elif isinstance(x,dict):
            for k in result:
                for row in x.get('claims',{}).get(k,[]): result[k].add(tuple(row))
            body=x.get('body') or x.get('angle')
            if body:
                if x.get('sign'): result['sign'].add((body,str(x['sign']).lower()))
                if x.get('house'): result['house'].add((body,int(x['house'])))
            if x.get('kind')=='aspect': result['aspect'].add((x['a'],x['b'],x['type']))
            if x.get('kind')=='transit': result['aspect'].add((x['t'],x['n'],x['a']))
            for k,v in x.items():
                if k!='claims' and isinstance(v,(dict,list)): visit(v)
    visit(raw)
    return result

def required_names(packs,lang,subject=None):
    """Keep the composer and PV12 aligned on exact, user-supplied display labels."""
    names=[p['_internal'].get('other_label') for p in packs if p['tool']=='compatibility']
    for p in packs:
        if p['tool']=='place':
            row=p['_internal'].get('place',{})
            names.append((row.get('name_tr') or row.get('name')) if lang=='tr' else row.get('name'))
    if subject and not subject.get('is_self',True): names.append(subject.get('label'))
    return list(filter(None,names))

def forbidden_phrases(lang):
    return AV2_TR+AV8_TR+RV4_TR+EXTRA_TR if lang=='tr' else AV2_EN+AV8_EN+RV4_EN+EXTRA_EN

def validate_answer(answer,packs,plan,lang,subject=None,allow_short=False,feedback=None):
    errors=[]
    def fail(rule,index=-1,**details):
        if not any(e['rule']==rule and e['segment']==index for e in errors): errors.append({'rule':rule,'segment':index})
        # Repair-only details stay out of the persisted audit and public stream.
        if feedback is not None and details: feedback.append({'rule':rule,'segment':index,**details})
    try: jsonschema.validate(answer,ANSWER_SCHEMA)
    except jsonschema.ValidationError: return [{'rule':'PV1_schema','segment':-1}]
    evidence={x['id']:x for p in packs for kind in ('facts','records','items','prose') for x in p[kind]}
    internal={key:value for p in packs for kind in ('facts','records','items') for key,value in p['_internal'].get(kind,{}).items()}
    for kind,key in (('card_candidates','card_refs'),('link_candidates','link_refs')):
        ids={c['id'] for p in packs for c in p[kind]}
        if any(i not in ids for i in answer[key]): fail('PV2_candidate')
    words=sum(len(s['text'].split()) for s in answer['segments']); lo,hi=bounds(plan)
    if words<(lo*.6 if allow_short else lo*.8) or words>hi*1.2: fail('PV1_length')
    paragraphs={}
    for i,s in enumerate(answer['segments']):
        text=s['text']; trace=s['trace']; paragraphs.setdefault(s['para'],[]).append(text)
        invalid_ids=[t for t in trace if t not in evidence]
        if invalid_ids: fail('PV2_trace',i,invalid_ids=invalid_ids)
        if (astro_terms(text,lang) or s['kind']=='astro') and (s['kind']!='astro' or not trace): fail('PV3_untraced',i)
        allowed=claims([internal.get(t,{}) for t in trace])
        for sentence in re.split(r'(?<=[.!?])\s+',text):
            bodies=matches(sentence,{**C.BODY[lang],**C.ANGLE[lang]},lang)
            for b,bt,_,_ in bodies:
                for sign,st,_,_ in matches(sentence,C.SIGN[lang],lang):
                    if 0<=st-bt<=6 and not any(bt<pos<st for _,pos,_,_ in bodies) and (b,sign) not in allowed['sign']: fail('PV4_claim_unsupported',i)
                for house,ht,_,_ in matches(sentence,C.AREA[lang],lang):
                    if abs(ht-bt)<=6 and (b,house) not in allowed['house']: fail('PV4_claim_unsupported',i)
                for other,ot,_,_ in bodies:
                    for aspect,at,_,_ in matches(sentence,C.ASPECT[lang],lang):
                        if bt<at<ot and ot-bt<=8 and (b,other,aspect) not in allowed['aspect'] and (other,b,aspect) not in allowed['aspect']: fail('PV4_claim_unsupported',i)
        traced_items=[evidence[t] for t in trace if t in evidence and 'dates' in evidence[t]]
        labels={x.get('band_label') for x in traced_items if x.get('band_label')}
        # Generic adjectives are only grades when attached to a timing/place judgement.
        all_labels={v for table in (C.GRADE,C.DAY_BAND,C.TONE,C.PLACE_BAND) for v in table[lang].values()}
        for label in all_labels if (traced_items or plan['intent'] in ('day','span','when','best_days','calendar_item','place','recommend','mixed')) else ():
            if phrase(text,label,lang) and not any(phrase(label,v,lang) or phrase(v,label,lang) for v in labels):
                if label not in ('good','iyi','quiet','sakin'): fail('PV5_band',i,label=label,allowed_labels=sorted(labels))
        if i==next((j for j,x in enumerate(answer['segments']) if x['kind']=='astro'),-1) and plan.get('reframe')=='yes_no' and not any(phrase(text,label,lang) for label in labels): fail('PV5_verdict',i)
        def date_ok(m):
            days=[int(m.group(1))]
            if m.group(2): days=list(range(days[0],int(m.group(2))+1))
            month=next(n+1 for n,name in enumerate(MONTHS[lang]) if fold(name,lang)==fold(m.group(3),lang))
            for day in days:
                okay=False
                for item in traced_items:
                    dates=[]
                    for value in item['dates']:
                        try: dates.append(date.fromisoformat(value[:10]))
                        except ValueError: pass
                    for year in ({int(m.group(4))} if m.group(4) else {d.year for d in dates}):
                        try: d=date(year,month,day)
                        except ValueError: continue
                        if dates and min(dates)<=d<=max(dates): okay=True
                if not okay: fail('PV6_date',i)
            return ''
        pattern=r'\b(\d{1,2})(?:\s*[–-]\s*(\d{1,2}))?\s+('+ '|'.join(MONTHS[lang])+r')(?:\s+(\d{4}))?\b'
        remainder=re.sub(pattern,date_ok,text,flags=re.I)
        if re.search(r'\d|[°%]|\b(orb|degrees?|derece|km|kilometre|miles?)\b',remainder,re.I): fail('PV6_number',i)
        blocked=[t for t in forbidden_phrases(lang) if phrase(text,t,lang,prefix=(lang=='tr' or t=='diagnos'))]
        if blocked: fail('PV7_forbidden',i,phrases=blocked)
        # Cancer is also a sign: illness use remains forbidden; traced sign use is allowed.
        if lang=='en' and phrase(text,'cancer',lang) and not any(s=='cancer' for _,s in allowed['sign']): fail('PV7_forbidden',i)
        if any(phrase(text,t,lang) for t in MASK): fail('PV8_mask',i)
        if any(phrase(text,t,lang) for t in INTERNAL) or re.search(r'\b[rfipkl]:|\b(?:modern|classical|transit)-[\w-]+',text): fail('PV9_internal',i)
        if re.search(r'[#*_`]|(?m:^[ \t]*(?:- |\d+\. ))|[\U0001F000-\U0001FAFF]|[\u2600-\u27bf]',text) or '\n' in text: fail('PV10_plain',i)
        if plan['intent']!='compatibility' and any(t.startswith('f:other:') for t in trace): fail('PV13_other',i)
    for texts in paragraphs.values():
        words=re.findall(r'\w+',fold(' '.join(texts),lang))
        tr=sum(w in {'ve','bir','bu','için','ile','olarak','daha','sizin','ama','değil'} for w in words)
        en=sum(w in {'the','and','your','you','with','this','is','can','of','in','for'} for w in words)
        if len(words)>12 and ((lang=='tr' and en>=3 and en>tr*2) or (lang=='en' and tr>=3 and tr>en*2)): fail('PV11_language')
    full=' '.join(s['text'] for s in answer['segments'])
    for name in required_names(packs,lang,subject):
        if fold(name,lang) not in fold(full,lang): fail('PV12_naming')
    if [s['para'] for s in answer['segments']]!=sorted(s['para'] for s in answer['segments']): fail('PV10_paragraph_order')
    return errors
