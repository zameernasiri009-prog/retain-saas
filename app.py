import html
import json
import re
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="English Learning Interactive Grammar Quiz",
    page_icon="🎓",
    layout="centered",
)

st.markdown(
    """
    <style>
        .main-banner {
            background: linear-gradient(135deg, #0B1120 0%, #1E3A8A 100%);
            padding: 20px 24px;
            border-radius: 12px;
            color: #FFFFFF !important;
            margin-bottom: 18px;
            border-bottom: 4px solid #F59E0B;
        }
        .main-banner h1, .main-banner p {
            margin: 0;
            color: #FFFFFF !important;
        }
        .main-banner h1 {
            font-size: 22px;
            font-weight: 700;
        }
        .main-banner p {
            margin-top: 6px;
            font-size: 13px;
            color: #F8FAFC !important;
        }
        .q-badge {
            display: inline-block;
            background: #1D4ED8;
            color: #FFFFFF !important;
            font-weight: 700;
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 999px;
            margin-bottom: 8px;
        }
        .q-prompt {
            font-size: 18px;
            font-weight: 600;
            margin: 6px 0 12px 0;
            line-height: 1.45;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

MCQ_QUESTIONS = [
    {
        "num": 1,
        "type": "Multiple Choice",
        "prompt": "You ___ in class 2, and ___ she from Turkey?",
        "pronounce": "You are in class two, and is she from Turkey?",
        "options": ["A) are / is", "B) am / are", "C) is / am"],
        "answer": "A) are / is",
        "rule": "Use 'are' with 'you' and 'is' with third-person singular 'she'.",
    },
    {
        "num": 2,
        "type": "Multiple Choice",
        "prompt": '"___ is she?" — "She\'s ten." And "___\'s he from?"',
        "pronounce": "How old is she? She is ten. And where is he from?",
        "options": ["A) Where / How old", "B) How old / Where", "C) Who / When"],
        "answer": "B) How old / Where",
        "rule": "'How old' asks about age, while 'Where' asks about origin or place.",
    },
    {
        "num": 3,
        "type": "Multiple Choice",
        "prompt": '"Are they Mexican?" — "No, they ___." And "We ___ from Canada."',
        "pronounce": "Are they Mexican? No, they are not. And we are from Canada.",
        "options": ["A) aren't / 're", "B) isn't / is", "C) don't / are"],
        "answer": "A) aren't / 're",
        "rule": "Plural subjects 'they' and 'we' use 'aren't' and \"'re\" (are) with the verb 'be'.",
    },
    {
        "num": 4,
        "type": "Multiple Choice",
        "prompt": "Which question is grammatically complete and correct?",
        "pronounce": "How old is she?",
        "options": ["A) How old's she?", "B) Where's he?", "C) How old is she?"],
        "answer": "C) How old is she?",
        "rule": "'How old is she?' is the standard full form.",
    },
    {
        "num": 5,
        "type": "Multiple Choice",
        "prompt": "I have ___ umbrella, ___ key, and two ___.",
        "pronounce": "I have an umbrella, a key, and two keys.",
        "options": ["A) an / a / keys", "B) a / an / keyes", "C) an / an / key"],
        "answer": "A) an / a / keys",
        "rule": "Use 'an' before a vowel sound ('umbrella'), 'a' before a consonant sound ('key'), and plural 'keys'.",
    },
    {
        "num": 6,
        "type": "Multiple Choice",
        "prompt": '"What are ___ right here?" — "They\'re keys." And "Who are ___ girls over there?"',
        "pronounce": "What are these right here? They are keys. And who are those girls over there?",
        "options": ["A) that / this", "B) these / those", "C) this / that"],
        "answer": "B) these / those",
        "rule": "'These' refers to plural things close by, and 'those' refers to plural people or things farther away.",
    },
    {
        "num": 7,
        "type": "Multiple Choice",
        "prompt": "This is my ___ house, and Senegal is in Africa. ___ flag is red, yellow, and green.",
        "pronounce": "This is my parents' house, and Senegal is in Africa. Its flag is red, yellow, and green.",
        "options": ["A) parents' / Its", "B) parent's / It's", "C) parents's / Their"],
        "answer": "A) parents' / Its",
        "rule": "Plural possessive ends with an apostrophe after s ('parents''), and possessive 'Its' has no apostrophe.",
    },
    {
        "num": 8,
        "type": "Multiple Choice",
        "prompt": "Choose the correct sentence.",
        "pronounce": "It is a fast car and my glasses are new.",
        "options": [
            "A) They're olds houses and a car fast.",
            "B) It's a fast car and my glasses are new.",
            "C) An Audi expensive is and she's talls.",
        ],
        "answer": "B) It's a fast car and my glasses are new.",
        "rule": "English adjectives never take plural '-s' and go before nouns or after 'be'.",
    },
    {
        "num": 9,
        "type": "Multiple Choice",
        "prompt": '"___ you live near here?" — "No, I ___." And "We ___ have meat for dinner."',
        "pronounce": "Do you live near here? No, I do not. And we do not have meat for dinner.",
        "options": ["A) Do / don't / don't", "B) Does / doesn't / aren't", "C) Are / 'm not / not"],
        "answer": "A) Do / don't / don't",
        "rule": "Use 'Do' and 'don't' with 'you' and 'we' in present simple questions and negatives.",
    },
    {
        "num": 10,
        "type": "Multiple Choice",
        "prompt": "She ___ TV in the evening, and he ___ eats meat.",
        "pronounce": "She watches TV in the evening, and he never eats meat.",
        "options": ["A) watch / doesn't never", "B) watches / never", "C) watching / no"],
        "answer": "B) watches / never",
        "rule": "Add '-es' for third-person singular 'watches', and use 'never' without double negatives.",
    },
]

REWRITE_QUESTIONS = [
    {
        "num": 11,
        "type": "Sentence Pattern (Mixed Words)",
        "mixed": "from / where / you / are / ?",
        "pronounce": "Where are you from?",
        "accepted": ["where are you from?", "where are you from"],
        "correct": "Where are you from?",
        "rule": "Question word ('Where') + verb 'be' ('are') + subject ('you') + preposition ('from') + question mark.",
    },
    {
        "num": 12,
        "type": "Sentence Pattern (Mixed Words)",
        "mixed": "is / old / a / house / it / .",
        "pronounce": "It is an old house.",
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
        "correct": "It is an old house.",
        "rule": "Subject ('It') + verb ('is') + article ('an' before vowel sound 'old') + adjective + noun ('house').",
    },
    {
        "num": 13,
        "type": "Sentence Pattern (Mixed Words)",
        "mixed": "near / live / do / here / you / ?",
        "pronounce": "Do you live near here?",
        "accepted": ["do you live near here?", "do you live near here"],
        "correct": "Do you live near here?",
        "rule": "Auxiliary 'Do' + subject ('you') + base verb ('live') + place phrase ('near here').",
    },
    {
        "num": 14,
        "type": "Sentence Pattern (Mixed Words)",
        "mixed": "work / does / where / he / ?",
        "pronounce": "Where does he work?",
        "accepted": ["where does he work?", "where does he work"],
        "correct": "Where does he work?",
        "rule": "Question word ('Where') + 'does' + singular subject ('he') + base verb ('work').",
    },
    {
        "num": 15,
        "type": "Sentence Pattern (Mixed Words)",
        "mixed": "breakfast / always / have / I",
        "pronounce": "I always have breakfast.",
        "accepted": ["i always have breakfast.", "i always have breakfast"],
        "correct": "I always have breakfast.",
        "rule": "Subject ('I') + frequency adverb ('always') + main verb ('have') + object ('breakfast').",
    },
]

ALL_15_QUESTIONS = MCQ_QUESTIONS + REWRITE_QUESTIONS


def render_html_box(html_str: str, height: int | str = "content", alt: str = "Embedded widget"):
    if hasattr(st, "iframe"):
        st.iframe(html_str, height=height, alt=alt)
    else:
        fixed_h = 140 if height == "content" else int(height)
        components.html(html_str, height=fixed_h)


def listen_button(text: str, key_id: str):
    lines = text if isinstance(text, list) else [text]
    payload = json.dumps(lines)
    safe_id = re.sub(r"[^A-Za-z0-9_]", "_", key_id)
    render_html_box(
        f"""
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:sans-serif;">
            <button type="button" id="listen_btn_{safe_id}" onclick="readAloud_{safe_id}()"
                style="background:#2563EB;color:#FFFFFF;border:none;padding:10px 18px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;">
                🔊 Listen
            </button>
            <span id="listen_status_{safe_id}" style="color:#E2E8F0;font-size:13px;"></span>
        </div>
        <script>
        function readAloud_{safe_id}() {{
            const items = {payload};
            const statusEl = document.getElementById("listen_status_{safe_id}");
            if (!("speechSynthesis" in window)) {{
                statusEl.textContent = items.join(" ");
                return;
            }}
            window.speechSynthesis.cancel();
            window.speechSynthesis.resume();
            const voices = window.speechSynthesis.getVoices();
            const enVoice = voices.find(v => v.lang && v.lang.toLowerCase().startsWith("en")) || null;
            statusEl.textContent = "Reading...";
            items.forEach((line, idx) => {{
                const u = new SpeechSynthesisUtterance(line);
                u.lang = "en-US";
                u.rate = 0.95;
                if (enVoice) u.voice = enVoice;
                if (idx === items.length - 1) {{
                    u.onend = () => {{ statusEl.textContent = ""; }};
                    u.onerror = () => {{ statusEl.textContent = ""; }};
                }}
                window.speechSynthesis.speak(u);
            }});
        }}
        if ("speechSynthesis" in window && window.speechSynthesis.onvoiceschanged !== undefined) {{
            window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
        }}
        </script>
        """,
        height=56,
        alt="Listen button",
    )


def normalize_str(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = re.sub(r"\s+([?.!,])", r"\1", s)
    return s


def grammar_ai_tutor_feedback(q: dict, user_answer: str, is_correct: bool) -> str:
    if is_correct:
        return (
            f"**Tutor Feedback — Great job!**\n"
            f"- **Why it works:** {q['rule']}\n"
            f"- **Next step:** Tap **🔊 Listen** and say the full sentence out loud."
        )
    expected = q.get("answer") or q.get("correct", "")
    tips = ["**Tutor Feedback — Let's fix this together:**"]
    if not user_answer.strip():
        tips.append("- **Problem:** No answer was entered yet.")
    else:
        tips.append(f"- **Your answer:** `{user_answer.strip()}`")
        if re.search(r"\bi\b", user_answer):
            tips.append("- **Capitalization:** Always write the subject pronoun **I** as a capital letter.")
        if q.get("num", 0) >= 11 and not user_answer.strip().endswith((".", "?")):
            tips.append("- **Punctuation:** End your sentence with a period (`.`) or question mark (`?`).")
    tips.append(f"- **Correct target:** **{expected}**")
    tips.append(f"- **Grammar rule:** {q['rule']}")
    return "\n".join(tips)


if "q_index" not in st.session_state:
    st.session_state.q_index = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "scores" not in st.session_state:
    st.session_state.scores = {}

st.markdown(
    """
    <div class="main-banner">
        <h1>🎓 ENGLISH LEARNING INTERACTIVE QUIZ</h1>
        <p>15 Grammar Items (10 Multiple Choice + 5 Sentence Patterns) with 🔊 Listen</p>
    </div>
    """,
    unsafe_allow_html=True,
)

idx = st.session_state.q_index
q = ALL_15_QUESTIONS[idx]
q_num = q["num"]
st.progress((idx + 1) / len(ALL_15_QUESTIONS), text=f"Question {q_num} of {len(ALL_15_QUESTIONS)}")
st.markdown(f'<div class="q-badge">{html.escape(q["type"])} • Question {q_num}</div>', unsafe_allow_html=True)

if q_num <= 10:
    st.markdown(f'<div class="q-prompt">{html.escape(q["prompt"])}</div>', unsafe_allow_html=True)
    listen_button(q["pronounce"], key_id=f"gram_{q_num}")
    selected = st.radio("Choose one option:", q["options"], index=None, key=f"radio_q_{q_num}")
    if st.button("Check Answer", type="primary", key=f"chk_mcq_{q_num}"):
        if selected is None:
            st.session_state.answers[q_num] = ("", False)
            st.session_state.scores[q_num] = False
        else:
            ok = selected == q["answer"]
            st.session_state.answers[q_num] = (selected, ok)
            st.session_state.scores[q_num] = ok
else:
    st.markdown('<div class="q-prompt">Arrange the mixed words into a full correct sentence:</div>', unsafe_allow_html=True)
    st.code(q["mixed"], language="text")
    listen_button(q["pronounce"], key_id=f"gram_{q_num}")
    typed = st.text_input("Write your full sentence here:", key=f"rewrite_q_{q_num}")
    if st.button("Check Sentence", type="primary", key=f"chk_rew_{q_num}"):
        norm_u = normalize_str(typed)
        variants = {norm_u, norm_u.replace("it's", "it is"), norm_u.replace("it is", "it's")}
        ok = False
        for acc in q["accepted"]:
            acc_n = normalize_str(acc)
            if acc_n in variants or acc_n.replace("it's", "it is") in variants:
                ok = True
                break
        st.session_state.answers[q_num] = (typed, ok)
        st.session_state.scores[q_num] = ok

if q_num in st.session_state.answers:
    ans_val, was_ok = st.session_state.answers[q_num]
    if was_ok:
        st.success("✅ Correct!")
    else:
        st.error("❌ Not quite right — check the Tutor feedback below.")
    st.markdown(grammar_ai_tutor_feedback(q, ans_val, was_ok))

col_prev, col_next, col_score = st.columns([1, 1, 2])
with col_prev:
    if st.button("⬅️ Previous", disabled=(idx == 0)):
        st.session_state.q_index = max(0, idx - 1)
        st.rerun()
with col_next:
    if st.button("Next ➡️", disabled=(idx == len(ALL_15_QUESTIONS) - 1)):
        st.session_state.q_index = min(len(ALL_15_QUESTIONS) - 1, idx + 1)
        st.rerun()
with col_score:
    total_right = sum(1 for v in st.session_state.scores.values() if v)
    st.info(f"**Score:** {total_right} / {len(ALL_15_QUESTIONS)} answered correctly")
