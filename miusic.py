from flask import Flask, request, jsonify, render_template_string
import yt_dlp
import subprocess
import os
import socket
import json
import threading
import time

app = Flask(__name__)

# Config
MPV_SOCKET = "/tmp/mpv_socket"
current_metadata = {"title": "Not Playing", "id": "", "thumb": "", "uploader": ""}
current_playlist = []
current_index = -1

# ---------- MPV Logic ----------
def start_mpv():
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return
        
    if os.path.exists(MPV_SOCKET):
        try:
            os.remove(MPV_SOCKET)
        except:
            pass

    subprocess.Popen([
        "mpv",
        "--no-video",
        "--idle=yes",
        f"--input-ipc-server={MPV_SOCKET}"
    ])

def mpv_send(cmd):
    try:
        s = socket.socket(socket.AF_UNIX)
        s.connect(MPV_SOCKET)
        s.send((json.dumps(cmd) + "\n").encode())
        data = s.recv(4096)
        s.close()
        return json.loads(data.decode())
    except Exception as e:
        return {"error": str(e)}

def mpv_get(prop):
    res = mpv_send({"command": ["get_property", prop]})
    return res.get("data", 0)

# ---------- Trending / Default Songs ----------
TRENDING_SONGS = [
    {"id": "V7LwfY5U5WI", "title": "Kesariya - Brahmastra", "uploader": "Arijit Singh", "thumb": "https://img.youtube.com/vi/V7LwfY5U5WI/mqdefault.jpg"},
    {"id": "G62C0Vv-1m0", "title": "Pehle Bhi Main - Animal", "uploader": "Vishal Mishra", "thumb": "https://img.youtube.com/vi/G62C0Vv-1m0/mqdefault.jpg"},
    {"id": "87V-P6fT9EY", "title": "Tumi Jake Bhalobasho", "uploader": "Iman Chakraborty", "thumb": "https://img.youtube.com/vi/87V-P6fT9EY/mqdefault.jpg"},
    {"id": "N9C776p98rE", "title": "Behula - Shunno", "uploader": "Shunno", "thumb": "https://img.youtube.com/vi/N9C776p98rE/mqdefault.jpg"},
    {"id": "n9L_X26W9vQ", "title": "Mon Majhi Re", "uploader": "Arijit Singh", "thumb": "https://img.youtube.com/vi/n9L_X26W9vQ/mqdefault.jpg"},
    {"id": "D_yX9G6l9iY", "title": "Lollipop Lagelu", "uploader": "Pawan Singh", "thumb": "https://img.youtube.com/vi/D_yX9G6l9iY/mqdefault.jpg"},
    {"id": "FvJ95G65t-0", "title": "Raja Ji", "uploader": "Pawan Singh", "thumb": "https://img.youtube.com/vi/FvJ95G65t-0/mqdefault.jpg"}
]

# ---------- Routes ----------

@app.route("/trending")
def trending():
    global current_playlist
    current_playlist = TRENDING_SONGS
    return jsonify(TRENDING_SONGS)

@app.route("/search")
def search():
    global current_playlist
    query = request.args.get("q")
    if not query:
        return jsonify([])
    
    results = []
    ydl_opts = {"quiet": True, "extract_flat": True, "skip_download": True}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # High limit for search results
            info = ydl.extract_info(f"ytsearch25:{query}", download=False)
            for entry in info.get("entries", []):
                results.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "thumb": entry["thumbnails"][0]["url"] if entry.get("thumbnails") else "",
                    "uploader": entry.get("uploader", "Unknown")
                })
        current_playlist = results
    except Exception as e:
        print(f"Search error: {e}")
        
    return jsonify(results)

@app.route("/play")
def play():
    global current_metadata, current_index
    vid = request.args.get("id")
    
    for i, s in enumerate(current_playlist):
        if s["id"] == vid:
            current_index = i
            current_metadata = s
            break

    mpv_send({
        "command": ["loadfile", f"https://www.youtube.com/watch?v={vid}", "replace"]
    })
    return "OK"

@app.route("/control/<cmd>")
def control(cmd):
    global current_index, current_metadata
    if cmd == "pause":
        mpv_send({"command": ["cycle", "pause"]})
    elif cmd == "next":
        if current_index < len(current_playlist) - 1:
            current_index += 1
            s = current_playlist[current_index]
            current_metadata = s
            mpv_send({"command": ["loadfile", f"https://www.youtube.com/watch?v={s['id']}", "replace"]})
    elif cmd == "prev":
        if current_index > 0:
            current_index -= 1
            s = current_playlist[current_index]
            current_metadata = s
            mpv_send({"command": ["loadfile", f"https://www.youtube.com/watch?v={s['id']}", "replace"]})
    return "OK"

@app.route("/seek")
def seek():
    pos = request.args.get("pos")
    mpv_send({"command": ["set_property", "time-pos", float(pos)]})
    return "OK"

@app.route("/status")
def status():
    return jsonify({
        "time": mpv_get("time-pos"),
        "duration": mpv_get("duration"),
        "paused": mpv_get("pause"),
        "idle": mpv_get("idle-active"), # Check if player is finished
        "meta": current_metadata
    })

# ---------- UI ----------
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tune Wave</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { background-color: #0d0d0d; color: #e2e2e2; font-family: 'Plus Jakarta Sans', sans-serif; }
        .m3-card { background: #1a1a1a; border-radius: 24px; transition: all 0.3s ease; }
        .m3-card:hover { background: #252525; transform: scale(1.02); }
        input[type="range"] { accent-color: #1db954; }
        .custom-scroll::-webkit-scrollbar { width: 6px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
        #loading-overlay { display: none; background: rgba(0,0,0,0.9); z-index: 100; }
    </style>
</head>
<body class="flex flex-col h-screen overflow-hidden">

    <!-- Loading Overlay -->
    <div id="loading-overlay" class="fixed inset-0 flex flex-col items-center justify-center">
        <div class="animate-spin w-16 h-16 border-4 border-green-500 border-t-transparent rounded-full mb-4"></div>
        <p class="text-lg font-semibold">Loading song...</p>
    </div>

    <!-- Header -->
    <header class="p-6 flex items-center justify-between">
        <div class="flex items-center gap-3">
            <div class="bg-green-500 p-2 rounded-xl"><i data-lucide="waves" class="text-black w-6 h-6"></i></div>
            <h1 class="text-2xl font-bold tracking-tight">Tune Wave</h1>
        </div>
        <div class="relative w-1/2 max-w-md">
            <input id="search-input" type="text" 
                class="w-full bg-[#1a1a1a] border-none rounded-full py-3 px-12 focus:ring-2 focus:ring-green-500 outline-none" 
                placeholder="Search songs, artists..."
                onkeyup="if(event.key==='Enter')performSearch()">
            <i data-lucide="search" class="absolute left-4 top-3.5 text-gray-400 w-5 h-5"></i>
        </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 overflow-y-auto px-6 custom-scroll pb-32">
        <div id="section-title" class="mb-6">
            <h2 class="text-xl font-bold">Recommended for You</h2>
        </div>
        <div id="results-grid" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6"></div>
    </main>

    <!-- Bottom Player -->
    <div class="fixed bottom-0 left-0 right-0 p-4">
        <div class="m3-card p-4 flex items-center gap-6 shadow-2xl border border-white/5 backdrop-blur-lg">
            
            <div class="flex items-center gap-4 w-1/4">
                <img id="player-thumb" src="https://via.placeholder.com/60" class="w-14 h-14 rounded-xl object-cover">
                <div class="overflow-hidden">
                    <h3 id="player-title" class="font-bold truncate text-sm">No song playing</h3>
                    <p id="player-status" class="text-xs text-gray-400 truncate">Tune Wave Player</p>
                </div>
            </div>

            <div class="flex-1 flex flex-col items-center">
                <div class="flex items-center gap-6 mb-2">
                    <button onclick="sendCtrl('prev')" class="hover:text-green-500 transition"><i data-lucide="skip-back"></i></button>
                    <button id="play-btn" onclick="sendCtrl('pause')" class="bg-white text-black p-3 rounded-full hover:scale-105 transition">
                        <i data-lucide="play" fill="black"></i>
                    </button>
                    <button onclick="sendCtrl('next')" class="hover:text-green-500 transition"><i data-lucide="skip-forward"></i></button>
                </div>
                <div class="w-full flex items-center gap-3 px-4 text-xs font-mono text-gray-400">
                    <span id="time-curr">0:00</span>
                    <input type="range" id="seek-bar" class="flex-1 h-1 rounded-lg appearance-none cursor-pointer" value="0" step="1" oninput="manualSeek(this.value)">
                    <span id="time-total">0:00</span>
                </div>
            </div>

            <div class="w-1/4 flex justify-end">
                <div class="bg-green-500/10 text-green-500 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider">
                    High Quality
                </div>
            </div>
        </div>
    </div>

    <script>
        lucide.createIcons();
        let isSeeking = false;
        let isLoading = false;

        function formatTime(s) {
            if (!s) return "0:00";
            let min = Math.floor(s / 60);
            let sec = Math.floor(s % 60);
            return `${min}:${sec < 10 ? '0' : ''}${sec}`;
        }

        async function loadTrending() {
            const r = await fetch('/trending');
            const data = await r.json();
            renderSongs(data);
        }

        async function performSearch() {
            const q = document.getElementById('search-input').value;
            if(!q) return loadTrending();
            const grid = document.getElementById('results-grid');
            grid.innerHTML = '<div class="col-span-full text-center py-20 animate-pulse">Searching...</div>';
            const r = await fetch(`/search?q=${encodeURIComponent(q)}`);
            const data = await r.json();
            renderSongs(data);
        }

        function renderSongs(data) {
            const grid = document.getElementById('results-grid');
            grid.innerHTML = '';
            data.forEach(song => {
                grid.innerHTML += `
                    <div class="m3-card p-4 cursor-pointer group" onclick="playSong('${song.id}')">
                        <div class="relative overflow-hidden rounded-2xl mb-3 aspect-square">
                            <img src="${song.thumb}" class="object-cover w-full h-full">
                            <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition">
                                <i data-lucide="play" class="w-12 h-12 text-white"></i>
                            </div>
                        </div>
                        <h4 class="font-semibold text-sm line-clamp-2">${song.title}</h4>
                        <p class="text-xs text-gray-500 mt-1">${song.uploader}</p>
                    </div>`;
            });
            lucide.createIcons();
        }

        function playSong(id) {
            isLoading = true;
            document.getElementById('loading-overlay').style.display = 'flex';
            fetch(`/play?id=${id}`);
        }

        function sendCtrl(c) { 
            // Trigger loading screen for Next/Prev
            if (c === 'next' || c === 'prev') {
                isLoading = true;
                document.getElementById('loading-overlay').style.display = 'flex';
            }
            fetch(`/control/${c}`); 
        }

        function manualSeek(val) {
            isSeeking = true;
            fetch(`/seek?pos=${val}`).then(() => { isSeeking = false; });
        }

        window.onload = loadTrending;

        setInterval(async () => {
            try {
                const r = await fetch('/status');
                const s = await r.json();
                
                if (s.meta.title && s.meta.title !== "Not Playing") {
                    document.getElementById('player-title').innerText = s.meta.title;
                    document.getElementById('player-thumb').src = s.meta.thumb;
                    document.getElementById('player-status').innerText = s.meta.uploader;
                    
                    // Hide loading once track starts or metadata changes properly
                    if (isLoading && s.time > 0) {
                        isLoading = false;
                        document.getElementById('loading-overlay').style.display = 'none';
                    }

                    // Autoplay logic
                    if (s.idle && !isLoading && !s.paused && s.meta.id !== "") {
                        sendCtrl('next');
                    }
                }

                if (s.duration && !isSeeking) {
                    const seek = document.getElementById('seek-bar');
                    seek.max = s.duration;
                    seek.value = s.time || 0;
                    document.getElementById('time-curr').innerText = formatTime(s.time);
                    document.getElementById('time-total').innerText = formatTime(s.duration);
                }

                const playBtn = document.getElementById('play-btn');
                playBtn.innerHTML = s.paused ? '<i data-lucide="play" fill="black"></i>' : '<i data-lucide="pause" fill="black"></i>';
                lucide.createIcons();
            } catch (e) {}
        }, 1000);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    start_mpv()
    app.run(host="0.0.0.0", port=5000, debug=True)