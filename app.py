import os
import requests
import re
import uuid
import time
from bs4 import BeautifulSoup
from flask import Flask, render_template_string

app = Flask(__name__)

# ⚠️ এখানে আপনার টার্গেট ওয়েবসাইটের লিংক দিন
TARGET_SITES = ["https://desibp1.com"] 

# Vercel এর জন্য টেম্পোরারি ক্যাশ মেমোরি
CACHE = {
    "videos":[],
    "last_updated": 0
}
CACHE_DURATION = 600 # ১০ মিনিট (৬০০ সেকেন্ড)

def get_stream_link(page_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(page_url, headers=headers, timeout=5)
        content = res.text
        m3u8 = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', content)
        if m3u8: return m3u8[0]
        mp4 = re.findall(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', content)
        if mp4: return mp4[0]
        return None
    except:
        return None

def fetch_videos_now():
    videos =[]
    for site in TARGET_SITES:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(site, headers=headers, timeout=8)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Vercel-এ টাইমআউট এড়াতে প্রথম ১৫টি লেটেস্ট ভিডিও চেক করবে
            for a in soup.find_all('a')[:15]: 
                img = a.find('img')
                page_link = a.get('href')
                
                if img and page_link and page_link.startswith('http'):
                    thumb = img.get('src') or img.get('data-src')
                    title = img.get('alt') or "New Video"
                    if thumb and thumb.startswith('//'): thumb = "https:" + thumb
                        
                    stream_url = get_stream_link(page_link)
                    if stream_url:
                        videos.append({
                            "id": str(uuid.uuid4())[:8],
                            "title": title,
                            "thumb": thumb,
                            "url": stream_url
                        })
        except Exception as e:
            print(f"Error: {e}")
    return videos

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 Auto Video Hub</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }</style>
</head>
<body class="bg-gray-900 text-white font-sans">
    <nav class="bg-gray-800 p-3 shadow-lg flex justify-between items-center border-b border-gray-700 sticky top-0 z-50">
        <a href="/" class="text-xl font-bold text-indigo-500 flex items-center gap-2">🎬 Auto Video Hub</a>
        <a href="/" class="bg-indigo-600 px-3 py-1.5 rounded hover:bg-indigo-500 text-xs font-bold text-white shadow-md">🔄 Refresh Latest</a>
    </nav>

    {% if current_video %}
    <div class="container mx-auto p-2 sm:p-4 max-w-4xl mt-2 block">
        <a href="/" class="inline-block mb-4 bg-gray-700 text-white px-3 py-1.5 rounded text-sm font-bold shadow">🔙 ফিরে যান</a>
        <div class="bg-black rounded-lg overflow-hidden shadow-2xl relative border border-gray-800">
            <video id="main-player" controls autoplay class="w-full aspect-video" controlsList="nodownload"></video>
        </div>
        <div class="bg-gray-800 p-4 mt-4 rounded-lg shadow-lg border border-gray-700">
            <h1 class="text-lg sm:text-xl font-bold text-white mb-2">{{ current_video.title }}</h1>
        </div>
    </div>
    <script>
        var url = "{{ current_video.url }}";
        var player = document.getElementById('main-player');
        if (url.includes('.m3u8')) {
            if (Hls.isSupported()) {
                var hls = new Hls(); hls.loadSource(url); hls.attachMedia(player);
                hls.on(Hls.Events.MANIFEST_PARSED, function() { player.play(); });
            } else if (player.canPlayType('application/vnd.apple.mpegurl')) { player.src = url; player.play(); }
        } else { player.src = url; player.play(); }
    </script>
    {% else %}
    <div class="container mx-auto p-4 block">
        <h2 class="text-lg font-bold mb-4 border-b border-gray-700 pb-2 flex justify-between">🔥 Latest Updates</h2>
        {% if videos %}
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 sm:gap-4">
            {% for video in videos %}
            <a href="/watch/{{ video.id }}" class="bg-gray-800 rounded-lg overflow-hidden shadow-md hover:shadow-xl transition border border-gray-700 group block">
                <div class="relative">
                    <img src="{{ video.thumb }}" class="w-full h-28 sm:h-32 object-cover group-hover:opacity-75 transition">
                    <div class="absolute bottom-1 right-1 bg-black bg-opacity-80 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">▶ Play</div>
                </div>
                <div class="p-2.5">
                    <h3 class="font-semibold text-xs text-gray-200 line-clamp-2">{{ video.title }}</h3>
                </div>
            </a>
            {% endfor %}
        </div>
        {% else %}
        <p class="text-center text-gray-400 mt-10 animate-pulse">ভিডিও আনা হচ্ছে... একটু অপেক্ষা করুন।</p>
        {% endif %}
    </div>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def home():
    current_time = time.time()
    # যদি ক্যাশ খালি থাকে বা ১০ মিনিট পার হয়ে যায়, তবে নতুন করে স্ক্র্যাপ করবে
    if not CACHE["videos"] or (current_time - CACHE["last_updated"] > CACHE_DURATION):
        CACHE["videos"] = fetch_videos_now()
        CACHE["last_updated"] = current_time
        
    return render_template_string(HTML_TEMPLATE, videos=CACHE["videos"], current_video=None)

@app.route('/watch/<video_id>')
def watch(video_id):
    video = next((v for v in CACHE["videos"] if v['id'] == video_id), None)
    if video:
        return render_template_string(HTML_TEMPLATE, videos=None, current_video=video)
    return "<body style='background:#111; color:white; text-align:center;'><h1 style='margin-top:50px;'>Video Not Found!</h1><a href='/' style='color:#6366f1;'>Go Home</a></body>", 404

# Vercel এর জন্য এটি দরকার (লোকাল পিসির জন্য)
if __name__ == '__main__':
    app.run(debug=True)
