from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Dict, List, Set


class ApplicationChannel(str, Enum):
    DIRECT_CAREERS_SITE = "direct_careers"     # 官方招聘网申
    INTERNAL_REFERRAL = "internal_referral"     # 员工内部推荐
    HEADHUNTER = "headhunter"                   # 猎头推荐
    BOSS_ZHIPIN = "boss_zhipin"                 # BOSS 直聘
    LAGOU = "lagou"                             # 拉勾招聘
    LIEPIN = "liepin"                           # 猎聘
    CAMPUS_TALK = "campus_talk"                 # 线下宣讲会/双选会
    OTHER = "other"


@dataclass
class ApplicationRecord:
    """历史投递记录"""
    record_id: str
    company_name: str
    role_title: str
    channel: ApplicationChannel
    applied_date: str  # YYYY-MM-DD
    status: str = "pending"  # "pending", "interviewing", "rejected", "withdrawn", "offered"
    recruiter_info: str = ""
    jd_text: str = ""


@dataclass
class CollisionCheckResult:
    """投递撞单与重投检测判定结果"""
    has_collision: bool
    risk_level: str  # "NONE", "LOW_WARNING", "HIGH_RISK_BLOCK"
    normalized_company: str
    reasons: List[str] = field(default_factory=list)
    conflicting_records: List[ApplicationRecord] = field(default_factory=list)
    cooldown_days_remaining: int = 0
    recommendation: str = ""


class CompanyEntityNormalizer:
    """公司实体及子公司集团别名标准化"""

    KNOWN_CLUSTERS: Dict[str, List[str]] = {
        "bytedance": [
            "字节跳动", "字节", "bytedance", "抖音", "tiktok", "今日头条",
            "北京字跳网络技术有限公司", "北京字节跳动科技有限公司", "lark", "飞书",
        ],
        "alibaba": [
            "阿里巴巴", "阿里", "alibaba", "淘宝", "天猫", "阿里云", "钉钉",
            "淘天", "蚂蚁", "蚂蚁集团", "ant group",
        ],
        "tencent": [
            "腾讯", "tencent", "微信", "wechat", "财付通", "腾讯云",
            "深圳市腾讯计算机系统有限公司",
        ],
        "meituan": [
            "美团", "美团点评", "meituan", "大众点评", "三快在线", "北京三快科技有限公司",
        ],
        "kuaishou": [
            "快手", "kuaishou", "快看", "达佳互联", "北京达佳互联信息技术有限公司",
        ],
        "baidu": [
            "百度", "baidu", "小度", "北京百度网讯科技有限公司",
        ],
        "jd": [
            "京东", "jd", "jd.com", "京东数科", "京东零售", "京东物流",
        ],
        "netease": [
            "网易", "netease", "有道", "网易雷火", "网易互娱",
        ],
        "pdd": [
            "拼多多", "pdd", "temu", "寻梦", "上海寻梦信息技术有限公司",
        ],
        "huawei": [
            "华为", "huawei", "海思", "华为终端",
        ],
        "microsoft": [
            "微软", "microsoft", "stca", "msra",
        ],
        "google": [
            "谷歌", "google", "alphabet",
        ],
    }

    @classmethod
    def normalize(cls, company_name: str) -> str:
        name_clean = company_name.strip().lower()
        if not name_clean:
            return "unknown"

        # 匹配已知集团
        for cluster_id, aliases in cls.KNOWN_CLUSTERS.items():
            for alias in aliases:
                if alias.lower() in name_clean:
                    return cluster_id

        # 通用后缀清洗
        suffixes = [
            "（中国）", "(中国)", "股份有限公司", "有限责任公司", "有限公司",
            "网络技术", "信息科技", "科技有限公司", "软件技术", "集团", "科技",
        ]
        res = name_clean
        for suf in suffixes:
            res = res.replace(suf.lower(), "")
        res = re.sub(r"[^\w\u4e00-\u9fa5]", "", res)
        return res or name_clean


class JobFingerprint:
    """计算岗位描述/标题的文本相似度指纹"""

    @classmethod
    def tokenize(cls, text: str) -> Set[str]:
        if not text:
            return set()
        # 提取英文单词与中文 1-gram / 2-gram
        tokens: Set[str] = set(re.findall(r"[a-zA-Z0-9_+#]+", text.lower()))
        zh_chars = re.findall(r"[\u4e00-\u9fa5]", text)
        for c in zh_chars:
            tokens.add(c)
        for i in range(len(zh_chars) - 1):
            tokens.add(zh_chars[i] + zh_chars[i + 1])
        return tokens

    @classmethod
    def jaccard_similarity(cls, text1: str, text2: str) -> float:
        s1 = cls.tokenize(text1)
        s2 = cls.tokenize(text2)
        if not s1 or not s2:
            return 0.0
        intersection = len(s1.intersection(s2))
        union = len(s1.union(s2))
        return intersection / union if union > 0 else 0.0


class DuplicateApplicationGuard:
    """多渠道防撞单与重复投递检测卫士"""

    @classmethod
    def check_application(
        cls,
        new_company: str,
        new_role: str,
        new_channel: ApplicationChannel,
        applied_date: str,
        history: List[ApplicationRecord],
        new_jd_text: str = "",
        cooldown_days: int = 180,
    ) -> CollisionCheckResult:
        norm_company = CompanyEntityNormalizer.normalize(new_company)

        try:
            curr_dt = datetime.strptime(applied_date, "%Y-%m-%d").date()
        except Exception:
            curr_dt = date.today()

        reasons: List[str] = []
        conflicts: List[ApplicationRecord] = []
        max_cooldown_left = 0
        risk_level = "NONE"

        for rec in history:
            rec_company_norm = CompanyEntityNormalizer.normalize(rec.company_name)
            if rec_company_norm != norm_company:
                continue

            try:
                rec_dt = datetime.strptime(rec.applied_date, "%Y-%m-%d").date()
                days_diff = (curr_dt - rec_dt).days
            except Exception:
                days_diff = 0

            # 1. 猎头渠道与内部推荐碰撞拦截 (Channel Collision)
            # 猎头已推进或内推已锁定时，严禁通过另一猎头或自投撞单
            active_statuses = {"pending", "interviewing"}
            if rec.status in active_statuses:
                if rec.channel in (ApplicationChannel.HEADHUNTER, ApplicationChannel.INTERNAL_REFERRAL):
                    if new_channel != rec.channel:
                        risk_level = "HIGH_RISK_BLOCK"
                        reasons.append(
                            f"【渠道撞单风险】该企业（{norm_company}）此前已通过「{rec.channel.value}」处于进行中流程（状态: {rec.status}）。"
                            f"若再次通过「{new_channel.value}」投递，将导致猎头佣金归属争议或 HR 系统锁定简历，造成恶劣影响。"
                        )
                        conflicts.append(rec)
                    elif new_channel == ApplicationChannel.HEADHUNTER and rec.recruiter_info:
                        risk_level = "HIGH_RISK_BLOCK"
                        reasons.append(
                            f"【多猎头撞单风险】此前已有猎头（{rec.recruiter_info}）录入系统，更换其他猎头将直接触发撞单黑名单。"
                        )
                        conflicts.append(rec)

            # 2. 同岗位职责高度重叠撞单 (Role Similarity Collision)
            role_sim = JobFingerprint.jaccard_similarity(
                f"{new_role} {new_jd_text}",
                f"{rec.role_title} {rec.jd_text}",
            )
            if rec.status in active_statuses and (role_sim > 0.30 or new_role.strip().lower() == rec.role_title.strip().lower()):
                if risk_level != "HIGH_RISK_BLOCK":
                    risk_level = "HIGH_RISK_BLOCK"
                reasons.append(
                    f"【同岗并行投递冲突】当前已有高度重合的岗位「{rec.role_title}」处于流程中（相似度: {role_sim:.2f}），同一实体同时投递多个同质化岗位易被 HR 视为海投并直接一票否决。"
                )
                conflicts.append(rec)

            # 3. 未通过冷冻期保护 (Cooldown Period Protection)
            if rec.status == "rejected" and days_diff < cooldown_days:
                cooldown_left = cooldown_days - days_diff
                if cooldown_left > max_cooldown_left:
                    max_cooldown_left = cooldown_left
                reasons.append(
                    f"【冷冻期拦截】此前在 {rec.applied_date} 投递过「{rec.role_title}」且结果为已挂/未通过，"
                    f"目前距今仅 {days_diff} 天，处于该企业 {cooldown_days} 天保护冷冻期内（剩余 {cooldown_left} 天）。"
                )
                conflicts.append(rec)
                if risk_level == "NONE":
                    risk_level = "LOW_WARNING"

        has_collision = (risk_level in ("HIGH_RISK_BLOCK", "LOW_WARNING"))
        recommendation = ""
        if risk_level == "HIGH_RISK_BLOCK":
            recommendation = "🛑 严禁此时投递！必须联系原有推荐渠道撤销、或等待前序流程明确完结。"
        elif risk_level == "LOW_WARNING":
            recommendation = "⚠️ 处于冷却期内。建议更换不同事业群（BU）或等待冷却期结束后更新全新简历再行投递。"
        else:
            recommendation = "✅ 未发现渠道冲突与冷冻期风险，可正常推进投递。"

        return CollisionCheckResult(
            has_collision=has_collision,
            risk_level=risk_level,
            normalized_company=norm_company,
            reasons=reasons,
            conflicting_records=conflicts,
            cooldown_days_remaining=max_cooldown_left,
            recommendation=recommendation,
        )
