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
import time

# ========= 題庫處理 =========
def load_questions_from_file(filename, num_questions=20):
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


# ========= 寄信功能 =========
def send_email_with_attachment(recipient_email, subject, content, attachment_path):
    sender_email = "ama112140@gm.ntcu.edu.tw"
    app_password = "vhkacrenrqenxgju"

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


# ========= Streamlit App 主程式 =========
def main():
    st.set_page_config(page_title="幾何測驗", layout="wide")
    st.title("國小幾何數學測驗")

    # 初始狀態定義
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "started" not in st.session_state:
        st.session_state.started = False
    if "questions" not in st.session_state:
        st.session_state.questions = []
    if "current" not in st.session_state:
        st.session_state.current = 0
    if "responses" not in st.session_state:
        st.session_state.responses = []
    if "answer_submitted" not in st.session_state:
        st.session_state.answer_submitted = False
    if "selected_option" not in st.session_state:
        st.session_state.selected_option = None
    if "selected_question_count" not in st.session_state:
        st.session_state.selected_question_count = 20

    # Step 1: 登入 + 選擇題數
    if not st.session_state.started:
        st.subheader("請輸入班級座號姓名")
        name = st.text_input("姓名")
        question_count = st.selectbox("選擇測驗題數", [10, 15, 20, 25], index=0)

        if st.button("開始測驗"):
            if name.strip() == "":
                st.warning("請輸入姓名")
            else:
                st.session_state.username = name
                st.session_state.selected_question_count = question_count
                st.session_state.questions = load_questions_from_file("Elementary School Geometry1.json", question_count)
                st.session_state.started = True
                st.rerun()
        return

    # Step 2: 顯示題目
    questions = st.session_state.questions
    current_index = st.session_state.current

    if current_index < len(questions):
        q = questions[current_index]
        st.write(f"### 第 {current_index + 1} 題")
        st.progress((current_index + 1) / len(questions))
        st.write(q["question"])

        selected = st.radio("請選出正確答案", q["options"], key=current_index)

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
                st.session_state.responses.append({
                    "題號": current_index + 1,
                    "題目": q["question"],
                    "選擇": selected,
                    "正確答案": q["answer"],
                    "正確與否": "正確" if correct else "錯誤",
                    "詳解": q["explanation"]
                })
                st.session_state.current += 1
                st.session_state.answer_submitted = False
                st.session_state.selected_option = None
                st.rerun()
    else:
        # Step 3: 測驗完成
        correct_count = sum(1 for r in st.session_state.responses if r["正確與否"] == "正確")
        total = len(st.session_state.responses)
        st.success(f"測驗完成！共 {total} 題，答對 {correct_count} 題")

        df = pd.DataFrame(st.session_state.responses)
        excel_filename = f"{st.session_state.username}_result.xlsx"
        df.to_excel(excel_filename, index=False, engine="openpyxl")

        summary = f"學生姓名：{st.session_state.username}\n答對題數：{correct_count}/{total}\n詳見附件 Excel。"

        send_email_with_attachment(
            recipient_email="ama112140@gm.ntcu.edu.tw",
            subject=f"{st.session_state.username} 的答題狀況",
            content=summary,
            attachment_path=excel_filename
        )

        try:
            os.remove(excel_filename)
        except:
            pass

        st.balloons()
        if st.button("重新開始測驗"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ========= 執行 =========
if __name__ == "__main__":
    main()
