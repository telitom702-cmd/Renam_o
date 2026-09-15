FROM python:3.11-slim

# এনভায়রনমেন্ট ভেরিয়েবল সেট করা
ENV PYTHONUNBUFFERED=1

# ওয়ার্ক ডিরেক্টরি সেট করা
WORKDIR /video_bot

# সিস্টেম ডিপেন্ডেন্সি (FFmpeg) ইন্সটল করা
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# পাইথন রিকোয়ারমেন্ট ইন্সটল করা
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# বাকি সব ফাইল কপি করা
COPY . .

# বট চালু করার কমান্ড
CMD ["python", "bot.py"]
