"""Catalogue-based Turkish/English lexical matching for PA validation."""
import re
import pa_catalogue as C

def fold(text,lang):
    return text.replace('İ','i').replace('I','ı').lower() if lang=='tr' else text.casefold()

def matches(text, table, lang):
    low=fold(text,lang); result=[]
    for key,label in table.items():
        for m in re.finditer(r'(?<!\w)'+re.escape(fold(label,lang))+r'(?!\w)',low):
            if lang=='tr' and label in ('Ay','Yay','Kova','Aslan','Balık','Koç','Terazi','kare'):
                original=text[m.start():m.end()]
                suffix=text[m.end():m.end()+1] in ("'",'’')
                nearby=low[max(0,m.start()-20):m.end()+20]
                if re.search(r'\b(bu|gelecek|geçen) ay\b',nearby): continue
                if not (suffix or (m.start()>0 and original[0].isupper()) or 'bur' in nearby): continue
            result.append((key,len(re.findall(r'\w+',text[:m.start()])),m.start(),m.end()))
    return result

def astro_terms(text,lang):
    found=matches(text,{**C.BODY[lang],**C.ANGLE[lang],**C.SIGN[lang]},lang)
    nouns=['burç','transit','retro','tutulma','Yeni Ay','Dolunay','gezegen','harita','yükselen'] if lang=='tr' else ['sign','transit','retrograde','eclipse','new moon','full moon','planet','chart','rising']
    return bool(found or matches(text,{x:x for x in nouns},lang))
