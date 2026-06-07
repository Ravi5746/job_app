import logging
import re
from typing import Optional
from bs4 import BeautifulSoup
from playwright.async_api import Locator

logger = logging.getLogger(__name__)


class DOMLayer:
    """
    Scrapes form HTML, injects data-qa-idx attributes directly into the live DOM,
    minifies structural markup for LLM consumption, and performs success validation.
    """

    async def get_active_modal(self, target) -> Optional[Locator]:
        """Locate the active, visible modal container in the target (Page or Frame)."""
        logger.info("[GetActiveModal] Starting search for active modal...")
        
        is_frame = hasattr(target, "page")
        selectors = [
            ".jobs-easy-apply-modal",
            ".artdeco-modal",
            "[role='dialog']",
            "div[role='region'][aria-label*='progress']",
            "div[role='region'][aria-label*='application']",
        ]
        if is_frame:
            selectors.extend(["form", "body"])

        for m_sel in selectors:
            try:
                locators = target.locator(f"{m_sel}:visible")
                count = await locators.count()
                logger.debug(f"[GetActiveModal] Selector '{m_sel}': found {count} visible element(s)")
                for i in range(count):
                    loc = locators.nth(i)
                    box = await loc.bounding_box()
                    logger.debug(f"[GetActiveModal]   Element {i}: BoundingBox={box}")
                    
                    is_linkedin = "linkedin.com" in target.url.lower()
                    if is_linkedin and m_sel != ".jobs-easy-apply-modal":
                        signature_sel = (
                            "progress, [role='progressbar'], [class*='easy-apply'], "
                            ".artdeco-completeness-meter-linear, .jobs-easy-apply-footer__info, "
                            "[data-easy-apply-next-button], .jobs-easy-apply-form-section__grouping"
                        )
                        sig_count = await loc.locator(signature_sel).count()
                        logger.debug(
                            f"[GetActiveModal]   Element {i} checking signatures: "
                            f"count={sig_count} (selector: '{signature_sel}')"
                        )
                        if sig_count == 0:
                            logger.debug(f"[GetActiveModal]   Element {i} rejected (no signature matches)")
                            continue
                    logger.info(f"[GetActiveModal] Match found! Selector: '{m_sel}', index: {i}")
                    return loc
            except Exception as e:
                logger.warning(f"[GetActiveModal] Selector '{m_sel}' check failed: {e}")
                continue
        logger.info("[GetActiveModal] No active modal found.")
        return None

    async def clean_and_tag(self, target, profile: Optional[dict] = None) -> str:
        """
        Uses the Python-validated modal locator from get_active_modal, then tags
        and minifies its HTML via element-scoped JS evaluation.
        """
        logger.info("[Scraper] Starting HTML tagging and cleaning...")

        modal_locator = await self.get_active_modal(target)
        if not modal_locator:
            logger.warning("[Scraper] No active modal found — cannot extract HTML.")
            return ""

        # Gather profile keywords for select option filtering
        profile_keywords = []
        if profile:
            for field in ["location", "phone", "phone_country_code", "email", "full_name"]:
                val = profile.get(field, "")
                if val:
                    words = re.findall(r'\b\w+\b|\+\d+', str(val))
                    profile_keywords.extend([w.lower() for w in words if len(w) > 1 or w.startswith('+')])
            profile_keywords = list(set(profile_keywords))

        try:
            html = await modal_locator.evaluate(
                """(modal, keywords) => {
                    function isVisible(el) {
                        if (!el) return false;
                        if (el.type === 'hidden') return false;
                        let curr = el;
                        while (curr && curr !== document.body) {
                            const style = window.getComputedStyle(curr);
                            if (style.display === 'none' || style.visibility === 'hidden') return false;
                            curr = curr.parentElement;
                        }
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 && rect.height === 0) return false;
                        return true;
                    }

                    const interactiveSelectors = [
                        "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='file'])",
                        "textarea",
                        "select"
                    ].join(",");
                    const interactiveElements = Array.from(modal.querySelectorAll(interactiveSelectors));

                    let idx = 1;
                    interactiveElements.forEach(el => {
                        if (isVisible(el)) {
                            el.setAttribute('data-qa-idx', String(idx));
                            idx++;
                        } else {
                            el.removeAttribute('data-qa-idx');
                        }
                    });
                    console.log("[JS Scraper] Tagged " + (idx - 1) + " interactive elements.");

                    const clone = modal.cloneNode(true);

                    // Capture selected values from the original modal first
                    const originalSelects = Array.from(modal.querySelectorAll("select"));
                    const selectedValues = originalSelects.map(sel => sel.value);

                    // Minify SELECT elements with many options (e.g. phone prefix select)
                    const selects = Array.from(clone.querySelectorAll("select"));
                    selects.forEach((select, selectIdx) => {
                        const originalValue = (selectedValues[selectIdx] || '').toLowerCase();
                        const options = Array.from(select.querySelectorAll("option"));
                        if (options.length > 15) {
                            const keptOptions = [];
                            options.forEach(opt => {
                                const text = opt.textContent.toLowerCase();
                                const val = (opt.getAttribute('value') || '').toLowerCase();
                                
                                // Keep if it was the selected option in the original select, or has selected attribute
                                if (opt.selected || opt.hasAttribute('selected') || (originalValue && (val === originalValue || text === originalValue))) {
                                    keptOptions.push(opt);
                                    return;
                                }
                                
                                // Keep if matches any keyword
                                const matchesKeyword = keywords && keywords.some(kw => text.includes(kw) || val.includes(kw));
                                if (matchesKeyword) {
                                    keptOptions.push(opt);
                                    return;
                                }
                            });
                            
                            // If we kept nothing, or very few, add the first 5 options as fallback
                            if (keptOptions.length < 5) {
                                for (let i = 0; i < Math.min(5, options.length); i++) {
                                    if (!keptOptions.includes(options[i])) {
                                        keptOptions.push(options[i]);
                                    }
                                }
                            }
                            
                            // Clear all options and append only kept ones
                            select.innerHTML = "";
                            keptOptions.forEach(opt => select.appendChild(opt));
                        }
                    });

                    const toUnwrap = Array.from(clone.querySelectorAll("div, span, strong, b, a, em, i, u, small, font, ul, ol, li"));
                    for (let i = toUnwrap.length - 1; i >= 0; i--) {
                        const node = toUnwrap[i];
                        if (node.parentNode && !node.hasAttribute('data-qa-idx')) {
                            while (node.firstChild) {
                                node.parentNode.insertBefore(node.firstChild, node);
                            }
                            node.parentNode.removeChild(node);
                        }
                    }

                    const tagsToKeep = new Set([
                        "FORM", "FIELDSET", "LEGEND", "LABEL", "INPUT",
                        "TEXTAREA", "SELECT", "OPTION",
                        "P", "H1", "H2", "H3", "H4", "H5", "H6"
                    ]);
                    const attrsToKeep = new Set([
                        "id", "name", "type", "value", "placeholder",
                        "checked", "selected", "required", "aria-label",
                        "aria-labelledby", "for", "data-qa-idx"
                    ]);

                    function cleanNode(node) {
                        if (!node) return;

                        if (node.nodeType !== Node.ELEMENT_NODE) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                const text = node.nodeValue.trim();
                                if (!text) {
                                    node.parentNode && node.parentNode.removeChild(node);
                                } else {
                                    node.nodeValue = text;
                                }
                            }
                            return;
                        }

                        if (!tagsToKeep.has(node.tagName) && !node.hasAttribute('data-qa-idx')) {
                            node.parentNode && node.parentNode.removeChild(node);
                            return;
                        }

                        const styleAttr = node.getAttribute('style') || '';
                        if (
                            node.getAttribute('type') === 'hidden' ||
                            styleAttr.includes('display: none') ||
                            styleAttr.includes('visibility: hidden') ||
                            node.hasAttribute('hidden')
                        ) {
                            node.parentNode && node.parentNode.removeChild(node);
                            return;
                        }

                        const attrs = Array.from(node.attributes);
                        attrs.forEach(attr => {
                            if (!attrsToKeep.has(attr.name.toLowerCase())) {
                                node.removeAttribute(attr.name);
                            }
                        });

                        const children = Array.from(node.childNodes);
                        children.forEach(cleanNode);

                        const containerTags = ["DIV", "SPAN", "P"];
                        if (containerTags.includes(node.tagName)) {
                            const hasChildren = node.childNodes.length > 0;
                            const hasText = node.textContent.trim().length > 0;
                            if (!hasChildren && !hasText) {
                                node.parentNode && node.parentNode.removeChild(node);
                            }
                        }
                    }

                    Array.from(clone.childNodes).forEach(cleanNode);

                    const cloneAttrs = Array.from(clone.attributes);
                    cloneAttrs.forEach(attr => {
                        if (!attrsToKeep.has(attr.name.toLowerCase())) {
                            clone.removeAttribute(attr.name);
                        }
                    });

                    return clone.outerHTML;
                }""",
                profile_keywords
            )
            if not html:
                logger.warning("[Scraper] JS evaluation returned empty string.")
                return ""
            
            orig_len = len(html)
            html = re.sub(r'\s+', ' ', html)
            html = re.sub(r'>\s+<', '><', html)
            html = html.strip()
            logger.info(f"[Scraper] Extracted {orig_len:,} chars, compressed to {len(html):,} chars of modal HTML.")
            return html
        except Exception as e:
            logger.error(f"[Scraper] Error during HTML clean and tag: {e}")
            return ""

    async def detect_success_element(self, target) -> bool:
        """Scoped locator success detection to prevent description panel false positives."""
        try:
            modal = await self.get_active_modal(target)
            curr_target = modal if modal else target

            # LinkedIn & Indeed success element selectors
            success_selectors = [
                "[data-test-modal] h2",
                "[data-test-modal-title]",
                "[aria-label*='application'] h3",
                "h3.t-18",
                ".ia-PostApply-success",
                ".ia-BasePage--success",
                "h1:has-text('submitted')",
                "h2:has-text('submitted')",
                "h3:has-text('submitted')",
                "p:has-text('submitted')",
            ]

            for sel in success_selectors:
                try:
                    loc = curr_target.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible(timeout=500):
                        text = (await loc.inner_text()).lower()
                        success_signals = [
                            "application sent",
                            "application was sent",
                            "successfully submitted",
                            "your application was submitted",
                            "submitted!",
                            "done"
                        ]
                        if any(s in text for s in success_signals):
                            logger.info(f"[DOMLayer] Success detected via '{sel}': {text}")
                            return True
                except Exception:
                    pass

            # Fallback container check but scoped specifically to modal text elements
            modal_text = (await curr_target.inner_text()).lower()
            success_lines = [
                "application sent",
                "application was sent",
                "successfully submitted",
                "your application was submitted",
            ]
            # Verify if it's a short modal confirming success rather than a long description
            if len(modal_text) < 1500 and any(s in modal_text for s in success_lines):
                logger.info(f"[DOMLayer] Success detected via container text check.")
                return True

        except Exception as e:
            logger.error(f"[DOMLayer] Error in detect_success_element: {e}")

        return False

    async def check_required_empty(self, target) -> list[str]:
        """JS evaluation of required fields within modal scope."""
        modal = await self.get_active_modal(target)
        curr_target = modal if modal else target
        
        try:
            return await curr_target.evaluate("""() => {
                const required = document.querySelectorAll('[required], [aria-required="true"]');
                const empty = [];
                for (const el of required) {
                    const v = (el.value || '').trim();
                    if (!v) {
                        empty.push(el.getAttribute('aria-label')
                                  || el.getAttribute('name')
                                  || el.getAttribute('data-qa-idx')
                                  || 'unknown');
                    }
                }
                return empty;
            }""")
        except Exception as e:
            logger.warning(f"[DOMLayer] check_required_empty evaluation failed: {e}")
            return []

    def extract_tagged_indices(self, html: str) -> set[str]:
        """Extract all data-qa-idx values. Used by HallucinationGuard."""
        return set(re.findall(r'data-qa-idx="(\d+)"', html))

    async def extract_tagged_fields(self, html: str) -> list[dict]:
        """Parse field metadata from minified HTML."""
        soup = BeautifulSoup(html, "html.parser")
        fields = []
        for el in soup.find_all(attrs={"data-qa-idx": True}):
            fields.append({
                "qa_idx":      el.get("data-qa-idx", ""),
                "type":        el.get("type", el.name),
                "aria-label":  el.get("aria-label", ""),
                "placeholder": el.get("placeholder", ""),
                "name":        el.get("name", ""),
                "id":          el.get("id", ""),
                "value":       el.get("value", ""),
                "required":    el.has_attr("required"),
            })
        return fields
