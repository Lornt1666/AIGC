from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RadarDecision(str, Enum):
    QUEUE_FOR_PHASE_3 = "queue_for_phase_3"
    QUEUE_WITH_CAUTION = "queue_with_caution"
    HOLD_FOR_HUMAN_REVIEW = "hold_for_human_review"
    REJECT = "reject"


class SourceRisk(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


@dataclass
class OpportunityRecord:
    opportunity_id: str
    source_platform: str
    source_type: str
    source_url: str
    source_attribution_required: bool
    discovered_at: str
    title: str
    employer: str = ""
    client: str = ""
    location: str = ""
    remote_status: str = "unknown"
    work_type: str = "unknown"
    employment_type: str = "unknown"
    pay_min: Optional[float] = None
    pay_max: Optional[float] = None
    pay_currency: str = ""
    pay_interval: str = "unknown"
    deadline: str = ""
    posted_at: str = ""
    updated_at: str = ""
    description_plain: str = ""
    description_html: str = ""
    requirements: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)
    skills_detected: List[str] = field(default_factory=list)
    tools_detected: List[str] = field(default_factory=list)
    discipline_taxonomy: List[str] = field(default_factory=list)
    automation_signals: Dict[str, bool] = field(default_factory=dict)
    ai_use_signals: Dict[str, bool] = field(default_factory=dict)
    platform_policy_status: str = "yellow"
    risk_flags: List[str] = field(default_factory=list)
    forbidden_flags: List[str] = field(default_factory=list)
    approval_required_before: List[str] = field(
        default_factory=lambda: [
            "message_employer",
            "apply",
            "submit_proposal",
            "submit_deliverable",
            "use_credentials",
            "use_operator_identity",
        ]
    )
    radar_score: int = 0
    radar_decision: str = RadarDecision.HOLD_FOR_HUMAN_REVIEW.value
    audit_notes: str = ""


@dataclass
class FetchResult:
    source_slug: str
    source_name: str
    raw_records: List[Dict[str, Any]]
    normalized_records: List[OpportunityRecord]


@dataclass
class RunStats:
    run_id: str
    started_at: str
    ended_at: str = ""
    sources_queried: List[str] = field(default_factory=list)
    connector_errors: Dict[str, str] = field(default_factory=dict)
    total_raw_records: int = 0
    duplicates_removed: int = 0
    total_processed: int = 0
    rejected_records: int = 0
    queued_for_phase_3: int = 0
    held_for_review: int = 0


class AuditLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, data: Dict[str, Any]) -> None:
        event = {
            "timestamp": utc_now(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


class TextCleaner:
    @staticmethod
    def html_to_text(value: str) -> str:
        if not value:
            return ""
        value = unescape(value)
        value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
        value = re.sub(r"</(p|li|div|h[1-6])>", "\n", value, flags=re.I)
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"[ \t\r\f\v]+", " ", value)
        value = re.sub(r"\n\s+", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    @staticmethod
    def normalize(value: Any) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    @staticmethod
    def normalize_list(values: Any) -> List[str]:
        if not values:
            return []
        if isinstance(values, list):
            return sorted({TextCleaner.normalize(v) for v in values if TextCleaner.normalize(v)})
        return [TextCleaner.normalize(values)]


class Classifier:
    TAXONOMY_RULES = {
        "software_coding": [
            "python",
            "javascript",
            "typescript",
            "react",
            "node",
            "api",
            "backend",
            "frontend",
            "developer",
            "engineer",
            "software",
            "automation",
            "script",
            "github",
        ],
        "api_documentation": [
            "api documentation",
            "developer docs",
            "openapi",
            "swagger",
            "technical documentation",
            "sdk",
            "docs",
            "readme",
        ],
        "research": [
            "research",
            "market research",
            "competitive analysis",
            "deep research",
            "literature review",
            "analysis",
        ],
        "data_analysis": [
            "data",
            "spreadsheet",
            "excel",
            "sql",
            "analytics",
            "dashboard",
            "reporting",
            "csv",
        ],
        "business_operations": [
            "operations",
            "workflow",
            "process",
            "business process",
            "sop",
        ],
        "prompt_engineering": [
            "prompt",
            "llm",
            "language model",
            "chatgpt",
            "generative ai",
        ],
        "writing_content": [
            "writer",
            "copywriter",
            "content",
            "blog",
            "editor",
            "documentation",
            "article",
        ],
        "design_ui_ux": [
            "ui",
            "ux",
            "figma",
            "designer",
            "product design",
        ],
        "qa_testing": [
            "qa",
            "testing",
            "test cases",
            "bug",
            "quality assurance",
        ],
        "customer_support": [
            "customer support",
            "helpdesk",
            "support specialist",
            "technical support",
        ],
        "cybersecurity_bug_bounty": [
            "security",
            "bug bounty",
            "vulnerability",
            "penetration",
            "infosec",
        ],
        "regulated_sensitive": [
            "legal counsel",
            "medical",
            "clinical",
            "therapy",
            "financial advice",
            "tax advice",
            "securities",
        ],
    }

    TOOL_KEYWORDS = [
        "python",
        "javascript",
        "typescript",
        "react",
        "node",
        "sql",
        "excel",
        "google sheets",
        "github",
        "openapi",
        "swagger",
        "figma",
        "zapier",
        "make.com",
    ]

    FORBIDDEN_OR_HIGH_RISK = [
        "fake review",
        "fake reviews",
        "fake engagement",
        "spam",
        "mass dm",
        "mass message",
        "mass messaging",
        "bypass",
        "captcha",
        "evade",
        "impersonate",
        "credential sharing",
        "malware",
        "phishing",
        "scrape linkedin",
        "auto apply hundreds",
        "avoid platform limits",
        "bypass detection",
    ]

    PRIVACY_SECURITY = [
        "personal data",
        "pii",
        "hipaa",
        "patient",
        "password",
        "credential",
        "secret key",
        "private key",
        "bank account",
    ]

    AI_FORBIDDEN = [
        "no ai",
        "ai prohibited",
        "do not use ai",
        "human-written only",
        "no chatgpt",
        "no generative ai",
    ]

    AI_ALLOWED = [
        "ai allowed",
        "ai tools allowed",
        "chatgpt allowed",
        "automation allowed",
        "use ai",
        "llm allowed",
    ]

    STRONG_TARGET_TERMS = [
        "api documentation",
        "developer documentation",
        "technical documentation",
        "process documentation",
        "documentation",
        "docs",
        "readme",
        "openapi",
        "swagger",
        "python",
        "automation",
        "script",
        "workflow",
        "spreadsheet",
        "excel",
        "sql",
        "csv",
        "dashboard",
        "data cleaning",
        "market research",
        "competitive analysis",
        "research report",
        "competitor research",
        "prompt",
        "system design",
        "good first issue",
        "help wanted",
        "bug",
        "test cases",
        "qa automation",
        "zapier",
        "make.com",
        "low-code",
        "no-code",
    ]

    MANAGEMENT_TITLE_TERMS = [
        "manager",
        "director",
        "head of",
        "vp ",
        "chief",
        "principal",
        "staff",
        "lead",
    ]

    EMPLOYMENT_ROLE_TITLE_TERMS = [
        "engineer",
        "developer",
        "manager",
        "designer",
        "associate",
        "specialist",
        "coordinator",
        "assistant",
        "consultant",
        "lead",
        "director",
        "head of",
    ]

    SENIOR_TITLE_TERMS = [
        "senior",
        "sr.",
        "staff",
        "principal",
        "lead",
        "head of",
    ]

    SALES_SUPPORT_TERMS = [
        "sales",
        "customer support",
        "customer success",
        "support consultant",
        "account executive",
        "account payable",
        "office assistant",
        "assistant",
        "coordinator",
        "client-facing",
        "phone support",
        "call center",
    ]

    CREATIVE_MEDIA_TERMS = [
        "video editor",
        "cinematic",
        "social media",
        "content creator",
        "influencer",
        "graphic designer",
    ]

    SUSPICIOUS_PAYMENT_TERMS = [
        "crypto",
        "ethereum",
        "bitcoin",
        "usdt",
        "74000 eth",
    ]

    def classify(self, record: OpportunityRecord) -> OpportunityRecord:
        text = self._record_text(record)
        title_text = record.title.lower()
        taxonomy = []
        for label, keywords in self.TAXONOMY_RULES.items():
            if any(keyword in text for keyword in keywords):
                taxonomy.append(label)

        if record.work_type == "open_source" and "open_source_contribution" not in taxonomy:
            taxonomy.append("open_source_contribution")

        record.discipline_taxonomy = sorted(set(taxonomy))
        record.automation_signals = {
            "api_related": "api" in text,
            "documentation_related": any(k in text for k in ["documentation", "docs", "readme"]),
            "research_related": any(k in text for k in ["research", "analysis", "review"]),
            "coding_related": any(
                k in text
                for k in ["python", "javascript", "developer", "engineer", "software", "code"]
            ),
            "data_related": any(k in text for k in ["data", "spreadsheet", "sql", "csv", "analytics"]),
            "writing_related": any(k in text for k in ["writer", "content", "copy", "article", "documentation"]),
            "repetitive_workflow": any(k in text for k in ["workflow", "repeatable", "process", "pipeline"]),
            "clear_deliverable": any(
                k in text
                for k in ["deliverable", "report", "documentation", "code", "dashboard", "summary", "readme"]
            ),
        }
        record.ai_use_signals = {
            "ai_allowed_explicit": any(k in text for k in self.AI_ALLOWED),
            "ai_forbidden_explicit": any(k in text for k in self.AI_FORBIDDEN),
            "ai_unclear": not any(k in text for k in self.AI_ALLOWED + self.AI_FORBIDDEN),
            "disclosure_needed": True,
        }
        record.forbidden_flags = [phrase for phrase in self.FORBIDDEN_OR_HIGH_RISK if phrase in text]

        if "regulated_sensitive" in record.discipline_taxonomy:
            add_once(record.risk_flags, "regulated_or_sensitive_domain")
        if record.ai_use_signals["ai_forbidden_explicit"]:
            add_once(record.risk_flags, "ai_use_forbidden_or_restricted")
        if any(term in text for term in self.PRIVACY_SECURITY):
            add_once(record.risk_flags, "privacy_or_security_sensitive")
        if not (record.pay_min or record.pay_max or record.pay_currency):
            add_once(record.risk_flags, "unclear_pay")
        if not record.employer and not record.client:
            add_once(record.risk_flags, "unclear_employer_or_client")
        if self._strong_target_hit_count(text) == 0 and record.work_type != "open_source":
            add_once(record.risk_flags, "weak_aigc_preferred_fit")
        if record.work_type == "job" and any(term in title_text for term in self.EMPLOYMENT_ROLE_TITLE_TERMS):
            add_once(record.risk_flags, "job_board_employment_role")
        if record.work_type == "job" and any(term in title_text for term in self.MANAGEMENT_TITLE_TERMS):
            add_once(record.risk_flags, "broad_management_role")
        if record.work_type == "job" and any(term in title_text for term in self.SENIOR_TITLE_TERMS):
            add_once(record.risk_flags, "senior_full_time_role")
        if any(term in text for term in self.SALES_SUPPORT_TERMS):
            add_once(record.risk_flags, "sales_support_or_admin_role")
        if any(term in text for term in self.CREATIVE_MEDIA_TERMS):
            add_once(record.risk_flags, "creative_media_role")
        if self._has_location_constraint(record):
            add_once(record.risk_flags, "location_constrained_role")
        if "bounty" in text and any(term in text for term in self.SUSPICIOUS_PAYMENT_TERMS):
            add_once(record.risk_flags, "suspicious_payment_setup")

        record.tools_detected = sorted(
            set(record.tools_detected + [tool for tool in self.TOOL_KEYWORDS if tool in text])
        )
        record.skills_detected = sorted(set(record.skills_detected))
        record.requirements = infer_bullets(record.description_plain, ["require", "must", "experience", "skill"])
        record.responsibilities = infer_bullets(record.description_plain, ["responsibil", "you will", "build", "maintain"])
        record.deliverables = infer_bullets(record.description_plain, ["deliver", "report", "documentation", "dashboard", "code"])
        return record

    @staticmethod
    def _record_text(record: OpportunityRecord) -> str:
        return " ".join(
            [
                record.title,
                record.description_plain,
                " ".join(record.requirements),
                " ".join(record.responsibilities),
                " ".join(record.deliverables),
                " ".join(record.skills_detected),
                " ".join(record.tools_detected),
            ]
        ).lower()

    @classmethod
    def _strong_target_hit_count(cls, text: str) -> int:
        return sum(1 for term in cls.STRONG_TARGET_TERMS if term in text)

    @staticmethod
    def _has_location_constraint(record: OpportunityRecord) -> bool:
        if record.work_type != "job":
            return False
        location = record.location.lower().strip()
        if not location:
            return False
        global_terms = ["worldwide", "anywhere", "global", "remote", "united states", "usa"]
        return not any(term in location for term in global_terms)


class RadarScorer:
    PREFERRED_TAXONOMY = {
        "software_coding",
        "api_documentation",
        "research",
        "data_analysis",
        "writing_content",
        "qa_testing",
        "prompt_engineering",
        "open_source_contribution",
    }

    STRONG_TARGET_TERMS = Classifier.STRONG_TARGET_TERMS

    CAUTION_PENALTIES = {
        "weak_aigc_preferred_fit": 16,
        "job_board_employment_role": 10,
        "broad_management_role": 12,
        "senior_full_time_role": 8,
        "sales_support_or_admin_role": 14,
        "creative_media_role": 12,
        "location_constrained_role": 8,
        "suspicious_payment_setup": 28,
        "unclear_pay": 5,
        "unclear_employer_or_client": 8,
    }

    def score(self, record: OpportunityRecord) -> OpportunityRecord:
        score = 0
        text = self._record_text(record)

        if record.platform_policy_status == SourceRisk.GREEN.value:
            score += 15
        elif record.platform_policy_status == SourceRisk.YELLOW.value:
            score += 10
        elif record.platform_policy_status == SourceRisk.ORANGE.value:
            score += 4

        if record.source_type in {"api", "rss", "public_feed"}:
            score += 10

        if record.title and (record.employer or record.client) and record.description_plain:
            score += 10
        elif record.title and record.description_plain:
            score += 7
        elif record.title:
            score += 4

        if record.automation_signals.get("clear_deliverable"):
            score += 10
        elif record.deliverables:
            score += 8

        if record.pay_min or record.pay_max:
            score += 10
        elif record.pay_currency:
            score += 6

        automation_true_count = sum(1 for value in record.automation_signals.values() if value)
        score += min(12, automation_true_count * 2)

        serious_risks = [
            flag
            for flag in record.risk_flags
            if flag
            not in {
                "unclear_pay",
                "unclear_employer_or_client",
                "weak_aigc_preferred_fit",
                "job_board_employment_role",
                "broad_management_role",
                "senior_full_time_role",
                "sales_support_or_admin_role",
                "creative_media_role",
                "location_constrained_role",
            }
        ]
        if not serious_risks:
            score += 10
        elif len(serious_risks) == 1:
            score += 5

        if record.platform_policy_status in {SourceRisk.GREEN.value, SourceRisk.YELLOW.value}:
            score += 10
        elif record.platform_policy_status == SourceRisk.ORANGE.value:
            score += 4

        target_hits = self._strong_target_hit_count(text)
        if target_hits >= 3:
            score += 15
        elif target_hits == 2:
            score += 10
        elif target_hits == 1:
            score += 6
        elif "open_source_contribution" in record.discipline_taxonomy:
            score += 8
        elif self.PREFERRED_TAXONOMY.intersection(set(record.discipline_taxonomy)):
            score += 3

        if record.forbidden_flags:
            score -= 40
        if "ai_use_forbidden_or_restricted" in record.risk_flags:
            score -= 25
        if "regulated_or_sensitive_domain" in record.risk_flags:
            score -= 15
        if "privacy_or_security_sensitive" in record.risk_flags:
            score -= 10
        for flag, penalty in self.CAUTION_PENALTIES.items():
            if flag in record.risk_flags:
                score -= penalty

        record.radar_score = max(0, min(100, score))
        if record.forbidden_flags:
            record.radar_decision = RadarDecision.REJECT.value
        elif record.radar_score >= 85:
            record.radar_decision = RadarDecision.QUEUE_FOR_PHASE_3.value
        elif record.radar_score >= 70:
            record.radar_decision = RadarDecision.QUEUE_WITH_CAUTION.value
        elif record.radar_score >= 50:
            record.radar_decision = RadarDecision.HOLD_FOR_HUMAN_REVIEW.value
        else:
            record.radar_decision = RadarDecision.REJECT.value
        return record

    @staticmethod
    def _record_text(record: OpportunityRecord) -> str:
        return " ".join(
            [
                record.title,
                record.description_plain,
                " ".join(record.requirements),
                " ".join(record.responsibilities),
                " ".join(record.deliverables),
                " ".join(record.skills_detected),
                " ".join(record.tools_detected),
                " ".join(record.discipline_taxonomy),
            ]
        ).lower()

    @classmethod
    def _strong_target_hit_count(cls, text: str) -> int:
        return sum(1 for term in cls.STRONG_TARGET_TERMS if term in text)


class OpportunityNormalizer:
    @staticmethod
    def make_id(source: str, title: str, employer: str, url: str) -> str:
        raw = f"{source}|{title}|{employer}|{url}".lower()
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class BaseConnector:
    def __init__(self, source: Dict[str, Any], run_config: Dict[str, Any]):
        self.source = source
        self.run_config = run_config
        self.normalizer = OpportunityNormalizer()

    @property
    def source_name(self) -> str:
        return self.source["name"]

    @property
    def source_slug(self) -> str:
        return self.source.get("slug", slugify(self.source_name))

    @property
    def timeout(self) -> int:
        return int(self.run_config.get("timeout_seconds", 20))

    @property
    def max_per_source(self) -> int:
        return int(self.run_config.get("max_per_source", 25))

    @property
    def user_agent(self) -> str:
        return self.run_config.get("user_agent", "AIGC-Opportunity-Radar/0.1 read-only")

    def fetch(self) -> FetchResult:
        raise NotImplementedError

    def request_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        request_headers = {"User-Agent": self.user_agent}
        if headers:
            request_headers.update(headers)
        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def request_bytes(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        request_headers = {"User-Agent": self.user_agent}
        if headers:
            request_headers.update(headers)
        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=self.timeout) as response:
            return response.read()


class WeWorkRemotelyRSSConnector(BaseConnector):
    def fetch(self) -> FetchResult:
        raw_items: List[Dict[str, Any]] = []
        records: List[OpportunityRecord] = []
        for feed_url in self.source.get("urls", []):
            xml_data = self.request_bytes(feed_url)
            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item"):
                raw = {
                    "feed_url": feed_url,
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "description": item.findtext("description", "") or "",
                    "pubDate": item.findtext("pubDate", ""),
                }
                raw_items.append(raw)
                if len(records) >= self.max_per_source:
                    continue
                title = TextCleaner.normalize(raw["title"])
                link = TextCleaner.normalize(raw["link"])
                description_html = raw["description"]
                description_plain = TextCleaner.html_to_text(description_html)
                employer = ""
                if ":" in title:
                    possible_employer, possible_title = title.split(":", 1)
                    employer = possible_employer.strip()
                    title = possible_title.strip()
                records.append(
                    OpportunityRecord(
                        opportunity_id=self.normalizer.make_id(self.source_name, title, employer, link),
                        source_platform=self.source_name,
                        source_type="rss",
                        source_url=link,
                        source_attribution_required=bool(self.source.get("attribution_required", True)),
                        discovered_at=utc_now(),
                        title=title,
                        employer=employer,
                        remote_status="remote",
                        work_type="job",
                        posted_at=TextCleaner.normalize(raw["pubDate"]),
                        description_plain=description_plain,
                        description_html=description_html,
                        platform_policy_status=self.source.get("status", SourceRisk.YELLOW.value),
                        audit_notes="Read-only RSS ingestion. Attribution required.",
                    )
                )
        return FetchResult(self.source_slug, self.source_name, raw_items, records)


class RemoteOKConnector(BaseConnector):
    def fetch(self) -> FetchResult:
        payload = self.request_json(self.source["url"])
        rows = [item for item in payload if isinstance(item, dict) and "legal" not in item]
        records = []
        for item in rows[: self.max_per_source]:
            title = TextCleaner.normalize(item.get("position", ""))
            employer = TextCleaner.normalize(item.get("company", ""))
            url = TextCleaner.normalize(item.get("url", ""))
            description_html = item.get("description", "") or ""
            description_plain = TextCleaner.html_to_text(description_html)
            records.append(
                OpportunityRecord(
                    opportunity_id=self.normalizer.make_id(self.source_name, title, employer, url),
                    source_platform=self.source_name,
                    source_type="api",
                    source_url=url,
                    source_attribution_required=bool(self.source.get("attribution_required", True)),
                    discovered_at=utc_now(),
                    title=title,
                    employer=employer,
                    location=TextCleaner.normalize(item.get("location", "")),
                    remote_status="remote",
                    work_type="job",
                    posted_at=TextCleaner.normalize(item.get("date", "")),
                    description_plain=description_plain,
                    description_html=description_html,
                    skills_detected=TextCleaner.normalize_list(item.get("tags", [])),
                    pay_min=coerce_float(item.get("salary_min")),
                    pay_max=coerce_float(item.get("salary_max")),
                    pay_currency="USD" if item.get("salary_min") or item.get("salary_max") else "",
                    pay_interval="year" if item.get("salary_min") or item.get("salary_max") else "unknown",
                    platform_policy_status=self.source.get("status", SourceRisk.YELLOW.value),
                    audit_notes="Read-only API ingestion. Attribution/direct link-back required. Blind applying is forbidden.",
                )
            )
        return FetchResult(self.source_slug, self.source_name, rows, records)


class RemotiveConnector(BaseConnector):
    def fetch(self) -> FetchResult:
        payload = self.request_json(self.source["url"])
        jobs = payload.get("jobs", [])
        records = []
        for item in jobs[: self.max_per_source]:
            title = TextCleaner.normalize(item.get("title", ""))
            employer = TextCleaner.normalize(item.get("company_name", ""))
            url = TextCleaner.normalize(item.get("url", ""))
            description_html = item.get("description", "") or ""
            description_plain = TextCleaner.html_to_text(description_html)
            records.append(
                OpportunityRecord(
                    opportunity_id=self.normalizer.make_id(self.source_name, title, employer, url),
                    source_platform=self.source_name,
                    source_type="api",
                    source_url=url,
                    source_attribution_required=bool(self.source.get("attribution_required", True)),
                    discovered_at=utc_now(),
                    title=title,
                    employer=employer,
                    location=TextCleaner.normalize(item.get("candidate_required_location", "")),
                    remote_status="remote",
                    work_type="job",
                    employment_type=TextCleaner.normalize(item.get("job_type", "unknown")).lower() or "unknown",
                    posted_at=TextCleaner.normalize(item.get("publication_date", "")),
                    description_plain=description_plain,
                    description_html=description_html,
                    skills_detected=TextCleaner.normalize_list(item.get("tags", [])),
                    platform_policy_status=self.source.get("status", SourceRisk.GREEN.value),
                    audit_notes="Read-only API ingestion. Attribution/link-back required.",
                )
            )
        return FetchResult(self.source_slug, self.source_name, jobs, records)


class GitHubIssueSearchConnector(BaseConnector):
    def fetch(self) -> FetchResult:
        raw_items: List[Dict[str, Any]] = []
        records: List[OpportunityRecord] = []
        for query in self.source.get("queries", []):
            if len(records) >= self.max_per_source:
                break
            params = urlencode(
                {
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": min(25, self.max_per_source),
                }
            )
            payload = self.request_json(
                f"{self.source['url']}?{params}",
                headers={"Accept": "application/vnd.github+json"},
            )
            for item in payload.get("items", []):
                raw = dict(item)
                raw["_aigc_query"] = query
                raw_items.append(raw)
                if len(records) >= self.max_per_source:
                    continue
                title = TextCleaner.normalize(item.get("title", ""))
                url = TextCleaner.normalize(item.get("html_url", ""))
                body = TextCleaner.normalize(item.get("body", "") or "")
                repo_url = item.get("repository_url", "")
                employer = repo_url.split("/")[-1] if repo_url else "GitHub Repository"
                labels = [
                    TextCleaner.normalize(label.get("name", ""))
                    for label in item.get("labels", [])
                    if isinstance(label, dict)
                ]
                records.append(
                    OpportunityRecord(
                        opportunity_id=self.normalizer.make_id(self.source_name, title, employer, url),
                        source_platform=self.source_name,
                        source_type="api",
                        source_url=url,
                        source_attribution_required=bool(self.source.get("attribution_required", False)),
                        discovered_at=utc_now(),
                        title=title,
                        employer=employer,
                        remote_status="remote",
                        work_type="open_source",
                        posted_at=TextCleaner.normalize(item.get("created_at", "")),
                        updated_at=TextCleaner.normalize(item.get("updated_at", "")),
                        description_plain=body,
                        skills_detected=labels,
                        platform_policy_status=self.source.get("status", SourceRisk.GREEN.value),
                        audit_notes="Read-only GitHub issue search. Contribution requires repo-rule review and human approval.",
                    )
                )
        return FetchResult(self.source_slug, self.source_name, raw_items, records)


CONNECTORS = {
    "wwr_rss": WeWorkRemotelyRSSConnector,
    "remoteok": RemoteOKConnector,
    "remotive": RemotiveConnector,
    "github_search": GitHubIssueSearchConnector,
}


class AIGCPhase2Radar:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.raw_dir = project_root / "data" / "phase2_raw"
        self.processed_dir = project_root / "data" / "phase2_processed"
        self.audit_dir = project_root / "data" / "audit"
        self.report_dir = project_root / "data" / "reports"
        for path in [self.raw_dir, self.processed_dir, self.audit_dir, self.report_dir]:
            path.mkdir(parents=True, exist_ok=True)
        self.ledger = AuditLedger(self.audit_dir / "aigc_phase2_audit.jsonl")
        self.classifier = Classifier()
        self.scorer = RadarScorer()
        self.stats = RunStats(run_id=self._make_run_id(), started_at=utc_now())

    def run_from_config(self, config_path: Path) -> List[OpportunityRecord]:
        config = load_json(config_path)
        self._load_phase1_registry()
        connectors = self._build_connectors(config)
        return self.run(connectors)

    def run(self, connectors: List[BaseConnector]) -> List[OpportunityRecord]:
        self.ledger.record(
            "phase2_run_start",
            {
                "run_id": self.stats.run_id,
                "started_at": self.stats.started_at,
                "external_actions_allowed": False,
            },
        )
        all_records: List[OpportunityRecord] = []
        for connector in connectors:
            connector_name = connector.__class__.__name__
            try:
                result = connector.fetch()
                self._write_raw_records(result.source_slug, result.raw_records)
                self.stats.sources_queried.append(result.source_name)
                self.stats.total_raw_records += len(result.raw_records)
                self.ledger.record(
                    "connector_success",
                    {
                        "connector": connector_name,
                        "source": result.source_name,
                        "raw_records": len(result.raw_records),
                        "normalized_records": len(result.normalized_records),
                    },
                )
                all_records.extend(result.normalized_records)
            except (HTTPError, URLError, TimeoutError, ET.ParseError, json.JSONDecodeError) as exc:
                message = f"{type(exc).__name__}: {exc}"
                self.stats.connector_errors[connector.source_name] = message
                self.ledger.record(
                    "connector_error",
                    {"connector": connector_name, "source": connector.source_name, "error": message},
                )
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self.stats.connector_errors[connector.source_name] = message
                self.ledger.record(
                    "connector_error",
                    {"connector": connector_name, "source": connector.source_name, "error": message},
                )

        deduped = self._dedupe(all_records)
        processed = []
        for record in deduped:
            record = self.classifier.classify(record)
            record = self.scorer.score(record)
            self.ledger.record(
                "opportunity_processed",
                {
                    "opportunity_id": record.opportunity_id,
                    "source_platform": record.source_platform,
                    "title": record.title,
                    "employer": record.employer,
                    "radar_score": record.radar_score,
                    "radar_decision": record.radar_decision,
                    "risk_flags": record.risk_flags,
                    "forbidden_flags": record.forbidden_flags,
                },
            )
            processed.append(record)

        processed = sorted(processed, key=lambda item: item.radar_score, reverse=True)
        self._finalize_stats(processed)
        self.ledger.record("phase2_run_complete", asdict(self.stats))
        return processed

    def export_queue(
        self,
        records: List[OpportunityRecord],
        path: Optional[Path] = None,
    ) -> Path:
        target = path or self.processed_dir / "aigc_phase2_opportunity_queue.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(record) for record in records]
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.ledger.record("queue_exported", {"path": str(target), "records": len(records)})
        return target

    def export_signature_update(self, records: List[OpportunityRecord], path: Optional[Path] = None) -> Path:
        target = path or self.report_dir / "phase2_signature_update.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.signature_update(records), encoding="utf-8")
        self.ledger.record("signature_update_exported", {"path": str(target)})
        return target

    def signature_update(self, records: List[OpportunityRecord]) -> str:
        queued = [
            item
            for item in records
            if item.radar_decision
            in {RadarDecision.QUEUE_FOR_PHASE_3.value, RadarDecision.QUEUE_WITH_CAUTION.value}
        ]
        rejected = [item for item in records if item.radar_decision == RadarDecision.REJECT.value]
        held = [item for item in records if item.radar_decision == RadarDecision.HOLD_FOR_HUMAN_REVIEW.value]
        top_categories = top_counts(flatten(item.discipline_taxonomy for item in records), limit=5)
        highest = [
            {
                "title": item.title,
                "employer": item.employer,
                "source": item.source_platform,
                "score": item.radar_score,
                "decision": item.radar_decision,
                "url": item.source_url,
            }
            for item in records[:10]
        ]
        return "\n".join(
            [
                "AIGC SIGNATURE UPDATE",
                "Operator:",
                "Justice Gray Maciocha",
                "Phase:",
                "Phase 2 - Opportunity Discovery Engine",
                "Operational Identity:",
                "Lawful Opportunity Radar",
                "Action Performed:",
                "Collected, normalized, classified, filtered, scored, and queued opportunities from read-only sources.",
                "Safety Review:",
                "No applications sent.",
                "No messages sent.",
                "No proposals submitted.",
                "No credentials used.",
                "No prohibited scraping performed by this engine.",
                "All external actions remain blocked.",
                "",
                "AIGC OPPORTUNITY RADAR QUEUE",
                f"Queue ID: AIGC-RADAR-{self.stats.run_id}",
                f"Source Window: {self.stats.started_at} to {self.stats.ended_at}",
                "Sources Queried:",
                *(f"- {source}" for source in self.stats.sources_queried),
                f"Total Raw Records: {self.stats.total_raw_records}",
                f"Duplicates Removed: {self.stats.duplicates_removed}",
                f"Total Processed: {len(records)}",
                f"Rejected Records: {len(rejected)}",
                f"Held for Human Review: {len(held)}",
                f"Queued for Phase 3: {len(queued)}",
                "Top Opportunity Types Found:",
                *(f"- {name}: {count}" for name, count in top_categories),
                "Highest Radar Scores:",
                json.dumps(highest, indent=2),
                "Connector Errors:",
                json.dumps(self.stats.connector_errors, indent=2),
                "Approval Required:",
                "No external approval required yet. Phase 2 is internal discovery only.",
                "Next Step:",
                "Run Phase 3 ology assessment on selected records.",
            ]
        ).strip() + "\n"

    def _build_connectors(self, config: Dict[str, Any]) -> List[BaseConnector]:
        connectors: List[BaseConnector] = []
        run_config = config.get("run", {})
        for source in config.get("sources", []):
            if not source.get("enabled", False):
                continue
            if source.get("status") not in {SourceRisk.GREEN.value, SourceRisk.YELLOW.value}:
                self.ledger.record("connector_skipped", {"source": source.get("name"), "reason": "source_not_green_or_yellow"})
                continue
            connector_key = source.get("connector")
            connector_type = CONNECTORS.get(connector_key)
            if not connector_type:
                self.ledger.record("connector_skipped", {"source": source.get("name"), "reason": "connector_not_implemented"})
                continue
            connectors.append(connector_type(source, run_config))
        return connectors

    def _dedupe(self, records: List[OpportunityRecord]) -> List[OpportunityRecord]:
        seen = set()
        deduped = []
        for record in records:
            key = "|".join(
                [
                    record.source_platform.lower(),
                    record.title.lower(),
                    record.employer.lower(),
                    record.source_url.lower(),
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        self.stats.duplicates_removed = len(records) - len(deduped)
        self.ledger.record(
            "dedupe_complete",
            {
                "input_count": len(records),
                "output_count": len(deduped),
                "duplicates_removed": self.stats.duplicates_removed,
            },
        )
        return deduped

    def _write_raw_records(self, source_slug: str, records: List[Dict[str, Any]]) -> None:
        target = self.raw_dir / f"raw_{source_slug}.json"
        target.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        self.ledger.record("raw_records_exported", {"path": str(target), "records": len(records)})

    def _load_phase1_registry(self) -> None:
        registry_path = self.project_root / "config" / "phase1_domain_registry.json"
        if registry_path.exists():
            registry = load_json(registry_path)
            self.ledger.record("phase1_registry_loaded", {"path": str(registry_path), "entries": len(registry)})
        else:
            self.ledger.record(
                "phase1_registry_missing",
                {
                    "path": str(registry_path),
                    "fallback": "Using enabled green/yellow sources from config/phase2_sources.json.",
                },
            )

    def _finalize_stats(self, records: List[OpportunityRecord]) -> None:
        self.stats.ended_at = utc_now()
        self.stats.total_processed = len(records)
        self.stats.rejected_records = sum(1 for item in records if item.radar_decision == RadarDecision.REJECT.value)
        self.stats.queued_for_phase_3 = sum(
            1
            for item in records
            if item.radar_decision
            in {RadarDecision.QUEUE_FOR_PHASE_3.value, RadarDecision.QUEUE_WITH_CAUTION.value}
        )
        self.stats.held_for_review = sum(
            1 for item in records if item.radar_decision == RadarDecision.HOLD_FOR_HUMAN_REVIEW.value
        )

    @staticmethod
    def _make_run_id() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def infer_bullets(text: str, trigger_terms: List[str], limit: int = 5) -> List[str]:
    if not text:
        return []
    chunks = re.split(r"[\n.]\s+", text)
    matches = []
    for chunk in chunks:
        normalized = TextCleaner.normalize(chunk)
        lower = normalized.lower()
        if len(normalized) < 20 or len(normalized) > 240:
            continue
        if any(term in lower for term in trigger_terms):
            matches.append(normalized)
        if len(matches) >= limit:
            break
    return matches


def add_once(values: List[str], value: str) -> None:
    if value not in values:
        values.append(value)


def coerce_float(value: Any) -> Optional[float]:
    if value in {None, "", 0, "0"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def flatten(groups: Iterable[Iterable[str]]) -> List[str]:
    output: List[str] = []
    for group in groups:
        output.extend(group)
    return output


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def top_counts(values: Iterable[str], limit: int = 5) -> List[tuple[str, int]]:
    counts: Dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run AIGC Phase 2 read-only opportunity radar.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase2_sources.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    radar = AIGCPhase2Radar(args.project_root)
    records = radar.run_from_config(args.config)
    queue_path = radar.export_queue(records)
    report_path = radar.export_signature_update(records)
    print(radar.signature_update(records))
    print(f"\nQueue exported: {queue_path}")
    print(f"Report exported: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
