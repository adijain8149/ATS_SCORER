import fitz
import requests

RESUME_TEXT = (
    "John Doe\n"
    "Email: john.doe@gmail.com | Phone: +1-555-123-4567\n"
    "LinkedIn: linkedin.com/in/johndoe | GitHub: github.com/johndoe\n\n"
    "PROFESSIONAL SUMMARY\n"
    "Experienced Software Engineer with 4+ years building scalable REST APIs using Python, FastAPI, React, PostgreSQL.\n\n"
    "SKILLS\n"
    "Python, FastAPI, Django, JavaScript, TypeScript, React, Node.js, PostgreSQL, MongoDB, Docker, Kubernetes, AWS, Git, CI/CD, Machine Learning, REST API\n\n"
    "EXPERIENCE\n"
    "Senior Software Engineer | Tech Solutions Inc | Jan 2022 - Present\n"
    "- Led development of microservices platform using FastAPI and Docker\n"
    "- Designed REST API endpoints serving 50K daily requests\n"
    "- Optimized PostgreSQL queries improving latency by 35%\n\n"
    "Software Developer | InnovateSoft | June 2019 - Dec 2021\n"
    "- Developed React dashboard for real-time analytics\n"
    "- Built CI/CD pipelines using GitHub Actions and AWS CodeDeploy\n\n"
    "PROJECTS\n"
    "AI Resume Analyzer 2024\n"
    "Built resume analysis engine using FastAPI spaCy SentenceTransformers Docker\n\n"
    "EDUCATION\n"
    "Bachelor of Science Computer Science | University of Engineering | 2019"
)

JD = (
    "Senior Python Backend Engineer. "
    "Requirements: 3+ years Python FastAPI Django PostgreSQL Redis Docker AWS CI/CD microservices REST APIs Machine Learning"
)


def make_pdf(text):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 72), text, fontsize=10)
    data = doc.write()
    doc.close()
    return data


pdf_bytes = make_pdf(RESUME_TEXT)
print("PDF bytes:", len(pdf_bytes))

resp = requests.post(
    "http://127.0.0.1:8000/api/v1/analyze-resume",
    files={"resume": ("resume.pdf", pdf_bytes, "application/pdf")},
    data={"job_description": JD},
    timeout=120,
)

print("Status:", resp.status_code)

if resp.status_code == 200:
    r = resp.json()
    score = r.get("ATS_score") or r.get("ats_score")
    print("ATS Score:", score)
    cs = r.get("component_scores", {})
    print("Formatting:", cs.get("formatting"), "/ 20")
    print("Keywords:", cs.get("keywords"), "/ 25")
    print("Content:", cs.get("content"), "/ 25")
    print("Skill Validation:", cs.get("skill_validation"), "/ 15")
    print("ATS Compat:", cs.get("ats_compatibility"), "/ 15")
    jd_res = r.get("jd_match_analysis") or r.get("jd_comparison")
    if jd_res:
        print("JD Match %:", jd_res.get("match_percentage"))
        print("Semantic similarity:", jd_res.get("semantic_similarity"))
        print("Matched:", jd_res.get("matched_keywords", [])[:6])
        print("Missing:", jd_res.get("missing_keywords", [])[:6])
    svd = r.get("skill_validation_details", {})
    print("Validated skills:", svd.get("validated_count"), "/", svd.get("total"))
    print("Interpretation:", str(r.get("interpretation", ""))[:120])
    print("Issues summary:", str(r.get("issues_summary", ""))[:120])
    fb = r.get("detailed_feedback", [])
    print("Feedback items:", len(fb))
    for item in fb[:4]:
        sev = str(item.get("severity", "")).upper()
        cat = item.get("category", "")
        msg = str(item.get("message", ""))[:70]
        print("  [" + sev + "] " + cat + ": " + msg)
    print("ALL TESTS PASSED")
else:
    print("ERROR:", resp.text[:600])
