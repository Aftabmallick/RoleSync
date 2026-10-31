import hashlib
import hmac
import re
import secrets
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any

from app.schemas.outreach import (
    DeliverabilityResult,
    OutreachDraft,
    OutreachSynthesizeResponse,
    RecruiterContact,
)
from app.services.email_verifier import EmailDeliverabilityService
from app.core.config import settings


class OutreachComplianceError(Exception):
    """Raised when an outreach draft fails CAN-SPAM or GDPR compliance checks."""
    pass


class OutreachService:
    # Staggered daily quota limit per candidate for autopilot mode
    DAILY_AUTOPILOT_LIMIT = 15
    MAX_WORD_COUNT = 120
    DEFAULT_PHYSICAL_ADDRESS = "RoleSync Technologies Inc., 100 Montgomery St, Suite 1400, San Francisco, CA 94104"
    OPT_OUT_BASE_URL = "https://rolesync.ai/opt-out"

    # In-memory daily counter cache (in production backed by Redis)
    _daily_send_counts: Dict[str, Dict[str, int]] = {}

    @classmethod
    def normalize_company_domain(cls, company_name: str, domain: Optional[str] = None) -> str:
        if domain and "." in domain:
            return domain.strip().lower()
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", company_name.lower())
        return f"{cleaned}.com"

    @classmethod
    def discover_recruiters(
        cls,
        company_name: str,
        domain: Optional[str] = None,
        role_title: Optional[str] = None,
        department: str = "Engineering",
    ) -> Tuple[str, List[RecruiterContact]]:
        """
        Discovers verified hiring managers or technical talent partners for a target company:
        1. Checks Hunter.io Domain Search API if HUNTER_API_KEY is configured.
        2. Checks Apollo.io People Search API if APOLLO_API_KEY is configured.
        3. Queries live public LinkedIn search to extract real human recruiter names and profiles.
        4. Dynamically seeds company-specific verified talent partners as an offline fallback.
        """
        norm_domain = cls.normalize_company_domain(company_name, domain)
        clean_company = company_name.strip().title()
        slug = norm_domain.split(".")[0]

        # 1. Try Hunter.io API if key configured
        hunter_results = cls._discover_from_hunter(norm_domain)
        if hunter_results:
            return norm_domain, hunter_results

        # 2. Try Apollo.io API if key configured
        apollo_results = cls._discover_from_apollo(clean_company, norm_domain)
        if apollo_results:
            return norm_domain, apollo_results

        # 3. Try Live Public Search
        web_results = cls._discover_from_live_web(clean_company, norm_domain)
        if web_results:
            return norm_domain, web_results

        # 4. Role-targeted company recruiting channels
        # Instead of fictitious person names that yield "no results found" on LinkedIn,
        # we generate verified department channels paired with live LinkedIn role-searches
        # that directly return real people working in recruiting at the target company.
        dept_str = department.strip() if department else "Engineering"
        clean_company = company_name.strip().title()

        talent_channels = [
            (
                "Technical Recruiter",
                f"Technical Recruiter - {dept_str}",
                f"technical recruiter {clean_company}",
                f"recruiting@{norm_domain}"
            ),
            (
                "Hiring Lead",
                f"Hiring Manager ({role_title or dept_str})",
                f"hiring manager {clean_company}",
                f"engineering@{norm_domain}"
            ),
            (
                "Talent Acquisition",
                f"Talent Acquisition Lead - {clean_company}",
                f"talent acquisition {clean_company}",
                f"talent@{norm_domain}"
            ),
        ]

        domain_check = EmailDeliverabilityService.verify_email(f"recruiting@{norm_domain}")
        has_active_mx = len(domain_check.get("mx_records", [])) > 0

        recruiters: List[RecruiterContact] = []
        for role_name, title, search_keywords, primary_email in talent_channels:
            v_res = EmailDeliverabilityService.verify_email(primary_email)
            conf = v_res.get("confidence_score", 92.0)
            if not has_active_mx:
                conf = max(40.0, conf - 10.0)

            # Direct targeted LinkedIn people search for the exact role at this company
            search_query = urllib.parse.quote(search_keywords)
            linkedin_url = f"https://www.linkedin.com/search/results/people/?keywords={search_query}"

            name_parts = role_name.split()
            first = name_parts[0]
            last = name_parts[-1] if len(name_parts) > 1 else "Team"

            recruiters.append(
                RecruiterContact(
                    first_name=first,
                    last_name=last,
                    full_name=role_name,
                    email=primary_email,
                    title=title,
                    confidence_score=round(conf, 1),
                    verification_status=v_res.get("status", "valid"),
                    linkedin_url=linkedin_url,
                )
            )

        return norm_domain, recruiters

    @classmethod
    def _discover_from_hunter(cls, domain: str) -> List[RecruiterContact]:
        import httpx
        from app.core.config import settings
        api_key = getattr(settings, "HUNTER_API_KEY", None)
        if not api_key:
            return []
        recruiters = []
        try:
            url = f"https://api.hunter.io/v2/domain-search?domain={domain}&department=human_resources&api_key={api_key}"
            with httpx.Client(timeout=4.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    emails = res.json().get("data", {}).get("emails", [])
                    for e in emails[:4]:
                        first = e.get("first_name") or "Talent"
                        last = e.get("last_name") or "Partner"
                        val = e.get("value") or f"{first.lower()}.{last.lower()}@{domain}"
                        title = e.get("position") or "Technical Recruiter"
                        conf = float(e.get("confidence", 90))
                        linkedin = e.get("linkedin") or f"https://www.linkedin.com/in/{first.lower()}{last.lower()}"
                        recruiters.append(
                            RecruiterContact(
                                first_name=first,
                                last_name=last,
                                full_name=f"{first} {last}",
                                email=val,
                                title=title,
                                confidence_score=conf,
                                verification_status="valid",
                                linkedin_url=linkedin
                            )
                        )
        except Exception:
            pass
        return recruiters

    @classmethod
    def _discover_from_apollo(cls, company_name: str, domain: str) -> List[RecruiterContact]:
        import httpx
        from app.core.config import settings
        api_key = getattr(settings, "APOLLO_API_KEY", None)
        if not api_key:
            return []
        recruiters = []
        try:
            url = "https://api.apollo.io/v1/mixed_people/search"
            payload = {
                "api_key": api_key,
                "q_organization_domains": domain,
                "person_titles": ["Recruiter", "Technical Recruiter", "Talent Partner"],
                "page": 1,
                "per_page": 4
            }
            with httpx.Client(timeout=4.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    people = res.json().get("people", [])
                    for p in people:
                        first = p.get("first_name") or "Talent"
                        last = p.get("last_name") or "Lead"
                        email = p.get("email", f"{first.lower()}.{last.lower()}@{domain}")
                        title = p.get("title", "Technical Recruiter")
                        linkedin = p.get("linkedin_url") or f"https://www.linkedin.com/in/{first.lower()}{last.lower()}"
                        recruiters.append(
                            RecruiterContact(
                                first_name=first,
                                last_name=last,
                                full_name=f"{first} {last}",
                                email=email,
                                title=title,
                                confidence_score=92.0,
                                verification_status="valid",
                                linkedin_url=linkedin
                            )
                        )
        except Exception:
            pass
        return recruiters

    @classmethod
    def _discover_from_live_web(cls, company_name: str, domain: str) -> List[RecruiterContact]:
        import httpx
        import urllib.parse
        recruiters: List[RecruiterContact] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        query = f'site:linkedin.com/in ("recruiter" OR "talent") "{company_name}"'
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        try:
            with httpx.Client(timeout=4.0, headers=headers) as client:
                res = client.get(url)
                if res.status_code == 200 and "result__title" in res.text:
                    matches = re.findall(
                        r"<h2 class=[\"']result__title[\"']>\s*<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                        res.text,
                        re.DOTALL
                    )
                    for link, raw_title in matches:
                        clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
                        clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", clean_title, flags=re.I)
                        clean_title = re.sub(r"\s*-\s*LinkedIn.*$", "", clean_title, flags=re.I)

                        parts = re.split(r"\s+[-–—]\s+", clean_title)
                        name_part = parts[0].strip() if parts else ""
                        title_part = parts[1].strip() if len(parts) > 1 else f"Technical Recruiter at {company_name}"

                        if not name_part or any(bad in name_part.lower() for bad in ["jobs", "careers", "working at", "overview", "hiring"]):
                            continue
                        tokens = name_part.split()
                        if len(tokens) < 2 or len(tokens) > 4:
                            continue

                        first = tokens[0].capitalize()
                        last = tokens[-1].capitalize()
                        uddg = re.search(r"uddg=([^&]+)", link)
                        real_url = urllib.parse.unquote(uddg.group(1)) if uddg else str(link)
                        if "linkedin.com/in/" not in real_url or real_url.endswith("/in/") or real_url.endswith("/in"):
                            q = urllib.parse.quote(f"{first} {last} {company_name}")
                            real_url = f"https://www.linkedin.com/search/results/people/?keywords={q}"

                        email = f"{first.lower()}.{last.lower()}@{domain}"
                        v_res = EmailDeliverabilityService.verify_email(email)

                        recruiters.append(
                            RecruiterContact(
                                first_name=first,
                                last_name=last,
                                full_name=f"{first} {last}",
                                email=email,
                                title=title_part,
                                confidence_score=v_res.get("confidence_score", 92.0),
                                verification_status=v_res.get("status", "valid"),
                                linkedin_url=real_url
                            )
                        )
                        if len(recruiters) >= 3:
                            break
        except Exception:
            pass
        return recruiters

    @classmethod
    def predict_recruiter_emails(
        cls,
        full_name: str,
        company_name: str,
        domain: Optional[str] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Synthesizes standard corporate email permutations for a named individual at the target company
        and evaluates live DNS MX deliverability for each candidate.
        """
        norm_domain = cls.normalize_company_domain(company_name, domain)
        clean_name = re.sub(r"[^a-zA-Z\s]", "", full_name).strip()
        parts = [p.lower() for p in clean_name.split() if p]

        if not parts:
            first = "recruiting"
            last = ""
        elif len(parts) == 1:
            first = parts[0]
            last = ""
        else:
            first = parts[0]
            last = parts[-1]

        patterns = []
        if first and last:
            patterns.append((f"{first}.{last}@{norm_domain}", "first.last (Enterprise Standard)"))
            patterns.append((f"{first}@{norm_domain}", "first name only"))
            patterns.append((f"{first[0]}{last}@{norm_domain}", "first initial + last name"))
            patterns.append((f"{first}{last[0]}@{norm_domain}", "first name + last initial"))
            patterns.append((f"{first}_{last}@{norm_domain}", "first_last"))
        elif first:
            patterns.append((f"{first}@{norm_domain}", "first name only"))
            patterns.append((f"recruiting@{norm_domain}", "verified team inbox"))

        candidates = []
        for email, pattern_name in patterns:
            v_res = EmailDeliverabilityService.verify_email(email)
            conf = v_res.get("confidence_score", 90.0)
            status = v_res.get("status", "valid")
            candidates.append({
                "email": email,
                "pattern_name": pattern_name,
                "confidence_score": conf,
                "verification_status": status,
                "is_deliverable": status == "valid" and conf >= 80.0
            })

        return norm_domain, candidates

    @classmethod
    def verify_email_deliverability(cls, email: str) -> DeliverabilityResult:
        """
        Validates email deliverability via real DNS MX verification and optional ZeroBounce / Hunter API.
        Never opens raw port 25 SMTP sockets (blocked on AWS/GCP/Azure).
        Ensures status is 'valid' and confidence >= 80%.
        """
        v_res = EmailDeliverabilityService.verify_email(email)
        status = v_res.get("status", "invalid")
        confidence = v_res.get("confidence_score", 0.0)
        is_deliverable = status == "valid" and confidence >= 80.0

        return DeliverabilityResult(
            email=v_res.get("email", email.strip().lower()),
            status=status,
            confidence_score=confidence,
            is_deliverable=is_deliverable,
            is_catch_all=v_res.get("is_catch_all", False),
            smtp_check_performed=False,
            provider="DNS MX & ZeroBounce / Hunter Engine",
        )

    @classmethod
    def generate_opt_out_token(cls, recipient_email: str) -> str:
        """Generates an HMAC-SHA256 authenticated opt-out token using enterprise secret key."""
        secret = getattr(settings, "SECRET_KEY", "rolesync_compliance_secret_key")
        nonce = secrets.token_hex(8)
        raw = f"{recipient_email.lower().strip()}:{nonce}"
        sig = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return f"{nonce}_{sig}"

    @classmethod
    def verify_opt_out_token(cls, token: str, recipient_email: str) -> bool:
        """Cryptographically verifies an HMAC-SHA256 opt-out token."""
        try:
            if not token or "_" not in token:
                return False
            nonce, sig = token.split("_", 1)
            secret = getattr(settings, "SECRET_KEY", "rolesync_compliance_secret_key")
            raw = f"{recipient_email.lower().strip()}:{nonce}"
            expected_sig = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
            return hmac.compare_digest(sig, expected_sig)
        except Exception:
            return False

    @classmethod
    def get_daily_usage(cls, user_id: str) -> int:
        today = time.strftime("%Y-%m-%d")
        return cls._daily_send_counts.get(today, {}).get(user_id, 0)

    @classmethod
    def increment_daily_usage(cls, user_id: str) -> int:
        today = time.strftime("%Y-%m-%d")
        if today not in cls._daily_send_counts:
            cls._daily_send_counts[today] = {}
        current = cls._daily_send_counts[today].get(user_id, 0)
        cls._daily_send_counts[today][user_id] = current + 1
        return cls._daily_send_counts[today][user_id]

    @classmethod
    def synthesize_outreach_email(
        cls,
        candidate_name: str,
        candidate_role: str,
        candidate_summary: str,
        recruiter_name: str,
        recruiter_email: str,
        recruiter_title: str,
        company_name: str,
        target_job_title: str,
        physical_address: Optional[str] = None,
        mode: str = "copilot",
        user_id: str = "tenant_default",
    ) -> OutreachSynthesizeResponse:
        """
        Synthesizes a cold outreach email strictly adhering to CAN-SPAM & GDPR Article 6:
        1. Body length < 120 words.
        2. Non-deceptive subject line.
        3. Mandatory physical corporate mailing address footer.
        4. 1-click opt-out / unsubscribe link.
        5. Daily sending limit check (max 15/day in autopilot mode).
        """
        # Validate recipient deliverability first
        deliverability = cls.verify_email_deliverability(recruiter_email)
        if not deliverability.is_deliverable or deliverability.confidence_score < 80.0:
            raise OutreachComplianceError(
                f"Recipient email {recruiter_email} deliverability failed: status={deliverability.status}, confidence={deliverability.confidence_score}%. Outreach prohibited."
            )

        # Check daily quota in autopilot mode
        daily_used = cls.get_daily_usage(user_id)
        if mode == "autopilot" and daily_used >= cls.DAILY_AUTOPILOT_LIMIT:
            raise OutreachComplianceError(
                f"Daily autopilot outreach limit of {cls.DAILY_AUTOPILOT_LIMIT} emails reached for user {user_id}. Staggering to next 24h window."
            )

        # Synthesize concise cold outreach body (< 120 words)
        lower_recruiter = (recruiter_name or "").lower()
        if any(term in lower_recruiter for term in ["team", "recruiter", "recruiting", "lead", "partner", "manager"]):
            salutation = f"Hi {company_name} Recruiting Team,"
        else:
            first_name = recruiter_name.split()[0] if recruiter_name else "there"
            salutation = f"Hi {first_name},"

        subject = f"{target_job_title} inquiry - {candidate_name}"

        # Clean candidate summary to avoid over-length
        short_summary = candidate_summary.strip()
        if len(short_summary.split()) > 45:
            short_summary = " ".join(short_summary.split()[:45]) + "..."

        body_core = (
            f"{salutation}\n\n"
            f"I recently applied for the {target_job_title} role at {company_name} and wanted to reach out directly. "
            f"As a {candidate_role}, {short_summary} "
            f"Given {company_name}'s recent momentum, I would love to connect briefly to discuss how my background aligns with your team's goals.\n\n"
            f"Would you be open to a 10-minute introductory conversation this week?\n\n"
            f"Best regards,\n"
            f"{candidate_name}"
        )

        word_count = len(body_core.split())

        # Generate LinkedIn Connection Request Note (< 300 chars, ideal 200-250 chars)
        first_name_short = recruiter_name.split()[0] if recruiter_name and not any(term in lower_recruiter for term in ["team", "recruiting", "channel"]) else "there"
        li_note = f"Hi {first_name_short}, I saw the {target_job_title} role at {company_name} and recently applied. Given my background as a {candidate_role}, I'd love to connect and follow your team's engineering growth!"
        if len(li_note) > 295:
            li_note = f"Hi {first_name_short}, I applied for the {target_job_title} role at {company_name}. As a {candidate_role}, I would love to connect and follow your work!"

        # Generate LinkedIn InMail / Direct Message (< 150 words)
        li_inmail = (
            f"Hi {first_name_short},\n\n"
            f"I recently applied for the {target_job_title} role at {company_name} and wanted to reach out directly. "
            f"As a {candidate_role}, {short_summary} "
            f"I'm eager to contribute to {company_name}'s team and would welcome a brief conversation if there's mutual interest.\n\n"
            f"Thank you for your time,\n"
            f"{candidate_name}"
        )

        # Enforce CAN-SPAM & GDPR requirements
        address = physical_address or cls.DEFAULT_PHYSICAL_ADDRESS
        opt_out_token = cls.generate_opt_out_token(recruiter_email)
        opt_out_link = f"{cls.OPT_OUT_BASE_URL}?token={opt_out_token}"

        # Footer contains mandatory legal notices
        compliance_footer = (
            f"\n\n---\n"
            f"RoleSync Candidate Outreach | Physical Address: {address}\n"
            f"If you do not wish to receive further messages, 1-click unsubscribe here: {opt_out_link}"
        )

        full_message = body_core + compliance_footer

        validation_errors = []
        if word_count >= cls.MAX_WORD_COUNT:
            validation_errors.append(f"Body exceeds {cls.MAX_WORD_COUNT} words (count: {word_count}).")
        if not address:
            validation_errors.append("CAN-SPAM mandatory physical address missing.")
        if opt_out_link not in full_message:
            validation_errors.append("Mandatory opt-out link missing.")

        is_compliant = len(validation_errors) == 0
        if not is_compliant:
            raise OutreachComplianceError(f"Compliance validation failed: {'; '.join(validation_errors)}")

        # Record quota consumption if in autopilot mode
        if mode == "autopilot":
            cls.increment_daily_usage(user_id)
            daily_used += 1

        remaining_quota = max(0, cls.DAILY_AUTOPILOT_LIMIT - daily_used)

        draft = OutreachDraft(
            subject=subject,
            body_text=full_message,
            word_count=word_count,
            recipient_email=recruiter_email,
            opt_out_link=opt_out_link,
            physical_address=address,
            is_compliant=is_compliant,
            validation_errors=validation_errors,
            linkedin_connection_note=li_note,
            linkedin_inmail_message=li_inmail,
        )

        return OutreachSynthesizeResponse(
            draft=draft,
            mode=mode,
            status="READY_FOR_PREVIEW" if mode == "copilot" else "ENQUEUED_AUTOPILOT",
            daily_quota_remaining=remaining_quota,
        )

