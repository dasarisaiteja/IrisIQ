import sqlite3
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "iris_database.db")


def get_connection():
    return sqlite3.connect(DB_NAME, timeout=30, check_same_thread=False)


def create_student_tables():
    """
    Non-destructive creation of student intelligence tables.
    Preserves all existing tables and data.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Student Profiles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        employee_code TEXT,
        full_name TEXT NOT NULL,
        age INTEGER,
        gender TEXT,
        email TEXT,
        mobile TEXT,
        school_college TEXT,
        course TEXT,
        year TEXT,
        stream TEXT,
        location TEXT,
        photo_path TEXT,
        created_on TEXT,
        updated_on TEXT
    )
    """)

    # 2. Academic Records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS academic_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        subject_name TEXT NOT NULL,
        marks_obtained REAL NOT NULL,
        max_marks REAL NOT NULL DEFAULT 100,
        grade TEXT,
        term TEXT,
        created_on TEXT
    )
    """)

    # 3. Student Skills
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        skill_name TEXT NOT NULL,
        skill_type TEXT,
        proficiency_score REAL NOT NULL,
        created_on TEXT
    )
    """)

    # 4. Student Interests
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        category TEXT,
        interest_name TEXT NOT NULL,
        level TEXT,
        created_on TEXT
    )
    """)

    # 5. Student Activities
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        title TEXT NOT NULL,
        activity_type TEXT,
        description TEXT,
        year TEXT,
        created_on TEXT
    )
    """)

    # 6. Assessment Questions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assessment_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        subcategory TEXT,
        question_text TEXT NOT NULL,
        answer_type TEXT DEFAULT 'likert',
        options_json TEXT NOT NULL,
        scoring_weights_json TEXT NOT NULL,
        scoring_direction TEXT DEFAULT 'positive',
        scoring_weight REAL DEFAULT 1.0,
        is_reverse_scored INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        version TEXT DEFAULT 'v1'
    )
    """)

    # Non-destructive schema migration for existing assessment_questions table
    cursor.execute("PRAGMA table_info(assessment_questions)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    if "answer_type" not in existing_cols:
        cursor.execute("ALTER TABLE assessment_questions ADD COLUMN answer_type TEXT DEFAULT 'likert'")
    if "scoring_direction" not in existing_cols:
        cursor.execute("ALTER TABLE assessment_questions ADD COLUMN scoring_direction TEXT DEFAULT 'positive'")
    if "scoring_weight" not in existing_cols:
        cursor.execute("ALTER TABLE assessment_questions ADD COLUMN scoring_weight REAL DEFAULT 1.0")
    if "is_reverse_scored" not in existing_cols:
        cursor.execute("ALTER TABLE assessment_questions ADD COLUMN is_reverse_scored INTEGER DEFAULT 0")
    if "is_active" not in existing_cols:
        cursor.execute("ALTER TABLE assessment_questions ADD COLUMN is_active INTEGER DEFAULT 1")

    # 7. Student Assessment Responses & Scores
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        domain TEXT NOT NULL,
        version TEXT DEFAULT 'v1',
        completed_on TEXT,
        raw_responses_json TEXT NOT NULL,
        scores_json TEXT NOT NULL
    )
    """)

    # 8. Prediction Results with Source Provenance
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prediction_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        category TEXT NOT NULL,
        sub_category TEXT,
        score REAL NOT NULL,
        label TEXT,
        confidence REAL,
        source TEXT NOT NULL,
        model_version TEXT,
        created_on TEXT
    )
    """)

    # 9. Career Catalog
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS career_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        career_name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        required_skills_json TEXT,
        required_subjects_json TEXT,
        interest_areas_json TEXT,
        aptitude_requirements_json TEXT,
        relevant_assessment_domains_json TEXT,
        work_style TEXT,
        education_pathway TEXT,
        required_certifications TEXT,
        future_opportunities TEXT,
        is_trending INTEGER DEFAULT 0,
        eligible_streams_json TEXT DEFAULT '["Science (STEM)", "Commerce & Business Studies", "Humanities & Social Sciences"]',
        development_requirements_json TEXT DEFAULT '[]',
        version TEXT DEFAULT 'v1',
        is_active INTEGER DEFAULT 1,
        trending_source TEXT DEFAULT 'curated_catalog'
    )
    """)

    # Non-destructive schema migration for existing career_catalog table
    cursor.execute("PRAGMA table_info(career_catalog)")
    existing_career_cols = [col[1] for col in cursor.fetchall()]
    if "eligible_streams_json" not in existing_career_cols:
        cursor.execute("ALTER TABLE career_catalog ADD COLUMN eligible_streams_json TEXT DEFAULT '[\"Science (STEM)\", \"Commerce & Business Studies\", \"Humanities & Social Sciences\"]'")
    if "development_requirements_json" not in existing_career_cols:
        cursor.execute("ALTER TABLE career_catalog ADD COLUMN development_requirements_json TEXT DEFAULT '[]'")
    if "version" not in existing_career_cols:
        cursor.execute("ALTER TABLE career_catalog ADD COLUMN version TEXT DEFAULT 'v1'")
    if "is_active" not in existing_career_cols:
        cursor.execute("ALTER TABLE career_catalog ADD COLUMN is_active INTEGER DEFAULT 1")
    if "trending_source" not in existing_career_cols:
        cursor.execute("ALTER TABLE career_catalog ADD COLUMN trending_source TEXT DEFAULT 'curated_catalog'")

    # 10. Activity & Sports Catalog
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_name TEXT UNIQUE NOT NULL,
        activity_type TEXT NOT NULL,
        benefits TEXT,
        skills_developed_json TEXT,
        aptitude_alignment_json TEXT
    )
    """)

    # 11. Report Versions (V1 / V2)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id TEXT UNIQUE NOT NULL,
        student_id TEXT NOT NULL,
        version_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_on TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

    # Seed baseline reference data
    seed_reference_data()


def seed_reference_data():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Seed Assessment Questions if empty
    cursor.execute("SELECT COUNT(*) FROM assessment_questions")
    if cursor.fetchone()[0] == 0:
        questions = [
            # A. Personality (Big Five)
            {
                "domain": "personality", "subcategory": "openness",
                "question_text": "I enjoy exploring novel abstract ideas and creative concepts even without immediate practical application.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"trait": "openness", "weight": 1.0})
            },
            {
                "domain": "personality", "subcategory": "conscientiousness",
                "question_text": "I maintain organized study habits, systematically plan deadlines, and finish tasks ahead of schedule.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"trait": "conscientiousness", "weight": 1.0})
            },
            {
                "domain": "personality", "subcategory": "extraversion",
                "question_text": "I feel energized when engaging in group discussions, public speaking, or collaborative events.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"trait": "extraversion", "weight": 1.0})
            },
            {
                "domain": "personality", "subcategory": "agreeableness",
                "question_text": "I actively listen to peers' concerns and strive for team harmony even during disagreements.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"trait": "agreeableness", "weight": 1.0})
            },
            {
                "domain": "personality", "subcategory": "emotional_stability",
                "question_text": "I stay composed, level-headed, and focused when unexpected exam or project hurdles occur.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"trait": "emotional_stability", "weight": 1.0})
            },

            # B. Critical Abilities
            {
                "domain": "critical_abilities", "subcategory": "problem_solving",
                "question_text": "When confronted with an intricate multi-step problem, how do you approach solving it?",
                "options_json": json.dumps([
                    {"text": "Try random approaches until something sticks", "val": 1},
                    {"text": "Seek immediate help before analyzing", "val": 2},
                    {"text": "Break it into discrete components and address root causes", "val": 4},
                    {"text": "Formulate hypotheses, test edge cases, and synthesize solutions", "val": 5}
                ]),
                "scoring_weights_json": json.dumps({"ability": "problem_solving", "weight": 1.0})
            },
            {
                "domain": "critical_abilities", "subcategory": "creative_ability",
                "question_text": "How often do you devise unconventional methods or creative workarounds to solve standard assignments?",
                "options_json": json.dumps([{"text": "Rarely", "val": 1}, {"text": "Occasionally", "val": 2}, {"text": "Frequently", "val": 4}, {"text": "Almost Always", "val": 5}]),
                "scoring_weights_json": json.dumps({"ability": "creative_ability", "weight": 1.0})
            },
            {
                "domain": "critical_abilities", "subcategory": "pressure_handling",
                "question_text": "During high-stakes deadlines or competitive examinations, my performance:",
                "options_json": json.dumps([
                    {"text": "Degrades significantly due to stress", "val": 1},
                    {"text": "Fluctuates inconsistently", "val": 2},
                    {"text": "Remains steady and disciplined", "val": 4},
                    {"text": "Peaks with heightened focus and clarity", "val": 5}
                ]),
                "scoring_weights_json": json.dumps({"ability": "pressure_handling", "weight": 1.0})
            },
            {
                "domain": "critical_abilities", "subcategory": "emotion_management",
                "question_text": "When receiving constructive criticism or facing academic setback:",
                "options_json": json.dumps([
                    {"text": "I feel demotivated and take it personally", "val": 1},
                    {"text": "I need extended time to recover enthusiasm", "val": 2},
                    {"text": "I objectively process feedback and adjust", "val": 4},
                    {"text": "I immediately extract growth opportunities and optimize", "val": 5}
                ]),
                "scoring_weights_json": json.dumps({"ability": "emotion_management", "weight": 1.0})
            },
            {
                "domain": "critical_abilities", "subcategory": "logical_reasoning",
                "question_text": "I naturally detect fallacies in arguments and deduce structured conclusions from raw evidence.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"ability": "logical_reasoning", "weight": 1.0})
            },

            # C. Learning Style – VAK
            {
                "domain": "learning_style", "subcategory": "vak",
                "question_text": "When learning a complex new topic, what format helps you understand fastest?",
                "options_json": json.dumps([
                    {"text": "Diagrams, flowcharts, infographics, and written summaries (Visual)", "val": "V"},
                    {"text": "Lectures, podcasts, verbal explanations, and group debates (Auditory)", "val": "A"},
                    {"text": "Hands-on labs, building prototypes, trial-and-error exercises (Kinesthetic)", "val": "K"}
                ]),
                "scoring_weights_json": json.dumps({"type": "VAK_single"})
            },
            {
                "domain": "learning_style", "subcategory": "vak",
                "question_text": "When assembling equipment or following instructions, you prefer:",
                "options_json": json.dumps([
                    {"text": "Looking at visual diagrams and schematics (Visual)", "val": "V"},
                    {"text": "Having someone talk you through each step (Auditory)", "val": "A"},
                    {"text": "Jumping right in and manipulating parts physically (Kinesthetic)", "val": "K"}
                ]),
                "scoring_weights_json": json.dumps({"type": "VAK_single"})
            },
            {
                "domain": "learning_style", "subcategory": "vak",
                "question_text": "In a study room, what is your most effective memorization technique?",
                "options_json": json.dumps([
                    {"text": "Color-coding notes, mind-mapping, and highlighting textbooks (Visual)", "val": "V"},
                    {"text": "Reciting facts aloud and debating concepts with study partners (Auditory)", "val": "A"},
                    {"text": "Walking around while studying or making physical flashcards (Kinesthetic)", "val": "K"}
                ]),
                "scoring_weights_json": json.dumps({"type": "VAK_single"})
            },

            # D. Leadership Style (Task vs Relationship)
            {
                "domain": "leadership_style", "subcategory": "orientation",
                "question_text": "When leading a team project, your primary priority is:",
                "options_json": json.dumps([
                    {"text": "Milestones, checklists, rigorous quality standards, and on-time delivery (Task)", "val": "T"},
                    {"text": "Team morale, psychological safety, consensus, and member growth (Relationship)", "val": "R"},
                    {"text": "Balanced blend of task rigor and team encouragement", "val": "B"}
                ]),
                "scoring_weights_json": json.dumps({"type": "leadership_single"})
            },
            {
                "domain": "leadership_style", "subcategory": "orientation",
                "question_text": "If a teammate struggles with their assignment, you first:",
                "options_json": json.dumps([
                    {"text": "Re-assign or restructure the workflow to safeguard the schedule (Task)", "val": "T"},
                    {"text": "Coach them 1-on-1, understand difficulties, and provide encouragement (Relationship)", "val": "R"},
                    {"text": "Provide standard documentation and clarify milestones", "val": "B"}
                ]),
                "scoring_weights_json": json.dumps({"type": "leadership_single"})
            },

            # E. Thinking vs Action
            {
                "domain": "thinking_action", "subcategory": "orientation",
                "question_text": "When starting a fresh project, do you tend to spend extensive time researching scenarios or do you execute immediate rapid prototypes?",
                "options_json": json.dumps([
                    {"text": "Heavy analytical planning and risk assessment before action (Thinking)", "val": 1},
                    {"text": "Moderate planning followed by deliberate execution", "val": 3},
                    {"text": "Rapid biased-to-action iteration and learn-by-doing (Action)", "val": 5}
                ]),
                "scoring_weights_json": json.dumps({"type": "scale_thinking_action"})
            },

            # F. Team Management vs Team Player
            {
                "domain": "team_player", "subcategory": "role",
                "question_text": "In group settings, which dynamic aligns best with your natural inclination?",
                "options_json": json.dumps([
                    {"text": "Setting goals, delegating responsibilities, and coordinating the overall vision (Team Management)", "val": "M"},
                    {"text": "Excelling in my specialized component and supporting teammates reliably (Team Player)", "val": "P"},
                    {"text": "Equally comfortable leading or executing specialized work", "val": "B"}
                ]),
                "scoring_weights_json": json.dumps({"type": "team_role_single"})
            },

            # G. Behavioural Indicators
            {
                "domain": "behavioral", "subcategory": "adaptability",
                "question_text": "I adjust smoothly to sudden changes in academic guidelines, schedules, or team assignments.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"indicator": "adaptability", "weight": 1.0})
            },
            {
                "domain": "behavioral", "subcategory": "perseverance",
                "question_text": "When a project encounters repetitive obstacles, I maintain energy and see it through to completion.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"indicator": "perseverance", "weight": 1.0})
            },

            # H. Emotional/Social Indicators
            {
                "domain": "emotional_social", "subcategory": "empathy",
                "question_text": "I easily sense when peers are feeling overwhelmed and proactively offer assistance.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"indicator": "empathy", "weight": 1.0})
            },
            {
                "domain": "emotional_social", "subcategory": "social_confidence",
                "question_text": "I feel confident introducing myself in new professional or academic forums.",
                "options_json": json.dumps([{"text": "Strongly Disagree", "val": 1}, {"text": "Disagree", "val": 2}, {"text": "Neutral", "val": 3}, {"text": "Agree", "val": 4}, {"text": "Strongly Agree", "val": 5}]),
                "scoring_weights_json": json.dumps({"indicator": "social_confidence", "weight": 1.0})
            }
        ]
        for q in questions:
            cursor.execute("""
            INSERT INTO assessment_questions (
                domain, subcategory, question_text, answer_type, options_json, 
                scoring_weights_json, scoring_direction, scoring_weight, is_reverse_scored, is_active, version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'v1')
            """, (
                q["domain"], q["subcategory"], q["question_text"],
                q.get("answer_type", "likert"), q["options_json"],
                q["scoring_weights_json"], q.get("scoring_direction", "positive"),
                q.get("scoring_weight", 1.0), q.get("is_reverse_scored", 0),
                q.get("is_active", 1)
            ))

    # 2. Seed Career Catalog if empty
    cursor.execute("SELECT COUNT(*) FROM career_catalog")
    if cursor.fetchone()[0] == 0:
        careers = [
            # Engineering & AI
            {
                "career_name": "Artificial Intelligence & ML Engineer",
                "category": "Engineering & AI",
                "required_skills": ["Python", "Machine Learning", "Linear Algebra", "Data Structures", "TensorFlow/PyTorch"],
                "required_subjects": ["Mathematics", "Computer Science", "Physics"],
                "interest_areas": ["Artificial Intelligence", "Robotics", "Algorithm Design", "Software Systems"],
                "aptitude_requirements": {"logical_reasoning": 85, "problem_solving": 85, "analytical_thinking": 80},
                "relevant_assessment_domains": ["critical_abilities", "cognitive", "thinking_action"],
                "work_style": "Analytical, systematic, and continuous experimentation",
                "education_pathway": "B.Tech/B.S. in Computer Science/AI -> M.S. or Specialization in Applied ML",
                "required_certifications": "Deep Learning Specialization, AWS/GCP ML Engineer",
                "future_opportunities": "High growth trajectory across autonomous systems, generative AI, and enterprise intelligence",
                "is_trending": 1
            },
            {
                "career_name": "Cloud Systems & DevOps Architect",
                "category": "Engineering & AI",
                "required_skills": ["Linux", "Cloud Architecture", "Docker/Kubernetes", "CI/CD", "Networking"],
                "required_subjects": ["Computer Science", "Mathematics"],
                "interest_areas": ["Cloud Infrastructure", "System Automation", "Cybersecurity"],
                "aptitude_requirements": {"problem_solving": 80, "planning": 75, "attention_to_detail": 80},
                "relevant_assessment_domains": ["critical_abilities", "thinking_action"],
                "work_style": "Structured, reliability-oriented, rapid troubleshooting",
                "education_pathway": "B.Tech/B.Sc in Information Technology / Systems Engineering",
                "required_certifications": "AWS Solutions Architect, CKA Kubernetes Administrator",
                "future_opportunities": "Mission-critical infrastructure role with universal demand across global tech",
                "is_trending": 1
            },

            # Human & Life Science
            {
                "career_name": "Biomedical Data Scientist",
                "category": "Human & Life Science",
                "required_skills": ["Bioinformatics", "Statistical Modeling", "Python/R", "Genomics", "Data Visualization"],
                "required_subjects": ["Biology", "Mathematics", "Computer Science"],
                "interest_areas": ["Genomics", "Healthcare Tech", "Molecular Biology", "Clinical Research"],
                "aptitude_requirements": {"logical_reasoning": 80, "analytical_thinking": 85, "memory": 75},
                "relevant_assessment_domains": ["critical_abilities", "cognitive"],
                "work_style": "Research-oriented, precision-driven, ethical analysis",
                "education_pathway": "B.S. in Biotechnology/Bioinformatics -> M.S. in Computational Biology",
                "required_certifications": "Bioinformatics Specialization, Good Clinical Practice (GCP)",
                "future_opportunities": "Accelerating demand in personalized medicine, pharmaceutical R&D, and genomic diagnostics",
                "is_trending": 1
            },

            # Management
            {
                "career_name": "Technology Product Manager",
                "category": "Management",
                "required_skills": ["Product Strategy", "User Research", "Agile Methodologies", "Communication", "Data Analytics"],
                "required_subjects": ["Computer Science / Economics", "Business Studies", "Languages"],
                "interest_areas": ["Product Design", "Entrepreneurship", "Market Dynamics", "Technology Trends"],
                "aptitude_requirements": {"communication": 85, "leadership": 80, "problem_solving": 80, "planning": 85},
                "relevant_assessment_domains": ["leadership_style", "team_player", "critical_abilities"],
                "work_style": "Collaborative, vision-oriented, cross-functional leadership",
                "education_pathway": "B.Tech / B.B.A -> MBA or Experience-led Transition in Tech Management",
                "required_certifications": "Certified Scrum Product Owner (CSPO), Pragmatic Institute Certified",
                "future_opportunities": "Core executive track in software and hardware technological ventures",
                "is_trending": 1
            },

            # Medical & Paramedical
            {
                "career_name": "Clinical Physician / Specialist",
                "category": "Medical & Paramedical",
                "required_skills": ["Clinical Diagnosis", "Patient Care", "Medical Ethics", "Critical Decision Making", "Empathy"],
                "required_subjects": ["Biology", "Chemistry", "Physics"],
                "interest_areas": ["Human Anatomy", "Pathology", "Patient Care", "Medical Research"],
                "aptitude_requirements": {"pressure_handling": 85, "emotion_management": 85, "memory": 85, "attention_to_detail": 90},
                "relevant_assessment_domains": ["critical_abilities", "emotional_social"],
                "work_style": "High-empathy, resilient under pressure, meticulous accuracy",
                "education_pathway": "MBBS / Pre-Med -> MD/MS Residency and Fellowship",
                "required_certifications": "State Medical Council Registration, USMLE/PLAB",
                "future_opportunities": "Resilient, esteemed lifelong profession with global mobility",
                "is_trending": 0
            },

            # Designing & Creativity
            {
                "career_name": "UI/UX & Digital Product Designer",
                "category": "Designing & Creativity",
                "required_skills": ["Figma", "Design Systems", "User Psychology", "Prototyping", "Design Thinking"],
                "required_subjects": ["Design / Arts", "Computer Science", "Psychology"],
                "interest_areas": ["Visual Aesthetics", "Human-Computer Interaction", "Animation", "Typography"],
                "aptitude_requirements": {"creative_ability": 90, "visual_spatial": 85, "empathy": 80},
                "relevant_assessment_domains": ["personality", "critical_abilities", "learning_style"],
                "work_style": "Iterative, empathetic, aesthetic and user-focused",
                "education_pathway": "B.Des in Interaction Design / Digital Media -> Industry Portfolio",
                "required_certifications": "Google UX Design Professional Certificate, Nielsen Norman Group UX Certification",
                "future_opportunities": "Elevated strategic role as digital user experiences define brand competitive advantage",
                "is_trending": 1
            },

            # Weather & Environment
            {
                "career_name": "Environmental Scientist & Climate Analyst",
                "category": "Weather & Environment",
                "required_skills": ["GIS Mapping", "Climate Data Modeling", "Environmental Impact Assessment", "Statistical Analysis"],
                "required_subjects": ["Environmental Science", "Geography / Earth Science", "Chemistry", "Physics"],
                "interest_areas": ["Renewable Energy", "Climate Action", "Ecology", "Atmospheric Physics"],
                "aptitude_requirements": {"analytical_thinking": 80, "problem_solving": 75, "planning": 80},
                "relevant_assessment_domains": ["critical_abilities", "cognitive"],
                "work_style": "Field-and-lab investigation, sustainability-driven, policy impact",
                "education_pathway": "B.Sc in Environmental Science / Meteorology -> M.Sc in Climate Dynamics",
                "required_certifications": "GIS Certification, LEED Green Associate",
                "future_opportunities": "Surging international demand tied to green transitions and ESG compliance",
                "is_trending": 1
            }
        ]
        for c in careers:
            cursor.execute("""
            INSERT INTO career_catalog (
                career_name, category, required_skills_json, required_subjects_json,
                interest_areas_json, aptitude_requirements_json, relevant_assessment_domains_json,
                work_style, education_pathway, required_certifications, future_opportunities, is_trending
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c["career_name"], c["category"], json.dumps(c["required_skills"]),
                json.dumps(c["required_subjects"]), json.dumps(c["interest_areas"]),
                json.dumps(c["aptitude_requirements"]), json.dumps(c["relevant_assessment_domains"]),
                c["work_style"], c["education_pathway"], c["required_certifications"],
                c["future_opportunities"], c["is_trending"]
            ))

    # 3. Seed Activities & Sports Catalog if empty
    cursor.execute("SELECT COUNT(*) FROM activity_catalog")
    if cursor.fetchone()[0] == 0:
        activities = [
            # Co-curricular
            {"name": "Chess", "type": "co-curricular", "benefits": "Sharpens foresight, strategic planning, and tactical calculation", "skills": ["Strategic Planning", "Pattern Recognition", "Focus"], "apt": {"logical_reasoning": 80, "planning": 80}},
            {"name": "Instrumental Music", "type": "co-curricular", "benefits": "Enhances neuro-auditory synchronization, patience, and fine motor coordination", "skills": ["Discipline", "Auditory Processing", "Fine Motor Skills"], "apt": {"creative_ability": 75, "attention_focus": 80}},
            {"name": "Singing & Vocal Arts", "type": "co-curricular", "benefits": "Builds breath control, emotional expression, and auditory memory", "skills": ["Vocal Range", "Emotional Expression", "Presence"], "apt": {"emotion_management": 75, "creative_ability": 75}},
            {"name": "Dance & Performing Arts", "type": "co-curricular", "benefits": "Develops rhythm, spatial orientation, physical poise, and kinesthetic agility", "skills": ["Rhythm", "Spatial Awareness", "Kinesthetic Memory"], "apt": {"visual_spatial": 75, "creative_ability": 75}},
            {"name": "Yoga & Mindfulness", "type": "co-curricular", "benefits": "Cultivates autonomic stress regulation, mind-body balance, and mental clarity", "skills": ["Breathwork", "Stress Regulation", "Flexibility"], "apt": {"pressure_handling": 80, "emotion_management": 80}},
            {"name": "Foreign Language Club", "type": "co-curricular", "benefits": "Broadens linguistic cognitive flexibility, memory encoding, and cultural empathy", "skills": ["Linguistic Fluency", "Cross-Cultural Communication", "Verbal Memory"], "apt": {"language_communication": 80, "memory": 75}},
            {"name": "Fine Arts & Craft", "type": "co-curricular", "benefits": "Refines visual aesthetics, color theory mastery, and creative patience", "skills": ["Visual Expression", "Detail Orientation", "Color Composition"], "apt": {"creative_ability": 80, "visual_spatial": 80}},
            {"name": "Photography & Videography", "type": "co-curricular", "benefits": "Enhances framing perspective, lighting sensitivity, and visual storytelling", "skills": ["Visual Framing", "Visual Storytelling", "Lighting"], "apt": {"visual_spatial": 80, "creative_ability": 75}},
            {"name": "Acting & Drama", "type": "co-curricular", "benefits": "Boosts stage confidence, empathy, emotional range, and improvisational skills", "skills": ["Public Speaking", "Character Empathy", "Improvisation"], "apt": {"social_confidence": 85, "language_communication": 80}},

            # Sports
            {"name": "Swimming", "type": "sports", "benefits": "Full-body aerobic conditioning, breath control, and independent stamina", "skills": ["Cardiovascular Stamina", "Kinesthetic Balance", "Self-Discipline"], "apt": {"perseverance": 80, "pressure_handling": 75}},
            {"name": "Horse Riding (Equestrian)", "type": "sports", "benefits": "Develops non-verbal animal communication, core stability, and calm assertiveness", "skills": ["Posture Balance", "Empathetic Attunement", "Courage"], "apt": {"emotion_management": 80, "pressure_handling": 80}},
            {"name": "Target Shooting & Archery", "type": "sports", "benefits": "Demands absolute breath stillness, pulse regulation, and laser target focus", "skills": ["Precision Aiming", "Pulse Regulation", "Laser Concentration"], "apt": {"attention_focus": 85, "pressure_handling": 85}},
            {"name": "Badminton / Tennis", "type": "sports", "benefits": "Reflex rapidity, hand-eye coordination, and tactical spatial court coverage", "skills": ["Reflex Velocity", "Hand-Eye Coordination", "Agility"], "apt": {"visual_spatial": 75, "perseverance": 75}},
            {"name": "Football / Soccer", "type": "sports", "benefits": "Team cohesion, cardiovascular endurance, and dynamic spatial game awareness", "skills": ["Teamwork", "Spatial Vision", "Endurance"], "apt": {"teamwork": 80, "visual_spatial": 75}},
            {"name": "Basketball", "type": "sports", "benefits": "High-speed decision making, verticality, hand-eye coordination, and rapid team interplay", "skills": ["Rapid Decision Making", "Hand-Eye Coordination", "Team Play"], "apt": {"teamwork": 80, "thinking_action": 75}}
        ]
        for a in activities:
            cursor.execute("""
            INSERT INTO activity_catalog (
                activity_name, activity_type, benefits, skills_developed_json, aptitude_alignment_json
            ) VALUES (?, ?, ?, ?, ?)
            """, (
                a["name"], a["type"], a["benefits"],
                json.dumps(a["skills"]), json.dumps(a["apt"])
            ))

    conn.commit()
    conn.close()


# Self-execute migration safely on import
create_student_tables()
