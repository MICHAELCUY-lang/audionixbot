import os
import logging
import random
import traceback
import json
import requests
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import yt_dlp
from moviepy.editor import AudioFileClip, VideoFileClip, ImageClip
from PIL import Image
import asyncio
from keep_alive import keep_alive

# Disable SSL verification for Python requests
os.environ['PYTHONHTTPSVERIFY'] = '0'

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from BotFather
TOKEN = os.environ.get("TOKEN", "8166423286:AAHTOH6M-0fjeQggPGM-kKPr2ivi7EqAmqA")

# Spotify API credentials - you need to set these environment variables
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "f8b64136c2b84dfe8a87792f371a0fef")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "a22e0a461f9b4cc580352f7843310d88")

# Setup temporary directory for file processing
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# Command handlers
async def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f'Halo {user.first_name}! 👋\n\n'
        f'Saya adalah bot konversi media dan pencari lagu.\n\n'
        f'Perintah yang tersedia:\n'
        f'/mp3tomp4 - Konversi MP3 ke MP4\n'
        f'/mp4tomp3 - Konversi MP4 ke MP3\n'
        f'/music - Mencari dan mengirim lagu\n\n'
        f'Untuk konversi, kirim filenya setelah memilih perintah konversi.'
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Cara menggunakan bot:\n\n'
        '1. Untuk konversi MP3 ke MP4:\n'
        '   - Ketik /mp3tomp4\n'
        '   - Kirim file MP3\n\n'
        '2. Untuk konversi MP4 ke MP3:\n'
        '   - Ketik /mp4tomp3\n'
        '   - Kirim file MP4\n\n'
        '3. Untuk mencari lagu:\n'
        '   - Ketik /music [nama lagu]\n'
        '   - Atau kirim: "cari lagu [nama lagu]"\n\n'
        'Bot akan mencari dari YouTube, SoundCloud, dan Spotify.'
    )

async def mp3_to_mp4_command(update: Update, context: CallbackContext) -> None:
    """Set the context to expect an MP3 file for conversion."""
    context.user_data['expecting'] = 'mp3_file'
    await update.message.reply_text('Silakan kirim file MP3 yang ingin dikonversi ke MP4.')

async def mp4_to_mp3_command(update: Update, context: CallbackContext) -> None:
    """Set the context to expect an MP4 file for conversion."""
    context.user_data['expecting'] = 'mp4_file'
    await update.message.reply_text('Silakan kirim file MP4 yang ingin dikonversi ke MP3.')

async def music_command(update: Update, context: CallbackContext) -> None:
    """Handle the /music command to search for music."""
    logger.info(f"Music command called with args: {context.args}")
    query = ' '.join(context.args) if context.args else ''
    if not query:
        await update.message.reply_text('Gunakan format: /music [nama lagu]')
        return

    logger.info(f"Searching for query: '{query}'")
    await update.message.reply_text(f'Mencari lagu: "{query}"...')
    await search_music(update, context, query)

async def handle_file(update: Update, context: CallbackContext) -> None:
    """Handle received files based on the expected file type."""
    if 'expecting' not in context.user_data:
        await update.message.reply_text('Silakan gunakan perintah /mp3tomp4 atau /mp4tomp3 terlebih dahulu.')
        return

    expecting = context.user_data['expecting']
    message = update.message

    logger.info(f"Handling file with expecting={expecting}, message.audio={message.audio}, message.video={message.video}")

    if expecting == 'mp3_file' and message.audio:
        await process_mp3_file(update, context)
    elif expecting == 'mp4_file' and message.video:
        await process_mp4_file(update, context)
    else:
        await message.reply_text('Format file tidak sesuai dengan operasi yang dipilih.')

async def process_mp3_file(update: Update, context: CallbackContext) -> None:
    """Process MP3 file and convert it to MP4."""
    message = update.message
    await message.reply_text('Mengunduh file MP3...')

    try:
        # Get file info
        file_id = message.audio.file_id
        file = await context.bot.get_file(file_id)
        file_path = os.path.join(TEMP_DIR, f"{file_id}.mp3")
        output_path = os.path.join(TEMP_DIR, f"{file_id}.mp4")

        # Download file
        await message.reply_text('Mulai mengunduh file MP3...')
        await file.download_to_drive(file_path)
        await message.reply_text('Mengkonversi MP3 ke MP4...')

        # Create a static image (black background) for the video
        audio_clip = AudioFileClip(file_path)
        await message.reply_text('File audio berhasil dibuka')

        # Cek apakah file static_image.jpeg ada
        image_path = os.path.join(os.path.dirname(__file__), "static_image.jpeg")
        if not os.path.exists(image_path):
            # Jika tidak ada, buat image hitam kosong menggunakan Pillow
            await message.reply_text('Membuat gambar background...')
            black_image = Image.new('RGB', (1280, 720), color='black')
            black_image.save(image_path)

        image_clip = ImageClip(image_path)
        image_clip = image_clip.set_duration(audio_clip.duration)
        video_clip = image_clip.set_audio(audio_clip)

        await message.reply_text('Menulis file video...')
        video_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24)

        # Send the converted file
        await message.reply_text('Konversi selesai! Mengirim file MP4...')
        await context.bot.send_video(
            chat_id=message.chat_id,
            video=open(output_path, 'rb'),
            caption="File MP3 Anda telah dikonversi ke MP4.",
            supports_streaming=True
        )

        # Clean up
        audio_clip.close()
        video_clip.close()
        os.remove(file_path)
        os.remove(output_path)

    except Exception as e:
        logger.error(f"Error in MP3 to MP4 conversion: {e}")
        logger.error(traceback.format_exc())
        await message.reply_text(f'Terjadi kesalahan saat konversi: {str(e)}')

    # Reset context
    context.user_data.pop('expecting', None)

async def process_mp4_file(update: Update, context: CallbackContext) -> None:
    """Process MP4 file and convert it to MP3."""
    message = update.message
    await message.reply_text('Mengunduh file MP4...')

    try:
        # Get file info
        file_id = message.video.file_id
        file = await context.bot.get_file(file_id)
        file_path = os.path.join(TEMP_DIR, f"{file_id}.mp4")
        output_path = os.path.join(TEMP_DIR, f"{file_id}.mp3")

        # Download file
        await message.reply_text('Mulai mengunduh file MP4...')
        await file.download_to_drive(file_path)
        await message.reply_text('File MP4 berhasil diunduh')

        # Tambahkan informasi file
        file_size = os.path.getsize(file_path)
        await message.reply_text(f'Info file: Ukuran={file_size} bytes')

        # Extract audio from video
        await message.reply_text('Membuka file video...')
        video_clip = VideoFileClip(file_path)
        await message.reply_text('Mengekstrak audio...')
        audio_clip = video_clip.audio

        if audio_clip is None:
            await message.reply_text('Video tidak memiliki audio track!')
            video_clip.close()
            os.remove(file_path)
            context.user_data.pop('expecting', None)
            return

        await message.reply_text('Menyimpan file audio...')
        audio_clip.write_audiofile(output_path)
        await message.reply_text('Audio berhasil diekstrak')

        # Send the converted file
        await message.reply_text('Konversi selesai! Mengirim file MP3...')
        await context.bot.send_audio(
            chat_id=message.chat_id,
            audio=open(output_path, 'rb'),
            title=os.path.basename(output_path),
            caption="File MP4 Anda telah dikonversi ke MP3."
        )

        # Clean up
        video_clip.close()
        audio_clip.close()
        os.remove(file_path)
        os.remove(output_path)

    except Exception as e:
        logger.error(f"Error in MP4 to MP3 conversion: {e}")
        logger.error(traceback.format_exc())
        await message.reply_text(f'Terjadi kesalahan saat konversi: {str(e)}')

    # Reset context
    context.user_data.pop('expecting', None)

async def handle_text(update: Update, context: CallbackContext) -> None:
    """Handle text messages for music search."""
    text = update.message.text.lower()

    if text.startswith('cari lagu '):
        query = text[10:]  # Remove "cari lagu " prefix
        logger.info(f"Text handler called with query: '{query}'")
        await update.message.reply_text(f'Mencari lagu: "{query}"...')
        await search_music(update, context, query)

# Function to get Spotify access token
async def get_spotify_access_token():
    """Get Spotify API access token."""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        logger.warning("Spotify credentials not set, skipping Spotify search")
        return None

    try:
        auth_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
        auth_bytes = auth_string.encode("utf-8")
        auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

        url = "https://accounts.spotify.com/api/token"
        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}

        response = requests.post(url, headers=headers, data=data)
        json_result = response.json()

        if 'access_token' in json_result:
            return json_result["access_token"]
        else:
            logger.error(f"Failed to get Spotify token: {json_result}")
            return None

    except Exception as e:
        logger.error(f"Error getting Spotify token: {e}")
        return None

# Function to search tracks on Spotify
async def search_spotify(query, token):
    """Search for tracks on Spotify."""
    if not token:
        return []

    try:
        url = "https://api.spotify.com/v1/search"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        params = {
            "q": query,
            "type": "track",
            "limit": 5
        }

        response = requests.get(url, headers=headers, params=params)
        json_result = response.json()

        tracks = []
        if 'tracks' in json_result and 'items' in json_result['tracks']:
            for item in json_result['tracks']['items']:
                # Format duration
                duration_ms = item.get('duration_ms', 0)
                minutes = int(duration_ms / 60000)
                seconds = int((duration_ms % 60000) / 1000)
                duration = f"{minutes}:{seconds:02d}"

                # Get artist names
                artists = ", ".join([artist['name'] for artist in item.get('artists', [])])

                track = {
                    'title': item.get('name', 'No title'),
                    'artists': artists,
                    'duration': duration,
                    'id': item.get('id', ''),
                    'external_url': item.get('external_urls', {}).get('spotify', ''),
                    'preview_url': item.get('preview_url', ''),
                    'album': item.get('album', {}).get('name', ''),
                    'platform': 'spotify',
                    'display': f"Spotify: {item.get('name', 'No title')} - {artists} ({duration})"
                }
                tracks.append(track)

        return tracks

    except Exception as e:
        logger.error(f"Error in Spotify search: {e}")
        logger.error(traceback.format_exc())
        return []

async def search_youtube(query):
    """Search for music on YouTube."""
    logger.info(f"Searching YouTube for: '{query}'")

    try:
        # Rotating User-Agents to avoid detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
        ]

        # Use a random User-Agent
        user_agent = random.choice(user_agents)

        # Updated yt-dlp configuration for searching
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'noplaylist': True,
            'extract_flat': True,
            'skip_download': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_color': True,
            'socket_timeout': 30,
            'noprogress': True,
            'geo_bypass': True,
            'cookiefile': None,
            'source_address': '0.0.0.0',
            # Added HTTP headers to mimic a browser
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
                'Referer': 'https://www.youtube.com/',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android'],
                    'player_skip': ['webpage'],
                }
            },
        }

        # Cari video
        results = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if info and 'entries' in info:
                # Filter entries yang tidak None dan memiliki ID
                results = [entry for entry in info['entries'] if entry is not None and entry.get('id')]
                logger.info(f"Found {len(results)} search results on YouTube")

        return results

    except Exception as e:
        logger.error(f"Error in YouTube search: {e}")
        logger.error(traceback.format_exc())
        return []

async def search_soundcloud(query):
    """Search for music on SoundCloud."""
    logger.info(f"Searching SoundCloud for: '{query}'")

    try:
        # SoundCloud search using yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'noplaylist': False,  # We want to search playlists too
        }

        results = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"scsearch5:{query}", download=False)
            if info and 'entries' in info:
                # Filter entries to get valid tracks
                results = [entry for entry in info['entries'] if entry is not None]
                logger.info(f"Found {len(results)} search results on SoundCloud")

        return results

    except Exception as e:
        logger.error(f"Error in SoundCloud search: {e}")
        logger.error(traceback.format_exc())
        return []

async def search_music(update: Update, context: CallbackContext, query: str) -> None:
    """Search for music and provide options from multiple platforms."""
    logger.info(f"search_music called with query: '{query}'")

    await update.message.reply_text(f'Mencari lagu di beberapa platform...')

    # Get Spotify token
    spotify_token = await get_spotify_access_token()

    # Run all searches concurrently
    youtube_results_task = asyncio.create_task(search_youtube(query))
    soundcloud_results_task = asyncio.create_task(search_soundcloud(query))
    spotify_results_task = asyncio.create_task(search_spotify(query, spotify_token))

    # Wait for all searches to complete
    youtube_results = await youtube_results_task
    soundcloud_results = await soundcloud_results_task
    spotify_results = await spotify_results_task

    # Gabungkan hasil pencarian
    all_results = []

    # Tambahkan hasil YouTube (maksimal 3)
    for i, result in enumerate(youtube_results[:3]):
        title = result.get('title', 'No title')
        duration = "Unknown"
        if 'duration' in result and result['duration']:
            minutes = int(result['duration'] // 60)
            seconds = int(result['duration'] % 60)
            duration = f"{minutes}:{seconds:02d}"

        all_results.append({
            'title': title,
            'duration': duration,
            'id': result.get('id', ''),
            'platform': 'youtube',
            'display': f"YouTube: {title} ({duration})"
        })

    # Tambahkan hasil SoundCloud (maksimal 3)
    for i, result in enumerate(soundcloud_results[:3]):
        title = result.get('title', 'No title')
        duration = "Unknown"
        if 'duration' in result and result['duration']:
            minutes = int(result['duration'] // 60)
            seconds = int(result['duration'] % 60)
            duration = f"{minutes}:{seconds:02d}"

        all_results.append({
            'title': title,
            'duration': duration,
            'id': result.get('id', ''),
            'url': result.get('url', ''),
            'platform': 'soundcloud',
            'display': f"SoundCloud: {title} ({duration})"
        })

    # Tambahkan hasil Spotify (maksimal 3)
    for i, result in enumerate(spotify_results[:3]):
        all_results.append({
            'title': result['title'],
            'artists': result['artists'],
            'duration': result['duration'],
            'id': result['id'],
            'preview_url': result['preview_url'],
            'external_url': result['external_url'],
            'platform': 'spotify',
            'display': result['display']
        })

    if not all_results:
        await update.message.reply_text('Tidak menemukan hasil untuk pencarian Anda.')
        return

    # Create inline keyboard with options
    keyboard = []
    for i, result in enumerate(all_results):
        platform = result['platform']

        if platform == 'youtube':
            item_id = result.get('id', '')
            callback_data = f"yt_{item_id}"
        elif platform == 'soundcloud':
            callback_data = f"sc_{result['url']}"
        elif platform == 'spotify':
            # For Spotify, we'll use preview URL if available, otherwise the external URL
            if result['preview_url']:
                callback_data = f"sp_preview_{result['id']}"
            else:
                callback_data = f"sp_external_{result['external_url']}"
        else:
            continue

        keyboard.append([
            InlineKeyboardButton(f"{i+1}. {result['display']}", callback_data=callback_data)
        ])

    logger.info(f"Created keyboard with {len(keyboard)} buttons")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Pilih lagu yang ingin diunduh:', reply_markup=reply_markup)

async def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks for music download."""
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.info(f"Button callback with data: {data}")

    if data.startswith("yt_"):
        video_id = data[3:]
        await query.edit_message_text(text=f"Mengunduh lagu dari YouTube... Mohon tunggu.")
        await download_from_youtube(query.message.chat_id, video_id, context)
    elif data.startswith("sc_"):
        track_url = data[3:]
        await query.edit_message_text(text=f"Mengunduh lagu dari SoundCloud... Mohon tunggu.")
        await download_from_soundcloud(query.message.chat_id, track_url, context)
    elif data.startswith("sp_preview_"):
        track_id = data[11:]
        await query.edit_message_text(text=f"Mengunduh preview dari Spotify... Mohon tunggu.")
        await download_from_spotify_preview(query.message.chat_id, track_id, context)
    elif data.startswith("sp_external_"):
        external_url = data[12:]
        # For external URLs, we'll just send the URL since we can't download directly
        await query.edit_message_text(
            text=f"Maaf, Spotify tidak memungkinkan pengunduhan langsung. Silakan gunakan tautan ini untuk mendengarkan:\n\n{external_url}\n\nAtau coba cari lagu yang sama di YouTube atau SoundCloud."
        )

async def download_from_spotify_preview(chat_id: int, track_id: str, context: CallbackContext) -> None:
    """Download music preview from Spotify and send it to the user."""
    logger.info(f"Starting Spotify preview download for track ID: {track_id}")

    # Get Spotify access token
    token = await get_spotify_access_token()
    if not token:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Tidak dapat terhubung ke Spotify. Silakan coba platform lain."
        )
        return

    # Inform user of progress
    progress_message = await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ Mengunduh preview dari Spotify... Mohon tunggu sebentar."
    )

    try:
        # Get track details
        url = f"https://api.spotify.com/v1/tracks/{track_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers)
        track_info = response.json()

        preview_url = track_info.get('preview_url')
        if not preview_url:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text="❌ Preview tidak tersedia untuk lagu ini. Silakan coba platform lain."
            )
            return

        # Get track name and artist
        title = track_info.get('name', 'Spotify Track')
        artists = ", ".join([artist['name'] for artist in track_info.get('artists', [])])
        album = track_info.get('album', {}).get('name', '')

        # Download preview
        output_path = os.path.join(TEMP_DIR, f"spotify_{track_id}.mp3")

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_message.message_id,
            text="⏳ Mengunduh preview... (50%)"
        )

        # Stream and download the preview
        preview_response = requests.get(preview_url, stream=True)
        with open(output_path, 'wb') as f:
            for chunk in preview_response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        # Check if file exists and has reasonable size
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text="⏳ Mengirim audio... (95%)"
            )

            # Send the audio preview
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=open(output_path, 'rb'),
                title=title,
                performer=artists,
                caption=f"🎵 {title} - {artists}\nAlbum: {album}\n\n⚠️ Ini hanya preview 30 detik dari Spotify."
            )

            # Delete progress message
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=progress_message.message_id
            )

            # Clean up
            os.remove(output_path)
        else:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text="❌ Tidak dapat mengunduh preview. Silakan coba platform lain."
            )

    except Exception as e:
        logger.error(f"Error in Spotify preview download: {e}")
        logger.error(traceback.format_exc())

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text=f"❌ Terjadi kesalahan saat mengunduh dari Spotify: {str(e)}\nSilakan coba platform lain."
            )
        except Exception:
            pass

async def download_from_youtube(chat_id: int, video_id: str, context: CallbackContext) -> None:
    """Download music from YouTube and send it to the user."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_path = os.path.join(TEMP_DIR, f"{video_id}.mp3")
    actual_output_path = output_path.replace('.mp3', '') + '.mp3'
    logger.info(f"Starting YouTube download for video ID: {video_id}")

    # Rotating User-Agents to avoid detection
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/123.0.0.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
    ]

    # Inform user of progress
    progress_message = await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ Mengunduh lagu... Mohon tunggu sebentar."
    )

    # Try direct download approach first - getting available formats
    try:
        format_opts = {
            'quiet': True,
            'no_warnings': True,
            'listformats': True,
            'skip_download': True,
            'nocheckcertificate': True,
            'http_headers': {
               'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Referer': 'https://www.youtube.com/',
            },
        }

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_message.message_id,
            text="⏳ Memeriksa format yang tersedia..."
        )

        formats = []
        with yt_dlp.YoutubeDL(format_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'formats' in info:
                formats = info['formats']
                logger.info(f"Found {len(formats)} available formats")
            title = info.get('title', 'Music')

        # Try to find an audio format
        audio_formats = []
        for fmt in formats:
            if fmt.get('acodec', 'none') != 'none' and fmt.get('vcodec', 'none') == 'none':
                audio_formats.append(fmt)

        # If no pure audio formats, look for formats with audio
        if not audio_formats:
            for fmt in formats:
                if fmt.get('acodec', 'none') != 'none':
                    audio_formats.append(fmt)

        if audio_formats:
            # Sort by quality (prefer higher bitrate)
            audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
            best_format = audio_formats[0]['format_id']
            logger.info(f"Selected format: {best_format}")

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text=f"⏳ Mengunduh audio dengan format terbaik..."
            )

            # Download with specific format
            download_opts = {
                'format': best_format,
                'outtmpl': output_path.replace('.mp3', ''),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'nocheckcertificate': True,
                'http_headers': {
                    'User-Agent': random.choice(user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Referer': 'https://www.youtube.com/',
                },
            }

            with yt_dlp.YoutubeDL(download_opts) as ydl:
                ydl.download([url])

            # Check if file exists
            if os.path.exists(actual_output_path) and os.path.getsize(actual_output_path) > 1024:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_message.message_id,
                    text="⏳ Mengirim audio... (95%)"
                )

                # Send the audio file
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=open(actual_output_path, 'rb'),
                    title=title,
                    caption=f"🎵 {title}\n\nDiunduh dari YouTube."
                )

                # Delete progress message
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=progress_message.message_id
                )

                # Clean up
                os.remove(actual_output_path)
                return
    except Exception as format_error:
        logger.error(f"Format detection failed: {format_error}")
        logger.error(traceback.format_exc())

    # If we're here, the first approach failed. Try the multi-strategy approach
    # Multiple download strategies to try
    download_strategies = [
        # Strategy 1: Specific format selection for audio
        {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'http_headers': {
                'User-Agent': random.choice(user_agents),
                'Referer': 'https://www.youtube.com/',
            },
            'extractor_args': {'youtube': {'player_client': ['web']}},
        },
        # Strategy 2: Try with generic format
        {
            'format': 'worstaudio/worst',  # Sometimes lower quality works when higher quality is blocked
            'http_headers': {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
            'extractor_args': {'youtube': {'player_client': ['android']}},
        },
        # Strategy 3: Mobile user agent
        {
            'format': 'bestaudio/best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/123.0.0.0 Mobile/15E148 Safari/604.1',
            },
            'extractor_args': {'youtube': {'player_client': ['ios']}},
        },
        # Strategy 4: No post-processing
        {
            'format': 'bestaudio/best',
            'postprocessors': [],  # Skip post-processing
            'http_headers': {
                'User-Agent': random.choice(user_agents),
            },
            'extractor_args': {'youtube': {'player_skip': ['webpage', 'configs']}},
        },
    ]

    # Base options
    base_opts = {
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_path.replace('.mp3', ''),
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'retries': 20,
        'fragment_retries': 20,
        'skip_unavailable_fragments': True,
        'noprogress': True,
        'nocheckcertificate': True,
        'cookiefile': None,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
    }

    # Try each strategy in sequence
    title = "Music"
    downloaded = False
    last_error = None

    for idx, strategy in enumerate(download_strategies):
        if downloaded:
            break

        try:
            # Update progress message
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text=f"⏳ Mencoba metode unduhan #{idx+1}... (Mohon tunggu)"
            )

            # Combine base options with strategy
            current_opts = {**base_opts, **strategy}
            logger.info(f"Trying download strategy {idx+1}")

            with yt_dlp.YoutubeDL(current_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                title = info_dict.get('title', 'Music')
                logger.info(f"Download successful with strategy {idx+1}")

            # If we get here, download was successful
            downloaded = True

            # Check if file exists and has reasonable size
            if os.path.exists(actual_output_path) and os.path.getsize(actual_output_path) > 1024:
                logger.info(f"File exists with size: {os.path.getsize(actual_output_path)} bytes")
                # Update progress
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_message.message_id,
                    text="⏳ Mengirim audio... (95%)"
                )

                # Send the audio file
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=open(actual_output_path, 'rb'),
                    title=title,
                    caption=f"🎵 {title}\n\nDiunduh dari YouTube."
                )

                # Delete progress message
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=progress_message.message_id
                )

                # Clean up
                os.remove(actual_output_path)
                return
            else:
                logger.warning(f"File invalid or not found at {actual_output_path}")
                # Invalid file, continue to next strategy
                downloaded = False
        except Exception as e:
            logger.error(f"Strategy {idx+1} failed: {e}")
            logger.error(traceback.format_exc())
            last_error = e
            continue

    # If all YouTube strategies failed, tell the user
    error_message = str(last_error) if last_error else "Tidak dapat mengunduh lagu dari YouTube"
    logger.error(f"All YouTube download strategies failed: {error_message}")

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_message.message_id,
            text=f"❌ Tidak bisa mengunduh dari YouTube: {error_message}\nSilakan coba platform lain seperti Spotify atau SoundCloud."
        )
    except Exception:
        pass

async def download_from_soundcloud(chat_id: int, track_url: str, context: CallbackContext) -> None:
    """Download music from SoundCloud and send it to the user."""
    output_path = os.path.join(TEMP_DIR, f"sc_{random.randint(10000, 99999)}.mp3")
    logger.info(f"Starting SoundCloud download for URL: {track_url}")

    # Inform user of progress
    progress_message = await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ Mengunduh lagu dari SoundCloud... Mohon tunggu sebentar."
    )

    try:
        # SoundCloud download options
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_path.replace('.mp3', ''),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'nocheckcertificate': True,
        }

        # Download from SoundCloud
        title = "SoundCloud Track"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text="⏳ Mengunduh audio... (50%)"
            )

            info_dict = ydl.extract_info(track_url, download=True)
            title = info_dict.get('title', 'SoundCloud Track')

        actual_output_path = output_path.replace('.mp3', '') + '.mp3'

        # Check if file exists and has reasonable size
        if os.path.exists(actual_output_path) and os.path.getsize(actual_output_path) > 1024:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text="⏳ Mengirim audio... (95%)"
            )

            # Send the audio file
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=open(actual_output_path, 'rb'),
                title=title,
                caption=f"🎵 {title}\n\nDiunduh dari SoundCloud."
            )

            # Delete progress message
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=progress_message.message_id
            )

            # Clean up
            os.remove(actual_output_path)
            return
        else:
            logger.warning(f"SoundCloud file invalid or not found")
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text="❌ File hasil tidak valid. Silakan coba lagi."
            )

    except Exception as e:
        logger.error(f"Error in SoundCloud download: {e}")
        logger.error(traceback.format_exc())

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text=f"❌ Terjadi kesalahan saat mengunduh musik dari SoundCloud: {str(e)}\nSilakan coba lagi nanti."
            )
        except Exception:
            pass

def main() -> None:
    """Start the bot."""
    # Keep the bot alive
    keep_alive()

    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("mp3tomp4", mp3_to_mp4_command))
    application.add_handler(CommandHandler("mp4tomp3", mp4_to_mp3_command))
    application.add_handler(CommandHandler("music", music_command))

    # Add file handler
    application.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.Document.ALL, handle_file))

    # Add text handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))

    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()