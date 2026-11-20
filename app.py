import html
import json
import os
import re
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="English Learning Interactive Quiz & Speaking Grader",
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
        "rule": "Plural subjects 'they' and 'we' use 'aren't' and "'re" (are) with the verb 'be'.",
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


def get_api_key() -> str:
    try:
        if "OPENAI_API_KEY" in st.secrets and st.secrets["OPENAI_API_KEY"]:
            return str(st.secrets["OPENAI_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY", "").strip()


def speaker(text: str, label: str = "🔊 Speak", key_id: str = "spk"):
    payload = json.dumps(text)
    safe_id = re.sub(r"[^A-Za-z0-9_]", "_", key_id)
    components.html(
        f"""
        <button type="button" id="btn_{safe_id}" onclick="say_{safe_id}()"
            style="background:#2563EB;color:#FFFFFF;border:none;padding:9px 16px;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;">
            {html.escape(label)}
        </button>
        <span id="spk_out_{safe_id}" style="margin-left:10px;font-size:13px;color:#FFFFFF;font-weight:500;"></span>
        <script>
        function say_{safe_id}() {{
            const t = {payload};
            const out = document.getElementById("spk_out_{safe_id}");
            if ("speechSynthesis" in window) {{
                window.speechSynthesis.cancel();
                const u = new SpeechSynthesisUtterance(t);
                u.lang = "en-US";
                u.rate = 0.95;
                out.textContent = "Speaking...";
                u.onend = () => {{ out.textContent = ""; }};
                u.onerror = () => {{ out.textContent = t; }};
                window.speechSynthesis.speak(u);
            }} else {{
                out.textContent = t;
            }}
        }}
        </script>
        """,
        height=48,
    )


def local_grammar_fallback(spoken_text: str, has_audio: bool, audio_bytes_len: int) -> dict:
    clean = re.sub(r"\s+", " ", (spoken_text or "").strip())
    lower = clean.lower()
    words = re.findall(r"[A-Za-z']+", clean)

    punct_sentences = [s.strip() for s in re.split(r"[.!?]+", clean) if len(re.findall(r"[A-Za-z']+", s)) >= 2]
    clause_parts = [c.strip() for c in re.split(r"\b(?:and|but|because|so)\b", clean, flags=re.I) if len(re.findall(r"[A-Za-z']+", c)) >= 2]
    sentence_units = max(len(punct_sentences), len(clause_parts))

    errors = []
    good = []

    if has_audio:
        good.append(f"Voice recorded ({audio_bytes_len:,} bytes).")
    else:
        errors.append("No voice recording attached yet. Tap Record Voice above.")

    if len(words) >= 3:
        good.append(f"Spoken text captured ({len(words)} words).")
    else:
        errors.append("No transcript or spoken text detected yet. Add OPENAI_API_KEY in Secrets for auto-transcription, or type/dictate your words.")

    if sentence_units >= 3:
        good.append(f"Detected {sentence_units} sentence units for the 3 prompts.")
    elif len(words) >= 3:
        errors.append(f"Detected {sentence_units} sentence unit(s); answer all 3 questions clearly.")

    if re.search(r"\b(he|she|it)\s+(have|do|go|like|work|live|eat|play|watch|study|get)\b", lower):
        errors.append("Subject-verb agreement: use 3rd-person singular verbs (has, does, goes, likes, works, lives, eats, plays, watches, studies, gets) with he/she/it.")

    if re.search(r"\b(i|we|they|you)\s+(has|does|goes|watches|studies|gets)\b", lower):
        errors.append("Subject-verb agreement: use base verbs (have, do, go, watch, study, get) with I/we/they/you.")

    if re.search(r"\bi\s+(is|are)\b", lower):
        errors.append("Verb 'be': use 'am' with 'I'.")

    if re.search(r"\b(he|she|it)\s+(am|are)\b", lower):
        errors.append("Verb 'be': use 'is' with 'he/she/it'.")

    if re.search(r"\b(we|they|you)\s+(am|is)\b", lower):
        errors.append("Verb 'be': use 'are' with 'we/they/you'.")

    if re.search(r"\ba\s+(apple|egg|ice|orange|umbrella|old|english)\b", lower):
        errors.append("Articles: use 'an' before vowel sounds (e.g., 'an orange', 'an old house', 'an umbrella').")

    if re.search(r"\b(don't|doesn't)\s+(has|is|are|went|came|ate|had|did)\b", lower):
        errors.append("Negatives: use the base verb after 'don't' or 'doesn't'.")

    if "how old's" in lower:
        errors.append("Question form: use 'How old is she?' instead of 'How old's she?'.")

    passed = (len(errors) == 0) and (len(words) >= 3)
    score_pct = 100 if passed else max(0, min(85, 85 - len(errors) * 15))

    if passed:
        good.append("Grammar check passed with zero errors.")

    return {
        "passed": passed,
        "score_pct": score_pct,
        "transcript": clean if clean else "(no transcript available)",
        "good": good,
        "errors": errors,
        "corrected_example": "",
    }


def grade_speaking_response(
    questions: list[str],
    spoken_text: str,
    audio_file,
) -> dict:
    has_audio = audio_file is not None
    audio_bytes = audio_file.getvalue() if has_audio else b""
    audio_bytes_len = len(audio_bytes)
    api_key = get_api_key()

    if not api_key:
        return local_grammar_fallback(spoken_text, has_audio, audio_bytes_len)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        transcript = (spoken_text or "").strip()

        if has_audio and audio_bytes_len > 0:
            mime_type = getattr(audio_file, "type", None) or "audio/wav"
            ext = "mp3" if "mp3" in mime_type else ("m4a" if "m4a" in mime_type else "wav")
            filename = getattr(audio_file, "name", None) or f"recording.{ext}"
            stt = client.audio.transcriptions.create(
                model="whisper-1",
                file=(filename, audio_bytes, mime_type),
            )
            heard = (getattr(stt, "text", "") or "").strip()
            if heard:
                transcript = heard

        if not transcript:
            return local_grammar_fallback("", has_audio, audio_bytes_len)

        prompt_block = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an encouraging English speaking & grammar coach. "
                        "Evaluate the student's spoken response to 3 prompts. "
                        "Return ONLY valid JSON with keys: "
                        "passed (boolean), score_pct (integer 0-100), good (list of short strings), "
                        "errors (list of short grammar/clarity fixes), corrected_example (string)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Speaking prompts:\n{prompt_block}\n\nStudent transcript:\n{transcript}",
                },
            ],
        )
        raw_text = (getattr(response, "output_text", "") or "").strip()
        json_match = re.search(r"\{.*\}", raw_text, flags=re.S)
        data = json.loads(json_match.group(0) if json_match else raw_text)

        good_list = [str(x) for x in data.get("good", []) if x]
        if has_audio:
            good_list.insert(0, f"Voice recorded ({audio_bytes_len:,} bytes) and transcribed.")
        error_list = [str(x) for x in data.get("errors", []) if x]
        score_val = max(0, min(100, int(data.get("score_pct", 0))))
        passed_val = bool(data.get("passed", len(error_list) == 0 and score_val >= 80))

        return {
            "passed": passed_val,
            "score_pct": score_val,
            "transcript": transcript,
            "good": good_list,
            "errors": error_list,
            "corrected_example": str(data.get("corrected_example", "")).strip(),
        }
    except Exception as exc:
        fb = local_grammar_fallback(spoken_text, has_audio, audio_bytes_len)
        fb["errors"].insert(0, f"AI grading fallback used ({exc}).")
        return fb


def normalize_str(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = re.sub(r"\s+([?.!,])", r"\1", s)
    return s


def grammar_ai_tutor_feedback(q: dict, user_answer: str, is_correct: bool) -> str:
    if is_correct:
        return (
            f"**AI Tutor Feedback — Great job!**\n"
            f"- **Why it works:** {q['rule']}\n"
            f"- **Next step:** Tap **🔊 Speak** and say the full sentence out loud."
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


if "q_index" not in st.session_state:
    st.session_state.q_index = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "scores" not in st.session_state:
    st.session_state.scores = {}
if "sp_index" not in st.session_state:
    st.session_state.sp_index = 0
if "sp_grades" not in st.session_state:
    st.session_state.sp_grades = {}

st.markdown(
    """
    <div class="main-banner">
        <h1>🎓 ENGLISH LEARNING INTERACTIVE QUIZ</h1>
        <p>15 Grammar Items (10 MCQ + 5 Sentence Patterns) &amp; 15 Speaking Sets with 🔊 Speak &amp; AI Review</p>
    </div>
    """,
    unsafe_allow_html=True,
)

section = st.radio(
    "Choose Quiz Stage:",
    ["1. Grammar Quiz (Questions 1–15)", "2. Speaking Practice (15 Sets × 3 Questions)"],
    horizontal=True,
)

if section.startswith("1."):
    idx = st.session_state.q_index
    q = ALL_15_QUESTIONS[idx]
    q_num = q["num"]
    st.progress((idx + 1) / len(ALL_15_QUESTIONS), text=f"Question {q_num} of {len(ALL_15_QUESTIONS)}")
    st.markdown(f'<div class="q-badge">{html.escape(q["type"])} • Question {q_num}</div>', unsafe_allow_html=True)

    if q_num <= 10:
        st.markdown(f'<div class="q-prompt">{html.escape(q["prompt"])}</div>', unsafe_allow_html=True)
        speaker(q["pronounce"], label="🔊 Speak", key_id=f"gram_{q_num}")
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
        speaker(q["pronounce"], label="🔊 Speak", key_id=f"gram_{q_num}")
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
            st.error("❌ Not quite right — check the AI Tutor feedback below.")
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

else:
    item_no, three_qs = SPEAKING_15_ITEMS[st.session_state.sp_index]
    st.progress((st.session_state.sp_index + 1) / len(SPEAKING_15_ITEMS), text=f"Set {item_no} of {len(SPEAKING_15_ITEMS)}")

    st.markdown(f'<div class="q-badge">Speaking Set {item_no} • 3 Questions</div>', unsafe_allow_html=True)
    for i, sq in enumerate(three_qs, start=1):
        st.markdown(f"**{i}. {sq}**")

    speaker(" ".join(three_qs), label="🔊 Speak", key_id=f"spk_set_{item_no}")

    audio_rec = st.audio_input("Record Voice", key=f"audio_rec_{item_no}") if hasattr(st, "audio_input") else None
    uploaded_voice = st.file_uploader(
        "Or upload voice recording (if preferred)",
        type=["wav", "mp3", "m4a", "ogg", "webm"],
        key=f"up_voice_{item_no}",
    )
    spoken_words = st.text_area(
        "Spoken sentences (optional if using audio with an API key, or type/dictate here):",
        key=f"spoken_words_{item_no}",
        height=90,
        placeholder="Example: My name is Zameer. I am from Tajikistan. I spell it Z-A-M-E-E-R.",
    )

    if st.button("Done", type="primary", key=f"done_{item_no}"):
        active_audio = audio_rec if audio_rec is not None else uploaded_voice
        st.session_state.sp_grades[item_no] = grade_speaking_response(
            three_qs,
            spoken_words,
            active_audio,
        )

    grade = st.session_state.sp_grades.get(item_no)
    if grade:
        if grade["passed"]:
            st.success(f"✓ CORRECT — Grade: {grade['score_pct']}%")
        else:
            st.error(f"✗ NEEDS FIXES — Grade: {grade['score_pct']}%")

        st.markdown(f"**Checked Speech:** {grade['transcript']}")
        for g in grade["good"]:
            st.markdown(f"- ✅ {g}")
        for e in grade["errors"]:
            st.markdown(f"- ❌ {e}")
        if grade.get("corrected_example"):
            st.info(f"**Model Answer:** {grade['corrected_example']}")

    prev_col, next_col = st.columns(2)
    with prev_col:
        if st.button("⬅️ Previous", disabled=(st.session_state.sp_index == 0)):
            st.session_state.sp_index = max(0, st.session_state.sp_index - 1)
            st.rerun()
    with next_col:
        if st.button("Next ➡️", disabled=(st.session_state.sp_index == len(SPEAKING_15_ITEMS) - 1)):
            st.session_state.sp_index = min(len(SPEAKING_15_ITEMS) - 1, st.session_state.sp_index + 1)
            st.rerun()
