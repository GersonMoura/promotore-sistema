# Use Python 3.11 slim
FROM python:3.11-slim

# Instalar dependências do sistema (poppler para pdf2image)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar pasta de uploads
RUN mkdir -p static/uploads

# Expor porta 8080
EXPOSE 8080

# Usar bash para executar start.sh
CMD ["bash", "start.sh"]

