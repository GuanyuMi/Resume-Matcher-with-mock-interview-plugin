"""Context builders for adaptive mock interview sessions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def build_resume_highlights(resume_data: dict[str, Any]) -> list[str]:
    """Summarize structured resume data into interview-ready highlights."""
    highlights: list[str] = []

    summary = (resume_data.get("summary") or "").strip()
    if summary:
        highlights.append(summary)

    for experience in resume_data.get("workExperience", [])[:4]:
        if not isinstance(experience, dict):
            continue
        title = experience.get("title", "")
        company = experience.get("company", "")
        years = experience.get("years", "")
        bullets = experience.get("description", [])
        bullet_text = ""
        if isinstance(bullets, list):
            bullet_text = "; ".join(str(item).strip() for item in bullets[:2] if str(item).strip())
        parts = [str(part).strip() for part in (title, company, years) if str(part).strip()]
        label = " | ".join(parts)
        if label and bullet_text:
            highlights.append(f"{label}: {bullet_text}")
        elif label:
            highlights.append(label)

    for project in resume_data.get("personalProjects", [])[:3]:
        if not isinstance(project, dict):
            continue
        name = project.get("name", "")
        role = project.get("role", "")
        bullets = project.get("description", [])
        bullet_text = ""
        if isinstance(bullets, list):
            bullet_text = "; ".join(str(item).strip() for item in bullets[:2] if str(item).strip())
        parts = [str(part).strip() for part in (name, role) if str(part).strip()]
        label = " | ".join(parts)
        if label and bullet_text:
            highlights.append(f"{label}: {bullet_text}")
        elif label:
            highlights.append(label)

    additional = resume_data.get("additional", {})
    if isinstance(additional, dict):
        skills = additional.get("technicalSkills", [])
        if isinstance(skills, list) and skills:
            highlights.append("Technical skills: " + ", ".join(str(skill).strip() for skill in skills[:12]))

    return _dedupe_preserve_order(highlights)


def build_skill_inventory(resume_data: dict[str, Any]) -> list[str]:
    """Extract a normalized skill inventory from the resume."""
    inventory: list[str] = []

    additional = resume_data.get("additional", {})
    if isinstance(additional, dict):
        for key in ("technicalSkills", "certificationsTraining", "languages", "awards"):
            value = additional.get(key, [])
            if isinstance(value, list):
                inventory.extend(str(item).strip() for item in value if str(item).strip())

    for experience in resume_data.get("workExperience", []):
        if not isinstance(experience, dict):
            continue
        for bullet in experience.get("description", [])[:3]:
            bullet_text = str(bullet).strip()
            if bullet_text:
                inventory.append(bullet_text)

    for project in resume_data.get("personalProjects", []):
        if not isinstance(project, dict):
            continue
        for bullet in project.get("description", [])[:3]:
            bullet_text = str(bullet).strip()
            if bullet_text:
                inventory.append(bullet_text)

    return _dedupe_preserve_order(inventory)


def build_interview_context(
    *,
    resume_id: str,
    job_id: str,
    job_content: str,
    resume_data: dict[str, Any],
    job_keywords: dict[str, Any],
) -> dict[str, Any]:
    """Create a stable interview context snapshot from resume and JD data."""
    resume_highlights = build_resume_highlights(resume_data)
    resume_inventory = build_skill_inventory(resume_data)
    inventory_text = " ".join(resume_inventory).casefold()

    required_skills = _dedupe_preserve_order(
        str(skill).strip() for skill in job_keywords.get("required_skills", [])
    )
    preferred_skills = _dedupe_preserve_order(
        str(skill).strip() for skill in job_keywords.get("preferred_skills", [])
    )
    keywords = _dedupe_preserve_order(
        str(keyword).strip() for keyword in job_keywords.get("keywords", [])
    )
    responsibilities = _dedupe_preserve_order(
        str(item).strip() for item in job_keywords.get("key_responsibilities", [])
    )

    matched_skills = [skill for skill in required_skills if skill.casefold() in inventory_text]
    missing_skills = [skill for skill in required_skills if skill.casefold() not in inventory_text]

    focus_areas = _dedupe_preserve_order(
        [*missing_skills[:4], *matched_skills[:3], *responsibilities[:4], *keywords[:4]]
    )
    if not focus_areas:
        focus_areas = _dedupe_preserve_order(required_skills or preferred_skills or keywords or responsibilities)

    match_ratio = 0.0
    if required_skills:
        match_ratio = round(len(matched_skills) / len(required_skills), 4)

    return {
        "resume_id": resume_id,
        "job_id": job_id,
        "job_excerpt": job_content[:1200],
        "core_requirements": required_skills or keywords[:8],
        "preferred_skills": preferred_skills[:8],
        "matched_skills": matched_skills[:8],
        "missing_skills": missing_skills[:8],
        "responsibilities": responsibilities[:8],
        "resume_highlights": resume_highlights[:8],
        "focus_areas": focus_areas[:8],
        "match_ratio": match_ratio,
    }
