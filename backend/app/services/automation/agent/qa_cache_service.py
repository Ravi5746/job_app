import logging
from datetime import datetime, timezone
import difflib
from sqlalchemy.orm import Session

from app.models.qa_cache import QACache

logger = logging.getLogger(__name__)

class QACacheService:
    def get_cached_answer(self, question_text: str, user_id: int, db: Session) -> tuple[str, str] | None:
        """
        Retrieves a cached answer if a question with difflib similarity > 0.92 exists for the user.
        """
        if not question_text or not question_text.strip():
            return None

        clean_question = question_text.strip()

        try:
            # Query all cached entries for the specific user
            cached_entries = db.query(QACache).filter(QACache.user_id == user_id).all()
            if not cached_entries:
                return None

            # First, check for an exact match (case-insensitive)
            for entry in cached_entries:
                if entry.question_text.lower() == clean_question.lower():
                    logger.info(f"[QACache] Exact match hit: '{clean_question}' -> '{entry.answer_text}'")
                    entry.used_count += 1
                    entry.last_used = datetime.now(timezone.utc)
                    db.commit()
                    return entry.answer_text, entry.reasoning or ""

            # If no exact match, use fuzzy matching via difflib
            best_entry = None
            best_score = -1.0

            for entry in cached_entries:
                similarity = difflib.SequenceMatcher(None, clean_question.lower(), entry.question_text.lower()).ratio()
                if similarity > best_score:
                    best_score = similarity
                    best_entry = entry

            if best_entry and best_score > 0.92:
                logger.info(
                    f"[QACache] Cache HIT: '{clean_question}' matched with cached question "
                    f"'{best_entry.question_text}' (similarity: {best_score:.4f}, user={user_id})"
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

    def save_to_cache(self, question_text: str, answer_text: str, user_id: int, db: Session, reasoning: str | None = None) -> None:
        """
        Saves a new question-answer pair to the cache for the given user.
        If the exact question text already exists for this user, it updates the answer and reasoning.
        """
        if not question_text or not question_text.strip() or not answer_text or not answer_text.strip():
            return

        clean_question = question_text.strip()
        clean_answer = answer_text.strip()
        clean_reasoning = reasoning.strip() if reasoning else None

        try:
            # Check if exact match already exists for this user
            entry = db.query(QACache).filter(QACache.question_text == clean_question, QACache.user_id == user_id).first()
            if entry:
                logger.info(f"[QACache] Updating existing exact match for: '{clean_question}' (user={user_id})")
                entry.answer_text = clean_answer
                entry.reasoning = clean_reasoning
                entry.question_embedding = [] # Store empty array instead of floats
                entry.last_used = datetime.now(timezone.utc)
            else:
                logger.info(f"[QACache] Saving new entry to cache: '{clean_question}' -> '{clean_answer}' (user={user_id})")
                new_entry = QACache(
                    user_id=user_id,
                    question_text=clean_question,
                    question_embedding=[], # Empty array
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
