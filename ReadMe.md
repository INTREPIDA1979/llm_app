# パーソナリティAIの環境構築について
## 用意するもの
- Google Cloud 
  - プロジェクト（プロジェクトID）
  - サービスアカウント（SQLクライアント、VertexAIユーザ権限あり）
  - CloudSQL（MySQL）、データベースも作成しておく
  - GitHubから以下のソースコードをダウンロードしておく。
    - https://github.com/INTREPIDA1979/llm_app
    - https://github.com/INTREPIDA1979/llm_meeting_batch
    - https://github.com/INTREPIDA1979/llm_questionnaire_batchあああ

## データベースの初期化
以下のコマンドでデータベースにアクセスする。
```
gcloud sql connect {インスタンス名} --user={DB_USER}
```

```
use {データベース名};
```

以下のSQLを実行する。
- llm_app/database/create_table_and_insert.sql

## Webアプリ環境の構築
以下のコマンドを実行する。
```
#/bin/sh
# set environment valiables
PROJECT_ID={PROJECT_ID}
REGION={REGION}
AR_REPO=llm-app
SERVICE_NAME=llm-app
SA_NAME={SERVICE_ACCONT_NAME}
DB_USER={DB_USER}
DB_PASS={DB_PASSWORD}
DB_NAME={DB_NAME}
INSTANCE_NAME={DB_INSTANCE}
GOOGLE_AI={GEMINI or VERTEX_AI}
GOOGLE_API_KEY={GOOGLE_API_KEY}

# プロジェクト設定の変更
gcloud config set project ${PROJECT_ID}

# API有効化
gcloud services enable --project=$PROJECT_ID run.googleapis.com \
 artifactregistry.googleapis.com \
 cloudbuild.googleapis.com \
 compute.googleapis.com \
 aiplatform.googleapis.com \
 iap.googleapis.com

# Artifacts repositories 作成(Webapp)
gcloud artifacts repositories create $AR_REPO \
 --location=$REGION \
 --repository-format=Docker \
 --project=$PROJECT_ID
  
# Deploy
cd llm_app
./deploy.sh
```

# AIミーティングバッチの構築
```AR_REPO=llm-meeting_batch
SERVICE_NAME=llm-meeting_batch

# Artifacts repositories 作成(AI Meeting batch)
gcloud artifacts repositories create $AR_REPO \
 --location=$REGION \
 --repository-format=Docker \
 --project=$PROJECT_ID

# deploy & execute
cd 
cd llm-meeting-batch
./deploy_create.sh

# (option) update & execute
./deploy_update.sh

# (option) execute only
./execute.sh
```

# AIアンケートバッチの構築
```
AR_REPO=llm-questionnaire_batch
SERVICE_NAME=llm-questionnaire_batch

(以降の手順は、AIミーティングバッチの構築と同じ)
```