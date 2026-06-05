import os
import sys
import re

sys.path.append("d:/automation/Job Applied/backend")
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/automation/Job Applied/backend/.env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.ai.compressor import ResumeCompressor, NLTK_AVAILABLE

def main():
    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    result = db.execute(text("SELECT content FROM resumes ORDER BY id DESC LIMIT 1")).fetchone()
    resume_content = result[0]
    
    print(f"Original resume length: {len(resume_content)}")
    print(f"NLTK AVAILABLE: {NLTK_AVAILABLE}")
    
    blocks = ResumeCompressor.reconstruct_blocks(resume_content)
    print(f"Total reconstructed blocks: {len(blocks)}")
    
    # Test the improved sectionize
    sections = {
        "HEADER": [],
        "SUMMARY": [],
        "SKILLS": [],
        "EXPERIENCE": [],
        "EDUCATION": [],
        "CERTIFICATIONS": [],
        "MISC": []
    }
    current_section = "HEADER"
    section_headers = {
        r"\b(?:summary|professional\s+summary|objective)\b": "SUMMARY",
        r"\b(?:skills|technical\s+skills|core\s+competencies|competencies|technologies)\b": "SKILLS",
        r"\b(?:experience|professional\s+experience|work\s+experience|employment\s+history)\b": "EXPERIENCE",
        r"\b(?:education|academic\s+background)\b": "EDUCATION",
        r"\b(?:certifications|certificates|licenses)\b": "CERTIFICATIONS",
    }
    
    # Run actual compression with job grouping and ranking
    sections = ResumeCompressor.sectionize(blocks)
    exp_blocks = sections.get("EXPERIENCE", [])
    
    # Group experience blocks by job
    jobs = []
    current_job = {"header": [], "bullets": []}
    
    for block in exp_blocks:
        is_bullet = block.startswith(("•", "-", "*", "▪", "◦", "■", "♦", "●", "★"))
        if not is_bullet:
            # If we see Client: or Role: and we already have bullets, start a new job group
            if (block.startswith(("Client:", "Company:", "Employer:")) or "Client:" in block) and current_job["bullets"]:
                jobs.append(current_job)
                current_job = {"header": [], "bullets": []}
            current_job["header"].append(block)
        else:
            current_job["bullets"].append(block)
            
    if current_job["header"] or current_job["bullets"]:
        jobs.append(current_job)
        
    print(f"\nGrouped into {len(jobs)} jobs:")
    for i, job in enumerate(jobs):
        print(f"  Job {i+1}: {repr(job['header'])} -> {len(job['bullets'])} bullets")
        
    # Compress each job's bullets
    compressed_exp_blocks = []
    seen_stems_list = []
    
    for job_idx, job in enumerate(jobs):
        # 1. Keep headers
        compressed_exp_blocks.extend(job["header"])
        
        # 2. Process bullets
        processed_bullets = []
        for bullet in job["bullets"]:
            bullet_match = re.match(r"^(\s*[•\-*▪◦■♦●★]\s*)", bullet)
            bullet_prefix = bullet_match.group(1) if bullet_match else "• "
            content_text = bullet[len(bullet_prefix):].strip()
            
            import nltk
            sentences = nltk.tokenize.sent_tokenize(content_text)
            kept_sentences = []
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                # Boilerplate
                if ResumeCompressor.is_boilerplate_sentence(sentence):
                    continue
                # Duplicate
                is_dup = False
                stems, _, _, _ = ResumeCompressor.get_content_stems_nltk(sentence)
                if len(stems) > 2:
                    for seen in seen_stems_list:
                        sim = ResumeCompressor.calculate_jaccard_similarity(stems, seen)
                        if sim > 0.60:
                            is_dup = True
                            break
                    if not is_dup:
                        seen_stems_list.append(stems)
                if not is_dup:
                    kept_sentences.append(sentence)
                    
            if kept_sentences:
                processed_bullets.append((bullet, bullet_prefix, " ".join(kept_sentences)))
                
        # 3. Calculate density and rank
        bullet_scores = []
        for orig_idx, (orig_bullet, prefix, content) in enumerate(processed_bullets):
            # Compute average sentence density and presence of proper nouns/numbers
            stems, density, has_proper, has_num = ResumeCompressor.get_content_stems_nltk(content)
            # Score formula: density + 0.2 if has_proper + 0.2 if has_num
            score = density + (0.2 if has_proper else 0.0) + (0.2 if has_num else 0.0)
            bullet_scores.append((score, orig_idx, orig_bullet, prefix, content))
            
        # Sort by score descending
        bullet_scores.sort(key=lambda x: x[0], reverse=True)
        
        # Keep top N (e.g. 6)
        top_n = bullet_scores[:6]
        # Sort back by original index to preserve resume ordering
        top_n.sort(key=lambda x: x[1])
        
        for score, orig_idx, orig_bullet, prefix, content in top_n:
            compressed_exp_blocks.append(prefix + content)
            
    print(f"\nTotal EXPERIENCE blocks after grouping & ranking: {len(compressed_exp_blocks)}")
    
    # Print sample of new EXPERIENCE section
    print("\n--- SAMPLE OF COMPRESSED EXPERIENCE ---")
    for block in compressed_exp_blocks[:15]:
        print(repr(block[:100]))
        
    db.close()

if __name__ == "__main__":
    main()
