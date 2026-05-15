import re
from pathlib import Path

from django.conf import settings


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "which",
    "with",
}


class LocalAnswerGenerator:
    def __init__(self):
        self._pipeline = None
        self._load_error = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        model_path = Path(settings.RAG_MODEL_PATH)
        if not model_path.exists():
            self._load_error = f"Local model folder not found: {model_path}"
            return
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            from transformers.utils import logging as hf_logging

            hf_logging.set_verbosity_error()

            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                local_files_only=True,
                trust_remote_code=True,
                attn_implementation="eager",
            )
            model.generation_config.do_sample = False
            model.generation_config.temperature = None
            model.generation_config.top_p = None
            model.generation_config.top_k = None
            self._pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)
        except Exception as exc:
            self._load_error = str(exc)

    @property
    def status(self):
        if self._pipeline:
            return {"available": True, "path": str(settings.RAG_MODEL_PATH), "mode": "huggingface_offline"}
        if Path(settings.RAG_MODEL_PATH).exists():
            return {"available": True, "path": str(settings.RAG_MODEL_PATH), "mode": "huggingface_offline_ready"}
        return {
            "available": False,
            "path": str(settings.RAG_MODEL_PATH),
            "mode": "extractive_fallback",
            "detail": self._load_error,
        }

    def generate(self, question, contexts):
        if not contexts:
            return "I could not find accessible enterprise context for this question."
        self._load()

        compact_context = "\n\n".join(
            f"[{i + 1}] {item['title']} ({item['source_id']}): {item['content'][:900]}"
            for i, item in enumerate(contexts[:5])
        )
        if self._pipeline:
            prompt = (
                "You are an enterprise RAG assistant. Answer only from the provided context. "
                "If evidence is insufficient, say what is missing. Cite sources by bracket number. "
                "Do not invent dates, counts, names, owners, systems, or root causes that are not explicitly stated.\n\n"
                f"Question: {question}\n\nContext:\n{compact_context}\n\nAnswer:"
            )
            output = self._pipeline(
                prompt,
                max_new_tokens=180,
                do_sample=False,
                return_full_text=False,
            )[0]["generated_text"]
            answer = output.strip()
            if (
                self._has_unsupported_numbers(answer, compact_context)
                or self._looks_unstable(answer)
                or self._has_low_support_sentences(answer, compact_context)
            ):
                return self._extractive_answer(contexts)
            return answer

        return self._extractive_answer(contexts)

    def _extractive_answer(self, contexts):
        top = contexts[0]
        same_source_contexts = [item for item in contexts[:3] if item["source_id"] == top["source_id"]]
        supporting = " ".join(item["content"] for item in same_source_contexts)
        sentences = [part.strip() for part in supporting.replace("\n", " ").split(".") if part.strip()]
        answer_sentences = sentences[:4]
        answer = ". ".join(answer_sentences)
        if answer:
            answer += "."
        return (
            f"{answer}\n\nThis answer is grounded in the highest-ranked accessible source, "
            f"{top['title']} ({top['source_id']})."
        )

    def _has_unsupported_numbers(self, answer, context):
        context_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", context.lower()))
        answer_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", answer.lower()))
        return any(number not in context_numbers for number in answer_numbers)

    def _looks_unstable(self, answer):
        lowered = answer.lower()
        unstable_phrases = [
            "source(s):",
            "the question asks",
            "missing information",
            "therefore, the missing",
            "i don't have enough",
        ]
        return any(phrase in lowered for phrase in unstable_phrases)

    def _content_terms(self, text):
        return {
            term
            for term in re.findall(r"[a-z0-9]+", text.lower())
            if len(term) > 2 and term not in STOPWORDS
        }

    def _has_low_support_sentences(self, answer, context):
        context_terms = self._content_terms(context)
        if not context_terms:
            return True
        sentences = [sentence.strip() for sentence in re.split(r"[.\n]+", answer) if sentence.strip()]
        for sentence in sentences:
            sentence_terms = self._content_terms(sentence)
            if len(sentence_terms) < 4:
                continue
            overlap = len(sentence_terms & context_terms) / len(sentence_terms)
            if overlap < 0.45:
                return True
        return False


generator = LocalAnswerGenerator()
