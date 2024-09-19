from app import db
from datetime import datetime

class Personality(db.Model):
    __tablename__ = 'personality'
    id = db.Column(db.Integer, primary_key=True)  # システムで使う番号
    name = db.Column(db.String(255))  # ニックネーム
    mail = db.Column(db.String(255))  # メールアドレス
    sex = db.Cloumn(db.Integer, default=0) # 性別
    age = db.Cloumn(db.Integer, default=0) # 年齢
    basic_info = db.Column(db.string(2000))  # 基本情報
    career_info = db.Column(db.String(2000))  # 経歴・キャリア
    stereo_type = db.Column(db.Integer, default=0)  # ステレオタイプ
    detail_info = db.Column(db.String(2000))  # 詳細パーソナル情報
    created_time = db.Column(db.DateTime, nullable=False, default=datetime.now)  # 作成日時
    updated_time = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)  # 更新日時
