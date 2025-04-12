import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import yt_dlp
from moviepy.editor import AudioFileClip, VideoFileClip, ImageClip
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
        '   - Atau kirim: "cari lagu [nama lagu]"'
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
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text('Gunakan format: /music [nama lagu]')
        return

    await search_music(update, context, query)

async def handle_file(update: Update, context: CallbackContext) -> None:
    """Handle received files based on the expected file type."""
    if 'expecting' not in context.user_data:
        await update.message.reply_text('Silakan gunakan perintah /mp3tomp4 atau /mp4tomp3 terlebih dahulu.')
        return

    expecting = context.user_data['expecting']
    message = update.message

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

    # Get file info
    file_id = message.audio.file_id
    file = await context.bot.get_file(file_id)
    file_path = os.path.join(TEMP_DIR, f"{file_id}.mp3")
    output_path = os.path.join(TEMP_DIR, f"{file_id}.mp4")

    # Download file
    await file.download_to_drive(file_path)
    await message.reply_text('Mengkonversi MP3 ke MP4...')

    try:
        # Create a static image (black background) for the video
        audio_clip = AudioFileClip(file_path)
        image_clip = ImageClip(os.path.join(os.path.dirname(__file__), "static_image.jpeg"))
        image_clip = image_clip.set_duration(audio_clip.duration)
        video_clip = image_clip.set_audio(audio_clip)
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
        os.remove(file_path)
        os.remove(output_path)

    except Exception as e:
        logger.error(f"Error in MP3 to MP4 conversion: {e}")
        await message.reply_text(f'Terjadi kesalahan saat konversi: {str(e)}')

    # Reset context
    context.user_data.pop('expecting', None)

async def process_mp4_file(update: Update, context: CallbackContext) -> None:
    """Process MP4 file and convert it to MP3."""
    message = update.message
    await message.reply_text('Mengunduh file MP4...')

    # Get file info
    file_id = message.video.file_id
    file = await context.bot.get_file(file_id)
    file_path = os.path.join(TEMP_DIR, f"{file_id}.mp4")
    output_path = os.path.join(TEMP_DIR, f"{file_id}.mp3")

    # Download file
    await file.download_to_drive(file_path)
    await message.reply_text('Mengkonversi MP4 ke MP3...')

    try:
        # Extract audio from video
        video_clip = VideoFileClip(file_path)
        audio_clip = video_clip.audio
        audio_clip.write_audiofile(output_path)

        # Send the converted file
        await message.reply_text('Konversi selesai! Mengirim file MP3...')
        await context.bot.send_audio(
            chat_id=message.chat_id,
            audio=open(output_path, 'rb'),
            title=os.path.basename(output_path),
            caption="File MP4 Anda telah dikonversi ke MP3."
        )

        # Clean up
        os.remove(file_path)
        os.remove(output_path)
        video_clip.close()
        audio_clip.close()

    except Exception as e:
        logger.error(f"Error in MP4 to MP3 conversion: {e}")
        await message.reply_text(f'Terjadi kesalahan saat konversi: {str(e)}')

    # Reset context
    context.user_data.pop('expecting', None)

async def handle_text(update: Update, context: CallbackContext) -> None:
    """Handle text messages for music search."""
    text = update.message.text.lower()

    if text.startswith('cari lagu '):
        query = text[10:]  # Remove "cari lagu " prefix
        await search_music(update, context, query)

async def search_music(update: Update, context: CallbackContext, query: str) -> None:
    """Search for music and provide options."""
    await update.message.reply_text(f'Mencari lagu: "{query}"...')

    try:
        # Konfigurasi yt-dlp dengan opsi untuk melewati verifikasi SSL
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'noplaylist': True,
            'extract_flat': True,
            'skip_download': True,
            'nocheckcertificate': True,  # Penting untuk melewati verifikasi SSL
            'ignoreerrors': False,
            'no_color': True,
            'socket_timeout': 30,
            'noprogress': True,
            'geo_bypass': True,
            'nocheckcertificate': True,  # Duplikasi untuk memastikan
            'cookiefile': None,  # Set ke None untuk menghindari masalah cookie
            'source_address': '0.0.0.0',  # Gunakan alamat sumber default
        }

        # Cari video
        results = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if info and 'entries' in info:
                # Filter entries yang tidak None dan memiliki ID
                results = [entry for entry in info['entries'] if entry is not None and entry.get('id')]

        if not results:
            await update.message.reply_text('Tidak menemukan hasil untuk pencarian Anda.')
            return

        # Create inline keyboard with options
        keyboard = []
        for i, result in enumerate(results):
            if i >= 5:  # Batasi sampai 5 hasil
                break

            title = result.get('title', 'Tidak ada judul')

            # Format durasi jika tersedia
            duration = "Unknown"
            if 'duration' in result and result['duration']:
                minutes = int(result['duration'] // 60)
                seconds = int(result['duration'] % 60)
                duration = f"{minutes}:{seconds:02d}"

            video_id = result.get('id', '')

            # Pastikan video_id tidak None sebelum menambahkan ke keyboard
            if video_id:
                keyboard.append([
                    InlineKeyboardButton(f"{i+1}. {title} ({duration})", callback_data=f"download_{video_id}")
                ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Pilih lagu yang ingin diunduh:', reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in music search: {e}")
        await update.message.reply_text(f'Terjadi kesalahan saat mencari musik: {str(e)}')

async def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks for music download."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("download_"):
        video_id = data[9:]
        await query.edit_message_text(text=f"Mengunduh lagu... Mohon tunggu.")

        # Download the music
        await download_and_send_music(query.message.chat_id, video_id, context)

async def download_and_send_music(chat_id: int, video_id: str, context: CallbackContext) -> None:
    """Download music from YouTube and send it to the user."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_path = os.path.join(TEMP_DIR, f"{video_id}.mp3")

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
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'noprogress': True,
        'nocheckcertificate': True,  # Melewati verifikasi SSL
        'cookiefile': None,
        'source_address': '0.0.0.0',
    }

    try:
        # Inform user of progress
        progress_message = await context.bot.send_message(
            chat_id=chat_id,
            text="⏳ Mengunduh lagu... (0%)"
        )

        # Download the audio
        title = "Music"
        actual_output_path = output_path.replace('.mp3', '') + '.mp3'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Update progress message
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text="⏳ Mengunduh lagu... (50%)"
            )

            info_dict = ydl.extract_info(url, download=True)
            title = info_dict.get('title', 'Music')

        # Update progress again
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_message.message_id,
            text="⏳ Memproses audio... (80%)"
        )

        # Check if file exists and has a reasonable size before sending
        if os.path.exists(actual_output_path) and os.path.getsize(actual_output_path) > 1024:
            # Update progress one more time
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

            # Delete progress message after successful send
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=progress_message.message_id
            )

            # Clean up
            os.remove(actual_output_path)
        else:
            # In case file doesn't exist or is too small
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text="❌ File hasil tidak valid. Silakan coba lagi."
            )

    except Exception as e:
        logger.error(f"Error in music download: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f'Terjadi kesalahan saat mengunduh musik: {str(e)}'
            )
        except:
            pass

        # Try to send anyway if file exists
        if os.path.exists(actual_output_path) and os.path.getsize(actual_output_path) > 1024:
            try:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=open(actual_output_path, 'rb'),
                    title=title,
                    caption=f"🎵 {title}\n\nDiunduh dari YouTube (dengan beberapa error)."
                )
                os.remove(actual_output_path)
            except Exception as send_error:
                logger.error(f"Failed to send audio after download error: {send_error}")
                # Try to clean up anyway
                try:
                    if os.path.exists(actual_output_path):
                        os.remove(actual_output_path)
                except:
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
