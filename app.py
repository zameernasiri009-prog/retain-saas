import os
import re
import streamlit as st

try:
    from gtts import gTTS
    import io

    HAS_GTTS = True
except Exception:
    HAS_GTTS = False

try:
    from google import genai

    HAS_GENAI = True
except Exception:
    HAS_GENAI = False

try:
    from openai import OpenAI

    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False


st.set_page_config(
    page_title="Oxford Beginner English Assessment",
    page_icon="📘",
    layout="wide",
)

# ---------------------------------------------------------------------------
# OXFORD-INSPIRED CLEAN STYLING
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        .oxford-header {
            background: linear-gradient(90deg, #002147 0%, #0F3D75 82%, #C59B27 100%);
            padding: 18px 24px;
            border-radius: 8px;
            color: #FFFFFF;
            margin-bottom: 18px;
            border-bottom: 4px solid #C59B27;
        }
        .oxford-header h1 {
            margin: 0;
            font-size: 24px;
            color: #FFFFFF;
            letter-spacing: 0.5px;
        }
        .oxford-header p {
            margin: 4px 0 0 0;
            font-size: 13px;
            color: #E2E8F0;
        }
        .q-card {
            background-color: #F8FAFC;
            border: 1px solid #CBD5E1;
            border-left: 5px solid #002147;
            border-radius: 6px;
            padding: 14px 18px;
            margin-bottom: 14px;
        }
        .q-title {
            font-weight: 700;
            color: #002147;
            font-size: 15px;
            margin-bottom: 6px;
        }
        .speak-box {
            background-color: #FFFBEB;
            border: 1px solid #FDE68A;
            border-left: 5px solid #C59B27;
            border-radius: 6px;
            padding: 14px 18px;
            margin-bottom: 14px;
        }
        .badge-ok {
            color: #166534;
            background-color: #DCFCE7;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 13px;
        }
        .badge-err {
            color: #991B1B;
            background-color: #FEE2E2;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 13px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# QUESTION BANK (1–10 MCQ, 11–15 SENTENCE REWRITE, SPEAKING ITEMS)
# ---------------------------------------------------------------------------
MCQ_QUESTIONS = [
    {
        "id": 1,
        "prompt": "You ___ in class 2, and ___ she from Turkey?",
        "audio_text": "You are in class two, and is she from Turkey?",
        "options": [
            "A) are / is",
            "B) am / are",
            "C) is / am",
        ],
        "answer": "A) are / is",
        "explanation": "Use 'are' with 'you' and 'is' with singular third-person 'she'.",
    },
    {
        "id": 2,
        "prompt": '"___ is she?" — "She\'s ten." And "___\'s he from?"',
        "audio_text": "How old is she? She's ten. And where's he from?",
        "options": [
            "A) Where / How old",
            "B) How old / Where",
            "C) Who / When",
        ],
        "answer": "B) How old / Where",
        "explanation": "'How old' asks about age ('She's ten'), and 'Where' asks about origin/place.",
    },
    {
        "id": 3,
        "prompt": '"Are they Mexican?" — "No, they ___." And "We ___ from Canada."',
        "audio_text": "Are they Mexican? No, they aren't. And we're from Canada.",
        "options": [
            "A) aren't / 're",
            "B) isn't / is",
            "C) don't / are",
        ],
        "answer": "A) aren't / 're",
        "explanation": "With plural 'they' and 'we' in 'be' sentences, use 'aren't' and "'re" (are).",
    },
    {
        "id": 4,
        "prompt": "Which question is correct?",
        "audio_text": "How old is she?",
        "options": [
            "A) How old's she?",
            "B) Where's he?",
            "C) How old is she?",
        ],
        "answer": "C) How old is she?",
        "explanation": "'How old is she?' is the standard grammatically full question form (note: 'Where's he?' is also natural, while 'How old's she?' is non-standard).",
    },
    {
        "id": 5,
        "prompt": "I have ___ umbrella, ___ key, and two ___.",
        "audio_text": "I have an umbrella, a key, and two keys.",
        "options": [
            "A) an / a / keys",
            "B) a / an / keyes",
            "C) an / an / key",
        ],
        "answer": "A) an / a / keys",
        "explanation": "'An' before vowel sound in 'umbrella', 'a' before consonant sound in 'key', and plural 'keys'.",
    },
    {
        "id": 6,
        "prompt": '"What are ___ right here?" — "They\'re keys." And "Who are ___ girls over there?"',
        "audio_text": "What are these right here? They're keys. And who are those girls over there?",
        "options": [
            "A) that / this",
            "B) these / those",
            "C) this / that",
        ],
        "answer": "B) these / those",
        "explanation": "'These' is plural for things nearby ('right here'), and 'those' is plural for people/things farther away ('over there').",
    },
    {
        "id": 7,
        "prompt": "This is my ___ house, and Senegal is in Africa. ___ flag is red, yellow, and green.",
        "audio_text": "This is my parents' house, and Senegal is in Africa. Its flag is red, yellow, and green.",
        "options": [
            "A) parents' / Its",
            "B) parent's / It's",
            "C) parents's / Their",
        ],
        "answer": "A) parents' / Its",
        "explanation": "Plural possessive 'parents'' puts the apostrophe after s, and possessive 'Its' (no apostrophe) modifies 'flag'.",
    },
    {
        "id": 8,
        "prompt": "Choose the correct sentence.",
        "audio_text": "It's a fast car and my glasses are new.",
        "options": [
            "A) They're olds houses and a car fast.",
            "B) It's a fast car and my glasses are new.",
            "C) An Audi expensive is and she's talls.",
        ],
        "answer": "B) It's a fast car and my glasses are new.",
        "explanation": "English adjectives do not take plural '-s' and come before the noun ('fast car'), while predicate adjectives follow 'be' ('glasses are new').",
    },
    {
        "id": 9,
        "prompt": '"___ you live near here?" — "No, I ___." And "We ___ have meat for dinner."',
        "audio_text": "Do you live near here? No, I don't. And we don't have meat for dinner.",
        "options": [
            "A) Do / don't / don't",
            "B) Does / doesn't / aren't",
            "C) Are / 'm not / not",
        ],
        "answer": "A) Do / don't / don't",
        "explanation": "Present simple with 'you' and 'we' uses 'do' / 'don't' for questions and negatives with main verbs like 'live' and 'have'.",
    },
    {
        "id": 10,
        "prompt": "She ___ TV in the evening, and he ___ eats meat.",
        "audio_text": "She watches TV in the evening, and he never eats meat.",
        "options": [
            "A) watch / doesn't never",
            "B) watches / never",
            "C) watching / no",
        ],
        "answer": "B) watches / never",
        "explanation": "Third-person singular 'she' takes 'watches' (-es after -ch), and 'never' expresses zero frequency before 'eats'.",
    },
]

REWRITE_QUESTIONS = [
    {
        "id": 11,
        "label": "Question 11 (Mixed Words 1)",
        "tokens": "from / where / you / are / ?",
        "audio_text": "Where are you from?",
        "accepted": [
            "where are you from?",
            "where are you from",
        ],
        "canonical": "Where are you from?",
    },
    {
        "id": 12,
        "label": "Question 12 (Mixed Words 2)",
        "tokens": "is / old / a / house / it / .",
        "audio_text": "It is an old house.",
        "accepted": [
            "it is an old house.",
            "it is an old house",
            "it's an old house.",
            "it's an old house",
            "it is a old house.",
            "it is a old house",
            "it's a old house.",
            "it's a old house",
        ],
        "canonical": "It is an old house. (or: It's an old house.)",
    },
    {
        "id": 13,
        "label": "Question 13 (Mixed Words 3)",
        "tokens": "near / live / do / here / you / ?",
        "audio_text": "Do you live near here?",
        "accepted": [
            "do you live near here?",
            "do you live near here",
        ],
        "canonical": "Do you live near here?",
    },
    {
        "id": 14,
        "label": "Question 14 (Mixed Words 4)",
        "tokens": "work / does / where / he / ?",
        "audio_text": "Where does he work?",
        "accepted": [
            "where does he work?",
            "where does he work",
        ],
        "canonical": "Where does he work?",
    },
    {
        "id": 15,
        "label": "Question 15 (Mixed Words 5)",
        "tokens": "breakfast / always / have / I /",
        "audio_text": "I always have breakfast.",
        "accepted": [
            "i always have breakfast.",
            "i always have breakfast",
        ],
        "canonical": "I always have breakfast.",
    },
]

SPEAKING_ITEMS = [
    (1, "What's your name? Where are you from? How do you spell it?"),
    (2, "Are you on holiday? Are you late? Are you from England?"),
    (3, "Who is she? How old is she? Is she from Russia?"),
    (4, "Where's he from? Is he married? Is he from Egypt?"),
    (5, "Who are they? Are they Mexican? Where are they from?"),
    (6, "What's your email? What's your friend's phone number? When's the concert?"),
    (7, "What's the woman's name? What's Main's phone number? What's Iain's email address?"),
    (8, "Who is this? Who are those girls over there? Is that your brother or sister?"),
    (9, "Whose house is this? Whose car is that? Whose name is Molly?"),
    (10, "Do you have a big family? What do you have in your bag? Are those old houses or new houses?"),
    (11, "How much is this book or watch? How much are these key rings? How much are those tickets?"),
    (12, "Can I have an orange juice? Is that a Manchester United shirt? What do you say at the end?"),
    (13, "What time do you get up? Where do you live? What do you do in the evening?"),
    (14, "Where do you work or study? Do you speak English? Do you go to English classes?"),
    (15, "What do you have for breakfast? What don't you have for lunch? What don't they have for dinner?"),
    (16, "Do you live near here? Do you watch a lot of TV? Do you like children?"),
    (17, "What does he do? What does she do? What do you do or study?"),
    (18, "Where does a doctor work? Where does a waiter or waitress work? Where does she work?"),
    (19, "What do you always do in the morning? What do you usually do after work or study? What do you sometimes do in the evening?"),
    (20, "What does he never eat? What does she sometimes do in the evening? What do you usually do at the weekend?"),
]


# ---------------------------------------------------------------------------
# BACKEND CHECKERS & AUDIO HELPERS
# ---------------------------------------------------------------------------
def normalize_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    cleaned = re.sub(r"\s+([?.!,])", r"\1", cleaned)
    return cleaned


def check_rewrite_answer(user_text: str, item: dict) -> tuple[bool, str]:
    norm_user = normalize_sentence(user_text)
    if not norm_user:
        return False, "Please write a complete sentence before checking."

    # Normalize contractions like "it's" vs "it is" for fair beginner grading
    variants = {norm_user}
    variants.add(norm_user.replace("it's", "it is"))
    variants.add(norm_user.replace("it is", "it's"))

    for acc in item["accepted"]:
        acc_clean = normalize_sentence(acc)
        if acc_clean in variants or acc_clean.replace("it's", "it is") in variants:
            return True, f"Correct! Accepted answer: {item['canonical']}"

    return False, f"Not quite. Expected: {item['canonical']}"


@st.cache_data(show_spinner=False)
def generate_tts_mp3(text: str, tld: str = "co.uk") -> bytes | None:
    if not HAS_GTTS:
        return None
    try:
        buf = io.BytesIO()
        tts = gTTS(text=text, lang="en", tld=tld)
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


def render_two_audios(key_prefix: str, text: str):
    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("🔊 Audio 1 — British Pronunciation (UK)")
        audio_uk = generate_tts_mp3(text, tld="co.uk")
        if audio_uk:
            st.audio(audio_uk, format="audio/mp3")
        else:
            st.info(f"UK Readout: *{text}*")
    with col_b:
        st.caption("🔊 Audio 2 — American Pronunciation (US)")
        audio_us = generate_tts_mp3(text, tld="com")
        if audio_us:
            st.audio(audio_us, format="audio/mp3")
        else:
            st.info(f"US Readout: *{text}*")


def count_sentences(text: str) -> int:
    parts = [s.strip() for s in re.split(r"[.!?]+", text.strip()) if s.strip()]
    return len(parts)


def evaluate_speaking_with_ai(
    prompts_text: str,
    spoken_transcript: str,
    provider: str,
    api_key: str,
) -> str:
    sent_count = count_sentences(spoken_transcript)
    if not spoken_transcript.strip():
        return "⚠️ Please enter or speak at least **3 sentences** answering all three questions first."

    system_instruction = (
        "You are an encouraging, strict, and accurate Oxford English beginner speaking examiner. "
        "The student is given three questions and must answer using AT LEAST THREE complete English sentences. "
        "First check if at least 3 sentences are provided. "
        "Then respond clearly using these exact sections:\n"
        "1. **Good**: What the student did well (meaning, vocabulary, or correct grammar).\n"
        "2. **Your Problems**: Exact grammar, word order, article, verb form, or missing-question mistakes, with the corrected sentence.\n"
        "3. **Model 3-Sentence Answer**: Three clean beginner model sentences answering all three prompts."
    )

    user_payload = (
        f"Speaking Prompts (3 questions):\n{prompts_text}\n\n"
        f"Detected Sentence Count: {sent_count}\n"
        f"Student Response:\n{spoken_transcript}"
    )

    if provider == "Gemini" and HAS_GENAI and api_key.strip():
        try:
            client = genai.Client(api_key=api_key.strip())
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"{system_instruction}\n\n{user_payload}",
            )
            return resp.text or "No feedback returned."
        except Exception as e:
            return f"AI error (Gemini): {e}"

    if provider == "OpenAI" and HAS_OPENAI and api_key.strip():
        try:
            client = OpenAI(api_key=api_key.strip())
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_payload},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content or "No feedback returned."
        except Exception as e:
            return f"AI error (OpenAI): {e}"

    # Deterministic fallback when no API key is configured yet
    problems = []
    if sent_count < 3:
        problems.append(
            f"You wrote/spoke only **{sent_count}** sentence(s). You must give **at least 3 sentences** (one for each of the 3 questions)."
        )
    if re.search(r"\bi\b", spoken_transcript) and not re.search(r"\bI\b", spoken_transcript):
        problems.append("Capitalize the pronoun **I** (not lowercase `i`).")
    if not problems:
        problems.append(
            "Connect an AI API key (Gemini or OpenAI) in the sidebar for line-by-line AI grammar & mistake diagnosis."
        )

    return (
        f"**Good**: You submitted {sent_count} sentence(s) for review.\n\n"
        f"**Your Problems**: " + " | ".join(problems)
    )


# ---------------------------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Assessment Controls")
    student_name = st.text_input("Student Name", value="")
    mode = st.radio(
        "Section",
        [
            "Part 1: Questions 1–15 (MCQ & Sentence Rewrite)",
            "Part 2: Speaking Practice (3 Questions Each)",
        ],
    )
    st.markdown("---")
    st.markdown("### 🤖 AI Speaking Examiner")
    ai_provider = st.selectbox("AI Provider", ["Gemini", "OpenAI"])
    env_default = (
        os.getenv("GEMINI_API_KEY", "")
        if ai_provider == "Gemini"
        else os.getenv("OPENAI_API_KEY", "")
    )
    api_key = st.text_input(
        f"{ai_provider} API Key",
        value=env_default,
        type="password",
        help="Required for live AI speaking feedback.",
    )


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="oxford-header">
        <h1>OXFORD BEGINNER ENGLISH ASSESSMENT</h1>
        <p>Interactive Grammar, Sentence Construction &amp; AI-Evaluated Speaking Module</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# PART 1: QUESTIONS 1–10 (MCQ) & 11–15 (SENTENCE REWRITE)
# ---------------------------------------------------------------------------
if mode.startswith("Part 1"):
    st.subheader("Section A: Multiple Choice (Questions 1–10)")
    mcq_score = 0

    for q in MCQ_QUESTIONS:
        st.markdown('<div class="q-card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="q-title">Question {q["id"]}: {q["prompt"]}</div>',
            unsafe_allow_html=True,
        )
        render_two_audios(f"mcq_{q['id']}", q["audio_text"])

        choice = st.radio(
            f"Select your answer for Q{q['id']}:",
            q["options"],
            index=None,
            key=f"mcq_choice_{q['id']}",
        )
        if choice is not None:
            if choice == q["answer"]:
                mcq_score += 1
                st.markdown('<span class="badge-ok">✓ Correct</span>', unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<span class="badge-err">✗ Incorrect — Correct: {q["answer"]}</span>',
                    unsafe_allow_html=True,
                )
            st.caption(q["explanation"])
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Section B: Mixed Words — Write the Full Correct Sentence (Questions 11–15)")
    rewrite_score = 0

    for item in REWRITE_QUESTIONS:
        st.markdown('<div class="q-card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="q-title">{item["label"]}: <code>{item["tokens"]}</code></div>',
            unsafe_allow_html=True,
        )
        render_two_audios(f"rew_{item['id']}", item["audio_text"])

        user_ans = st.text_input(
            f"Write the full correct sentence for Q{item['id']}:",
            key=f"rew_input_{item['id']}",
        )
        if user_ans.strip():
            is_ok, msg = check_rewrite_answer(user_ans, item)
            if is_ok:
                rewrite_score += 1
                st.markdown(f'<span class="badge-ok">✓ {msg}</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="badge-err">✗ {msg}</span>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    total_part1 = mcq_score + rewrite_score
    st.success(
        f"**{student_name or 'Student'} — Part 1 Score:** **{total_part1} / 15** "
        f"(Multiple Choice: {mcq_score}/10 • Sentence Rewrite: {rewrite_score}/5)"
    )


# ---------------------------------------------------------------------------
# PART 2: SPEAKING ITEMS (3 QUESTIONS PER ITEM + AI EVALUATION)
# ---------------------------------------------------------------------------
else:
    st.subheader("Speaking Assessment — Answer All 3 Questions (At Least 3 Sentences)")
    st.caption(
        "Listen to both pronunciations, record/upload or type your response with at least 3 complete sentences, "
        "and run AI evaluation for strengths and mistake analysis."
    )

    selected_idx = st.selectbox(
        "Choose Speaking Item (1–20)",
        range(len(SPEAKING_ITEMS)),
        format_func=lambda i: f"Speaking Item {SPEAKING_ITEMS[i][0]}: {SPEAKING_ITEMS[i][1]}",
    )
    item_num, prompts_str = SPEAKING_ITEMS[selected_idx]

    st.markdown('<div class="speak-box">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="q-title">Speaking Prompt #{item_num} (3 Questions)</div>',
        unsafe_allow_html=True,
    )
    st.write(f"**Questions:** {prompts_str}")
    st.markdown("</div>", unsafe_allow_html=True)

    render_two_audios(f"speak_{item_num}", prompts_str)

    # Optional microphone input if supported by Streamlit version & browser
    if hasattr(st, "audio_input"):
        st.audio_input(
            f"🎙️ Record your spoken answer for Item #{item_num} (optional)",
            key=f"mic_{item_num}",
        )

    transcript = st.text_area(
        "Write / paste your spoken sentences here (at least 3 sentences, one sentence per line or separated by periods):",
        height=130,
        placeholder=(
            "Example:\n"
            "My name is Ali.\n"
            "I am from Tajikistan.\n"
            "I spell it A-L-I."
        ),
        key=f"speak_text_{item_num}",
    )

    lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
    if lines:
        st.markdown("**Sentence-by-Sentence Preview:**")
        for idx_line, s_line in enumerate(lines, start=1):
            st.write(f"{idx_line}. {s_line}")

    if st.button("🤖 Evaluate Speaking with AI", type="primary", key=f"eval_btn_{item_num}"):
        with st.spinner("Analyzing your sentences and checking mistakes..."):
            feedback = evaluate_speaking_with_ai(
                prompts_text=prompts_str,
                spoken_transcript=transcript,
                provider=ai_provider,
                api_key=api_key,
            )
        st.markdown("### AI Speaking Evaluation")
        st.markdown(feedback)
