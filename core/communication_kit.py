from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class LetterType(str, Enum):
    COLD_OUTREACH = "cold_outreach"
    COVER_LETTER = "cover_letter"
    RESCHEDULE = "reschedule"
    THANK_YOU = "thank_you"
    FOLLOW_UP = "follow_up"
    SALARY_NEGOTIATION = "salary_negotiation"
    DECLINE_OFFER = "decline_offer"


@dataclass
class GeneratedLetter:
    letter_type: LetterType
    subject: str
    recipient: str
    body_text: str
    key_points: List[str] = field(default_factory=list)
    call_to_action: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ColdOutreachWriter:
    """针对猎头/HR/业务主管的技术背景自荐信生成器"""

    @staticmethod
    def write(
        candidate_name: str,
        recipient_name: str,
        target_company: str,
        target_role: str,
        core_skills: List[str],
        key_achievements: List[str],
        portfolio_link: Optional[str] = None,
    ) -> GeneratedLetter:
        subject = f"【自荐-{target_role}】{candidate_name} - {target_company}岗位求职沟通"
        skills_str = "、".join(core_skills[:4]) if core_skills else "全栈与系统工程"

        points = []
        for ach in key_achievements[:3]:
            points.append(f"• {ach}")

        ach_block = "\n".join(points) if points else "• 具备扎实的工程落地与复杂业务交付经验"
        link_block = f"\n个人主页/作品集/GitHub：{portfolio_link}\n" if portfolio_link else ""

        body = (
            f"尊敬的 {recipient_name}（{target_company} 招聘团队）：\n\n"
            f"您好！我是 {candidate_name}，长期关注 {target_company} 在行业中的技术突破。\n"
            f"获悉贵司正在热招「{target_role}」岗位，我的技术栈主要聚焦于 {skills_str}，"
            f"与该岗位的核心要求高度契合。\n\n"
            f"【核心能力与代表成果】：\n"
            f"{ach_block}\n"
            f"{link_block}\n"
            f"附件为我的最新个人简历。若团队当前有合适面试窗口，非常期待能有 15-20 分钟的电话沟通机会。\n"
            f"祝工作顺利！\n\n"
            f"{candidate_name}\n"
        )
        return GeneratedLetter(
            letter_type=LetterType.COLD_OUTREACH,
            subject=subject,
            recipient=recipient_name,
            body_text=body.strip(),
            key_points=key_achievements[:3],
            call_to_action="期待 15-20 分钟电话沟通机会",
        )


class CoverLetterWriter:
    """基于岗位要求深度定制的求职信（Cover Letter）"""

    @staticmethod
    def write(
        candidate_name: str,
        company_name: str,
        role_name: str,
        company_mission_hook: str,
        matching_experiences: List[str],
        contact_info: str,
    ) -> GeneratedLetter:
        subject = f"求职信：{candidate_name} 申请 {company_name} - {role_name}"

        exp_block = "\n".join([f"1. {exp}" for exp in matching_experiences[:3]])

        body = (
            f"尊敬的 {company_name} 招聘团队：\n\n"
            f"您好！\n\n"
            f"我非常荣幸能够向贵司投递「{role_name}」岗位申请。\n"
            f"我一直在关注 {company_name}，特别是贵团队在 {company_mission_hook} 方面的卓越探索与产品深耕。\n\n"
            f"结合我过往的工程实战与技术积累，我认为自己在以下方面能够为团队带来即战力贡献：\n"
            f"{exp_block}\n\n"
            f"面对复杂工程场景与业务指标挑战，我始终秉持严谨求实、以结果为导向的工程态度。"
            f"我深信我的加入能够协助团队加速关键模块迭代与系统可靠性交付。\n\n"
            f"期待能有机会参与贵司的面试评估，进一步探讨如何为 {company_name} 的技术发展创造价值。\n\n"
            f"此致，\n"
            f"敬礼！\n\n"
            f"{candidate_name}\n"
            f"联系方式：{contact_info}\n"
        )
        return GeneratedLetter(
            letter_type=LetterType.COVER_LETTER,
            subject=subject,
            recipient=company_name,
            body_text=body.strip(),
            key_points=matching_experiences[:3],
            call_to_action="期待参与面试评估",
        )


class RescheduleLetterWriter:
    """突发时间冲突时的专业礼貌改期申请信"""

    @staticmethod
    def write(
        candidate_name: str,
        interviewer_name: str,
        role_name: str,
        original_datetime: str,
        conflict_reason: str,
        available_slots: List[str],
    ) -> GeneratedLetter:
        subject = f"【面试改期申请】{candidate_name} - {role_name} - 原定 {original_datetime}"

        slots_block = "\n".join([f"• 候选时间 {i+1}：{slot}" for i, slot in enumerate(available_slots)])

        body = (
            f"尊敬的 {interviewer_name}：\n\n"
            f"您好！感谢您协调安排我于 {original_datetime} 进行的「{role_name}」面试。\n\n"
            f"非常抱歉，由于 {conflict_reason}，原定面试时间出现不可抗力冲突。"
            f"为了确保面试过程中网络环境与答辩专注度不受干扰，特此诚恳向您申请调整面试时间。\n\n"
            f"为尽量减少给面试官带来的不便，我已核实并准备好以下备选时间窗口：\n"
            f"{slots_block}\n\n"
            f"若上述时间仍与面试官安排有冲突，我亦可随时配合您协调的其他工作日时间段。\n"
            f"给您和面试团队带来的时间调整与繁琐流程，我深表歉意，再次感谢您的包容与协助！\n\n"
            f"{candidate_name}\n"
        )
        return GeneratedLetter(
            letter_type=LetterType.RESCHEDULE,
            subject=subject,
            recipient=interviewer_name,
            body_text=body.strip(),
            key_points=[conflict_reason] + available_slots,
            call_to_action="诚恳申请调整面试时间窗口",
        )


class ThankYouLetterWriter:
    """技术面结束后紧扣技术讨论细节的高情商感谢信"""

    @staticmethod
    def write(
        candidate_name: str,
        interviewer_name: str,
        role_name: str,
        round_name: str,
        discussed_topic: str,
        candidate_insight: str,
    ) -> GeneratedLetter:
        subject = f"【面试感谢与技术跟进】{candidate_name} - {round_name} - {role_name}"

        body = (
            f"尊敬的 {interviewer_name} 老师：\n\n"
            f"您好！非常感谢您今天抽空进行 {round_name} 交流。\n\n"
            f"在交流中，您就「{discussed_topic}」提出的工程思考与边界考量对我启发很大。"
            f"针对该问题，面试结束后我又进行了进一步的推演与文献梳理：{candidate_insight}。\n\n"
            f"这次深入探讨不仅让我对贵团队面临的高并发/高复杂度技术场景有了更具象的认知，"
            f"也更坚定了我希望加入团队并肩作战的意愿。\n\n"
            f"再次感谢您的专业指导与宝贵时间，期待后续进展！\n\n"
            f"{candidate_name}\n"
        )
        return GeneratedLetter(
            letter_type=LetterType.THANK_YOU,
            subject=subject,
            recipient=interviewer_name,
            body_text=body.strip(),
            key_points=[f"探讨话题: {discussed_topic}", f"跟进洞察: {candidate_insight}"],
            call_to_action="期待后续进展",
        )


class FollowUpLetterWriter:
    """投递或面试后超过约定周期的礼貌推进询问信"""

    @staticmethod
    def write(
        candidate_name: str,
        recruiter_name: str,
        role_name: str,
        interview_date: str,
        company_name: str,
    ) -> GeneratedLetter:
        subject = f"【面试进展咨询】{candidate_name} - {company_name} - {role_name}"

        body = (
            f"尊敬的 {recruiter_name}：\n\n"
            f"您好！我是 {candidate_name}，于 {interview_date} 参加了贵司（{company_name}）「{role_name}」的面试。\n\n"
            f"非常感谢贵团队在上一阶段面试中的专业接待与细致沟通。与各位面试官的交流让我对团队业务前景与技术氛围深具好感与向往。\n\n"
            f"理解贵司近期面试流程与综合评估工作较为繁忙，目前面试已过去约一周时间，"
            f"特此致信了解一下该岗位的最新评估进展及后续时间节奏。\n\n"
            f"若团队需要补充任何技术作品、论文证明或项目文档，我随时可配合提供。\n"
            f"感谢您的辛劳，期待您的答复！\n\n"
            f"{candidate_name}\n"
        )
        return GeneratedLetter(
            letter_type=LetterType.FOLLOW_UP,
            subject=subject,
            recipient=recruiter_name,
            body_text=body.strip(),
            key_points=[f"面试日期: {interview_date}", "咨询最新进度与补充材料"],
            call_to_action="了解最新评估进展",
        )


class SalaryNegotiationWriter:
    """基于对标行情与竞争 Offer 发起的专业薪酬谈判邮件"""

    @staticmethod
    def write(
        candidate_name: str,
        recruiter_name: str,
        company_name: str,
        role_name: str,
        current_offer_package: str,
        competing_offer_summary: str,
        target_adjustment: str,
        professional_rationale: str,
    ) -> GeneratedLetter:
        subject = f"【薪酬方案探讨与意向确认】{candidate_name} - {company_name} - {role_name}"

        body = (
            f"尊敬的 {recruiter_name}：\n\n"
            f"您好！非常感谢贵司与业务主管对我技术能力与综合素质的高度认可，并向我发出「{role_name}」的正式录用邀请（{current_offer_package}）。\n\n"
            f"通过与团队的数轮深度交流，我极其认同贵司的技术路线和业务发展空间，{company_name} 也是我当下首选的职业归宿。\n\n"
            f"在综合考量整体决策时，我目前亦收到了其他对标团队的意向确认（{competing_offer_summary}）。"
            f"考虑到 {professional_rationale}，若团队能在 {target_adjustment} 方面给予一定浮动或弹性调整，我将非常笃定地第一时间接受录用并完成入职签约。\n\n"
            f"我充分理解公司在薪酬职级体系上的规范性，提出此探讨旨在兼顾个人长期稳定性与对团队的高价值贡献预期。"
            f"期待能与您探讨达成双赢方案的可能性，再次由衷感谢您的耐心与协调！\n\n"
            f"{candidate_name}\n"
        )
        return GeneratedLetter(
            letter_type=LetterType.SALARY_NEGOTIATION,
            subject=subject,
            recipient=recruiter_name,
            body_text=body.strip(),
            key_points=[
                f"当前Offer: {current_offer_package}",
                f"对标情况: {competing_offer_summary}",
                f"诉求调整: {target_adjustment}",
            ],
            call_to_action="探讨达成双赢薪酬方案",
        )


class DeclineOfferWriter:
    """礼貌拒绝 Offer 并维系高价值行业人脉的回信"""

    @staticmethod
    def write(
        candidate_name: str,
        recruiter_name: str,
        company_name: str,
        role_name: str,
        decline_reason: str,
    ) -> GeneratedLetter:
        subject = f"【录用沟通与致谢】{candidate_name} - {company_name} - {role_name}"

        body = (
            f"尊敬的 {recruiter_name} 及 {company_name} 团队：\n\n"
            f"您好！再次由衷感谢贵司向我发出「{role_name}」的录用邀请，以及在长达数轮面试中面试官与 HR 团队所展现的高效、专业与信任。\n\n"
            f"在经过审慎深思与多维度权衡后，非常遗憾地告知您：由于 {decline_reason}，"
            f"我近期无法接受该录用邀请。\n\n"
            f"作出此项决定非常艰难，{company_name} 是一家极其优秀的团队，整个面试历程让我获益匪浅。"
            f"希望未来随着个人技术发展与团队业务演进，依然能有机会以新的形式与贵司开展合作。\n\n"
            f"由衷祝愿 {company_name} 业务蒸蒸日上，也祝您工作顺利、万事胜意！\n\n"
            f"{candidate_name}\n"
        )
        return GeneratedLetter(
            letter_type=LetterType.DECLINE_OFFER,
            subject=subject,
            recipient=recruiter_name,
            body_text=body.strip(),
            key_points=[f"拒绝原因: {decline_reason}"],
            call_to_action="保持长期行业人脉链接",
        )


class CareerCommunicationKit:
    """求职沟通信函套件总门面"""

    @classmethod
    def cold_outreach(cls, *args, **kwargs) -> GeneratedLetter:
        return ColdOutreachWriter.write(*args, **kwargs)

    @classmethod
    def cover_letter(cls, *args, **kwargs) -> GeneratedLetter:
        return CoverLetterWriter.write(*args, **kwargs)

    @classmethod
    def reschedule(cls, *args, **kwargs) -> GeneratedLetter:
        return RescheduleLetterWriter.write(*args, **kwargs)

    @classmethod
    def thank_you(cls, *args, **kwargs) -> GeneratedLetter:
        return ThankYouLetterWriter.write(*args, **kwargs)

    @classmethod
    def follow_up(cls, *args, **kwargs) -> GeneratedLetter:
        return FollowUpLetterWriter.write(*args, **kwargs)

    @classmethod
    def salary_negotiation(cls, *args, **kwargs) -> GeneratedLetter:
        return SalaryNegotiationWriter.write(*args, **kwargs)

    @classmethod
    def decline_offer(cls, *args, **kwargs) -> GeneratedLetter:
        return DeclineOfferWriter.write(*args, **kwargs)
