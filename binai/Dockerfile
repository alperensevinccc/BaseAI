# BaseAI için standart Python 3.10 imajını temel al
FROM python:3.10-slim

# Çalışma dizinini ayarla
WORKDIR /app/binai

# Bağımlılıkları kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala (Sonraki adımlarda eklenecek)
COPY . .

# Konteyner çalıştığında varsayılan komut (main.py'yi çalıştıracak)
CMD ["python", "main.py"]