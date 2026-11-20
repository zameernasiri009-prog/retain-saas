import base64
import html
import io
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


def listen_button(text: str, key_id: str):
    lines = text if isinstance(text, list) else [text]
    payload = json.dumps(lines)
    safe_id = re.sub(r"[^A-Za-z0-9_]", "_", key_id)
    components.html(
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
        height=54,
    )


def mic_recorder(key_id: str):
    safe_id = re.sub(r"[^A-Za-z0-9_]", "_", key_id)
    return components.html(
        f"""
        <div style="font-family:sans-serif;background:#111827;border:1px solid #334155;border-radius:10px;padding:14px;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <button type="button" id="mic_btn_{safe_id}" onclick="toggleMic_{safe_id}()"
                    style="background:#DC2626;color:#FFFFFF;border:none;padding:10px 18px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;">
                    🎙️ Mic
                </button>
                <span id="mic_status_{safe_id}" style="color:#F8FAFC;font-size:13px;font-weight:600;">Ready to record</span>
                <span id="mic_timer_{safe_id}" style="color:#FBBF24;font-size:13px;font-weight:700;">00:00</span>
            </div>
            <audio id="mic_player_{safe_id}" controls style="width:100%;margin-top:12px;display:none;"></audio>
        </div>
        <script>
        let recorder_{safe_id} = null;
        let stream_{safe_id} = null;
        let chunks_{safe_id} = [];
        let timerInterval_{safe_id} = null;
        let seconds_{safe_id} = 0;

        function sendToStreamlit_{safe_id}(payloadObj) {{
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: "streamlit:setComponentValue",
                value: payloadObj
            }}, "*");
        }}

        function formatTime_{safe_id}(sec) {{
            const m = String(Math.floor(sec / 60)).padStart(2, "0");
            const s = String(sec % 60).padStart(2, "0");
            return m + ":" + s;
        }}

        async function toggleMic_{safe_id}() {{
            const btn = document.getElementById("mic_btn_{safe_id}");
            const statusEl = document.getElementById("mic_status_{safe_id}");
            const timerEl = document.getElementById("mic_timer_{safe_id}");
            const player = document.getElementById("mic_player_{safe_id}");

            if (recorder_{safe_id} && recorder_{safe_id}.state === "recording") {{
                recorder_{safe_id}.stop();
                clearInterval(timerInterval_{safe_id});
                btn.textContent = "🎙️ Mic";
                btn.style.background = "#DC2626";
                statusEl.textContent = "Recorded";
                return;
            }}

            try {{
                if (stream_{safe_id}) {{
                    stream_{safe_id}.getTracks().forEach(t => t.stop());
                }}
                stream_{safe_id} = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                chunks_{safe_id} = [];
                recorder_{safe_id} = new MediaRecorder(stream_{safe_id});

                recorder_{safe_id}.ondataavailable = (e) => {{
                    if (e.data && e.data.size > 0) {{
                        chunks_{safe_id}.push(e.data);
                    }}
                }};

                recorder_{safe_id}.onstop = () => {{
                    const mimeType = recorder_{safe_id}.mimeType || "audio/webm";
                    const blob = new Blob(chunks_{safe_id}, {{ type: mimeType }});
                    const url = URL.createObjectURL(blob);
                    player.src = url;
                    player.style.display = "block";
                    if (stream_{safe_id}) {{
                        stream_{safe_id}.getTracks().forEach(t => t.stop());
                    }}

                    const reader = new FileReader();
                    reader.onloadend = () => {{
                        const dataUrl = reader.result || "";
                        const base64Data = dataUrl.includes(",") ? dataUrl.split(",")[1] : "";
                        sendToStreamlit_{safe_id}({{
                            base64: base64Data,
                            mime: mimeType,
                            name: "recording.webm"
                        }});
                    }};
                    reader.readAsDataURL(blob);
                }};

                recorder_{safe_id}.start();
                seconds_{safe_id} = 0;
                timerEl.textContent = "00:00";
                clearInterval(timerInterval_{safe_id});
                timerInterval_{safe_id} = setInterval(() => {{
                    seconds_{safe_id} += 1;
                    timerEl.textContent = formatTime_{safe_id}(seconds_{safe_id});
                }}, 1000);

                btn.textContent = "⏹ Stop";
                btn.style.background = "#059669";
                statusEl.textContent = "Recording...";
            }} catch (err) {{
                statusEl.textContent = "Mic error: " + (err && err.message ? err.message : "Allow microphone permission");
            }}
        }}
        </script>
        """,
        height=135,
    )


def ai_check_speaking(questions: list[str], audio_bytes: bytes, mime_type: str, filename: str, api_key: str) -> dict:
    if not api_key:
        return {
            "passed": False,
            "transcript": "(OPENAI_API_KEY not set in Streamlit Secrets)",
            "correct": [],
            "mistakes": ["Add OPENAI_API_KEY in Streamlit Secrets so AI can listen to your voice and check your grammar."],
            "better": [],
        }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        stt = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, io.BytesIO(audio_bytes), mime_type),
        )
        transcript = (getattr(stt, "text", "") or "").strip()

        if not transcript:
            return {
                "passed": False,
                "transcript": "(no speech heard)",
                "correct": [],
                "mistakes": ["No words were heard in your recording. Tap Mic, speak clearly, and tap Submit again."],
                "better": [],
            }

        prompt_block = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a friendly English tutor for absolute beginners. "
                        "Check the student's spoken transcript against the 3 questions using simple, easy beginner words. "
                        "Return ONLY valid JSON with keys: "
                        "passed (boolean), "
                        "correct (list of short simple strings showing what grammar or answers are right), "
                        "mistakes (list of short simple strings showing what grammar or answers are wrong), "
                        "better (list of short simple 'Try saying: ...' strings)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Questions:\n{prompt_block}\n\nStudent spoken words:\n{transcript}",
                },
            ],
        )
        raw_text = (getattr(response, "output_text", "") or "").strip()
        json_match = re.search(r"\{.*\}", raw_text, flags=re.S)
        data = json.loads(json_match.group(0) if json_match else raw_text)

        correct_list = [str(x) for x in data.get("correct", []) if x]
        mistakes_list = [str(x) for x in data.get("mistakes", []) if x]
        better_list = [str(x) for x in data.get("better", []) if x]
        passed_val = bool(data.get("passed", len(mistakes_list) == 0))

        return {
            "passed": passed_val,
            "transcript": transcript,
            "correct": correct_list,
            "mistakes": mistakes_list,
            "better": better_list,
        }
    except Exception as exc:
        return {
            "passed": False,
            "transcript": "(error checking voice)",
            "correct": [],
            "mistakes": [f"AI could not check the recording right now: {exc}"],
            "better": [],
        }


def normalize_str(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = re.sub(r"\s+([?.!,])", r"\1", s)
    return s


def grammar_ai_tutor_feedback(q: dict, user_answer: str, is_correct: bool) -> str:
    if is_correct:
        return (
            f"**AI Tutor Feedback — Great job!**\n"
            f"- **Why it works:** {q['rule']}\n"
            f"- **Next step:** Tap **🔊 Listen** and say the full sentence out loud."
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
if "sp_results" not in st.session_state:
    st.session_state.sp_results = {}
if "sp_recordings" not in st.session_state:
    st.session_state.sp_recordings = {}

api_key = get_api_key()

st.markdown(
    """
    <div class="main-banner">
        <h1>🎓 ENGLISH LEARNING INTERACTIVE QUIZ</h1>
        <p>15 Grammar Items (10 MCQ + 5 Sentence Patterns) &amp; 15 Speaking Sets with 🔊 Listen &amp; 🎙️ Mic</p>
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

    listen_button(three_qs, key_id=f"spk_set_{item_no}")
    mic_val = mic_recorder(key_id=f"mic_set_{item_no}")

    if isinstance(mic_val, dict) and mic_val.get("base64"):
        st.session_state.sp_recordings[item_no] = mic_val

    if st.button("Submit", type="primary", key=f"submit_voice_{item_no}"):
        rec = st.session_state.sp_recordings.get(item_no)
        if not rec or not rec.get("base64"):
            st.session_state.sp_results[item_no] = {
                "passed": False,
                "transcript": "(no voice recorded yet)",
                "correct": [],
                "mistakes": ["Please record your voice with Mic first, then tap Submit."],
                "better": [],
            }
        else:
            raw_bytes = base64.b64decode(rec["base64"])
            mime = rec.get("mime") or "audio/webm"
            fname = rec.get("name") or "recording.webm"
            with st.spinner("AI is checking your voice..."):
                st.session_state.sp_results[item_no] = ai_check_speaking(
                    three_qs,
                    raw_bytes,
                    mime,
                    fname,
                    api_key,
                )

    res = st.session_state.sp_results.get(item_no)
    if res:
        if res["passed"]:
            st.success("✅ Good job! Your grammar looks right.")
        else:
            st.warning("⚠️ Let's check your speaking:")

        st.markdown(f"**What you said:** {res['transcript']}")

        if res["correct"]:
            st.markdown("**Correct grammar:**")
            for c_item in res["correct"]:
                st.markdown(f"- ✅ {c_item}")

        if res["mistakes"]:
            st.markdown("**Mistakes to fix:**")
            for m_item in res["mistakes"]:
                st.markdown(f"- ❌ {m_item}")

        if res["better"]:
            st.markdown("**Better way to say it:**")
            for b_item in res["better"]:
                st.markdown(f"- 💡 {b_item}")

    prev_col, next_col = st.columns(2)
    with prev_col:
        if st.button("⬅️ Previous", disabled=(st.session_state.sp_index == 0)):
            st.session_state.sp_index = max(0, st.session_state.sp_index - 1)
            st.rerun()
    with next_col:
        if st.button("Next ➡️", disabled=(st.session_state.sp_index == len(SPEAKING_15_ITEMS) - 1)):
            st.session_state.sp_index = min(len(SPEAKING_15_ITEMS) - 1, st.session_state.sp_index + 1)
            st.rerun()
