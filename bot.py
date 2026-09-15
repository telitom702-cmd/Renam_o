import os
import logging
import threading
from pyrogram import Client, filters
from pyrogram.types import ForceReply, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
from database import add_user, count_users, set_mode, get_mode, save_caption, get_caption, save_thumbnail, get_thumbnail, delete_thumbnail
import ffmpeg
import uvicorn
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)

# টেলিগ্রাম বট ক্লায়েন্ট
bot_app = Client("video_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Render এর জন্য ফাস্ট এপিআই ওয়েব সার্ভার
web_app = FastAPI()

@web_app.get("/")
def home():
    return {"status": "Bot is running successfully!"}

def run_web():
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(web_app, host="0.0.0.0", port=port)

# স্টেপ ট্র্যাক করার জন্য ডিকশনারি
user_steps = {}

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# ---------------------------------------------------------
# সার্ভার ক্লিন সিস্টেম (Cleaner Function)
# ---------------------------------------------------------
async def clean_server(file_paths):
    """সার্ভার থেকে অস্থায়ী ফাইল ডিলিট করার ফাংশন"""
    for file in file_paths:
        if file and os.path.exists(file):
            try:
                os.remove(file)
                logging.info(f"🧹 Server Cleaned: {file}")
            except Exception as e:
                logging.error(f"Failed to delete {file}: {e}")

# ---------------------------------------------------------
# ইউজার ইন্টারফেস (বাটন ও প্রোগ্রেস বার)
# ---------------------------------------------------------
def start_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🖼️ থাম্বনেইল", callback_data="set_thumb"),
                InlineKeyboardButton("✍️ ক্যাপশন", callback_data="set_cap")
            ],
            [
                InlineKeyboardButton("🎞️ মোড: ভিডিও", callback_data="set_mode_video"),
                InlineKeyboardButton("📄 মোড: ডকুমেন্ট", callback_data="set_mode_doc")
            ],
            [
                InlineKeyboardButton("❌ থাম্বনেইল ডিলিট", callback_data="del_thumb"),
                InlineKeyboardButton("📊 স্ট্যাটাস", callback_data="stats")
            ],
            [InlineKeyboardButton("ℹ️ হেল্প", callback_data="help")]
        ]
    )

def skip_button(step):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⏭️ Skip (এড়িয়ে যান)", callback_data=f"skip_{step}")]]
    )

async def progress_bar(current, total, message):
    percent = (current / total) * 100
    text = f"⏳ প্রগ্রেস: {percent:.1f}%\n\n💾 {current/(1024*1024):.2f}MB / {total/(1024*1024):.2f}MB"
    try:
        await message.edit_text(text)
    except Exception:
        pass

# ---------------------------------------------------------
# ১. /start কমান্ড
# ---------------------------------------------------------
@bot_app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    add_user(message.from_user.id)
    await message.reply_text(
        "👋 স্বাগতম! আমি একটি অটো কনভার্ট ও রিনেম বট।\n\n"
        "📌 ফাইল পাঠালে আমি আপনাকে নতুন নাম ও ক্যাপশন লিখতে বলব। \n"
        "না লিখতে চাইলে Skip বাটনে ক্লিক করবেন।\n\n"
        "নিচের বাটনগুলো থেকে আপনার সেটিংস নির্বাচন করুন 👇",
        reply_markup=start_buttons()
    )

# ---------------------------------------------------------
# ২. বাটন ক্লিক হ্যান্ডলার
# ---------------------------------------------------------
@bot_app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data == "set_thumb":
        await query.message.edit("🖼️ অনুগ্রহ করে একটি ছবি পাঠান থাম্বনেইল হিসেবে সেট করার জন্য।")

    elif data == "set_cap":
        user_steps[user_id] = "set_default_cap"
        await query.message.reply_text("✍️ অনুগ্রহ করে আপনার ডিফল্ট ক্যাপশনটি লিখে পাঠান:", reply_markup=ForceReply(True))

    elif data == "del_thumb":
        thumb_path = get_thumbnail(user_id)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
        delete_thumbnail(user_id)
        await query.answer("✅ থাম্বনেইল মুছে ফেলা হয়েছে!", show_alert=True)

    elif data == "stats":
        total = count_users()
        await query.answer(f"📊 মোট ইউজার: {total}", show_alert=True)

    elif data == "set_mode_video":
        set_mode(user_id, "video")
        await query.answer("✅ আপনার আউটপুট মোড 'ভিডিও' সেট করা হয়েছে!", show_alert=True)

    elif data == "set_mode_doc":
        set_mode(user_id, "document")
        await query.answer("✅ আপনার আউটপুট মোড 'ডকুমেন্টস' সেট করা হয়েছে!", show_alert=True)

    elif data == "skip_rename":
        if user_id in user_steps and isinstance(user_steps[user_id], dict):
            user_steps[user_id]["rename"] = False
        await query.message.delete()
        await query.message.reply_text("✅ রিনেম স্কিপ করা হয়েছে।\n\nএখন ক্যাপশন লিখুন অথবা Skip করুন:", reply_markup=skip_button("caption"))

    elif data == "skip_caption":
        await query.message.delete()
        if user_id in user_steps and isinstance(user_steps[user_id], dict):
            data = user_steps[user_id]
            data["custom_caption"] = None
            original_msg = await client.get_messages(query.message.chat.id, data["msg_id"])
            await process_file(client, query.message, data, original_msg)
            del user_steps[user_id]

    elif data == "help":
        help_text = (
            "ℹ️ **কীভাবে ব্যবহার করবেন:**\n\n"
            "1. বটকে যেকোনো ডকুমেন্ট বা ভিডিও পাঠান।\n"
            "2. বট আপনাকে নতুন নাম ও ক্যাপশন লিখতে বলবে।\n"
            "3. চাইলে নতুন নাম লিখুন, না চাইলে Skip বাটনে ক্লিক করুন।\n"
            "4. আপনার সেটিংস অনুযায়ী ফাইল ভিডিও বা ডকুমেন্টস হিসেবে ফেরত পাবেন।"
        )
        await query.message.reply_text(help_text, reply_markup=start_buttons())

# ---------------------------------------------------------
# ৩. ইউজারের রিপ্লাই মেসেজ হ্যান্ডলার
# ---------------------------------------------------------
@bot_app.on_message(filters.reply & filters.private)
async def reply_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_steps:
        return

    step = user_steps[user_id]

    if step == "set_default_cap":
        save_caption(user_id, message.text)
        await message.reply_text("✅ ডিফল্ট ক্যাপশন সেভ হয়েছে!", reply_markup=start_buttons())
        del user_steps[user_id]

# ---------------------------------------------------------
# ৪. থাম্বনেইল সেভ হ্যান্ডলার
# ---------------------------------------------------------
@bot_app.on_message(filters.photo & filters.private)
async def save_thumb_handler(client, message):
    thumb_path = f"downloads/thumb_{message.from_user.id}.jpg"
    await message.download(file_name=thumb_path)
    save_thumbnail(message.from_user.id, thumb_path)
    await message.reply_text("✅ থাম্বনেইল সেভ হয়েছে!", reply_markup=start_buttons())

# ---------------------------------------------------------
# ৫. ফাইল রিসিভ করা মাত্রই রিনেমের জন্য জিজ্ঞেস করা
# ---------------------------------------------------------
async def ask_rename_and_caption(client, message, media_type):
    user_id = message.from_user.id
    user_steps[user_id] = {
        "action": "process", 
        "media_type": media_type, 
        "msg_id": message.id, 
        "rename": True,
        "original_file_name": message.document.file_name if media_type == "document" else (message.video.file_name or "Video.mp4")
    }
    
    text = "📝 অনুগ্রহ করে ফাইলের জন্য একটি নতুন নাম লিখুন (এক্সটেনশন ছাড়া, যেমন: My Video 2016):"
    await message.reply_text(text, reply_markup=skip_button("rename"))

# ---------------------------------------------------------
# ৬. নতুন নাম লিখলে এই হ্যান্ডলার কাজ করবে
# ---------------------------------------------------------
@bot_app.on_message(filters.text & filters.private & ~filters.command(["start", "setcaption", "setthumb", "delthumb"]))
async def text_handler(client, message):
    user_id = message.from_user.id
    
    if user_id in user_steps and isinstance(user_steps[user_id], dict) and user_steps[user_id].get("action") == "process":
        if user_steps[user_id].get("rename") == True:
            user_steps[user_id]["new_name"] = message.text
            user_steps[user_id]["rename"] = False
            await message.reply_text("✅ নাম সেভ হয়েছে।\n\nএখন ক্যাপশন লিখুন অথবা Skip করুন:", reply_markup=skip_button("caption"))
        
        else:
            user_steps[user_id]["custom_caption"] = message.text
            data = user_steps[user_id]
            original_msg = await client.get_messages(message.chat.id, data["msg_id"])
            await process_file(client, message, data, original_msg)
            del user_steps[user_id]

# ---------------------------------------------------------
# ৭. মূল ফিউচার: কনভার্ট, রিনেম, থাম্বনেইল লাগানো ও সার্ভার ক্লিন
# ---------------------------------------------------------
async def process_file(client, message, data, original_msg):
    media_type = data.get("media_type")
    new_name = data.get("new_name", None)
    custom_caption = data.get("custom_caption", None)
    original_file_name = data.get("original_file_name", "Video_File.mp4")

    caption = custom_caption or get_caption(message.from_user.id) or "✅ ফাইলটি সফলভাবে প্রসেস করা হয়েছে।"
    thumb_path = get_thumbnail(message.from_user.id)
    output_mode = get_mode(message.from_user.id)
    
    process_msg = await message.reply_text("⏳ ফাইল ডাউনলোড শুরু হয়েছে...")
    
    # সার্ভার ক্লিন সিস্টেমের জন্য সব ফাইলের ট্র্যাক রাখা হচ্ছে
    temp_files = []
    
    try:
        file_path = await original_msg.download(file_name="downloads/", progress=progress_bar, progress_args=(process_msg,))
        temp_files.append(file_path)
        
        await process_msg.edit_text("⚙️ প্রসেস হচ্ছে...")
        
        _, original_ext = os.path.splitext(original_file_name)
        if not original_ext:
            original_ext = ".mp4"
            
        if new_name:
            user_name, user_ext = os.path.splitext(new_name)
            if user_ext:
                final_name = new_name
            else:
                final_name = f"{new_name}{original_ext}"
                
            final_file = f"downloads/{final_name}"
            os.rename(file_path, final_file)
            temp_files.append(final_file)
        else:
            final_file = file_path
            
        if media_type == "document":
            await process_msg.edit_text("🎞️ ভিডিওতে কনভার্ট হচ্ছে...")
            video_file = f"downloads/Converted_{message.id}.mp4"
            stream = ffmpeg.input(final_file)
            stream = ffmpeg.output(stream, video_file, **{"c:v": "copy", "c:a": "copy"})
            ffmpeg.run(stream, quiet=True, overwrite_output=True)
            
            send_file = video_file
            temp_files.append(video_file)
        else:
            send_file = final_file
            
        await process_msg.edit_text("🚀 আপলোড হচ্ছে...")
        
        if output_mode == "document":
            await message.reply_document(
                document=send_file, caption=caption, thumb=thumb_path if thumb_path else None,
                progress=progress_bar, progress_args=(process_msg,)
            )
        else:
            await message.reply_video(
                video=send_file, caption=caption, thumb=thumb_path if thumb_path else None,
                progress=progress_bar, progress_args=(process_msg,)
            )
        
        await process_msg.delete()
        
    except Exception as e:
        await process_msg.edit_text(f"❌ এরর: {e}")
        
    finally:
        # 🧹 সার্ভার ক্লিন সিস্টেম: কাজ শেষ হলে বা এরর আসলেও সব ফাইল ডিলিট করবে
        await clean_server(temp_files)

# ---------------------------------------------------------
# ৮. ডকুমেন্ট বা ভিডিও রিসিভ করলে
# ---------------------------------------------------------
@bot_app.on_message(filters.document & filters.private)
async def document_handler(client, message):
    await ask_rename_and_caption(client, message, "document")

@bot_app.on_message(filters.video & filters.private)
async def video_handler(client, message):
    await ask_rename_and_caption(client, message, "video")

# ---------------------------------------------------------
# বট চালু করা
# ---------------------------------------------------------
if __name__ == "__main__":
    # ১. ওয়েব সার্ভার ব্যাকগ্রাউন্ডে চালু (Render পোর্ট এর জন্য)
    threading.Thread(target=run_web).start()
    
    # ২. মূল টেলিগ্রাম বট চালু
    print("Bot and Web Server are Running...")
    bot_app.run()
