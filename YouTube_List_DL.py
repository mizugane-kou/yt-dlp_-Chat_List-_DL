

#   ライブラリのインストール
#   pip install yt-dlp requests google-api-python-client tqdm mutagen pillow emoji


import yt_dlp
import os
import re
import requests
from googleapiclient.discovery import build
from tqdm import tqdm
from io import BytesIO
from mutagen.id3 import APIC, ID3
from PIL import Image
import time
import emoji

YOUTUBE_API_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # ここにYouTube Data APIのキーを入力してください



def sanitize_filename(filename):
    # 絵文字を "-" に置き換える
    filename = emoji.replace_emoji(filename, replace='-')
    # ファイル名に使えない文字を削除
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    return filename

# YouTube APIクライアントを作成
def get_youtube_api_client():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# プレイリストから動画情報を取得（URLとタイトルを返す）
def get_playlist_video_urls(playlist_url):
    # URLから余分なパラメータ（例: si=...）を取り除く
    playlist_url = playlist_url.split('&')[0]  
    playlist_id = playlist_url.split("list=")[-1]
    youtube = get_youtube_api_client()
    
    video_urls = []
    next_page_token = None
    
    while True:
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,  # 1回のリクエストで取得する動画数
            pageToken=next_page_token
        )
        response = request.execute()
        
        for item in response["items"]:
            video_urls.append({
                "id": item['snippet']['resourceId']['videoId'],
                "title": sanitize_filename(item['snippet']['title'])
            })
        
        # 次のページがあれば、続けてリクエスト
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    
    return video_urls

# サムネイル画像を保存
def save_thumbnail(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"サムネイル保存完了: {filename}")
    else:
        print(f"サムネイルの取得に失敗しました: {url}")




# カバーアートをMP3に適用
def apply_cover_art(mp3_file_path, jpg_file_path, max_size=(300, 300)):
    tags = ID3(mp3_file_path)
    
    with Image.open(jpg_file_path) as img:
        # Convert the image to RGB mode if it's not already
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size)
            
        with BytesIO() as img_byte_array:
            img.save(img_byte_array, format="JPEG")
            cover_img_byte_str = img_byte_array.getvalue()
    
    tags.add(APIC(mime="image/jpeg", type=3, data=cover_img_byte_str))
    tags.save()
    print(f"カバーアートが '{os.path.basename(mp3_file_path)}' に適用されました。")
    
    os.remove(jpg_file_path)
    print(f"サムネイル画像が削除されました: {jpg_file_path}")



# ダウンロード済みの動画タイトルを記録するファイルのパス
DOWNLOAD_HISTORY_FILE = "download_history.txt"

# ダウンロード済み動画を記録・読み込み
def load_download_history():
    if os.path.exists(DOWNLOAD_HISTORY_FILE):
        with open(DOWNLOAD_HISTORY_FILE, "r", encoding="utf-8") as file:
            return set(line.strip() for line in file.readlines())
    return set()

# ダウンロード済み動画タイトルを記録
def save_download_history(downloaded_titles):
    with open(DOWNLOAD_HISTORY_FILE, "a", encoding="utf-8") as file:
        for title in downloaded_titles:
            file.write(f"{title}\n")

# ダウンロードとサムネイルの保存

def download_audio_from_playlist(playlist_url, output_directory='DL', audio_format='mp3'):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'ignoreerrors': True,  # This helps in skipping download errors, but we'll handle them explicitly
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': audio_format,
            'preferredquality': '192',
        }],
        'outtmpl': {
            'default': f'{output_directory}/%(title)s.%(ext)s',
        },
        'quiet': False,
        'progress_hooks': [progress_hook],
    }

    video_urls = get_playlist_video_urls(playlist_url)
    downloaded_videos = load_download_history()

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for video_info in video_urls:
            try:
                video_id = video_info['id']
                title = video_info['title']

                if video_id in downloaded_videos:
                    print(f"DL済のためスキップします '{title}' (ID: {video_id}) ")
                    continue

                url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Try to extract video info, but handle if it's unavailable
                try:
                    info_dict = ydl.extract_info(url, download=False)
                    if info_dict is None:
                        print(f"発見できないためスキップします '{title}' (ID: {video_id}) ")
                        continue
                except yt_dlp.utils.DownloadError as e:
                    print(f"エラーが発生 スキップします '{title}' (ID: {video_id}) ")
                    continue

                thumbnail_url = info_dict.get('thumbnail')
                if thumbnail_url:
                    thumbnail_path = os.path.join(output_directory, f"{title}_thumbnail.jpg")
                    save_thumbnail(thumbnail_url, thumbnail_path)
                
                ydl.params['outtmpl']['default'] = f'{output_directory}/{sanitize_filename(video_info["title"])}.%(ext)s'
                ydl.download([url])

                mp3_file_path = os.path.join(output_directory, f"{sanitize_filename(title)}.mp3")
                if os.path.exists(thumbnail_path) and os.path.exists(mp3_file_path):
                    apply_cover_art(mp3_file_path, thumbnail_path)
                
                # Add to history after successful download
                downloaded_videos[video_id] = title
                save_download_history(downloaded_videos)
                print("待機中")
                time.sleep(1)

            except Exception as e:
                print(f"動画 '{title}' (ID: {video_id}) のダウンロード中にエラーが発生しました: {e}")
                continue




def load_download_history():
    downloaded_videos = {}
    if os.path.exists(DOWNLOAD_HISTORY_FILE):
        with open(DOWNLOAD_HISTORY_FILE, "r", encoding="utf-8") as file:
            for line in file:
                if ':' in line:
                    vid, title = line.strip().split(':', 1)
                    downloaded_videos[vid] = title
    return downloaded_videos

def save_download_history(downloaded_videos):
    with open(DOWNLOAD_HISTORY_FILE, "w", encoding="utf-8") as file:
        for vid, title in downloaded_videos.items():
            file.write(f"{vid}:{title}\n")





# 進捗バーの表示処理
def progress_hook(d):
    if d['status'] == 'downloading':
        pbar.update(d['downloaded_bytes'] - pbar.n)
    elif d['status'] == 'finished':
        pbar.n = pbar.total
        pbar.last_print_n = pbar.total
        pbar.update(0)
        pbar.set_postfix({"status": "finished"})
        print(f"\nダウンロード完了: {d['filename']}")

if __name__ == "__main__":
    playlist_url = input("再生リストURLを入力してください: ")

    with tqdm(unit='B', unit_scale=True, desc="ダウンロード中", total=100) as global_pbar:
        global pbar
        pbar = global_pbar
        download_audio_from_playlist(playlist_url)