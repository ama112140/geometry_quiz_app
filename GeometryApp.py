import streamlit as st
import json
import random
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import datetime
from groq import Groq

# ==========================================
# 1. AI 輔助功能 (提示與題目情境換皮)
# ==========================================
def ask_ai_for_hint(question, user_level="國小五年級"):
    try:
        if "GROQ_API_KEY" not in st.secrets:
            return "⚠️ 系統錯誤：請在 Streamlit Secrets 中設定 GROQ_API_KEY 才能使用 AI 功能。"
        
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"你是一位{user_level}數學老師。請針對題目給予一個「非常簡短、敘述式」的解題關鍵。"
                        "【嚴格規則】"
                        "1. 內容必須控制在 30~50 字以內。"
                        "2. 省略開場白，直接列出計算步驟。"
                        "3. 絕對不要給答案，也不要用代數符號 (x, y)。"
                        "4. 請用敘述式或短句。"
                    )
                },
                {
                    "role": "user",
                    "content": f"題目是：{question}。請給我簡短的提示。"
                }
            ],
            model="llama-3.3-70b-versatile", 
            temperature=0.3, 
        )
        return chat_completion.choices[0].message.content

    except Exception as e:
        return f"AI 連線錯誤：{str(e)}"

def rewrite_question_with_ai(original_text):
    """將原本的數學題目丟給 AI，請它用相同的數字與邏輯換一個新情境"""
    try:
        if "GROQ_API_KEY" not in st.secrets:
            return original_text # 沒設定 Key 就退回原題目

        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        prompt = f"""
        你是一個充滿創意的國小五年級數學老師。
        請將下面這道數學題「換一個全新的生活情境」。
        
        【情境要求】
        請發揮極致的創意，每次都隨機使用完全不同的主題（例如：校園生活、奇幻冒險、體育競賽、動物世界、節慶活動、美食烘焙、科幻未來...等）。請確保每次生成的情境都不落俗套，不要過度重複相同的主題！
        
        【原題目】：{original_text}
        
        【嚴格規則】：
        1. 必須保留原本題目中「所有的數字」，絕對不能修改數字，也不能自己亂加數字。
        2. 數學的計算邏輯必須和原題一模一樣。
        3. 只要輸出「新的題目敘述」即可，不要有任何開場白，也不要附上答案或算式。
        """
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.7, # 稍微調高溫度，讓情境更有創意
        )
        return chat_completion.choices[0].message.content.strip()

    except Exception as e:
        # 如果 AI 罷工或連線失敗，就安全地回傳原本的題目，確保測驗不中斷
        return original_text

# ==========================================
# 2. 題庫處理
# ==========================================
def load_questions_from_file(filename, num_questions=20):
    def format_equation(eq_str):
        text = str(eq_str)
        # 直接替換成 Unicode 的一般符號，更適合國小生閱讀
        text = text.replace("*", " × ").replace("/", " ÷ ")
        return text

    if not os.path.exists(filename):
        st.warning(f"找不到題庫檔案 {filename}，將使用測試題目。")
        dummy_questions = [
            {"original_text": "計算 1 + 1 = ?", "ans": "2", "equation": "1 + 1 = 2"},
            {"original_text": "請問 1/2 + 1/2 = ?", "ans": "1", "equation": "1/2 + 1/2 = 1"},
            {"original_text": "計算 3 × 5 = ?", "ans": "15", "equation": "3 * 5 = 15"}
        ]
        
        while len(dummy_questions) < num_questions:
            dummy_questions.append(dummy_questions[0])
            
        questions = []
        for item in dummy_questions:
            questions.append({
                "question": item["original_text"],
                "options": ["1", "2", "15", "10"],
                "answer": item["ans"],
                "explanation": f"解法：{format_equation(item['equation'])}"
            })
        return questions[:num_questions]

    with open(filename, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    questions = []
    for item in raw_data:
        correct_ans = item["ans"]
        try:
            correct_float = float(correct_ans)
            is_integer = correct_float.is_integer()
            fake_options = set()

            while len(fake_options) < 3:
                if is_integer:
                    noise = random.randint(-10, 10)
                    fake = int(correct_float + noise)
                    if fake != correct_float and fake > 0:
                        fake_options.add(str(fake))
                else:
                    noise = (random.randint(-10, 10)) * 0.1
                    fake = round(correct_float + noise, 1)
                    if fake != correct_float and fake > 0:
                        fake_options.add(str(fake))

            options = list(fake_options)
            options.append(str(int(correct_float)) if is_integer else str(round(correct_float, 1)))
            random.shuffle(options)
        except:
            options = [correct_ans]
            correct_float = 0
            is_integer = False

        questions.append({
            "question": item["original_text"],
            "options": options,
            "answer": str(int(correct_float)) if is_integer else str(round(correct_float, 1)),
            "explanation": f"解法：{format_equation(item['equation'])}"
        })

    return random.sample(questions, min(num_questions, len(questions)))

# ==========================================
# 3. 寄信功能
# ==========================================
def send_email_with_attachment(recipient_email, subject, content, attachment_path):
    if "EMAIL_USER" not in st.secrets or "EMAIL_PASSWORD" not in st.secrets:
        st.error("❌ 系統錯誤：請在 Streamlit Secrets 中設定 Email 帳號與密碼。")
        return

    sender_email = st.secrets["EMAIL_USER"]
    app_password = st.secrets["EMAIL_PASSWORD"]

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(content, "plain"))

    try:
        with open(attachment_path, "rb") as f:
            mime_part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            mime_part.set_payload(f.read())
            encoders.encode_base64(mime_part)
            mime_part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(attachment_path)}")
            msg.attach(mime_part)
    except Exception as e:
        st.error(f"附加檔案失敗：{e}")
        return

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        st.success("📨 檔案成功寄出！(只會寄這一次)")
    except Exception as e:
        st.error(f"發送 email 失敗：{e}")

# ==========================================
# 4. 問卷題目定義
# ==========================================
SCALE_OPTIONS = ["非常不符合", "不符合", "有點符合", "符合", "非常符合"]

AUTONOMOUS_QUESTIONS = [
    "我喜歡學到新的知識，也喜歡自己探索答案",
    "遇到不懂的地方，我會先自己想想看怎麼解決",
    "如果學習系統或 AI 工具給我新的任務，我願意試著完成",
    "我覺得自己能安排好學習的時間，不會拖到最後",
    "我會主動找資料或問老師、同學，讓自己更懂數學",
    "當 AI 給我回饋時，我會仔細看懂哪裡需要改進",
    "即使題目很難，我也會想辦法學會，而不是放棄",
    "我能自己決定學習的步驟，例如先練基本題再挑戰難題",
    "我覺得學習是有趣的事，而不是被強迫的事",
    "我願意為了學得更好，多花一些時間努力練習"
]

SELF_EFFICACY_QUESTIONS = [
    "我相信自己能學會老師或 AI 教的數學內容",
    "即使是比較難的數學題，我覺得自己也有辦法找到答案",
    "我覺得自己能在數學小考或作業中得到不錯的成績",
    "如果我認真練習，我能在數學上有明顯的進步",
    "我能清楚跟同學或老師說明我做題目的想法",
    "當我使用 AI 練習數學時，我覺得自己能越來越厲害",
    "遇到錯題時，我相信自己能理解錯在哪裡並改正",
    "我覺得自己能在課堂討論中正確回答數學問題",
    "我覺得我理解數學概念的能力不比其他同學差",
    "我相信自己能把學過的數學知識用在新的題目裡"
]

# ==========================================
# 5. Streamlit App 主程式
# ==========================================
def main():
    st.set_page_config(page_title="幾何測驗與學習平台", layout="wide")
    st.title("國小幾何數學測驗系統")

    # ==========================================
    # 初始化 Session State (確保變數存在)
    # ==========================================
    if "stage" not in st.session_state:
        st.session_state.stage = "login"
    if "background_data" not in st.session_state:
        st.session_state.background_data = {}
    if "mode" not in st.session_state:
        st.session_state.mode = "練習模式" 
    if "quiz_responses" not in st.session_state:
        st.session_state.quiz_responses = []
    if "survey_responses" not in st.session_state:
        st.session_state.survey_responses = {}
    if "questions" not in st.session_state:
        st.session_state.questions = []
    if "current_q_index" not in st.session_state:
        st.session_state.current_q_index = 0
    if "answer_submitted" not in st.session_state:
        st.session_state.answer_submitted = False
    if "selected_option" not in st.session_state:
        st.session_state.selected_option = None
    if "ai_hint" not in st.session_state:
        st.session_state.ai_hint = ""
    if "email_sent" not in st.session_state:
        st.session_state.email_sent = False

    # ==========================================
    # Phase 1: 登入與設定 (Login & Setup)
    # ==========================================
    if st.session_state.stage == "login":
        st.subheader("基本資料與模式選擇")
        st.info("歡迎來到數學測驗平台！請先填寫以下資料。")

        with st.form("login_form"):
            col1, col2 = st.columns(2)
            with col1:
                gender = st.radio("性別", ["男", "女"], index=None)
                tutoring = st.radio("有無補習", ["有", "無"], index=None)
            with col2:
                study_time = st.radio("每週數學時間", ["1小時以下", "1~3小時", "4~6小時", "6小時以上"], index=None)
                mode_choice = st.radio("請選擇進行模式", ["練習模式", "測驗模式"], index=None)
                question_count = st.selectbox("選擇測驗題數", [10, 15, 20, 25], index=0)
            
            submitted = st.form_submit_button("開始測驗")
            
            if submitted:
                if not gender or not tutoring or not study_time or not mode_choice:
                    st.warning("請完整填寫所有欄位（包含性別、補習、時間與模式）喔！")
                else:
                    st.session_state.background_data = {
                        "性別": gender,
                        "有無補習": tutoring,
                        "每週數學時間": study_time,
                        "測驗模式": mode_choice
                    }
                    st.session_state.mode = mode_choice
                    # 確保這裡的檔名和你 GitHub 上的 JSON 檔名完全一致
                    st.session_state.questions = load_questions_from_file("Elementary School Geometry Math.json", question_count)
                    
                    if not st.session_state.questions:
                        st.error("題庫讀取失敗")
                    else:
                        st.session_state.stage = "quiz"
                        st.rerun()

    # ==========================================
    # Phase 2: 數學測驗 (Quiz)
    # ==========================================
    elif st.session_state.stage == "quiz":
        questions = st.session_state.questions
        current_index = st.session_state.current_q_index

        if current_index < len(questions):
            q = questions[current_index]
            
            st.write(f"### 第 {current_index + 1} 題 / 共 {len(questions)} 題")
            st.progress((current_index + 1) / len(questions))
            
            # --- AI 題幹換皮核心邏輯 ---
            if "ai_rewritten_question" not in q:
                with st.spinner("✨ 系統正在為您隨機生成全新情境..."):
                    new_q_text = rewrite_question_with_ai(q['question'])
                    q["ai_rewritten_question"] = new_q_text
            
            st.markdown(f"#### {q['ai_rewritten_question']}")
            
            with st.expander("👀 查看原始題目原型"):
                st.caption(q['question'])
            # ---------------------------

            if st.session_state.mode.startswith("練習") and not st.session_state.answer_submitted:
                if st.button("🤖 呼叫 AI 老師給提示"):
                    with st.spinner("AI 老師正在思考中..."):
                        # 注意：這裡是針對換皮後的新題目給提示
                        hint = ask_ai_for_hint(q["ai_rewritten_question"])
                        st.session_state.ai_hint = hint
                
                if st.session_state.ai_hint:
                    st.info(f"💡 AI 提示：{st.session_state.ai_hint}")

            st.divider()

            selected = st.radio("請選出正確答案", q["options"], key=f"q_{current_index}", index=None)

            if st.session_state.mode.startswith("練習"):
                # --- 練習模式 ---
                if not st.session_state.answer_submitted:
                    if st.button("確認答案"):
                        if selected is None:
                            st.warning("請先選擇一個答案")
                        else:
                            st.session_state.selected_option = selected
                            st.session_state.answer_submitted = True
                            st.rerun()
                else:
                    correct = st.session_state.selected_option == q["answer"]
                    st.info(f"你選擇了：{st.session_state.selected_option}")
                    
                    if correct:
                        st.success("答對了！")
                    else:
                        st.error(f"答錯了，正確答案是：{q['answer']}")
                    
                    st.info(q["explanation"])

                    if st.button("下一題"):
                        st.session_state.quiz_responses.append({
                            "題號": current_index + 1,
                            "原始題目": q["question"],
                            "AI生成題目": q["ai_rewritten_question"],
                            "選擇": st.session_state.selected_option,
                            "正確答案": q["answer"],
                            "正確與否": "正確" if correct else "錯誤",
                            "詳解": q["explanation"]
                        })
                        st.session_state.current_q_index += 1
                        st.session_state.answer_submitted = False
                        st.session_state.selected_option = None
                        st.session_state.ai_hint = ""
                        st.rerun()

            else:
                # --- 測驗模式 ---
                btn_text = "下一題" if current_index < len(questions) - 1 else "交卷，進入問卷"
                
                if st.button(btn_text):
                    if selected is None:
                        st.warning("請先選擇一個答案")
                    else:
                        correct = selected == q["answer"]
                        st.session_state.quiz_responses.append({
                            "題號": current_index + 1,
                            "原始題目": q["question"],
                            "AI生成題目": q["ai_rewritten_question"],
                            "選擇": selected,
                            "正確答案": q["answer"],
                            "正確與否": "正確" if correct else "錯誤",
                            "詳解": q["explanation"]
                        })
                        st.session_state.current_q_index += 1
                        st.rerun()

        else:
            st.session_state.stage = "survey"
            st.rerun()

    # ==========================================
    # Phase 3: 學習量表問卷 (Survey)
    # ==========================================
    elif st.session_state.stage == "survey":
        st.subheader("🎉 測驗部分完成！")
        st.write("最後請幫忙填寫這份學習感受問卷，勾選「符合你自己的程度」。")
        
        with st.form("survey_form"):
            st.markdown("#### 第一部分：自主學習能力")
            ans_part1 = {}
            for i, q_text in enumerate(AUTONOMOUS_QUESTIONS):
                st.write(f"{i+1}. {q_text}")
                ans_part1[f"自主_{i+1}"] = st.radio(
                    f"自主_{i+1}", SCALE_OPTIONS, horizontal=True, index=None, key=f"auto_{i}", label_visibility="collapsed"
                )
                st.write("---")

            st.markdown("#### 第二部分：數學自我效能")
            ans_part2 = {}
            for i, q_text in enumerate(SELF_EFFICACY_QUESTIONS):
                st.write(f"{i+1}. {q_text}")
                ans_part2[f"效能_{i+1}"] = st.radio(
                    f"效能_{i+1}", SCALE_OPTIONS, horizontal=True, index=None, key=f"eff_{i}", label_visibility="collapsed"
                )
                st.write("---")

            submit_survey = st.form_submit_button("提交並查看成績")
            
            if submit_survey:
                if any(v is None for v in ans_part1.values()) or any(v is None for v in ans_part2.values()):
                    st.warning("還有題目沒填完喔！請檢查一下。")
                else:
                    full_survey = {}
                    for i, q in enumerate(AUTONOMOUS_QUESTIONS):
                        full_survey[f"自主學習_{i+1}"] = f"{q} [{ans_part1[f'自主_{i+1}']}]"
                    for i, q in enumerate(SELF_EFFICACY_QUESTIONS):
                        full_survey[f"自我效能_{i+1}"] = f"{q} [{ans_part2[f'效能_{i+1}']}]"
                    
                    st.session_state.survey_responses = full_survey
                    st.session_state.stage = "finished"
                    st.rerun()

    # ==========================================
    # Phase 4: 結算、存檔與寄信 (Finished)
    # ==========================================
    elif st.session_state.stage == "finished":
        quiz_data = st.session_state.quiz_responses
        correct_count = sum(1 for r in quiz_data if r["正確與否"] == "正確")
        total_quiz = len(quiz_data)
        score = int((correct_count / total_quiz) * 100) if total_quiz > 0 else 0
        
        if not st.session_state.email_sent:
            st.balloons()
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"學生數學學習評量結果_{timestamp}.xlsx"
            
            bg_data = st.session_state.background_data.copy()
            bg_data["分數"] = score
            bg_data["答對率"] = f"{correct_count}/{total_quiz}"
            df_bg = pd.DataFrame([bg_data])
            df_quiz = pd.DataFrame(quiz_data)
            
            survey_list = []
            for key, value in st.session_state.survey_responses.items():
                q_text = value.rsplit(" [", 1)[0]
                ans_text = value.rsplit(" [", 1)[1].replace("]", "")
                survey_list.append({"題號": key, "題目": q_text, "回答": ans_text})
            df_survey = pd.DataFrame(survey_list)

            try:
                with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
                    df_bg.to_excel(writer, sheet_name='基本資料', index=False)
                    df_quiz.to_excel(writer, sheet_name='測驗結果', index=False)
                    df_survey.to_excel(writer, sheet_name='問卷結果', index=False)
                
                st.write("📨 正在傳送成績報告給老師...")
                summary_text = (
                    f"模式：{st.session_state.mode}\n"
                    f"得分：{score} 分 ({correct_count}/{total_quiz})\n"
                    f"交卷編號(時間)：{timestamp}\n"
                    f"附件包含完整作答紀錄與問卷結果。"
                )
                
                send_email_with_attachment(
                    recipient_email="ama112140@gm.ntcu.edu.tw",
                    subject=f"學生數學學習評量報告 ({timestamp})",
                    content=summary_text,
                    attachment_path=excel_filename
                )
                
                os.remove(excel_filename)
                st.session_state.email_sent = True
                
            except Exception as e:
                st.error(f"處理檔案或寄信時發生錯誤：{e}")
        
        else:
            st.caption(f"✅ 成績已送出，現在您可以安心檢討試題。")

        st.success("恭喜完成所有項目！")
        st.subheader(f"🏆 您的最終成績：{score} 分")
        st.write(f"答對題數：{correct_count} / {total_quiz}")

        st.divider()
        st.subheader("📝 試題檢討")
        
        for resp in quiz_data:
            with st.expander(f"第 {resp['題號']} 題 - {resp['正確與否']}"):
                st.markdown(f"**AI 生成題目**：{resp['AI生成題目']}")
                st.caption(f"原始題目：{resp['原始題目']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**你的答案**：{resp['選擇']}")
                    if resp['正確與否'] == "錯誤":
                        st.error("❌ 答錯")
                    else:
                        st.success("✅ 答對")
                with col2:
                    st.write(f"**正確答案**：{resp['正確答案']}")
                st.info(f"💡 **詳解**：{resp['詳解']}")

        st.divider()
        if st.button("重新開始"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()