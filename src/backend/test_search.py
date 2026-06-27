import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from data_loader import load_opportunities
from searcher import search, normalise_arabic

opportunities = load_opportunities()

# normalisation tests 
def test_normalise_typo_ai():
    assert normalise_arabic("الاصتناعي") == "الاصطناعي"

def test_normalise_alef():
    assert normalise_arabic("أحمد") == "احمد"

def test_normalise_diacritics():
    result = normalise_arabic("مَنْحَة")
    assert "َ" not in result
    assert "ْ" not in result

def test_normalise_alef_maksura():
    assert normalise_arabic("يصفتى") == "يصفتي"

# earch quality tests 
def top_titles(query, n=3):
    results = search(query, opportunities, top_k=n)["results"]
    return [r["title_ar"] for r in results]

def test_germany_scholarship():
    titles = top_titles("منحة في المانيا", n=3)
    assert any("داد" in t or "المانيا" in t or "DAAD" in t
               for t in titles), f"Expected Germany result, got: {titles}"

def test_uk_scholarship():
    titles = top_titles("منحة في بريطانيا", n=3)
    assert any("شيفينغ" in t or "كومنولث" in t or "أكسفورد" in t
               for t in titles), f"Expected UK result, got: {titles}"

def test_ai_internship_arabic():
    titles = top_titles("تدريب في الذكاء الاصطناعي", n=3)
    assert any("ذكاء" in t or "AI" in t or "تعلم" in t
               for t in titles), f"Expected AI result, got: {titles}"

def test_ai_internship_typo():
    titles = top_titles("تدريب في الاصتناعي", n=3)
    assert any("ذكاء" in t or "AI" in t or "تعلم" in t
               for t in titles), f"Typo should still return AI result, got: {titles}"

def test_mixed_language_query():
    titles = top_titles("منحة data science في اوروبا", n=3)
    assert len(titles) == 3, "Should return 3 results"
    assert any("بيانات" in t or "جوجل" in t or "امستردام" in t
               for t in titles), f"Expected data science result, got: {titles}"

def test_egypt_opportunities():
    results = search("فرصة في مصر", opportunities, top_k=5)["results"]
    locations = [r["location"].lower() for r in results]
    assert any("egypt" in loc or "cairo" in loc
               for loc in locations), f"Expected Egypt location, got: {locations}"

def test_english_query():
    titles = top_titles("renewable energy scholarship Europe", n=3)
    assert len(titles) == 3

def test_no_empty_results():
    results = search("xyz123nonsense", opportunities, top_k=5)["results"]
    assert len(results) == 5, "Should always return top_k results even for nonsense queries"