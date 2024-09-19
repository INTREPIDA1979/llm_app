from __future__ import annotations

import datetime
import logging
import google.cloud.logging
import os

from flask import Flask, render_template, request, Response, jsonify

import sqlalchemy

from connect_connector import connect_with_connector
from connect_connector_auto_iam_authn import connect_with_connector_auto_iam_authn

from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory 
#from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import VertexAI
from langchain.schema import HumanMessage, SystemMessage

app = Flask(__name__)

logger = logging.getLogger()
log_client = google.cloud.logging.Client()
log_client.setup_logging()

###########################################
## 大きめなTODO（リファクタリング）リスト
## ・SQL処理をORマッピング方式に変更
## ・MVCモデル、機能単位で整理する。
## ・セッション管理
###########################################
# global変数
db = None

# LLM初期化　#TODO 後で関数にして、起動時に生成（グローバル変数はchainのみでよいので）
#llm = ChatGoogleGenerativeAI(model="gemini-pro")
llm = VertexAI(model="gemini-pro")
memory = ConversationBufferMemory (
  return_message=True
)

chain = ConversationChain(
  memory=memory,
  llm=llm
)

chat_personality = None

def init_connection_pool() -> sqlalchemy.engine.base.Engine:
    # use the connector when INSTANCE_CONNECTION_NAME (e.g. project:region:instance) is defined
    if os.environ.get("INSTANCE_CONNECTION_NAME"):
        return (
            connect_with_connector_auto_iam_authn()
            if os.environ.get("DB_IAM_USER")
            else connect_with_connector()
        )

    raise ValueError(
        "Missing database connection type. Please define one of INSTANCE_CONNECTION_NAME"
    )

@app.before_request
def init_db() -> sqlalchemy.engine.base.Engine:
    """Initiates connection to database and its' structure."""
    global db
    if db is None:
        db = init_connection_pool()

@app.route("/", methods=["GET"])
def render_index() -> str:
    return render_template("index.html")

### パーソナリティ管理 ###
# パーソナリティ一覧
@app.route("/personality_list")
def personality_list():
    query = """
        SELECT p.*, s.sex_name, st.stereo_name
          FROM personality as p
          JOIN sex as s ON p.sex = s.sex
          JOIN stereo_type as st ON p.stereo_type = st.stereo_type
         WHERE deleted_date is null
         ORDER BY p.id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            personalities = conn.execute(stmt, parameters={})
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('personality_list.html', personalities=personalities)

# パーソナリティ詳細
@app.route("/personality_detail")
def personality_detail():
    id = request.args.get('id', type=int)
    query = """
        SELECT p.*, s.sex_name, st.stereo_name
          FROM personality as p
          JOIN sex as s ON p.sex = s.sex
          JOIN stereo_type as st ON p.stereo_type = st.stereo_type
         WHERE id = :id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            res = conn.execute(stmt, parameters={"id": id})
            personality = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('personality_detail.html', personality=personality)

# パーソナリティ登録
@app.route("/personality_create_input")
def personality_create_input():
    stmt = sqlalchemy.text("SELECT * FROM sex ORDER BY sex")
    stmt2 = sqlalchemy.text("SELECT * FROM stereo_type ORDER BY stereo_type")
    try:
        with db.connect() as conn:
            res = conn.execute(stmt)
            sexes = res.fetchall()

            res2 = conn.execute(stmt2)
            stereo_types = res2.fetchall()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    
    return render_template('personality_create_input.html', sexes=sexes, stereo_types=stereo_types)

@app.route("/personality_create_action", methods=['POST'])
def personality_create_action():
    global llm

    name = request.form.get('name')
    mail = request.form.get('mail')
    sex = request.form.get('sex', type=int)
    age = request.form.get('age', type=int)
    basic_info = request.form.get('basic_info')
    career_info = request.form.get('career_info')
    stereo_type = request.form.get('stereo_type', type=int)
    detail_info = request.form.get('detail_info')

    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    stmt_sex = sqlalchemy.text("SELECT * FROM sex WHERE sex = :sex")
    stmt_stereo_type = sqlalchemy.text("SELECT * FROM stereo_type WHERE stereo_type = :stereo_type")
    try:
        with db.connect() as conn:
            res_sex = conn.execute(stmt_sex, parameters={"sex": sex})
            sex_name = res_sex.fetchone().sex_name

            res_stereo_types = conn.execute(stmt_stereo_type, parameters={"stereo_type": stereo_type})
            stereo_content = res_stereo_types.fetchone().stereo_content
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    system_message = "あなたは優秀なライター兼パーソナリティ心理学者です。次の個人の性格情報を要約して、日本語で500文字程度にしてください。個人名などは使わないでください。"
    personality_data = basic_info + ":" + career_info + ":" + stereo_content + ":" +detail_info
    response = llm.invoke(
        [
            SystemMessage(content=system_message), 
            HumanMessage(content=personality_data)
        ]
    )
    personality_summary = response

    query = """
        INSERT INTO personality (name, mail, sex, age, basic_info, career_info,
        stereo_type, detail_info, personality_summary, created_date, updated_date) 
        VALUES ( :name, :mail, :sex, :age, :basic_info, :career_info,
        :stereo_type, :detail_info, :personality_summary, :created_date, :updated_date)
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            conn.execute(
                stmt, parameters={
                    "name": name, "mail": mail, "sex": sex, "age": age,
                    "basic_info": basic_info, "career_info": career_info,
                    "stereo_type": stereo_type, "detail_info": detail_info,
                    "personality_summary": personality_summary, "created_date": current_date, "updated_date": current_date
                }
            )
            conn.commit()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('personality_create_action.html')

#パーソナリティ更新
@app.route("/personality_update_input")
def personality_update_input():
    id = request.args.get('id', type=int)
    query = """
        SELECT *
          FROM personality
         WHERE id = :id
    """
    stmt = sqlalchemy.text(query)
    stmt2 = sqlalchemy.text("SELECT * FROM sex ORDER BY sex")
    stmt3 = sqlalchemy.text("SELECT * FROM stereo_type ORDER BY stereo_type")
    try:
        with db.connect() as conn:
            res = conn.execute(stmt, parameters={"id": id})
            personality = res.fetchone()

            res2 = conn.execute(stmt2)
            sexes = res2.fetchall()

            res3 = conn.execute(stmt3)
            stereo_types = res3.fetchall()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('personality_update_input.html', personality=personality, sexes=sexes, stereo_types=stereo_types)

@app.route("/personality_update_action", methods=['POST'])
def personality_update_action():
    id = request.form.get('id', type=int)
    name = request.form.get('name')
    mail = request.form.get('mail')
    sex = request.form.get('sex', type=int)
    age = request.form.get('age', type=int)
    basic_info = request.form.get('basic_info')
    career_info = request.form.get('career_info')
    stereo_type = request.form.get('stereo_type', type=int)
    detail_info = request.form.get('detail_info')
    
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    stmt_sex = sqlalchemy.text("SELECT * FROM sex WHERE sex = :sex")
    stmt_stereo_type = sqlalchemy.text("SELECT * FROM stereo_type WHERE stereo_type = :stereo_type")
    try:
        with db.connect() as conn:
            res_sex = conn.execute(stmt_sex, parameters={"sex": sex})
            sex_name = res_sex.fetchone().sex_name

            res_stereo_types = conn.execute(stmt_stereo_type, parameters={"stereo_type": stereo_type})
            stereo_content = res_stereo_types.fetchone().stereo_content
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    system_message = "あなたは優秀なライター兼パーソナリティ心理学者です。次の個人の性格情報を要約して、日本語で500文字程度にしてください。個人名などは使わないでください。"
    personality_data = basic_info + ":" + career_info + ":" + stereo_content + ":" +detail_info
    response = llm.invoke(
        [
            SystemMessage(content=system_message), 
            HumanMessage(content=personality_data)
        ]
    )
    personality_summary = response

    query = """
        UPDATE personality
           SET name = :name,
               mail = :mail,
               sex = :sex,
               age = :age,
               basic_info = :basic_info,
               career_info = :career_info,
               stereo_type = :stereo_type,
               detail_info = :detail_info,
               personality_summary = :personality_summary,
               updated_date = :updated_date
         WHERE id = :id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            conn.execute(
                stmt, parameters={
                    "id": id, "name": name, "mail": mail, "sex": sex, "age": age,
                    "basic_info": basic_info, "career_info": career_info,
                    "stereo_type": stereo_type, "detail_info": detail_info,
                    "personality_summary": personality_summary, "updated_date": current_date
                }
            )
            conn.commit()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    personality = {
        'id' : id,
    }
    return render_template('personality_update_action.html', personality=personality)

#パーソナリティ削除
@app.route("/personality_delete_input")
def personality_delete_input():
    id = request.args.get('id', type=int)
    query = """
        SELECT * FROM personality where id = :id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            res = conn.execute(stmt, parameters={"id": id})
            personality = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('personality_delete_input.html', personality=personality)

@app.route("/personality_delete_action", methods=['POST'])
def personality_delete_action():
    id = request.form.get('id', type=int)
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    query = """
        UPDATE personality
           SET deleted_date = :deleted_date
         WHERE id = :id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            conn.execute(stmt, parameters={"id": id, "deleted_date": current_date})
            conn.commit()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('personality_delete_action.html')

####################################################################
# chatサービス
@app.route("/chat_list")
def chat_list():
    query = """
        SELECT p.*, s.sex_name, st.stereo_name
          FROM personality as p
          JOIN sex as s ON p.sex = s.sex
          JOIN stereo_type as st ON p.stereo_type = st.stereo_type
         WHERE p.deleted_date is null
         ORDER BY p.id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            res = conn.execute(stmt, parameters={})
            personalities = res.fetchall()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('chat_list.html', personalities=personalities)

@app.route("/chat_service")
def chat_service():
    global memory
    global chat_personality

    id = request.args.get('id', type=int)

    query = """
        SELECT * FROM personality WHERE id = :id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            res = conn.execute(stmt, parameters={"id": id})
            personality = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    sys_msg = "あなたは次に示すような人物です。" + personality.personality_summary + "あなたはこの人物になりきって、回答してみてください。回答は100文字程度でお願いします。回答はマークダウン形式で出力してください。"

    memory.clear()  # メモリーの初期化（新しい会話になっているため）
    memory.chat_memory.add_user_message(sys_msg)

    return render_template('chat_service.html', personality=personality)

@app.route("/chat", methods=['POST'])
def chat():
    #logger.error("---- chat start ---")
    global chain
    global chat_personality

    data = request.get_json()
    message = data['message']

    messages = chain.memory.load_memory_variables({})

    #logger.warning(f"保存されている件数： {len(messages)}")
    #logger.warning(str(messages))
    result=chain(message)

    #logger.warning(str(result))
    #logger.warning(str(chat_personality))

    response_api = {
        'answer': result["response"]
    }

    return jsonify(response_api) 

####################################################################
# AIミーティング
# AIミーティング一覧
@app.route("/meeting_list")
def meeting_list():
    query = """
        SELECT m.*, ms.meeting_status_name
          FROM meeting as m
          JOIN meeting_status as ms ON m.meeting_status = ms.meeting_status
         ORDER BY meeting_id
    """
    stmt = sqlalchemy.text(query)

    query2 = """
        SELECT mp.meeting_id, p.name
          FROM meeting_personality as mp
          JOIN personality as p ON mp.id = p.id
         ORDER BY mp.meeting_id, mp.id
    """
    stmt2 = sqlalchemy.text(query2)
    try:
        with db.connect() as conn:
            res1 = conn.execute(stmt)
            meetings = res1.fetchall()

            res2 = conn.execute(stmt2)
            meeting_personalities = res2.fetchall()

            #logger.warning(str(meeting_personalities))
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('meeting_list.html', meetings=meetings, meeting_personalities=meeting_personalities)

# AIミーティング詳細
@app.route("/meeting_detail")
def meeting_detail():
    meeting_id = request.args.get('meeting_id', type=int)
    query = """
        SELECT m.*, ms.meeting_status_name
          FROM meeting as m
          JOIN meeting_status as ms ON m.meeting_status = ms.meeting_status
         WHERE meeting_id = :meeting_id
    """
    stmt = sqlalchemy.text(query)

    query2 = """
        SELECT mp.meeting_id, p.name
          FROM meeting_personality as mp
          JOIN personality as p ON mp.id = p.id
         WHERE mp.meeting_id = :meeting_id
         ORDER BY mp.meeting_id, mp.id
    """
    stmt2 = sqlalchemy.text(query2)
    try:
        with db.connect() as conn:
            res = conn.execute(stmt, parameters={"meeting_id": meeting_id})
            meeting = res.fetchone()

            res2 = conn.execute(stmt2, parameters={"meeting_id": meeting_id})
            meeting_personalities = res2.fetchall()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('meeting_detail.html', meeting=meeting, meeting_personalities=meeting_personalities)

# AI会議登録入力画面
@app.route("/meeting_create_input")
def meeting_create_input():
    query = """
        SELECT p.*, s.sex_name, st.stereo_name
          FROM personality as p
          JOIN sex as s ON p.sex = s.sex
          JOIN stereo_type as st ON p.stereo_type = st.stereo_type
         WHERE p.deleted_date is null
         ORDER BY p.id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            personalities = conn.execute(stmt, parameters={})
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('meeting_create_input.html', personalities=personalities)

# AI会議登録完了画面
@app.route("/meeting_create_action", methods=['POST'])
def meeting_create_action():
    ids = request.form.getlist('ids') # personality.id for checkbox
    theme = request.form.get('theme')
    
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    query = """
        INSERT INTO meeting (theme, meeting_status, registered_date, updated_date) 
        VALUES ( :theme, :meeting_status, :registered_date, :updated_date)
    """
    stmt = sqlalchemy.text(query)
    stmt2= sqlalchemy.text("SELECT MAX( meeting_id ) as meeting_id FROM meeting")
    stmt3= sqlalchemy.text("INSERT INTO meeting_personality (meeting_id, id) VALUES (:meeting_id, :id)")

    try:
        with db.connect() as conn:
            
            # TODO コミット前にmeeting_idを取得して、関連テーブルとまとめてコミットするようにする。Insert時の戻り値（Cursor）は何が入ってくるかは確認したい。
            conn.execute(
                stmt, parameters={
                    "theme": theme, "meeting_status": 1, "registered_date": current_date, "updated_date": current_date
                }
            )
            conn.commit()

            meetings = conn.execute(stmt2)
            for meeting in meetings:
              meeting_id = meeting.meeting_id

            for id in ids:
              conn.execute(stmt3, parameters={"meeting_id": meeting_id, "id": id})

            conn.commit()

    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('meeting_create_action.html')

####################################################################
# AIアンケート
# AIアンケート一覧
@app.route("/questionnaire_list")
def questionnaire_list():
    query = """
        SELECT q.*, sr.sex_range_content, ar.age_range_content, qs.questionnaire_status_name
          FROM questionnaire as q
          JOIN sex_range as sr ON q.sex_range = sr.sex_range
          JOIN age_range as ar ON q.age_range = ar.age_range
          JOIN questionnaire_status as qs ON q.questionnaire_status = qs.questionnaire_status
         ORDER BY questionnaire_id
    """
    stmt = sqlalchemy.text(query)

    try:
        with db.connect() as conn:
            res = conn.execute(stmt)
            questionnaires = res.fetchall()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('questionnaire_list.html', questionnaires=questionnaires)

# AIアンケート詳細
@app.route("/questionnaire_detail")
def questionnaire_detail():
    questionnaire_id = request.args.get('questionnaire_id', type=int)
    query = """
        SELECT q.*, sr.sex_range_content, ar.age_range_content, qs.questionnaire_status_name
          FROM questionnaire as q
          JOIN sex_range as sr ON q.sex_range = sr.sex_range
          JOIN age_range as ar ON q.age_range = ar.age_range
          JOIN questionnaire_status as qs ON q.questionnaire_status = qs.questionnaire_status
         WHERE questionnaire_id = :questionnaire_id
    """
    stmt = sqlalchemy.text(query)
    try:
        with db.connect() as conn:
            res = conn.execute(stmt, parameters={"questionnaire_id": questionnaire_id})
            questionnaire = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('questionnaire_detail.html', questionnaire=questionnaire)

# AIアンケート登録入力画面
@app.route("/questionnaire_create_input")
def questionnaire_create_input():
    return render_template('questionnaire_create_input.html')

# AIアンケート登録完了画面
@app.route("/questionnaire_create_action", methods=['POST'])
def questionnaire_create_action():
    question = request.form.get('question')
    sex_range = request.form.get('sex_range', type=int)
    age_range = request.form.get('age_range', type=int)
    
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    query = """
        INSERT INTO questionnaire (question, sex_range, age_range, questionnaire_status, registered_date, updated_date) 
        VALUES ( :question, :sex_range, :age_range, :questionnaire_status, :registered_date, :updated_date)
    """
    stmt = sqlalchemy.text(query)

    try:
        with db.connect() as conn:
            
            conn.execute(
                stmt, parameters={
                    "question": question, "sex_range": sex_range, "age_range": age_range, "questionnaire_status": 1,
                    "registered_date": current_date, "updated_date": current_date})
            conn.commit()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('questionnaire_create_action.html')

##########################
# その他
# what's personality AI
@app.route("/whats_personalityai")
def whats_personalityai():
    return render_template('whats_personalityai.html')

@app.route("/use_case_list")
def use_case_list():
    return render_template('use_case_list.html')

@app.route("/idea_list")
def idea_list():
    return render_template('idea_list.html')

# 履歴
@app.route("/history")
def history():
    return render_template('history.html')

# バックログ
@app.route("/backlogs")
def backlogs():
    return render_template('backlogs.html')

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
