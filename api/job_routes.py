"""
找工作模块 — extracted from main.py (L808-L1273).

Endpoints: /ai/job/*
"""
import json
import logging
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Request,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import MODEL, DASHSCOPE_URL, DASHSCOPE_API_KEY
from sqlOrm import get_db, JobProfile
from token_utils import verify_token, get_optional_user_id
from services.job_mock_data import RESUME_TEMPLATES, MOCK_JOBS, match_jobs
from api.chat_routes import ensure_chat_access

try:
    from langchain.chat_models import init_chat_model
    from langchain.messages import HumanMessage
except ModuleNotFoundError as e:
    logging.getLogger(__name__).warning("Langchain import failed (optional feature): %s", e)


logger = logging.getLogger(__name__)
router = APIRouter()


# ==================================================================
# Pydantic 模型
# ==================================================================

class JobProfilePayload(BaseModel):
    name: str = ""
    gender: str = ""
    age: str = ""
    education: str = ""
    major: str = ""
    school: str = ""
    experience_years: str = ""
    target_city: str = ""
    target_role: str = ""
    skills: str = ""
    work_experience: str = ""
    project_experience: str = ""
    self_intro: str = ""
    preset_resume: str = ""


class JobProfileSaveRequest(BaseModel):
    profile: JobProfilePayload
    template_id: str = "classic"
    resume_content: Optional[str] = None


class JobGenerateResumeRequest(BaseModel):
    profile: JobProfilePayload
    template_id: str = "classic"
    lang: str = "zh"


class JobMatchRequest(BaseModel):
    profile: JobProfilePayload
    resume_content: str = ""


class ResumeAuditRequest(BaseModel):
    profile: JobProfilePayload
    resume_content: str = ""


class MockInterviewRequest(BaseModel):
    profile: JobProfilePayload
    resume_content: str = ""
    round: int = 1
    last_answer: str = ""
    interview_type: str = "general"


# ==================================================================
# Endpoints
# ==================================================================

@router.get("/ai/job/templates", summary="简历模板列表")
def job_templates():
    return {"code": 200, "templates": RESUME_TEMPLATES}


@router.get("/ai/job/mock-jobs", summary="虚拟岗位列表（BOSS直聘风格）")
def job_mock_list():
    return {"code": 200, "jobs": MOCK_JOBS, "source": "mock"}


@router.get("/ai/job/profile", summary="获取用户求职画像")
def get_job_profile(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    record = db.query(JobProfile).filter(JobProfile.user_id == user_id).first()
    if not record:
        return {"code": 200, "profile": {}, "template_id": "classic", "resume_content": ""}
    return {
        "code": 200,
        "profile": record.profile_data or {},
        "template_id": record.template_id or "classic",
        "resume_content": record.resume_content or "",
    }


@router.post("/ai/job/profile", summary="保存用户求职画像")
def save_job_profile(
        request: JobProfileSaveRequest,
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    record = db.query(JobProfile).filter(JobProfile.user_id == user_id).first()
    profile_dict = request.profile.model_dump()
    if record:
        record.profile_data = profile_dict
        record.template_id = request.template_id
        if request.resume_content is not None:
            record.resume_content = request.resume_content
    else:
        record = JobProfile(
            user_id=user_id,
            profile_data=profile_dict,
            template_id=request.template_id,
            resume_content=request.resume_content or "",
        )
        db.add(record)
    db.commit()
    return {"code": 200, "msg": "画像已保存"}


@router.post("/ai/job/generate-resume", summary="AI 完善简历")
def generate_job_resume(
        request: JobGenerateResumeRequest,
        http_request: Request,
        db: Session = Depends(get_db),
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ensure_chat_access(http_request, user_id)

    template_name = next(
        (t["name"] for t in RESUME_TEMPLATES if t["id"] == request.template_id),
        "经典简约",
    )
    profile = request.profile.model_dump()
    preset = profile.get("preset_resume") or ""

    if (request.lang or "zh").lower().startswith("en"):
        prompt = f"""You are a professional resume consultant. Based on the profile and draft below, produce a complete, professional, ready-to-submit English resume in the "{template_name}" style.

Requirements:
1. Use Markdown format with a clear structure (Basic Info, Objective, Education, Work/Project Experience, Skills, Summary)
2. Polish, complete and quantify achievements based on the draft; do not fabricate experience that clearly contradicts the profile
3. Keep the language concise and professional, suitable for job platforms
4. Output only the resume body, no extra explanation

[Profile]
{json.dumps(profile, ensure_ascii=False, indent=2)}

[Resume Draft]
{preset or "(No draft, please generate from the profile)"}
"""
    else:
        prompt = f"""你是一名专业简历顾问。请根据以下个人画像和预设简历草稿，按「{template_name}」风格输出一份完整、专业、可直接投递的中文简历。

要求：
1. 使用 Markdown 格式，结构清晰（基本信息、求职意向、教育背景、工作/项目经历、技能、自我评价）
2. 在草稿基础上润色、补全、量化成果，不要编造与画像明显矛盾的经历
3. 语言简洁专业，适合 BOSS 直聘等平台
4. 只输出简历正文，不要额外解释

【个人画像】
{json.dumps(profile, ensure_ascii=False, indent=2)}

【预设简历草稿】
{preset or "（无草稿，请根据画像生成）"}
"""

    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0.7,
    )
    result = model.invoke([HumanMessage(content=prompt)])
    resume_text = result.content if hasattr(result, "content") else str(result)

    if user_id:
        record = db.query(JobProfile).filter(JobProfile.user_id == user_id).first()
        if record:
            record.resume_content = resume_text
            record.profile_data = profile
            record.template_id = request.template_id
        else:
            db.add(JobProfile(
                user_id=user_id,
                profile_data=profile,
                template_id=request.template_id,
                resume_content=resume_text,
            ))
        db.commit()

    return {"code": 200, "resume": resume_text}


@router.post("/ai/job/match", summary="匹配推荐岗位")
def match_job_recommendations(
        request: JobMatchRequest,
        http_request: Request,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ensure_chat_access(http_request, user_id)
    profile = request.profile.model_dump()
    jobs = match_jobs(profile, request.resume_content)
    return {"code": 200, "jobs": jobs, "source": "mock"}


@router.post("/ai/job/resume-audit", summary="AI 简历漏洞检测")
def resume_audit(
        request: ResumeAuditRequest,
        http_request: Request,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ensure_chat_access(http_request, user_id)
    profile = request.profile.model_dump()
    resume = request.resume_content or profile.get("preset_resume") or ""

    lang = (profile.get("lang") or "zh").lower()
    if lang.startswith("en"):
        prompt = f"""You are a senior HR and resume consultant. Conduct a thorough audit of the resume below and identify ALL potential issues across these dimensions:

1. **Content Completeness** - Missing sections, sparse information, lack of quantifiable results
2. **Format & Structure** - Poor organization, inconsistent formatting, length issues
3. **Keyword Optimization** - Missing industry keywords, ATS-unfriendly language
4. **Professional Tone** - Casual language, vague statements, clichés
5. **Experience Presentation** - Poor action verbs, lack of STAR method, no metrics
6. **Red Flags** - Employment gaps unexplained, job-hopping patterns, irrelevant content

For each issue found, provide:
- **category**: one of the 6 dimensions above
- **severity**: "high" / "medium" / "low"
- **issue**: specific description of the problem
- **suggestion**: concrete, actionable fix

Also provide an overall **score** (0-100) and an **overall_summary** (2-3 sentences).

Return ONLY a JSON object in this exact format:
{{
    "score": 75,
    "overall_summary": "...",
    "issues": [
        {{"category": "...", "severity": "...", "issue": "...", "suggestion": "..."}}
    ]
}}

[Profile]
{json.dumps(profile, ensure_ascii=False, indent=2)}

[Resume]
{resume or "(No resume provided - audit based on profile only)"}
"""
    else:
        prompt = f"""你是一位资深 HR 和简历顾问。请对以下简历进行全面漏洞检测，从以下 6 个维度找出所有潜在问题：

1. **内容完整性** - 模块缺失、信息量不足、缺乏量化成果
2. **格式与结构** - 排版混乱、格式不统一、篇幅不合理
3. **关键词优化** - 缺少行业关键词、表述不利于 ATS 系统识别
4. **专业语气** - 口语化严重、表述模糊、套话空话
5. **经历呈现** - 缺乏行动动词、未用 STAR 法则、无数据支撑
6. **风险信号** - 空窗期未说明、跳槽频繁、无关信息过多

对每个问题，请提供：
- **category**：所属维度（6 个之一）
- **severity**：严重程度 "high" / "medium" / "low"
- **issue**：具体问题描述
- **suggestion**：可落地的修改建议

最后给出整体 **score**（0-100 分）和 **overall_summary**（2-3 句话）。

请只返回 JSON，格式如下：
{{
    "score": 75,
    "overall_summary": "...",
    "issues": [
        {{"category": "...", "severity": "...", "issue": "...", "suggestion": "..."}}
    ]
}}

【个人画像】
{json.dumps(profile, ensure_ascii=False, indent=2)}

【简历内容】
{resume or "（无简历内容 - 仅根据画像检测）"}
"""

    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0.5,
    )
    result = model.invoke([HumanMessage(content=prompt)])
    raw = result.content if hasattr(result, "content") else str(result)

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        audit_data = json.loads(cleaned)
    except (json.JSONDecodeError, Exception) as e:
        audit_data = {
            "score": 60,
            "overall_summary": "简历解析完成，建议补充更多细节和量化成果。" if not lang.startswith("en") else "Resume parsed, suggest adding more details and quantifiable achievements.",
            "issues": [
                {"category": "内容完整性", "severity": "medium",
                 "issue": "简历细节不足" if not lang.startswith("en") else "Insufficient resume details",
                 "suggestion": "请补充工作经历中的具体项目、成果数据和技术细节" if not lang.startswith("en") else "Please add specific projects, metrics and technical details in work experience"}
            ]
        }

    return {"code": 200, "audit": audit_data}


@router.post("/ai/job/mock-interview", summary="AI 模拟面试")
def mock_interview(
        request: MockInterviewRequest,
        http_request: Request,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ensure_chat_access(http_request, user_id)
    profile = request.profile.model_dump()
    resume = request.resume_content or profile.get("preset_resume") or ""
    target_role = profile.get("target_role") or profile.get("skills") or "软件开发"
    interview_round = request.round
    last_answer = request.last_answer or ""
    itype = request.interview_type

    lang = (profile.get("lang") or "zh").lower()
    is_en = lang.startswith("en")

    if interview_round == 1:
        if is_en:
            prompt = f"""You are a professional interviewer for the position of "{target_role}".

This is Round 1 - Opening. Please:
1. Greet the candidate warmly
2. Briefly introduce yourself as the interviewer
3. Ask them to start with a self-introduction (1-2 minutes)

Consider the candidate's profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Return ONLY a JSON object:
{{
    "question": "...",
    "round": 1,
    "interviewer_intro": "...",
    "tips": "1-2 minutes, focus on highlights relevant to the role"
}}
"""
        else:
            prompt = f"""你是一名「{target_role}」岗位的专业面试官。

当前是第 1 轮 - 开场。请：
1. 友好地问候候选人
2. 简单介绍自己（面试官身份）
3. 请候选人做一个 1-2 分钟的自我介绍

候选人画像参考：
{json.dumps(profile, ensure_ascii=False, indent=2)}

请只返回 JSON：
{{
    "question": "...",
    "round": 1,
    "interviewer_intro": "...",
    "tips": "1-2分钟，重点突出与岗位相关的亮点"
}}
"""
    else:
        if is_en:
            prompt = f"""You are a professional interviewer for "{target_role}".

Previous context:
- Candidate Profile: {json.dumps(profile, ensure_ascii=False, indent=2)}
- Resume: {resume[:1000]}
- Interview Round: {interview_round}
- Interview Type: {itype}
- Candidate's Last Answer: {last_answer[:2000]}

Please:
1. **Evaluate** the last answer on these criteria (score each 0-10):
   - Relevance to the question
   - Clarity and structure
   - Use of specific examples/data
   - Professional communication

2. **Provide feedback** (1-2 sentences): What was good, what to improve.

3. **Ask the NEXT question** appropriate for round {interview_round}:
   - Round 2-3: Technical questions related to {target_role} skills
   - Round 4-5: Behavioral/STAR questions (conflict, leadership, failure, achievement)
   - Round 6+: Domain-specific deep dive or case questions

Return ONLY a JSON object:
{{
    "feedback": {{"relevance": 8, "clarity": 7, "examples": 6, "communication": 8, "comment": "..."}},
    "question": "...",
    "round": {interview_round},
    "question_type": "technical/behavioral/case",
    "tips": "..."
}}
"""
        else:
            prompt = f"""你是一名「{target_role}」岗位的专业面试官。

背景信息：
- 候选人画像：{json.dumps(profile, ensure_ascii=False, indent=2)}
- 简历：{resume[:1000]}
- 当前轮次：第 {interview_round} 轮
- 面试类型：{itype}
- 候选人上一轮回答：{last_answer[:2000]}

请完成：
1. **点评上一轮回答**，从以下维度评分（每项 0-10 分）：
   - 切题程度
   - 清晰度与条理性
   - 实例/数据支撑
   - 表达专业性

2. **给出反馈**（1-2 句话）：回答好在哪里，哪些地方可以改进。

3. **提出下一个问题**，适合第 {interview_round} 轮：
   - 第 2-3 轮：与「{target_role}」技能相关的技术问题
   - 第 4-5 轮：行为面试题（STAR 法则）—— 冲突处理、领导力、失败经历、成就感等
   - 第 6 轮以后：深度专业问题或案例分析题

请只返回 JSON：
{{
    "feedback": {{"relevance": 8, "clarity": 7, "examples": 6, "communication": 8, "comment": "..."}},
    "question": "...",
    "round": {interview_round},
    "question_type": "technical/behavioral/case",
    "tips": "..."
}}
"""

    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0.7,
    )
    result = model.invoke([HumanMessage(content=prompt)])
    raw = result.content if hasattr(result, "content") else str(result)

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        interview_data = json.loads(cleaned)
    except (json.JSONDecodeError, Exception) as e:
        if is_en:
            interview_data = {
                "question": "Thank you. Now let's move to the next question. Tell me about a challenging project you worked on.",
                "round": interview_round,
                "feedback": {"relevance": 7, "clarity": 7, "examples": 6, "communication": 7, "comment": "Good answer, could add more specific examples."},
                "question_type": "behavioral",
                "tips": "Use STAR method: Situation, Task, Action, Result",
            }
        else:
            interview_data = {
                "question": "谢谢分享。我们来看看下一个问题——请讲一个你做过的有挑战性的项目。",
                "round": interview_round,
                "feedback": {"relevance": 7, "clarity": 7, "examples": 6, "communication": 7, "comment": "回答不错，可以补充更多具体实例和数据。"},
                "question_type": "behavioral",
                "tips": "建议使用 STAR 法则：情境、任务、行动、结果",
            }

    return {"code": 200, "interview": interview_data}
