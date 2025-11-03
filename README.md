# PROMOTORE - Sistema de Conferência Cadastral

Sistema web para conferência cadastral com processamento de documentos via IA.

## Tecnologias

- Python 3.11
- Flask
- OpenAI GPT-4
- PostgreSQL / SQLite
- Google Cloud Run

## Deploy

Este sistema está configurado para deploy automático no Google Cloud Run.

## Variáveis de Ambiente

- `OPENAI_API_KEY`: Chave da API OpenAI (obrigatória)
- `DATABASE_URL`: URL do PostgreSQL (opcional, usa SQLite se não configurada)
- `PORT`: Porta do servidor (configurada automaticamente pelo Cloud Run)

## Login Padrão

- Usuário: `admin`
- Senha: `admin123`

**⚠️ Altere a senha após o primeiro login!**

