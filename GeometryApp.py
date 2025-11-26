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

# ========= 題庫處理 (維持原樣) =========
def load_questions_from_file(filename, num_questions=20):
    if not os.path.exists(filename):
        return [{"question": "測試題目 1+1=?", "options": ["1", "2", "3", "4"], "answer": "2", "explanation": "1+1=2"}] * num_questions

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

        questions.append({
            "question": item["original_text"],
            "options": options,
            "answer": str(int(correct_float)) if is_integer else str(round(correct_float, 1)),
            "explanation": f"解法：{str(item['equation'])}"
        })

    return random.sample(questions, min(num_questions, len(questions)))


# ========= 寄信功能 (維持原樣) =========
def send_email_with_attachment(recipient_email, subject, content, attachment_path):
    sender_email = "ama112140@gm.ntcu.edu.tw"
    app_password = "lscnwdzqnaycmnoy"

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
        st.success("檔案成功寄出！")
    except Exception as e:
        st.error(f"發送 email 失敗：{e}")


# ========= 問卷題目定義 =========
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

# ========= Streamlit App 主程式 =========
def main():
    st.set_page_config(page_title="幾何測驗與學習量表", layout="wide")
    st.title("國小幾何數學測驗")

    if "stage" not in st.session_state:
        st.session_state.stage = "login"
    
    if "background_data" not in st.session_state:
        st.session_state.background_data = {}
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

    # ==========================================
    # Phase 1: 基本資料填寫 (Background Survey)
    # ==========================================
    if st.session_state.stage == "login":
        st.subheader("基本資料調查")
        st.info("各位小朋友好：本問卷是想要瞭解你的數學學習情形，請您依據自己的情形來選擇。你的回答沒有對或錯，也和成績完全無關。謝謝您！並祝您學業進步!")

        with st.form("login_form"):
            col1, col2 = st.columns(2)
            with col1:
                grade = st.text_input("年級")
                # [修改] 加入 index=None，預設不選
                gender = st.radio("性別", ["男", "女"], index=None)
            with col2:
                # [修改] 加入 index=None，預設不選
                tutoring = st.radio("有沒有參加過數學補習或家教", ["有", "無"], index=None)
                # [修改] 加入 index=None，預設不選
                study_time = st.radio("您一週願意花多少時間在數學上", ["1小時以下", "1~3小時", "4~6小時", "6小時以上"], index=None)
            
            st.divider()
            question_count = st.selectbox("選擇測驗題數", [10, 15, 20, 25], index=0)
            
            submitted = st.form_submit_button("開始測驗")
            
            if submitted:
                # [修改] 加入檢查邏輯：如果有任何一個沒填寫，顯示警告
                if not grade:
                    st.warning("請輸入年級")
                elif gender is None:
                    st.warning("請選擇性別")
                elif tutoring is None:
                    st.warning("請選擇是否有補習")
                elif study_time is None:
                    st.warning("請選擇每週數學時間")
                else:
                    st.session_state.background_data = {
                        "年級": grade,
                        "性別": gender,
                        "有無補習": tutoring,
                        "每週數學時間": study_time
                    }
                    st.session_state.questions = load_questions_from_file("Elementary School Geometry Math.json", question_count)
                    st.session_state.stage = "quiz"
                    st.rerun()

    # ==========================================
    # Phase 2: 數學測驗 (Math Quiz)
    # ==========================================
    elif st.session_state.stage == "quiz":
        questions = st.session_state.questions
        current_index = st.session_state.current_q_index

        if current_index < len(questions):
            q = questions[current_index]
            st.write(f"### 第 {current_index + 1} 題 / 共 {len(questions)} 題")
            st.progress((current_index + 1) / len(questions))
            st.write(q["question"])

            selected = st.radio("請選出正確答案", q["options"], key=f"q_{current_index}")

            if not st.session_state.answer_submitted:
                if st.button("確認答案"):
                    st.session_state.selected_option = selected
                    st.session_state.answer_submitted = True
                    st.rerun()
            else:
                selected = st.session_state.selected_option
                correct = selected == q["answer"]

                st.info(f"你選擇了：{selected}")
                if correct:
                    st.success("答對了！")
                else:
                    st.error(f"答錯了，正確答案是：{q['answer']}")
                st.info(q["explanation"])

                if st.button("下一題"):
                    st.session_state.quiz_responses.append({
                        "題號": current_index + 1,
                        "題目": q["question"],
                        "選擇": selected,
                        "正確答案": q["answer"],
                        "正確與否": "正確" if correct else "錯誤",
                        "詳解": q["explanation"]
                    })
                    
                    st.session_state.current_q_index += 1
                    st.session_state.answer_submitted = False
                    st.session_state.selected_option = None
                    st.rerun()
        else:
            st.session_state.stage = "survey"
            st.rerun()

    # ==========================================
    # Phase 3: 學習量表問卷 (Post-Quiz Survey)
    # ==========================================
    elif st.session_state.stage == "survey":
        st.subheader("🎉 測驗完成！請幫忙填寫最後的問卷")
        st.write("以下有20個問題，請根據每題所說的內容，勾選「符合你自己的程度」。")
        
        with st.form("survey_form"):
            st.markdown("#### 第一部分：自主學習能力")
            ans_part1 = {}
            for i, q_text in enumerate(AUTONOMOUS_QUESTIONS):
                st.write(f"{i+1}. {q_text}")
                # 這裡若也希望問卷不預選，可同樣加入 index=None，不過題目多時預設值有助於避免漏填檢查的麻煩
                # 為了嚴謹，這裡示範將問卷也設為不預選 (index=None)
                ans_part1[f"自主_{i+1}"] = st.radio(
                    f"自主_{i+1}", 
                    SCALE_OPTIONS, 
                    horizontal=True, 
                    index=None, # 若希望學生一定要手動選，加這行
                    key=f"auto_{i}",
                    label_visibility="collapsed"
                )
                st.write("---")

            st.markdown("#### 第二部分：數學自我效能")
            ans_part2 = {}
            for i, q_text in enumerate(SELF_EFFICACY_QUESTIONS):
                st.write(f"{i+1}. {q_text}")
                ans_part2[f"效能_{i+1}"] = st.radio(
                    f"效能_{i+1}", 
                    SCALE_OPTIONS, 
                    horizontal=True, 
                    index=None, # 若希望學生一定要手動選，加這行
                    key=f"eff_{i}",
                    label_visibility="collapsed"
                )
                st.write("---")

            submit_survey = st.form_submit_button("提交所有結果")
            
            if submit_survey:
                # 檢查問卷是否有漏填
                all_answered = True
                for val in ans_part1.values():
                    if val is None: all_answered = False
                for val in ans_part2.values():
                    if val is None: all_answered = False
                
                if not all_answered:
                    st.warning("請確認所有問卷題目都已完成勾選喔！")
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
    # Phase 4: 結算、存檔與寄信 (Final)
    # ==========================================
    elif st.session_state.stage == "finished":
        quiz_data = st.session_state.quiz_responses
        correct_count = sum(1 for r in quiz_data if r["正確與否"] == "正確")
        total_quiz = len(quiz_data)
        
        score = 0
        if total_quiz > 0:
            score = int((correct_count / total_quiz) * 100)
            
        st.success(f"恭喜完成所有項目！")
        st.subheader(f"您的測驗成績：{score} 分 (答對 {correct_count} / {total_quiz} 題)")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"數學評量結果_{timestamp}.xlsx"
        
        bg_data = st.session_state.background_data.copy()
        bg_data["測驗分數"] = score
        bg_data["答對題數"] = f"{correct_count}/{total_quiz}"
        
        df_bg = pd.DataFrame([bg_data])
        df_quiz = pd.DataFrame(quiz_data)
        
        survey_list = []
        for key, value in st.session_state.survey_responses.items():
            q_text = value.rsplit(" [", 1)[0]
            ans_text = value.rsplit(" [", 1)[1].replace("]", "")
            survey_list.append({"類型/題號": key, "題目內容": q_text, "學生回答": ans_text})
        df_survey = pd.DataFrame(survey_list)

        try:
            with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
                df_bg.to_excel(writer, sheet_name='基本資料', index=False)
                df_quiz.to_excel(writer, sheet_name='測驗結果', index=False)
                df_survey.to_excel(writer, sheet_name='問卷結果', index=False)
            
            st.write("正在傳送結果給老師...")
            
            summary = (
                f"收到一份新的學生評量報告。\n"
                f"測驗得分：{score} 分 (答對 {correct_count}/{total_quiz})\n"
                f"附件包含：背景調查(無個資)、答題狀況及學習量表。"
            )
            
            send_email_with_attachment(
                recipient_email="ama112140@gm.ntcu.edu.tw",
                subject=f"學生數學學習評量報告 - {score}分",
                content=summary,
                attachment_path=excel_filename
            )
            
            os.remove(excel_filename)
            
        except Exception as e:
            st.error(f"檔案處理發生錯誤：{e}")

        st.balloons()
        
        if st.button("重新開始"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()