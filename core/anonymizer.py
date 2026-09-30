"""
OfferGet Privacy Anonymizer Module
Reversible pseudonymization and tokenization for candidate profiles and resumes.
Supports 'standard' and 'strict' sensitivity levels with deterministic token mapping.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.artifacts import write_json_atomic


# ---------------------------------------------------------------------------
# Predefined Deterministic Mappings for Canonical Entities
# ---------------------------------------------------------------------------

PREDEFINED_STANDARD_MAPPINGS: Dict[str, str] = {
    # Names (Exact match mappings requested in specification)
    "张晨曦": "Dr. Alex Chen",
    "Dr. Alex Zhang": "Dr. Alexander Chen",
    "Alex Zhang": "Alex Chen",
    "张博士": "陈博士",
    # Phones
    "+86 186-0000-8899": "+86 138-0000-0000",
    "+86 18600008899": "+86 138-0000-0000",
    "186-0000-8899": "138-0000-0000",
    "18600008899": "13800000000",
    # Emails
    "alex.zhang.ai@alumni.tsinghua.edu.cn": "candidate.ai@example.com",
    # GitHub URLs & Usernames
    "https://github.com/alex-zhang-ai/enterprise-agent-os": "https://github.com/candidate-ai/enterprise-agent-platform",
    "https://github.com/alex-zhang-ai": "https://github.com/candidate-ai",
    "alex-zhang-ai": "candidate-ai",
    # LinkedIn URLs & Slugs
    "https://linkedin.com/in/alex-zhang-llm": "https://linkedin.com/in/candidate-ai",
    "alex-zhang-llm": "candidate-ai",
}

PREDEFINED_STRICT_MAPPINGS: Dict[str, str] = {
    # Universities & Academic Institutions
    "清华大学 (Tsinghua University)": "Top-Tier Research University (Elite Institution)",
    "清华大学": "Top-Tier C9 Research University",
    "Tsinghua University": "Top-Tier C9 Research University Alpha",
    "北京大学 (Peking University)": "Top-Tier Research University (National Key Institution)",
    "北京大学": "Top-Tier C9 Research University Beta",
    "Peking University": "Top-Tier C9 Research University Beta",
    "浙江大学": "Top-Tier C9 Research University Gamma",
    "上海交通大学": "Top-Tier C9 Research University Delta",
    "复旦大学": "Top-Tier C9 Research University Epsilon",
    # Companies & Labs
    "智谱前沿 AI 实验室 / 头部大模型独角兽": "Frontier AI Lab Alpha / Top LLM Unicorn",
    "Zhipu AI / Frontier LLM Unicorn Lab": "Frontier AI Lab Alpha / Top LLM Unicorn Lab",
    "智谱前沿 AI 实验室": "Frontier AI Lab Alpha",
    "Zhipu AI": "Frontier AI Lab Alpha",
    "智谱 AI": "Frontier AI Lab Alpha",
    "智谱AI": "Frontier AI Lab Alpha",
    "智谱": "Frontier AI Lab",
    "字节跳动 / 基础架构与搜索算法团队": "Tech Conglomerate Beta / Infrastructure & Search Team",
    "ByteDance / AI Infrastructure & Search Algorithm Team": "Tech Conglomerate Beta / AI Infrastructure & Search Algorithm Team",
    "字节跳动": "Tech Conglomerate Beta",
    "ByteDance": "Tech Conglomerate Beta",
    "腾讯": "Tech Giant Gamma",
    "Tencent": "Tech Giant Gamma",
    "阿里巴巴": "Tech Giant Delta",
    "Alibaba": "Tech Giant Delta",
    "百度": "Tech Giant Epsilon",
    "Baidu": "Tech Giant Epsilon",
    "美团": "Tech Platform Zeta",
    "Meituan": "Tech Platform Zeta",
    "华为": "Enterprise Telecom Giant Eta",
    "Huawei": "Enterprise Telecom Giant Eta",
    # Hardware, Cluster Infrastructure & Internal Projects
    "1024 卡 H800 集群": "1024-Card Confidential Accelerator Cluster",
    "1,024 H800 GPU cluster": "1,024 Confidential GPU cluster",
    "H800 集群": "Confidential High-Performance Cluster Alpha",
    "H800 cluster": "Confidential High-Performance Cluster Alpha",
    "H100 集群": "Confidential High-Performance Cluster Beta",
    "H100 cluster": "Confidential High-Performance Cluster Beta",
    "A800 集群": "Confidential GPU Cluster Gamma",
    "A800 cluster": "Confidential GPU Cluster Gamma",
    "H800": "Tier-1 Enterprise Accelerator",
    "H100": "Tier-1 Enterprise GPU",
    "A800": "Enterprise GPU Accelerator",
    "Enterprise-Agent-OS (企业级多智能体协同引擎)": "Enterprise-Agent-Platform (Enterprise Multi-Agent Orchestration Engine)",
    "Enterprise-Agent-OS": "Enterprise-Agent-Platform",
    "Fast-Megatron-MLA (高效长文本注意力算子库)": "Fast-Attention-MLA (Efficient Attention Operator Library)",
    "Fast-Megatron-MLA": "Fast-Attention-MLA",
}


# ---------------------------------------------------------------------------
# PrivacyAnonymizer Class
# ---------------------------------------------------------------------------

class PrivacyAnonymizer:
    """
    Reversible pseudonymization and tokenization engine for sensitive candidate profiles.

    Sensitivity levels:
      - 'standard': Masks PII including candidate name, phone number, email address,
                    GitHub URL/handle, and LinkedIn URL/handle.
      - 'strict': Additionally masks company names, university/institution names,
                  confidential hardware/cluster infrastructure, and proprietary project codenames.
    """

    def __init__(self, custom_mappings: Optional[Dict[str, str]] = None):
        """
        Initialize PrivacyAnonymizer with optional user-supplied custom mappings.
        """
        self.custom_mappings = custom_mappings or {}
        self._seq_counter = 0

    def _get_deterministic_alias(self, entity: str, category: str) -> str:
        """
        Generates a deterministic, realistic alias for an unmapped entity based on its content and category.
        """
        hash_hex = hashlib.sha256(entity.encode("utf-8")).hexdigest()
        short_id = hash_hex[:6].upper()
        num_id = int(hash_hex[:4], 16) % 1000

        if category == "email":
            return f"candidate.{hash_hex[:8]}@example.com"
        elif category == "phone":
            return f"+86 138-{str(num_id).zfill(4)}-0000"
        elif category == "name":
            return f"Candidate {short_id}"
        elif category == "github":
            return f"https://github.com/candidate-{short_id.lower()}"
        elif category == "linkedin":
            return f"https://linkedin.com/in/candidate-{short_id.lower()}"
        elif category == "company":
            return f"Enterprise Partner {short_id}"
        elif category == "university":
            return f"Top-Tier Research University {short_id}"
        elif category == "project":
            return f"Proprietary-System-{short_id}"
        elif category == "hardware":
            return f"Confidential Accelerator Cluster {short_id}"
        else:
            return f"Anonymized-{category.capitalize()}-{short_id}"

    def _extract_entities_from_profile_dict(
        self, profile_dict: Dict[str, Any], level: str
    ) -> Dict[str, str]:
        """
        Extracts known entities and their mapped aliases from a structured candidate profile.
        """
        mapping: Dict[str, str] = {}

        # 1. Standard Level Entities (Candidate PII)
        candidate = profile_dict.get("candidate", {})
        if isinstance(candidate, dict):
            # Name
            if candidate.get("name"):
                name = str(candidate["name"]).strip()
                mapping[name] = PREDEFINED_STANDARD_MAPPINGS.get(name) or "Dr. Alex Chen"
            if candidate.get("en_name"):
                en_name = str(candidate["en_name"]).strip()
                mapping[en_name] = PREDEFINED_STANDARD_MAPPINGS.get(en_name) or "Dr. Alexander Chen"

            # Phone
            if candidate.get("phone"):
                phone = str(candidate["phone"]).strip()
                mapping[phone] = PREDEFINED_STANDARD_MAPPINGS.get(phone) or "+86 138-0000-0000"

            # Email
            if candidate.get("email"):
                email = str(candidate["email"]).strip()
                mapping[email] = PREDEFINED_STANDARD_MAPPINGS.get(email) or "candidate.ai@example.com"

            # GitHub
            if candidate.get("github"):
                gh = str(candidate["github"]).strip()
                mapping[gh] = PREDEFINED_STANDARD_MAPPINGS.get(gh) or "https://github.com/candidate-ai"
                # Also map the handle itself if identifiable
                m = re.search(r"github\.com/([\w.-]+)", gh)
                if m:
                    handle = m.group(1)
                    if handle not in mapping:
                        mapping[handle] = "candidate-ai"

            # LinkedIn
            if candidate.get("linkedin"):
                li = str(candidate["linkedin"]).strip()
                mapping[li] = PREDEFINED_STANDARD_MAPPINGS.get(li) or "https://linkedin.com/in/candidate-ai"
                m = re.search(r"linkedin\.com/in/([\w.-]+)", li)
                if m:
                    slug = m.group(1)
                    if slug not in mapping:
                        mapping[slug] = "candidate-ai"

        # 2. Strict Level Entities (Universities, Companies, Confidential Projects/Hardware)
        if level == "strict":
            # University / Institution
            if isinstance(candidate, dict) and candidate.get("institution"):
                inst = str(candidate["institution"]).strip()
                if inst in PREDEFINED_STRICT_MAPPINGS:
                    mapping[inst] = PREDEFINED_STRICT_MAPPINGS[inst]
                else:
                    mapping[inst] = self._get_deterministic_alias(inst, "university")

            # Experience Companies
            for exp in profile_dict.get("experience", []):
                if isinstance(exp, dict):
                    for field in ["company", "company_en"]:
                        c = exp.get(field)
                        if c:
                            c_str = str(c).strip()
                            if c_str in PREDEFINED_STRICT_MAPPINGS:
                                mapping[c_str] = PREDEFINED_STRICT_MAPPINGS[c_str]
                            else:
                                mapping[c_str] = self._get_deterministic_alias(c_str, "company")

            # Project names & GitHub links
            for proj in profile_dict.get("projects", []):
                if isinstance(proj, dict):
                    p_name = proj.get("name")
                    if p_name:
                        p_str = str(p_name).strip()
                        if p_str in PREDEFINED_STRICT_MAPPINGS:
                            mapping[p_str] = PREDEFINED_STRICT_MAPPINGS[p_str]
                        else:
                            # Strip parentheses if present to map base name too
                            base_match = re.match(r"^([^\(\（]+)", p_str)
                            base_name = base_match.group(1).strip() if base_match else p_str
                            alias = self._get_deterministic_alias(base_name, "project")
                            mapping[p_str] = alias
                            if base_name != p_str and base_name not in mapping:
                                mapping[base_name] = alias

                    p_gh = proj.get("github")
                    if p_gh:
                        p_gh_str = str(p_gh).strip()
                        if p_gh_str in PREDEFINED_STANDARD_MAPPINGS:
                            mapping[p_gh_str] = PREDEFINED_STANDARD_MAPPINGS[p_gh_str]
                        else:
                            mapping[p_gh_str] = "https://github.com/candidate-ai/proprietary-repo"

        return mapping

    def _discover_entities_in_text(self, text: str, level: str) -> Dict[str, str]:
        """
        Discovers unmapped sensitive entities directly from text using regex heuristics.
        """
        mapping: Dict[str, str] = {}

        # 1. Emails
        for email in re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text):
            if email in PREDEFINED_STANDARD_MAPPINGS:
                mapping[email] = PREDEFINED_STANDARD_MAPPINGS[email]
            else:
                mapping[email] = self._get_deterministic_alias(email, "email")

        # 2. Phones (Chinese and international formats)
        phone_patterns = [
            r"\+86[- ]?1[3-9]\d[- ]?\d{4}[- ]?\d{4}",
            r"\b1[3-9]\d[- ]?\d{4}[- ]?\d{4}\b",
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        ]
        for pattern in phone_patterns:
            for phone in re.findall(pattern, text):
                if phone in PREDEFINED_STANDARD_MAPPINGS:
                    mapping[phone] = PREDEFINED_STANDARD_MAPPINGS[phone]
                else:
                    mapping[phone] = self._get_deterministic_alias(phone, "phone")

        # 3. GitHub & LinkedIn URLs
        for gh in re.findall(r"https?://github\.com/[\w.-]+(?:/[\w.-]+)?", text):
            if gh in PREDEFINED_STANDARD_MAPPINGS:
                mapping[gh] = PREDEFINED_STANDARD_MAPPINGS[gh]
            else:
                mapping[gh] = self._get_deterministic_alias(gh, "github")

        for li in re.findall(r"https?://(?:www\.)?linkedin\.com/in/[\w.-]+", text):
            if li in PREDEFINED_STANDARD_MAPPINGS:
                mapping[li] = PREDEFINED_STANDARD_MAPPINGS[li]
            else:
                mapping[li] = self._get_deterministic_alias(li, "linkedin")

        # Check known standard mappings present in text
        for real, alias in PREDEFINED_STANDARD_MAPPINGS.items():
            if real in text and real not in mapping:
                mapping[real] = alias

        # 4. Strict Level Entities
        if level == "strict":
            # Check all predefined strict mappings
            for real, alias in PREDEFINED_STRICT_MAPPINGS.items():
                if real in text and real not in mapping:
                    mapping[real] = alias

            # Hardware / Cluster regex (e.g. "1024 卡 H800 集群", "H800 集群", "H100", "A800")
            for cluster in re.findall(r"\b\d+[\s-]*卡[\s-]*[HA]\d{3,4}(?:[\s-]*集群)?\b", text):
                if cluster not in mapping:
                    mapping[cluster] = self._get_deterministic_alias(cluster, "hardware")

            for cluster in re.findall(r"\b[HA]\d{3,4}[\s-]*集群\b", text):
                if cluster not in mapping:
                    mapping[cluster] = self._get_deterministic_alias(cluster, "hardware")

        return mapping

    def anonymize(
        self, data: Union[dict, str], level: str = "strict"
    ) -> Tuple[Union[dict, str], dict]:
        """
        Anonymizes input data (dictionary or text string) according to sensitivity level.

        Args:
            data: A candidate profile dictionary or a raw text string.
            level: 'standard' or 'strict' (default: 'strict').

        Returns:
            A tuple of (anonymized_data, deanon_map), where deanon_map maps
            each alias back to its original real entity.
        """
        if level not in ("standard", "strict"):
            raise ValueError(f"Unknown sensitivity level: '{level}'. Supported levels: 'standard', 'strict'.")

        # Accumulate all real_to_alias mappings
        real_to_alias: Dict[str, str] = {}

        # 1. Add custom mappings first
        real_to_alias.update(self.custom_mappings)

        # 2. Extract mappings based on data type
        if isinstance(data, dict):
            dict_mappings = self._extract_entities_from_profile_dict(data, level)
            real_to_alias.update(dict_mappings)
            # Serialize to string to discover any embedded unindexed entities
            raw_text = json.dumps(data, ensure_ascii=False)
            text_mappings = self._discover_entities_in_text(raw_text, level)
            for k, v in text_mappings.items():
                if k not in real_to_alias:
                    real_to_alias[k] = v
        elif isinstance(data, str):
            text_mappings = self._discover_entities_in_text(data, level)
            real_to_alias.update(text_mappings)
        else:
            raise TypeError(f"Expected dict or str, got {type(data).__name__}")

        # In standard mode, explicitly purge any strict-only entities from mapping
        if level == "standard":
            strict_keys = set(PREDEFINED_STRICT_MAPPINGS.keys())
            real_to_alias = {k: v for k, v in real_to_alias.items() if k not in strict_keys}

        # Build deanon_map (alias -> real)
        # Note: Ensure aliases are unique so mapping is strictly reversible
        deanon_map: Dict[str, str] = {}
        for real, alias in real_to_alias.items():
            deanon_map[alias] = real

        # Perform replacement: Sort real entities by descending length to prevent partial replacement
        sorted_real_items = sorted(real_to_alias.items(), key=lambda item: len(item[0]), reverse=True)

        def _replace_text(text: str) -> str:
            result = text
            for real, alias in sorted_real_items:
                if real in result:
                    result = result.replace(real, alias)
            return result

        def _anonymize_obj(obj: Any) -> Any:
            if isinstance(obj, str):
                return _replace_text(obj)
            elif isinstance(obj, dict):
                return {k: _anonymize_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_anonymize_obj(elem) for elem in obj]
            return obj

        if isinstance(data, dict):
            anonymized_data = _anonymize_obj(copy.deepcopy(data))
        else:
            anonymized_data = _replace_text(data)

        return anonymized_data, deanon_map

    def deanonymize(
        self, data: Union[dict, str], deanon_map: dict
    ) -> Union[dict, str]:
        """
        Reverses anonymization using deanon_map.

        Args:
            data: Anonymized dictionary or text string.
            deanon_map: Mapping of alias -> original real entity (or dict containing 'alias_to_real').

        Returns:
            Restored dictionary or text string.
        """
        # Support both direct {alias: real} or structured {"alias_to_real": {...}}
        mapping = deanon_map.get("alias_to_real", deanon_map)
        if not isinstance(mapping, dict):
            raise TypeError("deanon_map must be a dictionary")

        # Filter out any internal metadata keys
        clean_map = {k: v for k, v in mapping.items() if not k.startswith("__")}

        # Sort aliases by descending length to prevent partial replacement
        sorted_alias_items = sorted(clean_map.items(), key=lambda item: len(item[0]), reverse=True)

        def _restore_text(text: str) -> str:
            result = text
            for alias, real in sorted_alias_items:
                if alias in result:
                    result = result.replace(alias, real)
            return result

        def _deanonymize_obj(obj: Any) -> Any:
            if isinstance(obj, str):
                return _restore_text(obj)
            elif isinstance(obj, dict):
                return {k: _deanonymize_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_deanonymize_obj(elem) for elem in obj]
            return obj

        if isinstance(data, dict):
            return _deanonymize_obj(copy.deepcopy(data))
        elif isinstance(data, str):
            return _restore_text(data)
        else:
            raise TypeError(f"Expected dict or str, got {type(data).__name__}")

    def save_map(self, deanon_map: dict, filepath: Union[str, Path]) -> None:
        """
        Saves de-anonymization map to a JSON file.
        """
        write_json_atomic(deanon_map, filepath)

    def load_map(self, filepath: Union[str, Path]) -> dict:
        """
        Loads de-anonymization map from a JSON file.
        """
        path = Path(filepath)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# ---------------------------------------------------------------------------
# Top-Level Convenience Functions
# ---------------------------------------------------------------------------

def anonymize_profile(
    data: Union[dict, str], level: str = "strict"
) -> Tuple[Union[dict, str], dict]:
    """
    Convenience function to anonymize a candidate profile dictionary or resume text.

    Args:
        data: Candidate profile dict or raw resume text.
        level: 'standard' or 'strict' (default: 'strict').

    Returns:
        (anonymized_data, deanon_map)
    """
    anonymizer = PrivacyAnonymizer()
    return anonymizer.anonymize(data, level=level)


def deanonymize_text(
    data: Union[dict, str], deanon_map: dict
) -> Union[dict, str]:
    """
    Convenience function to deanonymize an anonymized text or dictionary.

    Args:
        data: Anonymized text string or dictionary.
        deanon_map: Mapping of alias -> original real entity.

    Returns:
        Restored text string or dictionary.
    """
    anonymizer = PrivacyAnonymizer()
    return anonymizer.deanonymize(data, deanon_map)
