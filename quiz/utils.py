import requests
import re
import time
from difflib import SequenceMatcher
import logging


logger = logging.getLogger(__name__)


# Set your TextRazor API key
TEXTRAZOR_API_KEY = 'b4d325a9aa33b7384a96f21ebc6ba725e58c3c82b6e76931446e1718'

# TextRazor headers
headers = {
    'x-textrazor-key': TEXTRAZOR_API_KEY,
}

def preprocess_text(text):
    if text is None:
        return []
    text = re.sub(r'\W+', ' ', text.lower())
    tokens = text.split()
    return tokens

def analyze_text(text):
    if not text:
        return {}

    data = {
        'text': text,
        'extractors': 'entities,topics,words,relations,entailments,sentiment'
    }
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.post('https://api.textrazor.com', headers=headers, data=data)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request to TextRazor failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                raise e

def extract_entities(data):
    if not data:
        return set()
    entities = data.get('response', {}).get('entities', [])
    return set(entity['entityId'] for entity in entities)

def extract_keywords(data):
    if not data:
        return set()
    words = data.get('response', {}).get('words', [])
    keywords = set(word['lemma'] for word in words if 'lemma' in word)
    return keywords

def extract_relations(data):
    if not data:
        return []
    return data.get('response', {}).get('relations', [])

def get_synonyms(word):
    if not word:
        return set()

    data = {
        'text': word,
        'extractors': 'entailments'
    }
    try:
        response = requests.post('https://api.textrazor.com', headers=headers, data=data)
        response.raise_for_status()
        response_data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to TextRazor for synonyms failed: {e}")
        return set()

    synonyms = set()
    entailments = response_data.get('response', {}).get('entailments', [])
    for syn in entailments:
        entailed_word = syn.get('entailedWord')
        if entailed_word:
            synonyms.add(entailed_word)
    return synonyms

def expand_keywords(keywords):
    if not keywords:
        return []

    expanded_keywords = set(keywords)
    for keyword in keywords:
        synonyms = get_synonyms(keyword)
        expanded_keywords.update(synonyms)
    return list(expanded_keywords)

def hash_embedding(text):
    if not text:
        return 0
    return hash(text) % 1000

def calculate_cosine_similarity(emb1, emb2):
    norm1 = sum(a ** 2 for a in emb1) ** 0.5
    norm2 = sum(b ** 2 for b in emb2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return sum(a * b for a, b in zip(emb1, emb2)) / (norm1 * norm2)

def calculate_jaccard_similarity(set1, set2):
    if not set1 or not set2:
        return 0.0
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return float(len(intersection)) / len(union) if len(union) > 0 else 0.0

def calculate_soft_match(word1, word2):
    if not word1 or not word2:
        return 0.0
    return SequenceMatcher(None, word1, word2).ratio()

def grade_text_answer(user_answer, correct_answer, keywords):
    # Preprocess inputs
    user_tokens = preprocess_text(user_answer)
    correct_tokens = preprocess_text(correct_answer)
    keyword_tokens = preprocess_text(keywords)

    # If the user's answer exactly matches the correct answer, immediately mark it as correct
    if user_tokens == correct_tokens:
        return True, ["Correct"]

    expanded_keyword_tokens = expand_keywords(keyword_tokens)

    user_analysis = analyze_text(user_answer)
    correct_analysis = analyze_text(correct_answer)

    user_entities = extract_entities(user_analysis)
    correct_entities = extract_entities(correct_analysis)

    user_keywords = extract_keywords(user_analysis)
    correct_keywords = extract_keywords(correct_analysis)

    user_relations = extract_relations(user_analysis)
    correct_relations = extract_relations(correct_analysis)

    user_emb = [hash_embedding(' '.join(user_tokens))]
    correct_emb = [hash_embedding(' '.join(correct_tokens))]

    # Calculate similarity scores
    cosine_score = calculate_cosine_similarity(user_emb, correct_emb)
    jaccard_entity_score = calculate_jaccard_similarity(user_entities, correct_entities)
    jaccard_keyword_score = calculate_jaccard_similarity(user_keywords, correct_keywords)

    # Keyword matching with expanded synonyms and soft matching
    keyword_matches = sum(1 for keyword in expanded_keyword_tokens if
                          any(calculate_soft_match(keyword, token) > 0.8 for token in user_tokens))
    keyword_match_score = keyword_matches / len(expanded_keyword_tokens) if expanded_keyword_tokens else 0

    # Combine scores (heuristic)
    overall_score = (cosine_score * 0.3) + (jaccard_entity_score * 0.25) + (jaccard_keyword_score * 0.25) + (
                keyword_match_score * 0.2)

    # Generate feedback
    feedback = []
    if keyword_match_score < 0.7:
        missing_keywords = [kw for kw in expanded_keyword_tokens if
                            not any(calculate_soft_match(kw, token) > 0.8 for token in user_tokens)]
        feedback.append(f"Missing or incorrect keywords: {', '.join(missing_keywords)}")
    if cosine_score < 0.7:
        feedback.append("The overall content of your answer did not closely match the expected answer.")
    if jaccard_entity_score < 0.7:
        feedback.append("Your answer did not include enough relevant entities.")
    if jaccard_keyword_score < 0.7:
        feedback.append("Your answer did not include enough relevant keywords.")
    if len(user_relations) < len(correct_relations):
        feedback.append("Your answer did not include enough relevant relationships between entities.")

    is_correct = overall_score > 0.7
    return is_correct, feedback

def detailed_feedback(user_answer, correct_answer, keywords):
    is_correct, feedback = grade_text_answer(user_answer, correct_answer, keywords)

    # Enhanced feedback with suggestions
    if not is_correct:
        if "The overall content of your answer did not closely match the expected answer." in feedback:
            feedback.append("Try to focus more on the main concepts and details discussed in the correct answer.")
        if "Missing or incorrect keywords:" in feedback:
            feedback.append("Ensure you use the key terms relevant to the topic.")

    return is_correct, feedback