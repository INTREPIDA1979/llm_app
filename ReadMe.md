# パーソナリティAIの環境構築について
## 用意するもの
- Google Cloud 
  - プロジェクト（プロジェクトID）
  - サービスアカウント（SQLクライアント、VertexAIユーザ権限あり）
  - CloudSQL（MySQL）、データベースも作成しておく
  - GitHubから以下のソースコードをダウンロードしておく。
    - https://github.com/INTREPIDA1979/llm_app
    - https://github.com/INTREPIDA1979/llm_meeting_batch
    - https://github.com/INTREPIDA1979/llm_questionnaire_batch

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
  
# PUSH to Artifact Registry
cd
cd llm_app

gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --project=$PROJECT_ID

# deploy to Cloud Run
gcloud run deploy $SERVICE_NAME --port 7860 \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --service-account=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \
  --region=$REGION \
  --set-env-vars=PROJECT_ID=$PROJECT_ID,LOCATION=$REGION \
  --project=$PROJECT_ID \
  --set-env-vars INSTANCE_CONNECTION_NAME=$PROJECT_ID:$REGION:$INSTANCE_NAME \
  --set-env-vars DB_USER=$DB_USER \
  --set-env-vars DB_PASS=$DB_PASS \
  --set-env-vars DB_NAME=$DB_NAME
```

# AIミーティングバッチの構築
```
#/bin/sh
# set environment valiables
PROJECT_ID={PROJECT_ID}
REGION={REGION}
AR_REPO=llm-meeting-batch
SERVICE_NAME=llm-meeting-batch
SA_NAME={SERVICE_ACCUNT_NAME}
DB_USER={DB_USER}
DB_PASS={DB_PASS}
DB_NAME={DB_NAME}
INSTANCE_NAME={INSTANCE_NAME}
INSTANCE_CONNECTION_NAME='{PROJECT_ID}:{REGION}:{INSTANCE_NAME}'
#GOOGLE_AI='GEMINI'
GOOGLE_AI='VERTEX_AI'
#GOOGLE_API_KEY='{GOOGLE_API_KEY}'

# Artifacts repositories 作成(AI Meeting batch)
gcloud artifacts repositories create $AR_REPO \
 --location=$REGION \
 --repository-format=Docker \
 --project=$PROJECT_ID

# PUSH to Artifact Registry
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --project=$PROJECT_ID

# create to Cloud Run
cd 
cd llm-meeting-batch
gcloud run jobs create llm-meeting-batch \
 --image $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
 --service-account=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \
 --region=$REGION \
 --set-env-vars=PROJECT_ID=$PROJECT_ID,LOCATION=$REGION \
 --project=$PROJECT_ID \
 --tasks=1 \
 --cpu=1 \
 --max-retries=0 \
 --memory=512Mi \
 --parallelism=1 \
 --task-timeout=100 \
 --set-env-vars INSTANCE_CONNECTION_NAME=$INSTANCE_CONNECTION_NAME \
 --set-env-vars DB_USER=$DB_USER \
 --set-env-vars DB_PASS=$DB_PASS \
 --set-env-vars DB_NAME=$DB_NAME \
 --set-env-vars GOOGLE_AI=$GOOGLE_AI \
 --set-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY 

gcloud run jobs execute $SERVICE_NAME --region=$REGION

# (option) update & execute
# PUSH to Artifact Registry
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --project=$PROJECT_ID

# update to Cloud Run
gcloud run jobs update llm-meeting-batch \
 --region=$REGION \
 --set-env-vars=PROJECT_ID=$PROJECT_ID,LOCATION=$REGION \
 --project=$PROJECT_ID \
 --set-env-vars INSTANCE_CONNECTION_NAME=$INSTANCE_CONNECTION_NAME \
 --set-env-vars DB_USER=$DB_USER \
 --set-env-vars DB_PASS=$DB_PASS \
 --set-env-vars DB_NAME=$DB_NAME \
 --set-env-vars GOOGLE_AI=$GOOGLE_AI \
 --set-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY

gcloud run jobs execute $SERVICE_NAME --region=$REGION

# (option) execute only
gcloud run jobs execute $SERVICE_NAME --region=$REGION
```

# AIアンケートバッチの構築
```
AR_REPO=llm-questionnaire_batch
SERVICE_NAME=llm-questionnaire_batch

(上記設定以外は、AIミーティングバッチの構築と同じ)
```