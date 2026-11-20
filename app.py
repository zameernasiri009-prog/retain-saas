import json
import re
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="English Learning Interactive Quiz",
    page_icon="🎓",
    layout="centered",
)

# ---------------------------------------------------------------------------
# CLEAN MODERN STYLING (HIGH-CONTRAST WHITE TEXT ON DARK CARDS)
# ---------------------------------------------------------------------------
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
        .step-card {
            background: #111827;
            border: 1px solid #334155;
            border-left: 5px solid #38BDF8;
            border-radius: 10px;
            padding: 18px 20px;
            margin: 12px 0 16px 0;
            color: #FFFFFF !important;
        }
        .step-card * {
            color: #FFFFFF !important;
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
            color: #FFFFFF !important;
            margin: 6px 0 12px 0;
            line-height: 1.45;
        }
        .tutor-box {
            background: #0F172A;
            border: 1px solid #2DD4BF;
            border-left: 5px solid #14B8A6;
            border-radius: 10px;
            padding: 14px 18px;
            margin-top: 12px;
            color: #FFFFFF !important;
        }
        .tutor-box *, .tutor-box p, .tutor-box li, .tutor-box strong, .tutor-box code {
            color: #FFFFFF !important;
        }
        .speak-card {
            background: #1E1B4B;
            border: 1px solid #F59E0B;
            border-left: 5px solid #F59E0B;
            border-radius: 10px;
            padding: 16px 20px;
            margin: 12px 0;
            color: #FFFFFF !important;
        }
        .speak-card *, .speak-card p, .speak-card strong {
            color: #FFFFFF !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# QUIZ DATA: 10 MULTIPLE CHOICE + 5 SENTENCE REWRITE + 15 SPEAKING ITEMS
# ---------------------------------------------------------------------------
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
        "pronounce": "How old is she? She's ten. And where's he from?",
        "options": ["A) Where / How old", "B) How old / Where", "C) Who / When"],
        "answer": "B) How old / Where",
        "rule": "'How old' asks about age, while 'Where' asks about origin or place.",
    },
    {
        "num": 3,
        "type": "Multiple Choice",
        "prompt": '"Are they Mexican?" — "No, they ___." And "We ___ from Canada."',
        "pronounce": "Are they Mexican? No, they aren't. And we're from Canada.",
        "options": ["A) aren't / 're", "B) isn't / is", "C) don't / are"],
        "answer": "A) aren't / 're",
        "rule": "Plural subjects 'they' and 'we' use 'aren't' and 're (are) with the verb 'be'.",
    },
    {
        "num": 4,
        "type": "Multiple Choice",
        "prompt": "Which question is grammatically complete and correct?",
        "pronounce": "How old is she?",
        "options": ["A) How old's she?", "B) Where's he?", "C) How old is she?"],
        "answer": "C) How old is she?",
        "rule": "'How old is she?' is the standard full form (never contract 'is' onto 'old' as *old's).",
    },
    {
        "num": 5,
        "type": "Multiple Choice",
        "prompt": "I have ___ umbrella, ___ key, and two ___.",
        "pronounce": "I have an umbrella, a key, and two keys.",
        "options": ["A) an / a / keys", "B) a / an / keyes", "C) an / an / key"],
        "answer": "A) an / a / keys",
        "rule": "Use 'an' before a vowel sound ('umbrella'), 'a' before a consonant sound ('key'), and regular plural 'keys'.",
    },
    {
        "num": 6,
        "type": "Multiple Choice",
        "prompt": '"What are ___ right here?" — "They\'re keys." And "Who are ___ girls over there?"',
        "pronounce": "What are these right here? They're keys. And who are those girls over there?",
        "options": ["A) that / this", "B) these / those", "C) this / that"],
        "answer": "B) these / those",
        "rule": "'These' refers to plural things close by, and 'those' refers to plural people/things farther away.",
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
        "pronounce": "It's a fast car and my glasses are new.",
        "options": [
            "A) They're olds houses and a car fast.",
            "B) It's a fast car and my glasses are new.",
            "C) An Audi expensive is and she's talls.",
        ],
        "answer": "B) It's a fast car and my glasses are new.",
        "rule": "English adjectives never take plural '-s' and go before nouns ('fast car') or after 'be' ('glasses are new').",
    },
    {
        "num": 9,
        "type": "Multiple Choice",
        "prompt": '"___ you live near here?" — "No, I ___." And "We ___ have meat for dinner."',
        "pronounce": "Do you live near here? No, I don't. And we don't have meat for dinner.",
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
        "rule": "Add '-es' for third-person singular 'watches', and use 'never' (not double negatives).",
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
        "mixed": "breakfast / always / have / I /",
        "pronounce": "I always have breakfast.",
        "accepted": ["i always have breakfast.", "i always have breakfast"],
        "correct": "I always have breakfast.",
        "rule": "Subject ('I') + frequency adverb ('always') + main verb ('have') + object ('breakfast').",
    },
]

ALL_15_QUESTIONS = MCQ_QUESTIONS + REWRITE_QUESTIONS

SPEAKING_15_ITEMS = [
    (1, ["What's your name?", "Where are you from?", "How do you spell it?"]),
    (2, ["Are you on holiday?", "Are you late?", "Are you from England?"]),
    (3, ["Who is she?", "How old is she?", "Is she from Russia?"]),
    (4, ["Where's he from?", "Is he married?", "Is he from Egypt?"]),
    (5, ["Who are they?", "Are they Mexican?", "Where are they from?"]),
    (6, ["What's your email?", "What's your friend's phone number?", "When's the concert?"]),
    (7, ["What's the woman's name?", "What's Main's phone number?", "What's Iain's email address?"]),
    (8, ["Who is this?", "Who are those girls over there?", "Is that your brother or sister?"]),
    (9, ["Whose house is this?", "Whose car is that?", "Whose name is Molly?"]),
    (10, ["Do you have a big family?", "What do you have in your bag?", "Are those old houses or new houses?"]),
    (11, ["How much is this book or watch?", "How much are these key rings?", "How much are those tickets?"]),
    (12, ["Can I have an orange juice?", "Is that a Manchester United shirt?", "What do you say at the end?"]),
    (13, ["What time do you get up?", "Where do you live?", "What do you do in the evening?"]),
    (14, ["Where do you work or study?", "Do you speak English?", "Do you go to English classes?"]),
    (15, ["What do you have for breakfast?", "What don't you have for lunch?", "What don't they have for dinner?"]),
]


# ---------------------------------------------------------------------------
# ONE-TAP PRONUNCIATION BUTTON (NO PLAYER BAR / TIMELINE)
# ---------------------------------------------------------------------------
def pronounce_button(text: str, label: str = "🔊 Pronunciation", key_id: str = "p"):
    safe_text = json.dumps(text)
    html = f"""
    <div style="margin: 6px 0 10px 0;">
        <button id="btn_{key_id}" onclick="speakNow_{key_id}()"
            style="
                background: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 9px 16px;
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 6px;
            ">
            {label}
        </button>
        <span id="status_{key_id}" style="margin-left: 10px; font-size: 13px; color: #FFFFFF; font-weight: 500;"></span>
    </div>
    <script>
        function speakNow_{key_id}() {{
            const phrase = {safe_text};
            const stEl = document.getElementById("status_{key_id}");
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel();
                const utter = new SpeechSynthesisUtterance(phrase);
                utter.lang = "en-US";
                utter.rate = 0.95;
                stEl.innerText = "Speaking...";
                utter.onend = () => {{ stEl.innerText = ""; }};
                utter.onerror = () => {{ stEl.innerText = phrase; }};
                window.speechSynthesis.speak(utter);
            }} else {{
                stEl.innerText = phrase;
            }}
        }}
    </script>
    """
    components.html(html, height=48)


# ---------------------------------------------------------------------------
# ONE-TAP SPEAKER / VOICE INPUT WIDGET FOR SPEAKING PART
# ---------------------------------------------------------------------------
def voice_speaker_widget(item_idx: int):
    html = f"""
    <div style="
        background: #111827;
        border: 1px solid #475569;
        border-radius: 10px;
        padding: 12px 14px;
        margin: 8px 0 10px 0;
        color: #FFFFFF;
    ">
        <button type="button" onclick="startMic_{item_idx}()"
            style="
                background: #DC2626;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
            ">
            🎙️ Press &amp; Speak
        </button>
        <span id="mic_state_{item_idx}" style="margin-left: 10px; font-size: 13px; color: #FFFFFF;">
            Tap to speak your 3 sentences
        </span>
        <div id="live_speech_{item_idx}" style="
            margin-top: 8px;
            font-size: 14px;
            font-weight: 600;
            color: #FFFFFF;
        "></div>
    </div>
    <script>
        function startMic_{item_idx}() {{
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            const stateEl = document.getElementById("mic_state_{item_idx}");
            const outEl = document.getElementById("live_speech_{item_idx}");
            if (!SpeechRec) {{
                stateEl.innerText = "Voice mic not supported in this browser—use the text box below.";
                return;
            }}
            const rec = new SpeechRec();
            rec.lang = "en-US";
            rec.interimResults = true;
            rec.continuous = false;
            stateEl.innerText = "Listening... speak clearly now.";
            rec.onresult = (event) => {{
                let transcript = "";
                for (let i = 0; i < event.results.length; i++) {{
                    transcript += event.results[i][0].transcript + " ";
                }}
                outEl.innerText = "Heard: " + transcript.trim();
            }};
            rec.onerror = (e) => {{
                stateEl.innerText = "Mic notice: " + e.error + " (you can also type below).";
            }};
            rec.onend = () => {{
                stateEl.innerText = "Done listening. Copy/paste or edit below if needed, then tap Get AI Tutor Feedback.";
            }};
            rec.start();
        }}
    </script>
    """
    components.html(html, height=105)


# ---------------------------------------------------------------------------
# GUARANTEED INSTANT AI TUTOR FEEDBACK (NO SETUP REQUIRED)
# ---------------------------------------------------------------------------
def normalize_str(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = re.sub(r"\s+([?.!,])", r"\1", s)
    return s


def grammar_ai_tutor_feedback(q: dict, user_answer: str, is_correct: bool) -> str:
    if is_correct:
        return (
            f"**AI Tutor Feedback — Great job!**\n"
            f"- **Why it works:** {q['rule']}\n"
            f"- **Next step:** Say the full sentence aloud using the **Pronunciation** button to lock in the rhythm."
        )

    expected = q.get("answer") or q.get("correct", "")
    tips = ["**AI Tutor Feedback — Let's fix this together:**"]
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


def speaking_ai_tutor_feedback(questions_3: list[str], response_text: str) -> str:
    clean = response_text.strip()
    if not clean:
        return (
            "**AI Tutor Feedback:**\n"
            "- **Problem:** No spoken sentences detected yet.\n"
            "- **Action:** Press **Press & Speak** (or type 3 sentences below) to answer all 3 questions, one sentence per question."
        )

    sentences = [s.strip() for s in re.split(r"[.!?]+|\n+", clean) if s.strip()]
    count = len(sentences)

    good_points = []
    problems = []

    if count >= 3:
        good_points.append(f"You gave **{count} sentences**, meeting the 3-sentence requirement.")
    else:
        problems.append(
            f"You only gave **{count}** sentence(s). Answer all **3 questions** with **3 separate sentences** (1 sentence for each question)."
        )

    if re.search(r"\bi\b", clean):
        problems.append("Use capital **I** instead of lowercase `i`.")
    else:
        good_points.append("Clean pronoun capitalization.")

    if len(clean.split()) >= 6:
        good_points.append("Good attempt at full-sentence communication.")
    else:
        problems.append("Your response is very short—try answering each of the 3 questions in a full sentence.")

    if not good_points:
        good_points.append("You made an effort to answer the prompt.")
    if not problems:
        problems.append("No major beginner grammar issues spotted—focus on smooth pronunciation and natural intonation.")

    return (
        "**AI Tutor Evaluation:**\n"
        "- **Good:** " + " ".join(good_points) + "\n"
        "- **Your Problems:** " + " ".join(problems) + "\n"
        f"- **Prompts to Cover:** {questions_3[0]} | {questions_3[1]} | {questions_3[2]}"
    )


# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------
if "q_index" not in st.session_state:
    st.session_state.q_index = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "scores" not in st.session_state:
    st.session_state.scores = {}
if "speak_index" not in st.session_state:
    st.session_state.speak_index = 0
if "speak_feedback" not in st.session_state:
    st.session_state.speak_feedback = {}


# ---------------------------------------------------------------------------
# HEADER & MODE SWITCHER
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="main-banner">
        <h1>🎓 ENGLISH LEARNING INTERACTIVE QUIZ</h1>
        <p>Step-by-Step Grammar (10 MCQ + 5 Sentence Patterns) &amp; 15-Item Speaking Coach</p>
    </div>
    """,
    unsafe_allow_html=True,
)

section = st.radio(
    "Choose Quiz Stage:",
    ["1. Grammar Quiz (Questions 1–15, One by One)", "2. Speaking Practice (15 Items × 3 Questions)"],
    horizontal=True,
)


# ---------------------------------------------------------------------------
# PART 1: ONE-BY-ONE INTERACTIVE QUIZ (1–10 MCQ, 11–15 SENTENCE REWRITE)
# ---------------------------------------------------------------------------
if section.startswith("1."):
    idx = st.session_state.q_index
    q = ALL_15_QUESTIONS[idx]
    q_num = q["num"]

    st.progress((idx + 1) / len(ALL_15_QUESTIONS), text=f"Question {q_num} of {len(ALL_15_QUESTIONS)}")

    st.markdown('<div class="step-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="q-badge">{q["type"]} • Question {q_num}</div>', unsafe_allow_html=True)

    if q_num <= 10:
        st.markdown(f'<div class="q-prompt">{q["prompt"]}</div>', unsafe_allow_html=True)
        pronounce_button(q["pronounce"], label="🔊 Pronunciation", key_id=f"q_{q_num}")
        selected = st.radio(
            "Choose one option:",
            q["options"],
            index=None,
            key=f"radio_q_{q_num}",
        )
        if st.button("Check Answer", type="primary", key=f"chk_mcq_{q_num}"):
            if selected is None:
                st.session_state.answers[q_num] = ("", False)
                st.session_state.scores[q_num] = False
            else:
                ok = selected == q["answer"]
                st.session_state.answers[q_num] = (selected, ok)
                st.session_state.scores[q_num] = ok
    else:
        st.markdown(
            f'<div class="q-prompt">Arrange the mixed words into a full correct sentence:<br/>'
            f'<code>{q["mixed"]}</code></div>',
            unsafe_allow_html=True,
        )
        pronounce_button(q["pronounce"], label="🔊 Pronunciation", key_id=f"q_{q_num}")
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

    st.markdown("</div>", unsafe_allow_html=True)

    if q_num in st.session_state.answers:
        ans_val, was_ok = st.session_state.answers[q_num]
        if was_ok:
            st.success("✅ Correct!")
        else:
            st.error("❌ Not quite right — check the AI Tutor feedback below.")
        st.markdown('<div class="tutor-box">', unsafe_allow_html=True)
        st.markdown(grammar_ai_tutor_feedback(q, ans_val, was_ok))
        st.markdown("</div>", unsafe_allow_html=True)

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


# ---------------------------------------------------------------------------
# PART 2: SPEAKING PRACTICE (15 ITEMS × 3 QUESTIONS)
# ---------------------------------------------------------------------------
else:
    s_idx = st.session_state.speak_index
    item_no, three_qs = SPEAKING_15_ITEMS[s_idx]

    st.progress((s_idx + 1) / len(SPEAKING_15_ITEMS), text=f"Speaking Set {item_no} of {len(SPEAKING_15_ITEMS)}")

    st.markdown('<div class="speak-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="q-badge">Speaking Set {item_no} • 3 Questions (Answer with 3 Sentences)</div>', unsafe_allow_html=True)
    st.markdown(
        f"1. **{three_qs[0]}**<br/>"
        f"2. **{three_qs[1]}**<br/>"
        f"3. **{three_qs[2]}**",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    pronounce_button(" ".join(three_qs), label="🔊 Listen Questions", key_id=f"sp_{item_no}")
    voice_speaker_widget(item_no)

    spoken_or_typed = st.text_area(
        "Your 3 spoken/written sentences (1 sentence for each of the 3 questions):",
        height=110,
        placeholder="Sentence 1...\nSentence 2...\nSentence 3...",
        key=f"sp_input_{item_no}",
    )

    if st.button("🤖 Get AI Tutor Feedback", type="primary", key=f"sp_eval_{item_no}"):
        st.session_state.speak_feedback[item_no] = speaking_ai_tutor_feedback(three_qs, spoken_or_typed)

    if item_no in st.session_state.speak_feedback:
        st.markdown('<div class="tutor-box">', unsafe_allow_html=True)
        st.markdown(st.session_state.speak_feedback[item_no])
        st.markdown("</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Previous Speaking Set", disabled=(s_idx == 0)):
            st.session_state.speak_index = max(0, s_idx - 1)
            st.rerun()
    with c2:
        if st.button("Next Speaking Set ➡️", disabled=(s_idx == len(SPEAKING_15_ITEMS) - 1)):
            st.session_state.speak_index = min(len(SPEAKING_15_ITEMS) - 1, s_idx + 1)
            st.rerun()
