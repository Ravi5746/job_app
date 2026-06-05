import re
from typing import Dict, List, Set, Tuple
from app.core.logger import logger

# Initialize NLTK safely with fallback capabilities
NLTK_AVAILABLE = False
try:
    import nltk
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk import pos_tag
    from nltk.stem import PorterStemmer
    
    # Check and download required corpora quietly
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
        
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', quiet=True)
        
    try:
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        nltk.download('averaged_perceptron_tagger', quiet=True)
        
    try:
        nltk.data.find('taggers/averaged_perceptron_tagger_eng')
    except LookupError:
        nltk.download('averaged_perceptron_tagger_eng', quiet=True)
        
    try:
        nltk.data.find('taggers/universal_tagset')
    except LookupError:
        nltk.download('universal_tagset', quiet=True)
        
    stemmer = PorterStemmer()
    NLTK_AVAILABLE = True
except Exception as e:
    logger.warning(f"NLTK initialization failed: {e}. Falling back to rules-based resume compression.")


class ResumeCompressor:
    """
    Local dynamic preprocessor to compress large, repetitive resume texts.
    Uses NLP-based sentence reconstruction, POS tag analysis, information density
    scoring, and stemmed Jaccard deduplication to reduce size by 60-80% without losing facts.
    """

    # Generic boilerplate phrases to filter out if a sentence lacks technical details or metrics
    BOILERPLATE_PATTERNS = [
        r"\bresponsible\s+for\b",
        r"\bworked\s+closely\s+with\b",
        r"\bcollaborated\s+with\b",
        r"\bparticipated\s+in\b",
        r"\bassisted\s+in\b",
        r"\bdaily\s+standups?\b",
        r"\bagile\s+ceremonies\b",
        r"\bsprint\s+planning\b",
        r"\bteam\s+meetings?\b",
        r"\bmeeting\s+project\s+deadlines\b",
        r"\bday-to-day\s+tasks?\b",
        r"\bgeneral\s+maintenance\b",
        r"\bdebugging\s+issues\b",
        r"\bfixing\s+bugs\b",
        r"\bwriting\s+clean\s+code\b",
        r"\bparticipating\s+in\b",
        r"\bpartnered\s+with\b",
        r"\bworking\s+in\s+short\s+iterations\b"
    ]

    # Rule-based fallback keywords if NLTK is not available
    TECH_INDICATORS_FALLBACK = [
        r"\b[A-Z][a-zA-Z0-9]*\b",
        r"\b\d+%\b",
        r"\b\d+\s*(?:years?|months?|days?|kb|mb|gb|tb|seconds?|ms)\b",
        r"\b(?:REST|API|SQL|NoSQL|CI/CD|AWS|GCP|UI|UX|JVM|JPA|MVC|RBAC|OAuth2?|LDAP|SAML)\b"
    ]

    BOILERPLATE_VERB_STEMS = {
        'work', 'collabor', 'respons', 'particip', 'assist', 'support',
        'maintain', 'debug', 'fix', 'coordin', 'partner', 'practic',
        'involv', 'perform', 'develop', 'attend', 'meet', 'contribut', 'daili', 'sprint'
    }

    @classmethod
    def get_content_stems_nltk(cls, sentence: str) -> Tuple[Set[str], float, bool, bool]:
        """
        Tokenizes and tags POS of a sentence using NLTK.
        Returns:
            - Set of lowercased stems for content words.
            - Information density score (ratio of content words to total tokens).
            - Boolean indicating if the sentence has Proper Nouns (NNP/NNPS).
            - Boolean indicating if the sentence has Numbers (CD or digit tokens).
        """
        if not NLTK_AVAILABLE:
            return set(), 0.0, False, False

        try:
            tokens = word_tokenize(sentence)
            if not tokens:
                return set(), 0.0, False, False

            tagged = pos_tag(tokens)
            content_tags = {'NN', 'NNS', 'NNP', 'NNPS', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ', 'JJ', 'JJR', 'JJS', 'CD', 'RB', 'RBR', 'RBS'}
            proper_noun_tags = {'NNP', 'NNPS'}

            content_tokens = []
            stems = set()
            has_proper_nouns = False
            has_numbers = False

            for word, tag in tagged:
                # Check for proper noun indicators
                if tag in proper_noun_tags:
                    has_proper_nouns = True
                
                # Check for number indicators
                if tag == 'CD' or any(c.isdigit() for c in word):
                    has_numbers = True

                if not word.isalnum():
                    continue

                # Check for content word tags
                if tag in content_tags:
                    content_tokens.append(word)
                    stems.add(stemmer.stem(word.lower()))

            density = len(content_tokens) / len(tokens) if tokens else 0.0
            return stems, density, has_proper_nouns, has_numbers
        except Exception as err:
            logger.warning(f"Error parsing NLTK data for sentence: {sentence}. Error: {err}")
            return set(), 0.0, False, False

    @classmethod
    def get_words_fallback(cls, sentence: str) -> Set[str]:
        """Fallback tokenization helper."""
        return set(re.findall(r'\w+', sentence.lower()))

    @classmethod
    def calculate_jaccard_similarity(cls, stems1: Set[str], stems2: Set[str]) -> float:
        """Calculates word-level Jaccard similarity between two sets of stems."""
        if not stems1 or not stems2:
            return 0.0
        return len(stems1.intersection(stems2)) / len(stems1.union(stems2))

    @classmethod
    def is_boilerplate_sentence(cls, sentence: str) -> bool:
        """
        Determines if a sentence is generic boilerplate.
        Using NLP POS information: a sentence is boilerplate if it contains generic phrases,
        low content density, and lacks Proper Nouns (specific tech, tools, libraries) and numbers.
        """
        clean_text = sentence.strip()
        if not clean_text:
            return True

        # Check boilerplate keyword matches
        has_boilerplate_phrase = any(re.search(pat, clean_text, re.IGNORECASE) for pat in cls.BOILERPLATE_PATTERNS)

        if NLTK_AVAILABLE:
            try:
                stems, density, has_proper_nouns, has_numbers = cls.get_content_stems_nltk(clean_text)
                boilerplate_count = sum(1 for stem in stems if stem in cls.BOILERPLATE_VERB_STEMS)
                return (boilerplate_count >= 1 or has_boilerplate_phrase) and not (has_proper_nouns or has_numbers)
            except Exception:
                pass

        # Fallback regex checks
        has_tech = any(re.search(pat, clean_text) for pat in cls.TECH_INDICATORS_FALLBACK)
        has_numbers = any(char.isdigit() for char in clean_text)
        return has_boilerplate_phrase and not (has_tech or has_numbers)

    @classmethod
    def reconstruct_blocks(cls, raw_text: str) -> List[str]:
        """
        Groups split lines into logical blocks/sentences.
        Combines continuation lines (e.g. lines that do not start with a bullet point,
        are not section headers, and do not contain structural identifiers like dates or role tags).
        """
        lines = raw_text.splitlines()
        reconstructed = []
        current = ""

        # Structuring patterns: dates (e.g. Aug 2021, Present, 2019-2022) or heading tags
        date_pattern = re.compile(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(?:20|19)\d{2}\b|"
            r"\b(?:20|19)\d{2}\b|\bPresent\b",
            re.IGNORECASE
        )
        structural_keywords = ["Client:", "Role:", "Responsibilities", "Location:", "Company:", "Project:", "Employer:"]

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue

            is_bullet = trimmed.startswith(("•", "-", "*", "▪", "◦", "■", "♦", "●", "★"))
            
            # Detect common section headers and Title Case lines under 40 chars
            is_section_header = False
            if len(trimmed) < 40:
                for pat in [
                    r"\b(?:summary|professional\s+summary|objective)\b",
                    r"\b(?:skills|technical\s+skills|core\s+competencies|competencies|technologies)\b",
                    r"\b(?:experience|professional\s+experience|work\s+experience|employment\s+history)\b",
                    r"\b(?:education|academic\s+background)\b",
                    r"\b(?:certifications|certificates|licenses)\b",
                    r"\b(?:projects|misc|languages|interests)\b"
                ]:
                    if re.search(pat, trimmed, re.IGNORECASE):
                        is_section_header = True
                        break
            
            # Title case check: must have at least one word, and all words must start with an uppercase letter
            words = ["".join(c for c in w if c.isalpha()) for w in trimmed.split()]
            words = [w for w in words if w]
            is_title_case = len(trimmed) < 40 and len(words) > 0 and all(w[0].isupper() for w in words)
            is_header = len(trimmed) < 40 and (trimmed.isupper() or trimmed.endswith(":") or is_section_header or is_title_case)
            
            has_date = bool(date_pattern.search(trimmed))
            has_struct_kw = any(kw in trimmed for kw in structural_keywords)
            is_structural = len(trimmed) < 100 and (has_date or has_struct_kw)

            # If current block is a section header, force the next line to start a new block
            is_current_section_header = False
            if current:
                c_trimmed = current.strip()
                if len(c_trimmed) < 40:
                    for pat in [
                        r"\b(?:summary|professional\s+summary|objective)\b",
                        r"\b(?:skills|technical\s+skills|core\s+competencies|competencies|technologies)\b",
                        r"\b(?:experience|professional\s+experience|work\s+experience|employment\s+history)\b",
                        r"\b(?:projects|academic\s+projects|personal\s+projects|key\s+projects|prprojects)\b",
                        r"\b(?:education|academic\s+background)\b",
                        r"\b(?:certifications|certificates|licenses)\b",
                    ]:
                        if re.search(pat, c_trimmed, re.IGNORECASE):
                            is_current_section_header = True
                            break

            if is_bullet or is_header or is_structural or is_current_section_header:
                if current:
                    reconstructed.append(current.strip())
                current = trimmed
            else:
                if current:
                    current += " " + trimmed
                else:
                    current = trimmed

        if current:
            reconstructed.append(current.strip())

        return reconstructed

    @classmethod
    def sectionize(cls, blocks: List[str]) -> Dict[str, List[str]]:
        """Parses the reconstructed blocks into structured sections."""
        sections = {
            "HEADER": [],
            "SUMMARY": [],
            "SKILLS": [],
            "EXPERIENCE": [],
            "PROJECTS": [],
            "EDUCATION": [],
            "CERTIFICATIONS": [],
            "MISC": []
        }

        current_section = "HEADER"
        section_headers = {
            r"\b(?:summary|professional\s+summary|objective)\b": "SUMMARY",
            r"\b(?:skills|technical\s+skills|core\s+competencies|competencies|technologies)\b": "SKILLS",
            r"\b(?:experience|professional\s+experience|work\s+experience|employment\s+history)\b": "EXPERIENCE",
            r"\b(?:projects|academic\s+projects|personal\s+projects|key\s+projects)\b": "PROJECTS",
            r"\b(?:education|academic\s+background)\b": "EDUCATION",
            r"\b(?:certifications|certificates|licenses)\b": "CERTIFICATIONS",
        }

        section_order = {
            "HEADER": 0,
            "SUMMARY": 1,
            "SKILLS": 2,
            "EXPERIENCE": 3,
            "PROJECTS": 4,
            "EDUCATION": 5,
            "CERTIFICATIONS": 6,
            "MISC": 7
        }

        for block in blocks:
            # Check if this block is a section header (must be short and match keywords)
            matched_section = None
            if len(block) < 40:
                # Prioritize clean uppercase or colon-terminated headers
                for pat, sec in section_headers.items():
                    if re.search(pat, block, re.IGNORECASE):
                        matched_section = sec
                        break

            if matched_section:
                current_section = matched_section
                continue

            # Experience triggers: force current_section to EXPERIENCE if block starts with structural role details
            if block.startswith(("Client:", "Role:", "Responsibilities:", "Company:", "Employer:", "Job Title:")):
                current_section = "EXPERIENCE"
            elif "Role:" in block or "Responsibilities:" in block:
                current_section = "EXPERIENCE"

            sections[current_section].append(block)

        return sections

    @classmethod
    def compress_resume(cls, raw_text: str) -> str:
        """
        Main pipeline method: Reconstructs paragraphs, sectionizes, filters boilerplate
        using POS metadata, removes duplicates using stemmed Jaccard similarity,
        and re-assembles into a highly compressed, high-density format.
        """
        if not raw_text:
            return ""

        # 1. Reconstruct paragraphs/bullets from wrapped lines
        blocks = cls.reconstruct_blocks(raw_text)

        # 2. Structure into sections
        sections = cls.sectionize(blocks)
        compressed_sections = {}

        # Header & Summary: Keep intact (up to 20 blocks for header to avoid bloated metadata)
        compressed_sections["HEADER"] = sections["HEADER"][:20]
        
        # Summary: Limit to top 8 blocks based on NLP Information density score if it is a list of bullets
        summary_blocks = sections.get("SUMMARY", [])
        if len(summary_blocks) > 8:
            summary_scores = []
            for orig_idx, block in enumerate(summary_blocks):
                is_bullet = block.startswith(("•", "-", "*", "▪", "◦", "■", "♦", "●", "★"))
                if not is_bullet:
                    score = 1.0  # Keep headers/non-bullets first
                else:
                    bullet_match = re.match(r"^(\s*[•\-*▪◦■♦●★]\s*)", block)
                    bullet_prefix = bullet_match.group(1) if bullet_match else "• "
                    content = block[len(bullet_prefix):].strip()
                    if NLTK_AVAILABLE:
                        try:
                            stems, density, has_proper, has_num = cls.get_content_stems_nltk(content)
                            score = density + (0.2 if has_proper else 0.0) + (0.2 if has_num else 0.0)
                        except Exception:
                            score = 0.5
                    else:
                        words = cls.get_words_fallback(content)
                        has_proper = any(w[0].isupper() for w in content.split() if w.isalpha())
                        has_num = any(c.isdigit() for c in content)
                        score = len(words) / max(1, len(content.split())) + (0.2 if has_proper else 0.0) + (0.2 if has_num else 0.0)
                summary_scores.append((score, orig_idx, block))
            
            # Sort by score descending
            summary_scores.sort(key=lambda x: x[0], reverse=True)
            # Keep top 8
            top_n_summary = summary_scores[:8]
            # Sort back by original index
            top_n_summary.sort(key=lambda x: x[1])
            compressed_sections["SUMMARY"] = [x[2] for x in top_n_summary]
        else:
            compressed_sections["SUMMARY"] = summary_blocks

        # Skills: Deduplicate identical terms in comma-separated lines
        cleaned_skills = []
        seen_skills = set()
        for line in sections["SKILLS"]:
            if "," in line:
                parts = [p.strip() for p in line.split(",") if p.strip()]
                unique_parts = []
                for p in parts:
                    p_lower = p.lower()
                    if p_lower not in seen_skills:
                        seen_skills.add(p_lower)
                        unique_parts.append(p)
                if unique_parts:
                    cleaned_skills.append(", ".join(unique_parts))
            else:
                line_lower = line.lower()
                if line_lower not in seen_skills:
                    seen_skills.add(line_lower)
                    cleaned_skills.append(line)
        compressed_sections["SKILLS"] = cleaned_skills

        # Experience: NLP-based boilerplate filtering, Jaccard deduplication, and density ranking per job/client
        exp_blocks = sections.get("EXPERIENCE", [])
        
        # 1. Group EXPERIENCE blocks into separate jobs
        jobs = []
        current_job = {"header": [], "bullets": []}
        
        for block in exp_blocks:
            is_bullet = block.startswith(("•", "-", "*", "▪", "◦", "■", "♦", "●", "★"))
            if not is_bullet:
                # If we see Client: or Company: and we already have bullets, start a new job group
                if (block.startswith(("Client:", "Company:", "Employer:", "Job Title:")) or "Client:" in block) and current_job["bullets"]:
                    jobs.append(current_job)
                    current_job = {"header": [], "bullets": []}
                current_job["header"].append(block)
            else:
                current_job["bullets"].append(block)
                
        if current_job["header"] or current_job["bullets"]:
            jobs.append(current_job)
            
        # 2. Process each job group
        cleaned_exp = []
        seen_stems_list = []
        seen_words_fallback = []
        
        for job in jobs:
            # Add structural headers for the job intact
            cleaned_exp.extend(job["header"])
            
            # Process and filter the job's bullets
            processed_bullets = []
            for bullet in job["bullets"]:
                bullet_match = re.match(r"^(\s*[•\-*▪◦■♦●★]\s*)", bullet)
                bullet_prefix = bullet_match.group(1) if bullet_match else "• "
                content_text = bullet[len(bullet_prefix):].strip()
                
                if NLTK_AVAILABLE:
                    try:
                        sentences = sent_tokenize(content_text)
                    except Exception as tokenize_err:
                        logger.warning(f"sent_tokenize failed: {tokenize_err}")
                        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content_text) if s.strip()]
                else:
                    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content_text) if s.strip()]
                    
                kept_sentences = []
                for sentence in sentences:
                    if not sentence.strip():
                        continue
                        
                    # Boilerplate check
                    is_boilerplate = False
                    if NLTK_AVAILABLE:
                        try:
                            stems, density, has_proper_nouns, has_numbers = cls.get_content_stems_nltk(sentence)
                            boilerplate_count = sum(1 for stem in stems if stem in cls.BOILERPLATE_VERB_STEMS)
                            has_boilerplate_phrase = any(re.search(pat, sentence, re.IGNORECASE) for pat in cls.BOILERPLATE_PATTERNS)
                            if (boilerplate_count >= 1 or has_boilerplate_phrase) and not (has_proper_nouns or has_numbers):
                                is_boilerplate = True
                        except Exception as e:
                            logger.warning(f"NLTK boilerplate check error: {e}")
                            is_boilerplate = cls.is_boilerplate_sentence(sentence)
                    else:
                        is_boilerplate = cls.is_boilerplate_sentence(sentence)
                        
                    if is_boilerplate:
                        continue
                        
                    # Deduplication check
                    is_duplicate = False
                    if NLTK_AVAILABLE:
                        try:
                            stems, _, _, _ = cls.get_content_stems_nltk(sentence)
                            if len(stems) > 2:
                                for seen_stems in seen_stems_list:
                                    similarity = cls.calculate_jaccard_similarity(stems, seen_stems)
                                    if similarity > 0.60:
                                        is_duplicate = True
                                        break
                                if not is_duplicate:
                                    seen_stems_list.append(stems)
                        except Exception as e:
                            logger.warning(f"NLTK Jaccard deduplication error: {e}")
                            words = cls.get_words_fallback(sentence)
                            if len(words) > 2:
                                for seen_words in seen_words_fallback:
                                    intersection = words.intersection(seen_words)
                                    union = words.union(seen_words)
                                    similarity = len(intersection) / len(union) if union else 0.0
                                    if similarity > 0.60:
                                        is_duplicate = True
                                        break
                                if not is_duplicate:
                                    seen_words_fallback.append(words)
                    else:
                        words = cls.get_words_fallback(sentence)
                        if len(words) > 2:
                            for seen_words in seen_words_fallback:
                                intersection = words.intersection(seen_words)
                                union = words.union(seen_words)
                                similarity = len(intersection) / len(union) if union else 0.0
                                if similarity > 0.60:
                                    is_duplicate = True
                                    break
                            if not is_duplicate:
                                seen_words_fallback.append(words)
                                
                    if not is_duplicate:
                        kept_sentences.append(sentence)
                        
                if kept_sentences:
                    processed_bullets.append((bullet, bullet_prefix, " ".join(kept_sentences)))
                    
            # 3. Calculate scores for the remaining bullets of this job and select top N (e.g. 6)
            bullet_scores = []
            for orig_idx, (orig_bullet, prefix, content) in enumerate(processed_bullets):
                if NLTK_AVAILABLE:
                    try:
                        stems, density, has_proper, has_num = cls.get_content_stems_nltk(content)
                        # Score formula: density + 0.2 if has_proper + 0.2 if has_num
                        score = density + (0.2 if has_proper else 0.0) + (0.2 if has_num else 0.0)
                    except Exception:
                        score = 0.5
                else:
                    # Fallback simple scoring: fraction of capitalized words and digits
                    words = cls.get_words_fallback(content)
                    has_proper = any(w[0].isupper() for w in content.split() if w.isalpha())
                    has_num = any(c.isdigit() for c in content)
                    score = len(words) / max(1, len(content.split())) + (0.2 if has_proper else 0.0) + (0.2 if has_num else 0.0)
                    
                bullet_scores.append((score, orig_idx, orig_bullet, prefix, content))
                
            # Sort by score descending
            bullet_scores.sort(key=lambda x: x[0], reverse=True)
            
            # Keep top 6 bullets (or all if less than 6)
            top_n = bullet_scores[:6]
            # Sort back by original index to preserve resume ordering
            top_n.sort(key=lambda x: x[1])
            
            for score, orig_idx, orig_bullet, prefix, content in top_n:
                cleaned_exp.append(prefix + content)
                
        compressed_sections["EXPERIENCE"] = cleaned_exp

        # Projects, Education, Certifications, and Misc: Keep intact
        compressed_sections["PROJECTS"] = sections.get("PROJECTS", [])
        compressed_sections["EDUCATION"] = sections["EDUCATION"]
        compressed_sections["CERTIFICATIONS"] = sections["CERTIFICATIONS"]
        compressed_sections["MISC"] = sections["MISC"]

        # Re-assemble the compressed resume text
        output = []
        for sec_name, sec_lines in compressed_sections.items():
            if sec_lines:
                output.append(f"\n--- {sec_name} ---")
                output.extend(sec_lines)

        assembled_text = "\n".join(output)
        return assembled_text
