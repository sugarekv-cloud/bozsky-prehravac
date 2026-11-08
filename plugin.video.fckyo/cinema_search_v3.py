# -*- coding: utf-8 -*-
"""Language-aware Webshare search planning and verified classic discovery.

Titles are only search seeds. A movie or episode is never displayed unless
the search response contains a matching Webshare video file that passes the
existing availability checker.
"""
import re
from difflib import SequenceMatcher
from novinky_catalogue import normalize, parse_video_name
from smartsearch import variants

# Czech title / common original name / known release year.
# Search terms are NOT links or proof that a title is present on Webshare.
MOVIE_SEEDS=(
 ('Zelená míle','The Green Mile',1999),
 ('Avengers','The Avengers',2012),
 ('Vykoupení z věznice Shawshank','The Shawshank Redemption',1994),
 ('Forrest Gump','Forrest Gump',1994),
 ('Kmotr','The Godfather',1972),
 ('Pulp Fiction','Pulp Fiction',1994),
 ('Temný rytíř','The Dark Knight',2008),
 ('Avengers: Endgame','Avengers Endgame',2019),
 ('Avengers: Infinity War','Avengers Infinity War',2018),
 ('Schindlerův seznam',"Schindler's List",1993),
 ('Počátek','Inception',2010),
 ('Interstellar','Interstellar',2014),
 ('Pán prstenů: Společenstvo Prstenu','The Lord of the Rings The Fellowship of the Ring',2001),
 ('Pán prstenů: Dvě věže','The Lord of the Rings The Two Towers',2002),
 ('Pán prstenů: Návrat krále','The Lord of the Rings The Return of the King',2003),
 ('Sedm','Se7en',1995),
 ('Matrix','The Matrix',1999),
 ('Gladiátor','Gladiator',2000),
 ('Klub rváčů','Fight Club',1999),
 ('Nedotknutelní','Intouchables',2011),
 ('Titanic','Titanic',1997),
 ('Duna','Dune',2021),
 ('Duna: Část druhá','Dune Part Two',2024),
 ('Oppenheimer','Oppenheimer',2023),
 ('Avengers: Age of Ultron','Avengers Age of Ultron',2015),
 ('Avatar','Avatar',2009),
 ('Avatar: The Way of Water','Avatar The Way of Water',2022),
 ('Léon','Léon The Professional',1994),
 ('Dokonalý trik','The Prestige',2006),
 ('Mlčení jehňátek','The Silence of the Lambs',1991),
 ('Zachraňte vojína Ryana','Saving Private Ryan',1998),
 ('Terminátor 2: Den zúčtování','Terminator 2 Judgment Day',1991),
 ('Jurský park','Jurassic Park',1993),
 ('Návrat do budoucnosti','Back to the Future',1985),
 ('Nespoutaný Django','Django Unchained',2012),
 ('Hanebný pancharti','Inglourious Basterds',2009),
 ('Život je krásný','La vita è bella',1997),
 ('Cesta do fantazie','Spirited Away',2001),
 ('Toy Story: Příběh hraček','Toy Story',1995),
 ('Joker','Joker',2019),
 ('Whiplash','Whiplash',2014),
 ('Parazit','Parasite',2019),
 ('Vlk z Wall Street','The Wolf of Wall Street',2013),
 ('Zelená kniha','Green Book',2018),
 ('Hodný, zlý a ošklivý','The Good the Bad and the Ugly',1966),
 ('Mafiáni','Goodfellas',1990),
 ('Obvyklí podezřelí','The Usual Suspects',1995),
)
SHOW_SEEDS=(
 ('Perníkový táta','Breaking Bad',2008),
 ('Hra o trůny','Game of Thrones',2011),
 ('Černobyl','Chernobyl',2019),
 ('Bratrstvo neohrožených','Band of Brothers',2001),
 ('The Last of Us','The Last of Us',2023),
 ('Stranger Things','Stranger Things',2016),
 ('Temný případ','True Detective',2014),
 ('Narcos','Narcos',2015),
 ('Zaklínač','The Witcher',2019),
 ('Better Call Saul','Better Call Saul',2015),
 ('Sherlock','Sherlock',2010),
 ('Peaky Blinders','Peaky Blinders',2013),
 ('Rod draka','House of the Dragon',2022),
 ('The Boys','The Boys',2019),
 ('Andor','Andor',2022),
 ('Přátelé','Friends',1994),
 ('Kancl','The Office',2005),
 ('Černé zrcadlo','Black Mirror',2011),
)
ALIASES={normalize(n):tuple(dict.fromkeys(x for x in (n,o) if x))
         for n,o,y in MOVIE_SEEDS+SHOW_SEEDS}
for n,o,y in MOVIE_SEEDS+SHOW_SEEDS:
    ALIASES[normalize(o)]=tuple(dict.fromkeys(x for x in (n,o) if x))


SEARCH_YEAR = re.compile(r'^(.*?)\s*(?:\(|\[)?((?:19|20)\d{2})(?:\)|\])?\s*$')


def title_and_year(query):
    """Accept 'The Matrix (1999)', 'Matrix.1999' and bare title searches."""
    query=str(query or '').strip()
    match=SEARCH_YEAR.match(re.sub(r'[._]+', ' ',query))
    if match and normalize(match.group(1)):
        return match.group(1).strip(' ._-'),match.group(2)
    return query,''


_SEARCH_EPISODE = re.compile(
    r'(?i)(?<![a-z0-9])s(\d{1,2})[ ._-]*e(\d{1,3})(?!\d)|'
    r'(?i:(?<![a-z0-9])(\d{1,2})x(\d{1,3})(?!\d))')


def search_intent(query):
    """Parse user-entered title, optional release year and episode.

    Examples: 'Stranger Things S01E02', 'Show.1x03', 'Duna (2021)'.
    Keep the original search text for display/cache identity, but never
    include season/episode tokens when querying Webshare by SERIES title.
    """
    text=str(query or '').strip()
    match=_SEARCH_EPISODE.search(text)
    season=episode=None
    if match:
        season=int(match.group(1) or match.group(3))
        episode=int(match.group(2) or match.group(4))
        text=(text[:match.start()]+' '+text[match.end():]).strip(' ._-')
    title,year=title_and_year(text)
    return title,year,season,episode


def candidate_names(query, metadata=None):
    """Localized/original names, known sequels and safe franchise expansions.

    Metadata never creates a playable result: names only generate search terms.
    """
    title,_=title_and_year(query)
    names=[]
    seen=set()
    def add(value):
        value=str(value or '').strip()
        key=normalize(value)
        if key and key not in seen:
            seen.add(key)
            names.append(value)
    add(title)
    for value in ALIASES.get(normalize(title),()):
        add(value)
    if metadata and isinstance(metadata,dict):
        for key in ('title','original','original_title','name'):
            add(metadata.get(key))
    # "Pán prstenů" or "Duna" should also discover individual film parts,
    # even if their English original filenames lack any Czech words.
    prefix=normalize(title)
    if len(prefix)>=4:
        for cz,original,_year in MOVIE_SEEDS+SHOW_SEEDS:
            if any(normalize(n).startswith(prefix+' ') for n in (cz,original)):
                add(cz)
                add(original)
                if len(names)>=28:
                    break
    for value in tuple(names):
        norm=normalize(value)
        if norm.startswith('the '):
            add(value.split(' ',1)[1])
    return names


def cached_title_aliases(query, home, limit=14):
    """Find Czech/original title spellings from already verified local cards.

    Never introduce unmatched catalogue titles: aliases only generate actual
    Webshare queries and matched files still pass availability verification.
    """
    target=normalize(title_and_year(query)[0])
    if len(target)<3 or not isinstance(home,dict):
        return []
    results=[]
    seen=set()
    for card in (home.get('_all_movies') or [])+(home.get('_all_shows') or [])+(
                home.get('movies') or [])+(home.get('shows') or []):
        if not isinstance(card,dict):
            continue
        titles=[str(card.get(k) or '') for k in ('title','raw','original')]
        normalized=[normalize(name) for name in titles]
        if not any(n==target or n.startswith(target+' ') or
                   target.startswith(n+' ') for n in normalized if n):
            continue
        for name in titles:
            key=normalize(name)
            if key and key not in seen:
                seen.add(key)
                results.append(name)
                if len(results)>=limit:
                    return results
    return results


def query_plan(query, metadata=None, limit=18):
    """Interleave aliases BEFORE generating dotted/ASCII spelling variants.

    Old ordering exhausted the first 10 requests with spellings of one title,
    so an English filename could be missed even when its alias was known.
    """
    titles=candidate_names(query,metadata)
    result=[]
    seen=set()
    def add(value):
        value=str(value or '').strip()
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    # Search each language/title first, not every spelling of just one title.
    for title in titles:
        add(title)
        if len(result)>=limit:
            return result[:limit]
    for title in titles:
        for value in variants(title)[1:]:
            add(value)
            if len(result)>=limit:
                return result[:limit]
    return result[:limit]


def episode_query_plan(query, season, episode, metadata=None, limit=18):
    """Try an exact episode Webshare filename search before broad title pages.

    This uses the official Webshare filename search, not an assumed
    episode-index API. The ordinary title variants remain as fallbacks.
    """
    base=query_plan(query,metadata,limit=limit)
    if not base or season is None or episode is None:
        return base
    tag='S%02dE%02d'%(int(season),int(episode))
    alt='%dx%02d'%(int(season),int(episode))
    targeted=[]
    for title in base[:3]:
        targeted.append(title+' '+tag)
    for title in base[:2]:
        targeted.append(title+'.'+tag)
        targeted.append(title+' '+alt)
    return list(dict.fromkeys(targeted+base))[:limit]


def search_suggestions(query, remote=None, home=None, limit=5):
    """Suggest corrected TITLE searches, never invented playable releases.

    Remote Webshare /suggest results are input hints, not availability
    evidence. Revalidate every selected suggestion through normal search.
    """
    requested=normalize(query)
    if len(requested)<4:
        return []
    pool=[]
    for title,original,year in MOVIE_SEEDS+SHOW_SEEDS:
        pool.extend((title,original))
    if isinstance(home,dict):
        for item in (home.get('_all_movies') or [])+(home.get('_all_shows') or []):
            if isinstance(item,dict) and item.get('ident') and item.get('files'):
                pool.extend(str(item.get(k) or '') for k in ('title','raw','original'))
    for raw in (remote or [])[:25]:
        if isinstance(raw,dict):
            raw=raw.get('value') or raw.get('name') or ''
        raw=str(raw or '').strip()
        if not raw:
            continue
        parsed=parse_video_name(raw)
        pool.append(parsed['title'] if parsed else raw)
    unique={}
    for item in pool:
        title=re.sub(r'[\[\]<>\r\n\t]', ' ',str(item or '')).strip()[:90]
        key=normalize(title)
        if not key or key==requested or len(key)<4:
            continue
        score=SequenceMatcher(None,requested,key).ratio()
        # Very short incomplete names need a stronger prefix match.
        if key.startswith(requested+' ') and len(requested)>=5:
            score=max(score,0.82)
        if score>=0.75 and (key not in unique or score>unique[key][0]):
            unique[key]=(score,title)
    return [item[1] for item in sorted(unique.values(),
            key=lambda pair:(-pair[0],len(pair[1]),pair[1].casefold()))[:limit]]


def is_title_match(parsed, names, kind=None, year=None):
    """Match whole title or a bounded prefix/suffix (Avengers -> Endgame)."""
    if not parsed:
        return False
    if kind=='movie' and parsed['kind']!='movie':
        return False
    if kind=='show' and parsed['kind'] not in ('episode','series'):
        return False
    if year and parsed.get('year') and str(year)!=str(parsed['year']):
        return False
    got=normalize(parsed['title'])
    targets=[normalize(s) for s in names if s]
    return any(got==t or got.startswith(t+' ') or got.endswith(' '+t)
               for t in targets if len(t)>=3)


def matching_files(files, names, kind=None, year=None):
    from cinema_content_filter import safe_file
    output=[];seen=set()
    for f in files or []:
        if not safe_file(f):
            continue
        ident=str(f.get('ident') or '')
        if not ident or ident in seen or str(f.get('password','0'))=='1':
            continue
        if str(f.get('removed','0'))=='1' or str(f.get('available','1'))=='0':
            continue
        if str(f.get('adult','0'))=='1' or str(f.get('copyrighted','0'))=='1':
            continue
        p=parse_video_name(f.get('name',''))
        if is_title_match(p,names,kind,year):
            seen.add(ident)
            output.append(f)
    return output



def localized_title(raw, kind='movie', year=None):
    """Return a known Czech title only for a precise release match."""
    source=MOVIE_SEEDS if kind=='movie' else SHOW_SEEDS
    name=normalize(raw)
    for cz,original,release_year in source:
        # An exact original name (or its optional English article) is required.
        variants_of_name={normalize(cz),normalize(original)}
        if normalize(original).startswith('the '):
            variants_of_name.add(normalize(original)[4:])
        if name not in variants_of_name:
            continue
        if year and kind=='movie' and str(year)!=str(release_year):
            continue
        return {'title':cz,'original':original,
                'year':str(release_year)}
    return None

def seed_batch(catalogue, offset=0, count=8):
    """Finite progress through classics, with the first batch covering core titles."""
    if not catalogue:return []
    return [catalogue[(offset+i)%len(catalogue)] for i in range(min(count,len(catalogue)))]
