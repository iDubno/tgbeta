import os
import asyncio
import aiohttp
import aiofiles
from pyrogram import Client, enums
import ssl
import logging

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = -1001341570295

APP_CENTER_URL = "https://api.appcenter.ms/v0.1/public/sdk/apps/f9726602-67c9-48d2-b5d0-4761f1c1a8f3/releases/latest"
THUMBNAIL_URL = "https://graph.org/file/b8895c429c91ac72b542d.png"
THUMBNAIL_PATH = "thumb.jpg"

sslcontext = ssl.create_default_context()
sslcontext.check_hostname = False
sslcontext.verify_mode = ssl.CERT_NONE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def download_file(session, url, message, total_size, file_path, retries=3):
    for attempt in range(retries):
        try:
            async with session.get(url, ssl=sslcontext) as response:
                response.raise_for_status()
                downloaded_size = 0
                last_update_time = asyncio.get_event_loop().time()
                
                async with aiofiles.open(file_path, 'wb') as file:
                    async for chunk in response.content.iter_chunked(8192):
                        await file.write(chunk)
                        downloaded_size += len(chunk)
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_update_time >= 2:  # Update every 2 seconds
                            percentage = (downloaded_size / total_size) * 100
                            await message.edit_text(
                                f"**Build {short_version} ({version}) was released.**\n"
                                f"__Downloading... {downloaded_size / 1024 / 1024:.2f} MB of {total_size / 1024 / 1024:.2f} MB ({percentage:.2f}%)__"
                            )
                            last_update_time = current_time
                
                await message.edit_text(
                    f"**Build {short_version} ({version}) was released.**\n"
                    f"__Downloaded {total_size / 1024 / 1024:.2f} MB (100%)__"
                )
                
                return file_path
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise

async def main():
    app = Client("telegram_beta", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    conn = aiohttp.TCPConnector(limit_per_host=10, ssl=sslcontext)
    async with aiohttp.ClientSession(connector=conn) as session:
        if not os.path.exists(THUMBNAIL_PATH):
            await download_file(session, THUMBNAIL_URL, None, 0, THUMBNAIL_PATH)
        async with session.get(APP_CENTER_URL) as response:
            response.raise_for_status()
            data = await response.json()
        
        global version, short_version
        version = os.getenv('INPUT_VERSION')
        short_version = os.getenv('INPUT_SHORT_VERSION')
        download_url = os.getenv('INPUT_DOWNLOAD_URL')
        release_notes = os.getenv('INPUT_RELEASE_NOTES')
        total_size = data['size']

        async with app:
            if download_url == 'not found':
                await app.send_message(CHAT_ID, "⚠ Warning! New release with no download URL found. Recommend investigation.")
            else:
                message = await app.send_photo(CHAT_ID, photo=THUMBNAIL_URL, caption=f"**Build {short_version} ({version}) was released.**\n__Preparing to download...__")
                apk_path = "app.apk"
                file_path = await download_file(session, download_url, message, total_size, apk_path)
                await app.send_chat_action(CHAT_ID, enums.ChatAction.UPLOAD_DOCUMENT)
                caption = f"🚀 **New Beta v{short_version} ({version}) released!**\n\n"
                caption += f"📝 Release notes:\n{release_notes}"
                await app.send_document(CHAT_ID, file_path, caption=caption, thumb=THUMBNAIL_PATH)
                await message.delete()
                os.remove(apk_path)

if __name__ == "__main__":
    asyncio.run(main())
