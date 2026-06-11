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
            logger.warning("[Scraper] No active modal found — falling back to target body.")
            if hasattr(target, "locator"):
                modal_locator = target.locator("body")
            else:
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

                    const originalInputs = Array.from(modal.querySelectorAll("input, textarea"));
                    const inputValues = originalInputs.map(el => el.type === 'checkbox' || el.type === 'radio' ? el.checked : el.value);

                    // Minify SELECT elements with many options (e.g. phone prefix select)
                    const selects = Array.from(clone.querySelectorAll("select"));
                    
                    const clonedInputs = Array.from(clone.querySelectorAll("input, textarea"));
                    clonedInputs.forEach((el, i) => {
                        if (el.type === 'checkbox' || el.type === 'radio') {
                            if (inputValues[i]) el.setAttribute('checked', 'checked');
                            else el.removeAttribute('checked');
                        } else {
                            if (inputValues[i]) el.setAttribute('value', inputValues[i]);
                        }
                    });

                    selects.forEach((select, selectIdx) => {
                        const originalValue = (selectedValues[selectIdx] || '').toLowerCase();
                        const options = Array.from(select.querySelectorAll("option"));
                        if (options.length > 20) {
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
                            
                            // If we kept nothing, or very few, add the first 3 options as fallback
                            if (keptOptions.length < 3) {
                                for (let i = 0; i < Math.min(3, options.length); i++) {
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

                    const toUnwrap = Array.from(clone.querySelectorAll("div, span, strong, b, a, em, i, u, small, font, ul, ol, li, section, main, header, footer, aside, article, nav, details"));
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
                        "aria-labelledby", "for", "data-qa-idx",
                        "disabled", "readonly", "aria-disabled", "aria-readonly"
                    ]);

                    function cleanNode(node) {
                        if (!node) return;

                        if (node.nodeType !== Node.ELEMENT_NODE) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                let text = node.nodeValue.trim();
                                if (!text) {
                                    node.parentNode && node.parentNode.removeChild(node);
                                } else {
                                    if (text.length > 150) {
                                        text = text.substring(0, 150) + "...";
                                    }
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
            if hasattr(curr_target, "goto"):
                modal_text = (await curr_target.locator("body").inner_text()).lower()
            else:
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
            return await curr_target.evaluate("""(node) => {
                const root = node || document;
                const required = root.querySelectorAll('[required], [aria-required="true"]');
                const empty = [];
                const checkedRadioGroups = new Set();
                
                for (const el of required) {
                    const type = (el.getAttribute('type') || '').toLowerCase();
                    const name = el.getAttribute('name');
                    
                    if (type === 'radio') {
                        if (name) {
                            if (checkedRadioGroups.has(name)) continue;
                            checkedRadioGroups.add(name);
                            const group = root.querySelectorAll(`input[type="radio"][name="${name}"]`);
                            const anyChecked = Array.from(group).some(r => r.checked);
                            if (!anyChecked) {
                                empty.push(el.getAttribute('aria-label')
                                          || name
                                          || el.getAttribute('data-qa-idx')
                                          || 'unknown');
                            }
                        } else {
                            if (!el.checked) {
                                empty.push(el.getAttribute('aria-label')
                                          || el.getAttribute('data-qa-idx')
                                          || 'unknown');
                            }
                        }
                    } else if (type === 'checkbox') {
                        if (!el.checked) {
                            empty.push(el.getAttribute('aria-label')
                                      || el.getAttribute('name')
                                      || el.getAttribute('data-qa-idx')
                                      || 'unknown');
                        }
                    } else {
                        const v = (el.value || '').trim();
                        const vLower = v.toLowerCase();
                        if (!v || vLower === 'select an option' || vLower === 'select' || vLower === 'select_one' || vLower === '--') {
                            empty.push(el.getAttribute('aria-label')
                                      || el.getAttribute('name')
                                      || el.getAttribute('data-qa-idx')
                                      || 'unknown');
                        }
                    }
                }
                return empty;
            }""")
        except Exception as e:
            logger.warning(f"[DOMLayer] check_required_empty evaluation failed: {e}")
            return []

    def extract_tagged_indices(self, html: str) -> set[str]:
        """Extract all data-qa-idx values. Used by HallucinationGuard."""
        # Handle both HTML (data-qa-idx="1") and minified schema format (qa_idx: 1)
        indices = re.findall(r'data-qa-idx="(\d+)"', html)
        if not indices:
            indices = re.findall(r'qa_idx:\s*(\d+)', html)
        return set(indices)

    async def extract_tagged_fields(self, html: str) -> list[dict]:
        """Parse field metadata from minified HTML."""
        soup = BeautifulSoup(html, "html.parser")
        fields = []
        for el in soup.find_all(attrs={"data-qa-idx": True}):
            field_id = el.get("id", "")
            label_text = ""
            if field_id:
                label_el = soup.find("label", attrs={"for": field_id})
                if label_el:
                    label_text = label_el.get_text(strip=True)
                    
            fields.append({
                "qa_idx":      el.get("data-qa-idx", ""),
                "type":        el.get("type", el.name),
                "aria-label":  el.get("aria-label", ""),
                "placeholder": el.get("placeholder", ""),
                "name":        el.get("name", ""),
                "id":          field_id,
                "value":       el.get("value", ""),
                "required":    el.has_attr("required"),
                "checked":     el.has_attr("checked"),
                "label":       label_text,
            })
        return fields

    async def extract_structured_schema(self, target, profile: Optional[dict] = None) -> list[dict]:
        """
        Extracts interactive fields from the modal viewport as structured JSON using
        Playwright's locator attributes and accessibility guidelines.
        """
        modal_locator = await self.get_active_modal(target)
        curr_target = modal_locator if modal_locator else target

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
            # We first run a DOM pass to ensure data-qa-idx properties are updated/injected
            # so Playwright selectors can interact with data-qa-idx keys consistently
            await self.clean_and_tag(target, profile)

            fields = await curr_target.evaluate(
                """(container, keywords) => {
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

                    const selectors = ["input", "select", "textarea"].join(",");
                    const elements = Array.from(container.querySelectorAll(selectors));
                    
                    return elements.filter(isVisible).map(el => {
                        const id = el.id || "";
                        const name = el.name || "";
                        const type = (el.getAttribute('type') || el.tagName.toLowerCase()).toLowerCase();
                        const qa_idx = el.getAttribute('data-qa-idx') || "";
                        const placeholder = el.placeholder || "";
                        const ariaLabel = el.getAttribute('aria-label') || "";
                        const required = el.hasAttribute('required') || el.getAttribute('aria-required') === 'true';
                        const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
                        
                        // Resolve label text
                        let labelText = "";
                        if (id) {
                            const labelEl = container.querySelector(`label[for="${id}"]`);
                            if (labelEl) {
                                labelText = labelEl.textContent.trim();
                            }
                        }
                        if (!labelText) {
                            // Try parent label
                            let parent = el.parentElement;
                            while (parent && parent !== container) {
                                if (parent.tagName === 'LABEL') {
                                    labelText = parent.textContent.trim();
                                    break;
                                }
                                parent = parent.parentElement;
                            }
                        }
                        
                        // Extract select options if it's a dropdown
                        let options = [];
                        if (el.tagName.toLowerCase() === 'select') {
                            const allOpts = Array.from(el.options);
                            const originalValue = (el.value || '').toLowerCase();
                            
                            if (allOpts.length > 20) {
                                const keptOpts = [];
                                allOpts.forEach(opt => {
                                    const text = opt.textContent.toLowerCase();
                                    const val = (opt.getAttribute('value') || '').toLowerCase();
                                    
                                    if (opt.selected || opt.hasAttribute('selected') || (originalValue && (val === originalValue || text === originalValue))) {
                                        keptOpts.push(opt.textContent.trim());
                                        return;
                                    }
                                    
                                    const matchesKeyword = keywords && keywords.some(kw => text.includes(kw) || val.includes(kw));
                                    if (matchesKeyword) {
                                        keptOpts.push(opt.textContent.trim());
                                        return;
                                    }
                                });
                                
                                if (keptOpts.length < 3) {
                                    for (let i = 0; i < Math.min(3, allOpts.length); i++) {
                                        const text = allOpts[i].textContent.trim();
                                        if (!keptOpts.includes(text)) {
                                            keptOpts.push(text);
                                        }
                                    }
                                }
                                options = keptOpts;
                            } else {
                                options = allOpts.map(o => o.textContent.trim()).filter(Boolean);
                            }
                        }

                        return {
                            qa_idx: qa_idx,
                            type: type,
                            id: id,
                            name: name,
                            placeholder: placeholder,
                            aria_label: ariaLabel,
                            "aria-label": ariaLabel,
                            label: labelText,
                            required: required,
                            disabled: disabled,
                            checked: el.checked || false,
                            value: el.value || "",
                            options: options
                        };
                    });
                }""",
                profile_keywords
            )
            return fields
        except Exception as e:
            logger.error(f"[DOMLayer] extract_structured_schema failed: {e}")
            return []

    def to_minified_schema_string(self, fields: list[dict]) -> str:
        """Serialize structured fields list to a token-efficient text format."""
        lines = []
        for f in fields:
            if not f.get("qa_idx"):
                continue
            line = f"- qa_idx: {f['qa_idx']} | type: {f['type']}"
            label = f.get("label") or f.get("aria_label") or f.get("placeholder") or f.get("name")
            if label:
                line = f"{line} | label: {label}"
            if f.get("required"):
                line = f"{line} | required: true"
            if f.get("disabled"):
                line = f"{line} | disabled: true"
            if f.get("type") in ("checkbox", "radio"):
                line = f"{line} | checked: {str(f['checked']).lower()}"
            elif f.get("value"):
                line = f"{line} | value: {f['value']}"
            if f.get("options"):
                line = f"{line} | options: {f['options']}"
            lines.append(line)
        return "\n".join(lines)

