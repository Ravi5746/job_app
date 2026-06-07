import logging
from datetime import datetime, timezone
import numpy as np
from sqlalchemy.orm import Session

from app.models.qa_cache import QACache
from app.services.automation.agent.semantic_classifier import semantic_classifier

logger = logging.getLogger(__name__)

class QACacheService:
    def get_cached_answer(self, question_text: str, db: Session) -> tuple[str, str] | None:
        """
        Retrieves a cached answer if a question with cosine similarity > 0.92 exists.
        Falls back to exact string match if sentence-transformers is disabled.
        """
        if not question_text or not question_text.strip():
            return None

        clean_question = question_text.strip()

        # Fallback to exact match if SentenceTransformer model is disabled
        if not semantic_classifier.enabled or not semantic_classifier.model:
            logger.info(f"[QACache] Semantic search disabled. Performing exact match check for: '{clean_question}'")
            entry = db.query(QACache).filter(QACache.question_text == clean_question).first()
            if entry:
                logger.info(f"[QACache] Exact match hit: '{clean_question}' -> '{entry.answer_text}'")
                entry.used_count += 1
                entry.last_used = datetime.now(timezone.utc)
                db.commit()
                return entry.answer_text, entry.reasoning or ""
            return None

        try:
            # Query all cached entries
            cached_entries = db.query(QACache).all()
            if not cached_entries:
                return None

            # Generate input embedding
            input_emb = semantic_classifier.model.encode([clean_question], convert_to_numpy=True)[0]
            input_norm = np.linalg.norm(input_emb)
            if input_norm > 1e-12:
                input_emb = input_emb / input_norm

            best_entry = None
            best_score = -1.0

            for entry in cached_entries:
                if not entry.question_embedding:
                    continue
                entry_emb = np.array(entry.question_embedding)
                entry_norm = np.linalg.norm(entry_emb)
                if entry_norm > 1e-12:
                    entry_emb = entry_emb / entry_norm
                    similarity = float(np.dot(input_emb, entry_emb))
                    if similarity > best_score:
                        best_score = similarity
                        best_entry = entry

            if best_entry and best_score > 0.92:
                logger.info(
                    f"[QACache] Cache HIT: '{clean_question}' matched with cached question "
                    f"'{best_entry.question_text}' (similarity: {best_score:.4f})"
                )
                best_entry.used_count += 1
                best_entry.last_used = datetime.now(timezone.utc)
                db.commit()
                return best_entry.answer_text, best_entry.reasoning or ""
            else:
                if best_entry:
                    logger.info(f"[QACache] Cache MISS: Best similarity was {best_score:.4f} for '{best_entry.question_text}'")
                else:
                    logger.info("[QACache] Cache MISS: No entries in cache.")

        except Exception as e:
            logger.exception(f"[QACache] Error during cached answer retrieval: {e}")

        return None

    def save_to_cache(self, question_text: str, answer_text: str, reasoning: str | None, db: Session) -> None:
        """
        Saves a new question-answer pair and its embedding to the cache.
        If the exact question text already exists, it updates the answer and reasoning.
        """
        if not question_text or not question_text.strip() or not answer_text or not answer_text.strip():
            return

        clean_question = question_text.strip()
        clean_answer = answer_text.strip()
        clean_reasoning = reasoning.strip() if reasoning else None

        try:
            # Generate embedding
            embedding_list = []
            if semantic_classifier.enabled and semantic_classifier.model:
                input_emb = semantic_classifier.model.encode([clean_question], convert_to_numpy=True)[0]
                embedding_list = input_emb.tolist()

            # Check if exact match already exists
            entry = db.query(QACache).filter(QACache.question_text == clean_question).first()
            if entry:
                logger.info(f"[QACache] Updating existing exact match for: '{clean_question}'")
                entry.answer_text = clean_answer
                entry.reasoning = clean_reasoning
                entry.question_embedding = embedding_list
                entry.last_used = datetime.now(timezone.utc)
            else:
                logger.info(f"[QACache] Saving new entry to cache: '{clean_question}' -> '{clean_answer}'")
                new_entry = QACache(
                    question_text=clean_question,
                    question_embedding=embedding_list,
                    answer_text=clean_answer,
                    reasoning=clean_reasoning,
                    used_count=1,
                    last_used=datetime.now(timezone.utc)
                )
                db.add(new_entry)

            db.commit()
        except Exception as e:
            db.rollback()
            logger.exception(f"[QACache] Error saving Q&A to cache: {e}")

qa_cache_service = QACacheService()
