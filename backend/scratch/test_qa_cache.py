import sys
import os
import logging

# Set up paths to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_qa_cache")

from app.db.session import SessionLocal
from app.models.qa_cache import QACache
from app.services.automation.agent.qa_cache_service import qa_cache_service
from app.services.automation.agent.semantic_classifier import semantic_classifier

def run_tests():
    logger.info("Initializing test...")
    db = SessionLocal()
    try:
        # 1. Clean existing test data
        logger.info("Cleaning qa_cache table...")
        db.query(QACache).delete()
        db.commit()

        # 2. Check if semantic classifier is enabled
        logger.info(f"Semantic classifier enabled: {semantic_classifier.enabled}")
        if not semantic_classifier.enabled:
            logger.warning("Sentence-transformers is disabled. Semantic similarity tests will fall back to exact match.")

        # 3. Add test entries to cache
        logger.info("Adding sample QA entries to cache...")
        samples = [
            ("How many years of professional software engineering experience do you have?", "5 years"),
            ("Are you comfortable with working in hybrid model?", "Yes, I am comfortable with hybrid work."),
            ("What is your expected salary (LPA)?", "15 LPA"),
        ]

        for q, a in samples:
            qa_cache_service.save_to_cache(q, a, "Test reasoning", db)

        # Verify insertion
        cached_count = db.query(QACache).count()
        logger.info(f"Successfully cached {cached_count} entries.")
        assert cached_count == len(samples), f"Expected {len(samples)} entries, got {cached_count}"

        # 4. Test Exact Match
        logger.info("\n--- Test 1: Exact Match Retrieval ---")
        q1 = "How many years of professional software engineering experience do you have?"
        res1 = qa_cache_service.get_cached_answer(q1, db)
        assert res1 is not None, "Exact match lookup failed!"
        ans1, reason1 = res1
        logger.info(f"Q: '{q1}'\nA: '{ans1}' (Reasoning: '{reason1}')")
        assert ans1 == "5 years"

        # Verify used count incremented
        entry1 = db.query(QACache).filter(QACache.question_text == q1).first()
        logger.info(f"Used count for exact match: {entry1.used_count}")
        assert entry1.used_count == 2, f"Expected used_count to be 2 (1 initial + 1 retrieval), got {entry1.used_count}"

        # 5. Test Semantic Similarity Retrieval (only if enabled)
        if semantic_classifier.enabled:
            logger.info("\n--- Test 2: Semantic Match Retrieval (>0.92 similarity) ---")
            # Phrased differently but semantic meaning is the same
            q2 = "Are you comfortable working in a hybrid model?"
            res2 = qa_cache_service.get_cached_answer(q2, db)
            assert res2 is not None, f"Semantic lookup failed for: '{q2}'"
            ans2, reason2 = res2
            logger.info(f"Q: '{q2}'\nA: '{ans2}'")
            assert ans2 == "Yes, I am comfortable with hybrid work."

            # Another semantic match test
            q3 = "Expected salary (LPA)?"
            res3 = qa_cache_service.get_cached_answer(q3, db)
            assert res3 is not None, f"Semantic lookup failed for: '{q3}'"
            ans3, reason3 = res3
            logger.info(f"Q: '{q3}'\nA: '{ans3}'")
            assert ans3 == "15 LPA"

        # 6. Test Cache Miss
        logger.info("\n--- Test 3: Cache Miss (Unrelated Question) ---")
        q_miss = "What is your favorite programming language?"
        res_miss = qa_cache_service.get_cached_answer(q_miss, db)
        logger.info(f"Q: '{q_miss}' -> Cache response: {res_miss}")
        assert res_miss is None, f"Expected cache miss for unrelated question, but got: {res_miss}"

        logger.info("\n=== All Tests Passed Successfully! ===")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
