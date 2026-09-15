import os
import logging
from pyrogram import Client, filters
from pyrogram.types import ForceReply, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
from database import add_user, count_users, set_mode, get_mode, save_caption, get_caption, save_thumbnail, get_thumbnail, delete_thumbnail
import ffmpeg

logging.basicConfig(level=logging.INFO)
app = Client("video_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# স্টেপ ট্র্যাক করার জন্য ডিকশনারি
user_steps = {}

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# স্টার্ট বাটন ডিজাইন
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

# Skip বাটন তৈরির ফাংশন
def skip_button(step):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⏭️ Skip (এড়িয়ে যান)", callback_data=f"skip_{step}")]]
    )

# প্রোগ্রেস বার
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
@app.on_message(filters.command("start") & filters.private)
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
@app.on_callback_query()
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
        # রিনেম স্কিপ করলে শুধু ক্যাপশনের জন্য জিজ্ঞেস করবে
        if user_id in user_steps and isinstance(user_steps[user_id], dict):
            user_steps[user_id]["rename"] = False
        await query.message.delete()
        await query.message.reply_text("✅ রিনেম স্কিপ করা হয়েছে।\n\nএখন ক্যাপশন লিখুন অথবা Skip করুন:", reply_markup=skip_button("caption"))

    elif data == "skip_caption":
        # ক্যাপশন স্কিপ করলে সরাসরি ফাইল প্রসেসিং শুরু করবে
        await query.message.delete()
        if user_id in user_steps and isinstance(user_steps[user_id], dict):
            data = user_steps[user_id]
            data["custom_caption"] = None
            await process_file(client, query.message, data)
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
@app.on_message(filters.reply & filters.private)
async def reply_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_steps:
        return

    step = user_steps[user_id]

    # ডিফল্ট ক্যাপশন সেট করা
    if step == "set_default_cap":
        save_caption(user_id, message.text)
        await message.reply_text("✅ ডিফল্ট ক্যাপশন সেভ হয়েছে!", reply_markup=start_buttons())
        del user_steps[user_id]

# ---------------------------------------------------------
# ৪. থাম্বনেইল সেভ হ্যান্ডলার
# ---------------------------------------------------------
@app.on_message(filters.photo & filters.private)
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
    # মূল ফাইলের মেসেজ আইডি সেভ করে রাখা হচ্ছে
    user_steps[user_id] = {
        "action": "process", 
        "media_type": media_type, 
        "msg_id": message.id, 
        "rename": True,
        "original_file_name": message.document.file_name if media_type == "document" else message.video.file_name
    }
    
    text = "📝 অনুগ্রহ করে ফাইলের জন্য একটি নতুন নাম লিখুন (এক্সটেনশন ছাড়া, যেমন: My Video 2016):"
    await message.reply_text(text, reply_markup=skip_button("rename"))

# ---------------------------------------------------------
# ৬. নতুন নাম লিখলে এই হ্যান্ডলার কাজ করবে
# ---------------------------------------------------------
@app.on_message(filters.text & filters.private & ~filters.command(["start", "setcaption", "setthumb", "delthumb"]))
async def text_handler(client, message):
    user_id = message.from_user.id
    
    if user_id in user_steps and isinstance(user_steps[user_id], dict) and user_steps[user_id].get("action") == "process":
        if user_steps[user_id].get("rename") == True:
            # নতুন নাম সেট করে ক্যাপশনের জন্য জিজ্ঞেস করা
            user_steps[user_id]["new_name"] = message.text
            user_steps[user_id]["rename"] = False
            
            await message.reply_text("✅ নাম সেভ হয়েছে।\n\nএখন ক্যাপশন লিখুন অথবা Skip করুন:", reply_markup=skip_button("caption"))
        
        else:
            # ক্যাপশন লিখলে ফাইল প্রসেস করা
            user_steps[user_id]["custom_caption"] = message.text
            data = user_steps[user_id]
            await process_file(client, message, data)
            del user_steps[user_id]

# ---------------------------------------------------------
# ৭. মূল ফিউচার: কনভার্ট, রিনেম, থাম্বনেইল লাগানো (সঠিক এক্সটেনশন সহ)
# ---------------------------------------------------------
async def process_file(client, message, data):
    media_type = data.get("media_type")
    new_name = data.get("new_name", None)
    custom_caption = data.get("custom_caption", None)
    original_file_name = data.get("original_file_name", "Video_File.mp4")

    caption = custom_caption or get_caption(message.from_user.id) or "✅ ফাইলটি সফলভাবে প্রসেস করা হয়েছে।"
    thumb_path = get_thumbnail(message.from_user.id)
    output_mode = get_mode(message.from_user.id)
    
    process_msg = await message.reply_text("⏳ ফাইল ডাউনলোড শুরু হয়েছে...")
    
    try:
        original_msg = message.reply_to_message if message.reply_to_message else message
        
        # ডাউনলোড করা ফাইলের পাথ
        file_path = await original_msg.download(file_name="downloads/", progress=progress_bar, progress_args=(process_msg,))
        
        await process_msg.edit_text("⚙️ প্রসেস হচ্ছে...")
        
        # মূল ফাইলের এক্সটেনশন বের করা (যেমন: .mkv, .mp4)
        _, original_ext = os.path.splitext(original_file_name)
        if not original_ext:
            original_ext = ".mp4" # এক্সটেনশন না থাকলে ডিফল্ট mp4
            
        # রিনেম লজিক (এক্সটেনশন সহ সঠিকভাবে)
        if new_name:
            # ইউজার যদি এক্সটেনশন না দেয়, তবে আসল এক্সটেনশন যোগ করা হবে
            user_name, user_ext = os.path.splitext(new_name)
            if user_ext:
                final_name = new_name
            else:
                final_name = f"{new_name}{original_ext}"
                
            final_file = f"downloads/{final_name}"
            os.rename(file_path, final_file)
        else:
            # স্কিপ করলে আসল ফাইলের নামই থাকবে
            final_file = file_path
            
        # কনভার্ট লজিক (ডকুমেন্টস টু ভিডিও)
        if media_type == "document":
            await process_msg.edit_text("🎞️ ভিডিওতে কনভার্ট হচ্ছে...")
            
            # ভিডিও কনভার্ট করার সময় আউটপুট ফাইলের এক্সটেনশন .mp4 করা হচ্ছে
            video_file = f"downloads/Converted_{message.id}.mp4"
            stream = ffmpeg.input(final_file)
            # কপি কোডেক ব্যবহার করা হচ্ছে যাতে কোয়ালিটি নষ্ট না হয়
            stream = ffmpeg.output(stream, video_file, **{"c:v": "copy", "c:a": "copy"})
            ffmpeg.run(stream, quiet=True, overwrite_output=True)
            
            os.remove(final_file) # পুরোনো ফাইল ডিলিট
            send_file = video_file
        else:
            send_file = final_file
            
        await process_msg.edit_text("🚀 আপলোড হচ্ছে...")
        
        # আউটপুট মোড অনুযায়ী পাঠানো
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
        if 'send_file' in locals() and os.path.exists(send_file):
            os.remove(send_file)

# ডকুমেন্ট বা ভিডিও রিসিভ করলে রিনেমের জন্য জিজ্ঞেস করবে
@app.on_message(filters.document & filters.private)
async def document_handler(client, message):
    await ask_rename_and_caption(client, message, "document")

@app.on_message(filters.video & filters.private)
async def video_handler(client, message):
    await ask_rename_and_caption(client, message, "video")

if __name__ == "__main__":
    print("Bot is Running with Fixed Extension Logic...")
    app.run()
