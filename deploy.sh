#!/usr/bin/env bash
# Deploy Blinkdrop to Cloud Run with a least-privilege runtime identity.
#
#   PROJECT=my-project REGION=europe-west1 ./deploy.sh
#
# Idempotent: re-running skips anything that already exists.
set -euo pipefail

PROJECT="${PROJECT:?set PROJECT}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-blinkdrop}"
SA_NAME="${SA_NAME:-blinkdrop-run}"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
ROLE_ID="${ROLE_ID:-blinkdropFirestore}"
SECRET="${SECRET:-blinkdrop-admin-password}"
MAX_INSTANCES="${MAX_INSTANCES:-10}"

echo "==> Enabling APIs"
gcloud services enable run.googleapis.com firestore.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com --project "$PROJECT"

echo "==> Firestore database (skipped if present)"
gcloud firestore databases create --location="$REGION" --project "$PROJECT" 2>/dev/null \
  || echo "    already exists"

echo "==> Runtime service account"
gcloud iam service-accounts create "$SA_NAME" \
  --display-name "Blinkdrop Cloud Run runtime" --project "$PROJECT" 2>/dev/null \
  || echo "    already exists"

# Deliberately omits datastore.entities.delete: the application has no business
# deleting documents, and withholding it keeps a regression from being
# destructive.
echo "==> Custom role (read/write, no delete)"
gcloud iam roles create "$ROLE_ID" --project "$PROJECT" \
  --title "Blinkdrop Firestore access" \
  --permissions "datastore.entities.create,datastore.entities.get,datastore.entities.list,datastore.entities.update,datastore.databases.get" \
  --stage GA 2>/dev/null || echo "    already exists"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role "projects/${PROJECT}/roles/${ROLE_ID}" --condition=None >/dev/null

echo "==> Admin password secret"
if ! gcloud secrets describe "$SECRET" --project "$PROJECT" >/dev/null 2>&1; then
  echo "    creating $SECRET — enter the dashboard password, then Ctrl-D:"
  gcloud secrets create "$SECRET" --data-file=- --project "$PROJECT"
fi
gcloud secrets add-iam-policy-binding "$SECRET" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/secretmanager.secretAccessor --project "$PROJECT" >/dev/null

echo "==> Deploying"
gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --service-account "$SA_EMAIL" \
  --allow-unauthenticated \
  --max-instances "$MAX_INSTANCES" \
  --set-env-vars "STORAGE_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=${PROJECT},ADMIN_AUTH=basic" \
  --set-secrets "ADMIN_PASSWORD=${SECRET}:latest"

echo
echo "Deployed. The feedback form is public; the dashboard requires the admin"
echo "password. Put Cloud Armor in front of POST /api/feedback before the pilot"
echo "carries real traffic — the in-app rate limit is per instance only."
