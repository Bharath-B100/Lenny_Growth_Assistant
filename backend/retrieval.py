import re
from . import db

STOP = set('a an the and or in on for of to is are was were with from about can could should would how what why when where who tell me please write create generate essay html markdown document based this that these those it its into make turn advice explain give use using lenny podcast transcripts say says words word section sections approximately short long practical useful brief page checklist playbook'.split())

def terms(query):
    return list(dict.fromkeys(w.lower() for w in re.findall(r'[A-Za-z][A-Za-z0-9-]{2,}', query) if w.lower() not in STOP))[:24]

def retrieve(query, previous_question='', limit=6):
    tokens = terms(query)
    # Short follow-ups and transformations inherit the previous topical question.
    if len(tokens) < 3 or re.search(r'\b(this|that|these|those|above|it|essay|html|markdown)\b', query, re.I):
        tokens = list(dict.fromkeys(terms(previous_question) + tokens))[:24]
    if not tokens:
        return []
    tsquery = ' | '.join(tokens)
    rows = db.all_rows('''
      SELECT c.id AS chunk_id,c.episode_id,c.text,c.timestamp,e.title,e.guest,
             e.source_url,e.video_url,e.source_revision,
             ts_rank_cd(c.search, to_tsquery('english', %s), 32) +
             2 * ts_rank_cd(to_tsvector('english',c.text), to_tsquery('english', %s), 32) AS rank
      FROM chunks c JOIN episodes e ON e.id=c.episode_id
      WHERE c.search @@ to_tsquery('english', %s)
      ORDER BY (length(trim(e.guest))>3 AND position(lower(e.guest) in lower(%s))>0) DESC,
               rank DESC,c.id LIMIT 60
    ''', (tsquery,tsquery,tsquery,previous_question+' '+query))
    # A named guest in the conversation is a stronger topical signal than generic
    # words such as 'users' appearing in unrelated episodes.
    topic = (previous_question + ' ' + query).lower()
    def guest_match(row):
        name = row['guest'].lower().strip()
        return bool(len(name.split()) >= 2 and name in topic)
    guest_words={w for row in rows if guest_match(row) for w in terms(row['guest'])}
    topical=[t for t in tokens if t not in guest_words]
    def topical_overlap(row):
        body=row['text'].lower()
        return sum(bool(re.search(r'\b'+re.escape(t)+r'\b',body)) for t in topical)
    rows.sort(key=lambda row: (guest_match(row),topical_overlap(row),float(row['rank'])), reverse=True)
    selected, counts = [], {}
    # Refuse lexical coincidences on only one of several unrelated subject terms.
    for row in rows:
        hay = (row['text']+' '+row['title']).lower()
        matched = sum(t in hay for t in tokens)
        if len(tokens) >= 3 and matched < 2:
            continue
        # When the user explicitly names a guest, several passages from that
        # episode are more useful than unrelated hits from generic terms.
        episode_cap=4 if guest_match(row) else 2
        if counts.get(row['episode_id'],0) >= episode_cap:
            continue
        counts[row['episode_id']] = counts.get(row['episode_id'],0)+1
        row['id'] = f'S{len(selected)+1}'
        row['rank'] = float(row['rank'])
        selected.append(row)
        if len(selected) == limit:
            break
    return selected

def evidence_text(sources):
    return '\n\n'.join(f"[{s['id']}] {s['title']} — {s['guest']}\n{s['text']}" for s in sources)

