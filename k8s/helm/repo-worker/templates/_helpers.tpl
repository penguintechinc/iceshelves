{{/*
Expand the name of the chart.
*/}}
{{- define "repo-worker.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "repo-worker.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "repo-worker.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "repo-worker.labels" -}}
helm.sh/chart: {{ include "repo-worker.chart" . }}
{{ include "repo-worker.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "repo-worker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "repo-worker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Get the S3 secret name
*/}}
{{- define "repo-worker.s3SecretName" -}}
{{- if .Values.storage.s3.existingSecret }}
{{- .Values.storage.s3.existingSecret }}
{{- else }}
{{- printf "%s-s3" (include "repo-worker.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Get the auth secret name
*/}}
{{- define "repo-worker.authSecretName" -}}
{{- if .Values.auth.existingSecret }}
{{- .Values.auth.existingSecret }}
{{- else }}
{{- printf "%s-auth" (include "repo-worker.fullname" .) }}
{{- end }}
{{- end }}
