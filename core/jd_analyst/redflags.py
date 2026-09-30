"""
Red Flags & Trap Detector for Tech & AI Job Descriptions.
"""

import re
from typing import List, Dict, Any
from .models import (
    RedFlagType,
    RedFlagItem,
    RedFlagReport,
    DecodedJD,
)


class RedFlagDetector:
    """
    Detects critical career traps, deceptive job postings, and technical red flags:
    1. DEPARTMENT_DISCONNECT (部门主营业务割裂/边缘业务)
    2. ARCHITECTURE_REGRESSION (技术架构倒退/造轮子)
    3. ONE_MAN_FULLSTACK (全栈一人扛/榨干型岗位)
    4. INFINITE_EQUITY_PIE (无限期权画饼/低薪创业陷阱)
    5. COMPUTE_SHORTAGE (缺少真实算力/空中楼阁)
    6. PSEUDO_LLM_WRAPPER (套壳伪大模型/无核心壁垒)
    7. UNBOUNDED_OVERTIME (权责不清/无底线待命)
    """

    DETECTION_RULES: List[Dict[str, Any]] = [
        {
            "type": RedFlagType.ONE_MAN_FULLSTACK,
            "title_cn": "全栈一人扛陷阱 (One-Person Fullstack Burnout)",
            "title_en": "One-Person Fullstack Trap",
            "severity": "HIGH",
            "pattern": r"(全栈|前后端|同时负责.*?(?:算法|模型).*?(?:前端|页面|后端|运维|DevOps|测试|数据清洗|产品设计)|一人负责端到端全流程上线)",
            "risk_analysis": "公司或团队编制严重不足，试图用一份算法薪资招聘包含算法、架构、数据管道、前后端以及生产运维的'全能工具人'。候选人入职后精力将被无穷无尽的工程碎片脏活（修CSS、调接口、配Nginx、修网络）彻底稀释，无法聚焦大模型核心算法沉淀，极易导致技术断代与严重身心疲惫。",
            "interview_defense": "反问业务主管：『请问当前团队内部算法研发与工程、数据、前端的协同分工是怎样的？是否有独立的Infra团队负责GPU集群运维与模型上线管道，还是全部由本岗位直接闭环？』",
        },
        {
            "type": RedFlagType.COMPUTE_SHORTAGE,
            "title_cn": "缺少真实算力陷阱 (Compute Shortage / Mirage)",
            "title_en": "Lack of Dedicated GPU Compute",
            "severity": "HIGH",
            "pattern": r"(消费级显卡|单卡|几张4090|3090|自购显卡|算力按需申请|公有云单机按需租赁|无固定算力池)",
            "risk_analysis": "在JD中宣称自研或调优数百亿/千亿级别基座大模型，但实际基础设施仅有零散消费级GPU或按小时租赁的临时云服务器。缺乏稳定的万卡/千卡分布式训练集群与专属InfiniBand高速网络。候选人入职后将陷入'巧妇难为无米之炊'的绝境，大部分时间在排队抢卡或修OOM显存爆炸。",
            "interview_defense": "反问技术负责人：『目前团队掌管的核心算力物理机规模是多少卡（如H100/A800/910B）？多机多卡训练的网络互联拓扑是RoCE还是InfiniBand？日常实验的排队调度周期一般是多久？』",
        },
        {
            "type": RedFlagType.DEPARTMENT_DISCONNECT,
            "title_cn": "部门主营业务割裂/边缘业务陷阱 (Peripheral Disconnected Lab)",
            "title_en": "Core Business Disconnect Risk",
            "severity": "HIGH",
            "pattern": r"(创新实验室|前沿探索小组|预研小分队|不考核短期营收|集团预研|AI探索部门)",
            "risk_analysis": "所属团队偏向纯粹的'面子工程'或与母公司核心营收业务完全脱节的孤岛实验室。一旦经济周期波动或母公司降本增效，此类无直接商业造血能力的边缘项目往往首当其冲遭遇预算腰斩甚至整组撤编，简历上留下一堆未上线代码。",
            "interview_defense": "反问业务总监：『该实验室/团队的技术成果，目前在集团核心商业产品矩阵中的转化路径是什么？团队在未来1-2年的核心立项预算是否由集团直接拨备，考核指标更看重学术产出还是商业ROI？』",
        },
        {
            "type": RedFlagType.INFINITE_EQUITY_PIE,
            "title_cn": "无限期权画饼/低薪剥削陷阱 (Infinite Equity Illusion)",
            "title_en": "Illiquid Equity vs Below-Market Cash",
            "severity": "HIGH",
            "pattern": r"(极具诱惑力的期权池|早期合伙人|期权代替现金|薪资可灵活按期权调整|具有不计得失的创业精神|高额原始股)",
            "risk_analysis": "用毫无流动性保障的虚幻期权份额抵扣应得的现金Base薪资。初创团队早期期权稀释率极高、兑现退出周期长（通常4年以上），在当前退出流动性收紧的市场环境下极大概率沦为废纸，实质是以低成本套取候选人高强度智力劳动力。",
            "interview_defense": "反问HR与创始人：『请问公司目前的期权行权价(Strike Price)、总股本底数与最新一轮融资估值是多少？期权的归属周期(Vesting Schedule)与离职回购条款是否明确写入正式劳动合同？现金Base是否有底线保障？』",
        },
        {
            "type": RedFlagType.PSEUDO_LLM_WRAPPER,
            "title_cn": "套壳伪大模型陷阱 (Wrapper / Pseudo-LLM Hype)",
            "title_en": "API Wrapper Hype without Moat",
            "severity": "MEDIUM",
            "pattern": r"(调用OpenAI|熟练调用三方API|仅需编写Prompt|Prompt工程大师|基于已有开源工具简单封装)",
            "risk_analysis": "岗位名为'大模型算法研发'，实际工作仅仅是在三方闭源模型API上写简单的Prompt或套壳调用开源模板。没有基座调优、无底层系统架构、无垂直领域模型长尾数据闭环，技术壁垒极薄，极易被模型厂商原生能力更新一键碾压淘汰。",
            "interview_defense": "反问技术主管：『团队的技术护城河到底建立在垂直领域私有模型微调、强化学习对齐、推理算子定制，还是在业务层Prompt工程与工作流集成？未来有无自建私有化模型的长期规划？』",
        },
        {
            "type": RedFlagType.ARCHITECTURE_REGRESSION,
            "title_cn": "技术架构倒退/手工造轮子 (Architecture Regression)",
            "title_en": "Legacy Architecture & Wheel Reinvention",
            "severity": "MEDIUM",
            "pattern": r"(自主研发底层框架|不依赖现有成熟开源生态|从底层重写PyTorch|纯自研矩阵运算库|SVN|维护古董旧系统)",
            "risk_analysis": "团队出于盲目自大或历史技术包袱，排斥成熟的业界开源标准（如PyTorch/vLLM/DeepSpeed），强推维护落后封闭的自制工具，导致候选人所学技能严重脱节主流技术社区，丧失市场竞争力。",
            "interview_defense": "反问架构师：『团队选择自研底层组件的根本技术诉求是什么？在与业界最新成熟框架（如vLLM/FlashAttention-3）的生态兼容性与演进速度上，团队如何保障长效竞争力？』",
        },
        {
            "type": RedFlagType.UNBOUNDED_OVERTIME,
            "title_cn": "权责不清/无底线加班陷阱 (Boundless Overtime / Blur Boundaries)",
            "title_en": "Extreme Overtime & Boundary Blur",
            "severity": "MEDIUM",
            "pattern": r"(抗压能力极强|24小时响应|工作生活融为一体|全天候待命|无条件服从临时安排|狼性文化|大小周)",
            "risk_analysis": "暗示严重且无规律的过度加班，组织管理与项目排期极度混乱，常态化依靠'人肉救火'弥补架构缺陷或产品无序迭代，极易引发健康危机与职业倦怠。",
            "interview_defense": "反问HR与团队成员：『团队日常的平均下班时间一般在几点？周末及法定节假日的紧急On-Call响应频次如何？如果出现非工作时间紧急故障，是否有明确的补休或津贴制度？』",
        },
    ]

    def detect(self, jd: DecodedJD) -> RedFlagReport:
        """Analyze DecodedJD to identify red flags and compile a report."""
        text = jd.raw_text
        detected_flags: List[RedFlagItem] = []

        # 1. Rule-based detection from text
        for rule in self.DETECTION_RULES:
            matches = list(re.finditer(rule["pattern"], text, re.IGNORECASE))
            if matches:
                trigger_snippet = " ... ".join([m.group(0) for m in matches[:3]])
                detected_flags.append(
                    RedFlagItem(
                        flag_type=rule["type"],
                        title_cn=rule["title_cn"],
                        title_en=rule["title_en"],
                        severity=rule["severity"],
                        trigger_snippet=trigger_snippet,
                        risk_analysis=rule["risk_analysis"],
                        interview_defense=rule["interview_defense"],
                    )
                )

        # 2. Structural heuristics detection
        # e.g., if JD has massive number of responsibilities across both frontend, backend, algorithm, and infra
        has_frontend = bool(re.search(r"(Vue|React|前端|Web界面|小程序)", text, re.IGNORECASE))
        has_algo = bool(re.search(r"(大模型|LLM|预训练|对齐|RLHF|算法研发)", text, re.IGNORECASE))
        has_ops = bool(re.search(r"(K8s|Docker|集群运维|监控告警|Nginx|运维)", text, re.IGNORECASE))
        if has_frontend and has_algo and has_ops:
            if not any(f.flag_type == RedFlagType.ONE_MAN_FULLSTACK for f in detected_flags):
                detected_flags.append(
                    RedFlagItem(
                        flag_type=RedFlagType.ONE_MAN_FULLSTACK,
                        title_cn="全栈一人扛陷阱 (Multi-Domain Overload)",
                        title_en="One-Person Fullstack Trap",
                        severity="HIGH",
                        trigger_snippet="JD同时苛求前端(Vue/React)、大模型算法核心研发与K8s生产运维",
                        risk_analysis="岗位涉猎广度严重失焦，一个人承担整套软件工程与核心算法研发，日常工作注定沦为多维救火队员。",
                        interview_defense="反问团队编制：『请问岗位的第一核心产出权重是什么？团队内是否有专职前端与DevOps提供支持？』",
                    )
                )

        # Calculate risk score and level
        risk_score = 0
        for f in detected_flags:
            if f.severity == "HIGH":
                risk_score += 35
            elif f.severity == "MEDIUM":
                risk_score += 20
            else:
                risk_score += 10
        risk_score = min(risk_score, 100)

        if risk_score >= 60:
            overall_level = "SEVERE"  # 严重高危
            summary = "警惕！该岗位存在多项高危红旗与潜在职场深坑，极大概率存在算力空虚、过度压榨或业务边缘化风险，建议审慎推进并在面试中全力攻防反问。"
        elif risk_score >= 35:
            overall_level = "HIGH"  # 较高风险
            summary = "注意！该岗位侦测到部分敏感信号，可能存在职责边界模糊或加班强度过高的隐忧，需在面试中重点核实基础设施与团队分工。"
        elif risk_score > 0:
            overall_level = "MODERATE"  # 中等提示
            summary = "该岗位总体技术方向明确，但包含个别大厂黑话或敏捷应变要求，入职前应了解具体的业务考核KPI与排期节奏。"
        else:
            overall_level = "LOW"  # 纯净安全
            summary = "未检测到明显的岗位红旗与陷阱套路，JD表述规范专业，核心职责与技术栈聚焦，属于较为扎实的核心技术研发岗位。"

        return RedFlagReport(
            flags=detected_flags,
            overall_risk_level=overall_level,
            risk_score=risk_score,
            summary=summary,
        )
