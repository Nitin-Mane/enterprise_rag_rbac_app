import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from api.models import DataSource, DocumentChunk, QueryAudit
from api.services.generation import generator
from api.services.rbac import visible_sources_for


ROUTE_KEYWORDS = {
    "finance": ["finance", "revenue", "cost", "invoice", "budget", "vendor"],
    "security": ["incident", "alert", "audit", "login", "token", "policy", "risk"],
    "operations": ["sla", "outage", "warehouse", "ticket", "capacity", "latency"],
    "compliance": ["gdpr", "sox", "retention", "control", "compliance", "finding"],
    "engineering": ["api", "deployment", "schema", "database", "service", "technical"],
}


def route_query(question):
    lowered = question.lower()
    routes = []
    for route, words in ROUTE_KEYWORDS.items():
        if any(word in lowered for word in words):
            routes.append(route)
    return routes or ["general"]


def keyword_overlap(question, content):
    q_terms = set(re.findall(r"[a-z0-9]+", question.lower()))
    c_terms = set(re.findall(r"[a-z0-9]+", content.lower()))
    if not q_terms:
        return 0
    return len(q_terms & c_terms) / len(q_terms)


def retrieve(user, question, limit=5):
    all_sources = list(DataSource.objects.all())
    visible_sources, blocked_sources = visible_sources_for(user, all_sources)
    visible_ids = [source.id for source in visible_sources]
    chunks = list(DocumentChunk.objects.filter(source_id__in=visible_ids).select_related("source"))
    routes = route_query(question)

    if not chunks:
        explainability = {
            "query_terms": sorted(set(re.findall(r"[a-z0-9]+", question.lower())))[:12],
            "accessible_sources": len(visible_sources),
            "blocked_sources": len(blocked_sources),
            "candidate_chunks": 0,
            "retrieved_chunks": 0,
            "top_score": 0,
            "retrieval_method": "hybrid_tfidf_lexical_routing",
        }
        return [], routes, blocked_sources, explainability

    corpus = [f"{chunk.title} {chunk.content}" for chunk in chunks]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(corpus)
    query_vector = vectorizer.transform([question])
    semantic_scores = cosine_similarity(query_vector, matrix).flatten()

    scored = []
    for index, chunk in enumerate(chunks):
        source_text = " ".join([chunk.source.description, chunk.source.title]).lower()
        route_boost = 0.08 if any(route in source_text for route in routes) else 0
        lexical = keyword_overlap(question, chunk.content)
        score = float((semantic_scores[index] * 0.78) + (lexical * 0.22) + route_boost)
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for score, chunk in scored[:limit]:
        results.append(
            {
                "score": round(score, 4),
                "semantic_score": round(float(semantic_scores[chunks.index(chunk)]), 4),
                "lexical_overlap": round(keyword_overlap(question, chunk.content), 4),
                "source_id": chunk.source.source_id,
                "title": chunk.title,
                "source_type": chunk.source.source_type,
                "sensitivity": chunk.source.sensitivity,
                "page": chunk.page,
                "content": chunk.content,
                "citation": f"{chunk.source.title}, ref {chunk.page}",
                "parser": chunk.metadata.get("parser", "unknown"),
                "ocr_used": chunk.metadata.get("ocr_used", False),
            }
        )
    explainability = {
        "query_terms": sorted(set(re.findall(r"[a-z0-9]+", question.lower())))[:12],
        "accessible_sources": len(visible_sources),
        "blocked_sources": len(blocked_sources),
        "candidate_chunks": len(chunks),
        "retrieved_chunks": len(results),
        "top_score": results[0]["score"] if results else 0,
        "retrieval_method": "hybrid_tfidf_lexical_routing",
        "score_weights": {"semantic": 0.78, "lexical": 0.22, "route_boost": 0.08},
    }
    return results, routes, blocked_sources, explainability


def answer_question(user, question):
    contexts, routes, blocked, explainability = retrieve(user, question)
    answer = generator.generate(question, contexts)
    confidence = round(sum(item["score"] for item in contexts[:3]) / max(len(contexts[:3]), 1), 3) if contexts else 0
    audit = QueryAudit.objects.create(
        user=user,
        question=question,
        routed_sources=routes,
        blocked_sources=blocked,
        confidence=confidence,
    )
    return {
        "answer": answer,
        "confidence": confidence,
        "routes": routes,
        "citations": [
            {
                "source_id": item["source_id"],
                "title": item["title"],
                "citation": item["citation"],
                "score": item["score"],
                "semantic_score": item["semantic_score"],
                "lexical_overlap": item["lexical_overlap"],
                "parser": item["parser"],
                "ocr_used": item["ocr_used"],
                "excerpt": item["content"][:360],
            }
            for item in contexts
        ],
        "blocked_sources": blocked,
        "explainability": explainability,
        "audit_id": audit.id,
        "model": generator.status,
    }
