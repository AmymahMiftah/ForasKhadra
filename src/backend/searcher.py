import re
import numpy as np
from datetime import date
from typing import Optional
from embedder import embed_queries, embed_passages

# Arabic normalisation
ARABIC_CORRECTIONS = {
    "الاصتناعي": "الاصطناعي",
    "الاصطناعى": "الاصطناعي",
    "الاصناعي": "الاصطناعي",
    "اصطناعى": "اصطناعي",
    "الاصتناعى": "الاصطناعي",
    "الاصطنعي": "الاصطناعي",
    "الاصطنائي": "الاصطناعي",
    "اصتناعي": "اصطناعي",
    "اصناعي": "اصطناعي",
    "المتقفرة": "المتوفرة",
    "المتوقفرة": "المتوفرة",
    "المتوفره": "المتوفرة",
    "منحه": "منحة",
    "منحت": "منحة",
    "وضيفة": "وظيفة",
    "وظيفه": "وظيفة",
    "وضيفه": "وظيفة",
    "دراسه": "دراسة",
    "تدريبي": "تدريب",
    "تدريبه": "تدريب",
    "برنامح": "برنامج",
    "جامعه": "جامعة",
    "فرصه": "فرصة",
    "ابحت": "ابحث",
    "بحت": "بحث",
}


def normalise_arabic(text: str) -> str:
    words = text.split()
    corrected = [ARABIC_CORRECTIONS.get(w, w) for w in words]
    text = " ".join(corrected)
    text = re.sub(r'[\u064B-\u065F\u0670\u0640]', '', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ؤ', 'و', text)
    text = re.sub(r'ئ', 'ي', text)
    return text


# Expiry filter ──
def filter_expired(opportunities: list) -> list:
    today = date.today()
    active = []
    for o in opportunities:
        deadline_str = o.get("deadline", "")
        if not deadline_str:
            active.append(o)
            continue
        try:
            if date.fromisoformat(deadline_str) >= today:
                active.append(o)
        except ValueError:
            active.append(o)
    return active


# synonym expansion 
SYNONYMS = {
    "بريطانيا": ["uk", "united", "kingdom", "britain", "england"],
    "بريطاني": ["uk", "united", "kingdom", "british"],
    "بريطانية": ["uk", "united", "kingdom", "british"],
    "انجلترا": ["uk", "united", "kingdom", "england"],
    "امريكا": ["usa", "united", "states", "america"],
    "امريكي": ["usa", "united", "states", "american"],
    "الواليات": ["usa", "united", "states", "america"],
    "المتحدة": ["united", "states", "kingdom"],
    "المانيا": ["germany", "german", "berlin"],
    "فرنسا": ["france", "french", "paris"],
    "كندا": ["canada", "canadian"],
    "اليابان": ["japan", "japanese"],
    "الصين": ["china", "chinese", "beijing"],
    "اوروبا": ["europe", "european", "eu"],
    "مصر": ["egypt", "egyptian", "cairo"],
    "السعودية": ["saudi", "arabia", "riyadh"],
    "سعودية": ["saudi", "arabia"],
    "الامارات": ["uae", "dubai", "abu", "dhabi", "emirates"],
    "دبي": ["dubai", "uae", "emirates"],
    "تركيا": ["turkey", "turkish"],
    "كوريا": ["korea", "korean", "south"],
    "استراليا": ["australia", "australian"],
    "هولندا": ["netherlands", "dutch", "amsterdam"],
    "ايطاليا": ["italy", "italian"],
    "سويسرا": ["switzerland", "swiss", "geneva"],
    "ليبيا": ["libya", "libyan", "tripoli", "benghazi"],
    "الاردن": ["jordan", "amman"],
    "لبنان": ["lebanon", "beirut"],
    "فلسطين": ["palestine", "palestinian"],
    "الهند": ["india", "indian"],
    "باكستان": ["pakistan", "pakistani"],
    "منحة": ["scholarship", "grant", "fellowship", "award"],
    "منح": ["scholarship", "grant", "fellowship"],
    "تدريب": ["internship", "training", "intern"],
    "وظيفة": ["job", "career", "position", "employment"],
    "وظائف": ["jobs", "careers", "positions"],
    "زمالة": ["fellowship", "postdoc", "residency"],
    "مدرسة": ["school", "program", "course"],
    "صيفية": ["summer", "seasonal"],
    "برنامج": ["program", "programme"],
    "دكتوراه": ["phd", "doctorate", "doctoral"],
    "ماجستير": ["masters", "master", "postgraduate", "graduate"],
    "بكالوريوس": ["undergraduate", "bachelor", "bachelors"],
    "دراسات": ["graduate", "postgraduate", "studies"],
    "عليا": ["graduate", "postgraduate", "advanced"],
    "ذكاء": ["ai", "artificial", "intelligence", "machine"],
    "اصطناعي": ["ai", "artificial", "intelligence"],
    "بيانات": ["data", "science", "analytics"],
    "طاقة": ["energy", "renewable", "sustainable"],
    "متجددة": ["renewable", "sustainable", "green"],
    "صحة": ["health", "medical", "medicine", "healthcare"],
    "قانون": ["law", "legal", "justice"],
    "اقتصاد": ["economics", "economy", "finance"],
    "هندسة": ["engineering", "engineer"],
    "برمجة": ["programming", "software", "coding", "developer"],
    "امن": ["security", "cybersecurity", "safety"],
    "سيبراني": ["cybersecurity", "security", "cyber"],
    "بيئة": ["environment", "environmental", "climate"],
    "مناخ": ["climate", "environment", "sustainability"],
    "ريادة": ["entrepreneurship", "startup", "innovation"],
    "اعمال": ["business", "entrepreneurship", "management"],
    "الامم": ["united", "nations", "un", "unicef", "undp"],
    "يونيسف": ["unicef", "children"],
    "اليونسكو": ["unesco", "education", "culture"],
    "جوجل": ["google", "alphabet"],
    "مايكروسوفت": ["microsoft", "azure"],
    "امازون": ["amazon", "aws"],
    "ميتا": ["meta", "facebook", "instagram"],
    "ممولة": ["funded", "fully", "scholarship", "stipend"],
    "مجانية": ["free", "funded"],
    "مدفوعة": ["paid", "stipend", "salary"],
    "شباب": ["youth", "young", "students"],
    "طالب": ["students", "undergraduate", "graduate"],
    "خريجين": ["graduates", "alumni", "recent"],
    "نساء": ["women", "female", "gender"],
    "مراة": ["women", "female", "gender"],
    "عرب": ["arab", "arabic", "mena"],
    "عربية": ["arab", "arabic", "mena"],
    "chevening": ["chevening", "uk", "britain", "scholarship", "masters", "british", "شيفينغ"],
    "شيفينغ": ["chevening", "uk", "britain", "scholarship", "masters", "british"],
    "fulbright": ["fulbright", "usa", "scholarship", "graduate", "masters", "phd", "فولبرايت"],
    "فولبرايت": ["fulbright", "usa", "scholarship", "graduate"],
    "daad": ["daad", "germany", "scholarship", "renewable", "energy", "داد"],
    "داد": ["daad", "germany", "scholarship", "renewable", "energy"],
    "erasmus": ["erasmus", "europe", "eu", "scholarship", "exchange"],
    "gates": ["gates", "cambridge", "scholarship", "phd", "masters"],
    "غيتس": ["gates", "cambridge", "scholarship"],
    "rhodes": ["rhodes", "oxford", "scholarship"],
    "رودس": ["rhodes", "oxford", "scholarship"],
    "schwarzman": ["schwarzman", "china", "tsinghua", "leadership"],
    "شوارزمان": ["schwarzman", "china", "leadership"],
    "kaust": ["kaust", "saudi", "stem", "graduate"],
    "كاوست": ["kaust", "saudi", "stem", "graduate"],
    "climate": ["climate", "environment", "sustainability", "green", "renewable"],
    "change": ["climate", "change", "sustainability"],
    "sustainability": ["sustainability", "climate", "environment", "green", "renewable"],
    "green": ["green", "renewable", "sustainability", "environment", "climate"],
    "تغير": ["change", "climate", "sustainability"],
    "احتباس": ["climate", "warming", "environment"],
    "كربون": ["carbon", "climate", "environment", "sustainability"],
    "قدرات": ["capacity", "building", "skills", "training", "youth"],
    "بناء": ["building", "capacity", "development"],
    "ليبي": ["libya", "libyan", "tripoli", "benghazi"],
    "capacity": ["capacity", "building", "skills"],
    "building": ["building", "capacity", "development"],
    "undp": ["undp", "un", "development", "youth", "libya"],
}


def expand_query(query: str) -> set:
    """Normalise then expand Arabic query words with English synonyms"""
    normalised = normalise_arabic(query)
    words = set(re.findall(r'\w+', normalised.lower()))
    expanded = set(words)
    for word in words:
        if word in SYNONYMS:
            expanded.update(SYNONYMS[word])
    return expanded


# ─Keyword boost 
def keyword_boost(query: str, opp: dict, boost: float = 0.08) -> float:
    
    query_words = expand_query(query)
    target_text = " ".join([
        opp.get("title", ""),
        opp.get("title_ar", ""),
        opp.get("location", ""),
        opp.get("organisation", ""),
        " ".join(opp.get("tags", []))
    ]).lower()
    target_words = set(re.findall(r'\w+', target_text))
    matches = query_words & target_words
    if not matches:
        return 0.0
    ratio = len(matches) / max(len(query_words), 1)
    return boost * ratio


# Core search functions
def cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.dot(a, b.T)


def extract_highlights_batch(query_emb: np.ndarray, opportunities: list) -> list:

    all_sentences = []
    sentence_map = []

    for i, opp in enumerate(opportunities):
        sentences = [s.strip() for s in opp["description"].split(".") if len(s.strip()) > 15]
        if not sentences:
            sentences = [opp["description"][:150]]
        sentence_map.append((i, len(sentences)))
        all_sentences.extend(sentences)

    if not all_sentences:
        return ["" for _ in opportunities]

    all_embs = embed_passages(all_sentences, batch_size=64)
    scores = cosine_sim(query_emb, all_embs)[0]

    highlights = []
    cursor = 0
    for opp_idx, count in sentence_map:
        opp_scores = scores[cursor: cursor + count]
        best = int(np.argmax(opp_scores))
        sentences = [s.strip() for s in opportunities[opp_idx]["description"].split(".") if len(s.strip()) > 15]
        if not sentences:
            sentences = [opportunities[opp_idx]["description"][:150]]
        highlights.append(sentences[best])
        cursor += count

    return highlights


# Score threshold
SCORE_THRESHOLD = 0.65
MAX_RESULTS = 30


def search(
    query: str,
    opportunities: list,
    embeddings_matrix: np.ndarray, # separate matrix
    top_k: Optional[int] = None,
    extract_highlight: bool = True,
) -> dict:
 
    active = opportunities

    if not active:
        return {"query": query, "results": [], "total_results": 0, "expired_filtered": 0}

    normalised_query = normalise_arabic(query)
    query_emb = embed_queries([normalised_query])

   
    semantic_scores = cosine_sim(query_emb, embeddings_matrix)[0]

    final_scores = np.array([
        semantic_scores[i] + keyword_boost(query, active[i])
        for i in range(len(active))
    ])

    sorted_indices = np.argsort(final_scores)[::-1]

    if top_k is not None:
        qualified = list(sorted_indices[:top_k])
    else:
        qualified = [
            i for i in sorted_indices
            if final_scores[i] >= SCORE_THRESHOLD
        ][:MAX_RESULTS]

    if not qualified:
        qualified = list(sorted_indices[:3])

    top_opps = [active[i] for i in qualified]
    top_scores = [float(final_scores[i]) for i in qualified]

    if extract_highlight:
        highlights = extract_highlights_batch(query_emb, top_opps)
    else:
        highlights = [""] * len(top_opps)

    results = []
    for opp, score, highlight in zip(top_opps, top_scores, highlights):
        results.append({
            "title": opp["title"],
            "title_ar": opp.get("title_ar", opp["title"]),
            "type": opp["type"],
            "organisation": opp["organisation"],
            "deadline": opp["deadline"],
            "location": opp.get("location", ""),
            "link": opp["link"],
            "tags": opp.get("tags", []),
            "highlight": highlight,
            "score": score,
            "id": opp.get("id", ""),
        })

    return {
        "query": query,
        "results": results,
        "total_results": len(results),
        "expired_filtered": 0,
    }