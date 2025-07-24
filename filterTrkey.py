# -*- coding: utf-8 -*-
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import EditBannedRequest, GetParticipantRequest, GetFullChannelRequest
from telethon.tl.types import ChatBannedRights
from telethon.tl.functions.messages import ImportChatInviteRequest
try:
    from telethon.errors import FloodWait    # Telethon ≥ 1.34
except ImportError:
    from telethon.errors.rpcerrorlist import FloodWaitError as FloodWait
import asyncio, time
import json # لإدارة ملفات JSON

# ============== بيانات الدخول والإعدادات ==============
# الـ API ID والـ API Hash الخاصين بحسابك الشخصي (Userbot)
# **تأكد أن هذه القيم صحيحة من my.telegram.org**
my_api_id = 25202058
my_api_hash = 'ff6480cf0caf92223033f597401e5bf4'

# توكن البوت اللي أنت عاوزه يشتغل كواجهة (من @BotFather)
my_BOT_TOKEN = '1887695108:AAFLzc_KasLNKltLILSJoOQculfLYl9g8CU'# تأكد أن هذا التوكن هو بتاعك

# معلومات المطور والقناة (للاستخدام في الخاص فقط)
DEV_USERNAME = "developer: @x_4_f"  
CHANNEL_LINK_DISPLAY_TEXT = "source" # النص اللي هيظهر للينك
CHANNEL_LINK_URL = "https://t.me/ALTRKI_Story"

# ==================== إعدادات المستخدمين المسموح لهم ====================
# سيتم تحميل هذه القيم من ملف config.json
ALLOWED_USER_IDS = []
ALLOWED_USERNAMES = []

# اسم ملف الإعدادات
CONFIG_FILE = 'config.json'

# قاموس لتخزين حالة المستخدمين (مثلاً: هل ينتظر البوت منهم معرف مستخدم؟)
USER_STATE = {} # {user_id: "waiting_for_admin_id"}

# دالة لتحميل الإعدادات من ملف JSON
def load_config():
    global ALLOWED_USER_IDS, ALLOWED_USERNAMES
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            ALLOWED_USER_IDS = config.get('allowed_user_ids', [])
            ALLOWED_USERNAMES = config.get('allowed_usernames', [])
            print(f"Loaded config: IDs={ALLOWED_USER_IDS}, Usernames={ALLOWED_USERNAMES}")
    except FileNotFoundError:
        print(f"{CONFIG_FILE} not found. Creating with default owner ID.")
        # تعيين الـ ID الخاص بك كمالك عند أول تشغيل إذا لم يوجد ملف الإعدادات
        # **هنا لازم تحط الـ ID بتاعك كمالك البوت لو مكنتش حاطه قبل كده**
        # **هذا الـ ID هو الأساسي الذي سيسمح لك بإدارة البوت من الخاص**
        ALLOWED_USER_IDS = [6258807551] # <<<<< تأكد أن هذا هو الـ ID الخاص بك كمالك
        ALLOWED_USERNAMES = []
        save_config() # حفظ الإعدادات الافتراضية
    except json.JSONDecodeError:
        print(f"Error decoding {CONFIG_FILE}. It might be corrupted. Creating new config.")
        # في حالة تلف الملف، يتم إعادة إنشائه بالـ ID الافتراضي للمالك
        ALLOWED_USER_IDS = [6258807551] # <<<<< تأكد أن هذا هو الـ ID الخاص بك كمالك
        ALLOWED_USERNAMES = []
        save_config()

# دالة لحفظ الإعدادات إلى ملف JSON
def save_config():
    config = {
        'allowed_user_ids': ALLOWED_USER_IDS,
        'allowed_usernames': ALLOWED_USERNAMES
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    print(f"Saved config: IDs={ALLOWED_USER_IDS}, Usernames={ALLOWED_USERNAMES}")

# تحميل الإعدادات عند بدء تشغيل السكريبت
load_config()

# إنشاء الكلاينت: سيعمل كـ Userbot (بصلاحيات حسابك) وسيستقبل الأوامر كبوت (بالتوكن)
cli = TelegramClient("tito_session", my_api_id, my_api_hash).start(bot_token=my_BOT_TOKEN)

# إعدادات الحظر
BAN_RIGHTS = ChatBannedRights(until_date=None, view_messages=True) # حظر دائم

# مجموعات تم إيقاف التطهير فيها
STOP_CLEANUP = set()
# قاموس لتخزين مهام التطهير النشطة لكل دردشة
ACTIVE_CLEANUPS = {}
# قاموس لتخزين روابط الدعوة لكل شات
CHAT_INVITE_LINKS = {}

# قاموس لتخزين رسائل البدء المؤقتة ليتم حذفها لاحقًا
START_MESSAGES_TO_DELETE = {}

# --- وظائف مساعدة ---

# دالة للتحقق مما إذا كان المستخدم مسموحًا له باستخدام البوت
async def is_user_allowed(user_id, username):
    # تحقق من الـ ID
    if user_id in ALLOWED_USER_IDS:
        return True
    # تحقق من اسم المستخدم (إذا كان موجوداً وتم إدخاله في القائمة)
    if username and username.lower() in [u.lower() for u in ALLOWED_USERNAMES]:
        return True
    return False


# حظر مستخدم مع تجاوز FloodWait والأخطاء الشائعة
async def ban_user(chat_id, user_id):
    while True:
        try:
            await cli(EditBannedRequest(chat_id, user_id, BAN_RIGHTS))
            # print(f"Successfully banned user {user_id} in {chat_id}.") # إزالة طباعة النجاح لتقليل الحمل
            return True
        except FloodWait as e:
            print(f"FloodWait: Waiting for {e.seconds} seconds before retrying ban for {user_id} in {chat_id}")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            error_str = str(e).lower()
            if "user_admin_invalid" in error_str or "not an admin" in error_str or "participant is not a member" in error_str or "user_not_participant" in error_str:
                # هذا اليوزر ليس موجودا او ادمن او غير مشارك
                # print(f"Skipping ban for {user_id} in {chat_id}: User is an admin, not a member, or cannot be banned by bot. Error: {e}") # إزالة طباعة التخطي
                return False
            elif "channelprivateerror" in error_str or "chat_write_forbidden" in error_str or "peer_id_invalid" in error_str:
                print(f"Bot lost access to chat {chat_id}. Attempting to re-join. Error: {e}")
                STOP_CLEANUP.add(chat_id) # أوقف العملية
                await re_join_chat(chat_id) # حاول إعادة الانضمام
                return False
            else:
                # print(f"Failed to ban user {user_id} in {chat_id} due to unhandled error: {e}") # إزالة طباعة الخطأ العام
                return False

# العامل المسؤول عن تنفيذ الحظر من قائمة الانتظار
async def worker(chat_id, queue, counter_list):
    me_id = (await cli.get_me()).id # جلب ID البوت مرة واحدة
    while True:
        user = await queue.get()
        if user is None: # قيمة حراسة للإشارة إلى العامل بالتوقف
            queue.task_done()
            break
        
        if chat_id in STOP_CLEANUP:
            queue.task_done()
            continue
        
        # تحسين التحقق: محاولة الحظر مباشرة ثم التعامل مع الأخطاء
        # هذا يقلل من عدد طلبات GetParticipantRequest التي قد تكون بطيئة
        if user.id == me_id or user.bot: # لا تحظر البوت نفسه أو البوتات الأخرى
            queue.task_done()
            continue

        # محاولة الحظر وإضافة العداد لو نجح
        ban_successful = await ban_user(chat_id, user.id)
        if ban_successful:
            counter_list[0] += 1 # زيادة العداد فقط عند النجاح
        
        queue.task_done() # اكمال مهمة المستخدم بغض النظر عن نجاح الحظر

# دالة لإعادة الانضمام للمحادثة (صامتة في المجموعة)
async def re_join_chat(chat_id):
    if chat_id in CHAT_INVITE_LINKS and CHAT_INVITE_LINKS[chat_id]:
        invite_hash = CHAT_INVITE_LINKS[chat_id].split('/')[-1]
        print(f"Attempting to re-join chat {chat_id} using invite link: {CHAT_INVITE_LINKS[chat_id]}")
        try:
            await cli(ImportChatInviteRequest(invite_hash))
            print(f"Successfully re-joined chat {chat_id}.")
            STOP_CLEANUP.discard(chat_id) # أزل من قائمة الإيقاف لتسمح بالاستئناف لو لسه فيه شغل
            return True
        except Exception as e:
            print(f"Failed to re-join chat {chat_id}: {e}")
            return False
    else:
        print(f"No invite link available for chat {chat_id}. Cannot re-join automatically.")
        return False

# مهمة التنظيف السريعة جداً (التصفية الخاطفة الشبحية)
async def blitz_cleanup(chat_id):
    queue = asyncio.Queue()
    counter_list = [0]
    users_to_ban = []  

    print(f"Starting blitz cleanup for {chat_id}: Gathering all participants first...")
    start_gather_time = time.time()

    # محاولة الحصول على رابط الدعوة (صامتة تماماً للمستخدم)
    # هذه الخطوة مهمة جداً لضمان قدرة البوت على العودة إذا طُرد
    if chat_id not in CHAT_INVITE_LINKS or not CHAT_INVITE_LINKS[chat_id]:
        try:
            full_chat = await cli(GetFullChannelRequest(chat_id))
            if full_chat.full_chat.exported_invite:
                CHAT_INVITE_LINKS[chat_id] = full_chat.full_chat.exported_invite.link
                print(f"Obtained invite link for {chat_id}: {CHAT_INVITE_LINKS[chat_id]}")
            else:
                print(f"No invite link available for {chat_id}. Automatic re-join might fail.")
        except Exception as e:
            print(f"Could not get invite link for {chat_id}: {e} (suppressed message for user)")
            pass  

    try:
        # استخدام aggressive=True لجمع أكبر عدد ممكن من المشاركين بسرعة
        # لا نقوم بالتحقق من الأدمان هنا لتقليل الحمل، سيتم التعامل معها في العامل
        async for user in cli.iter_participants(chat_id, aggressive=True):
            users_to_ban.append(user)

        print(f"Finished gathering {len(users_to_ban)} potential users to ban in {int(time.time()-start_gather_time)} seconds.")

    except Exception as e:
        print(f"Error during initial participant gathering for chat {chat_id}: {e}")
        error_str = str(e).lower()
        if "channelprivateerror" in error_str or "chat_write_forbidden" in error_str or "peer_id_invalid" in error_str:
            print(f"Bot lost access to chat {chat_id} during gather. Attempting to re-join and stopping cleanup.")
            STOP_CLEANUP.add(chat_id)
            await re_join_chat(chat_id) # حاول يرجع بس بصمت
            return  

    # بدء العمال بعد جمع كل المستخدمين
    # زيادة عدد العمال بشكل كبير جداً لتحقيق أقصى سرعة
    NUM_WORKERS = 100 # تم زيادة العدد هنا
    workers_tasks = [asyncio.create_task(worker(chat_id, queue, counter_list)) for _ in range(NUM_WORKERS)]

    # إضافة كل المستخدمين للـ queue
    for user in users_to_ban:
        if chat_id in STOP_CLEANUP:
            break
        await queue.put(user)
    
    # إرسال قيم الحراسة للعمال ليتوقفوا بعد إفراغ الـ queue
    for _ in workers_tasks:
        await queue.put(None)  

    print(f"All {len(users_to_ban)} users added to queue. Waiting for workers to finish...")
    start_ban_time = time.time()

    # انتظار العمال لإنهاء مهامهم
    await queue.join()
    await asyncio.gather(*workers_tasks)

    print(f"Blitz cleanup for chat {chat_id} finished. Total banned: {counter_list[0]} in {int(time.time()-start_ban_time)} seconds for banning phase.")
    
    # حذف مهمة التنظيف من القائمة النشطة
    if chat_id in ACTIVE_CLEANUPS:
        del ACTIVE_CLEANUPS[chat_id]

# --- أوامر البوت (صامتة في المجموعة قدر الإمكان) ---

# رسالة الترحيب /start (فقط في الخاص)
@cli.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    if event.is_private:
        # تحقق من صلاحية المستخدم: هل هو ضمن المسموح لهم؟
        sender = await event.get_sender()
        if not await is_user_allowed(sender.id, sender.username):
            await event.respond("🚫 عفواً، هذا البوت مخصص للاستخدام من قبل مستخدمين معينين فقط.")
            return

        me = await event.client.get_me()
        await event.respond(
            f"""✨ مرحباً بك في عالم **تركي**! ✨

أنا هنا لأجعل مجموعتك أكثر نظاماً ونظافة.
أقوم بتصفية الأعضاء غير المرغوب فيهم بسرعة وكفاءة عالية.

🔥 *كيف أبدأ العمل؟*
فقط أرسل كلمة «تركي» في المجموعة وسأبدأ مهمتي فوراً.

🛑 *لإيقاف التصفية:* أرسل كلمة «بس» في المجموعة.

{DEV_USERNAME}
📢 **chanal:** [{CHANNEL_LINK_DISPLAY_TEXT}]({CHANNEL_LINK_URL})""",
            buttons=[
                [Button.inline("🛠 الأوامر", b"commands")],
                [Button.url("📢 انضم للقناة", CHANNEL_LINK_URL)],
                [Button.url("➕ أضفني لمجموعتك", f"https://t.me/{me.username}?startgroup=true")],
                [Button.inline("👤 إدارة المسؤولين", b"manage_admins")] # زر جديد لإدارة المسؤولين
            ]
        )
    elif event.is_group:
        # لا يرد على /start في المجموعات على الإطلاق ليبقى صامتاً
        pass

# زر الأوامر والرجوع (فقط في الخاص)
@cli.on(events.CallbackQuery(data=b"commands"))
async def command_help_callback(event):
    await event.answer()
    # تحقق من صلاحية المستخدم
    sender = await event.get_sender()
    if not await is_user_allowed(sender.id, sender.username):
        await event.edit("🚫 عفواً، لا تملك الصلاحية للوصول إلى هذه الأوامر.")
        return

    await event.edit(
        """🧠 *طريقة التشغيل:*

- أرسل كلمة `تركي` في أي مجموعة وأنا مشرف فيها وسأبدأ التصفية فوراً.
- أرسل `بس` لإيقاف التصفية.

📌 *ملاحظة هامة:* تأكد أن البوت لديه صلاحيات المشرف الكاملة و'حظر المستخدمين' و'حذف الرسائل' ليعمل بكفاءة.""",
        buttons=[Button.inline("🔙 رجوع", b"back_to_start")]
    )

@cli.on(events.CallbackQuery(data=b"back_to_start"))
async def back_to_start_callback(event):
    await event.answer()
    # تحقق من صلاحية المستخدم
    sender = await event.get_sender()
    if not await is_user_allowed(sender.id, sender.username):
        await event.edit("🚫 عفواً، لا تملك الصلاحية للوصول.")
        return

    me = await event.client.get_me()
    await event.edit(
        f"""✨ مرحباً بك في عالم **تركي**! ✨

أنا هنا لأجعل مجموعتك أكثر نظاماً ونظافة.
أقوم بتصفية الأعضاء غير المرغوب فيهم بسرعة وكفاءة عالية.

🔥 *كيف أبدأ العمل؟*
فقط أرسل كلمة «تركي» في المجموعة وسأبدأ مهمتي فوراً.

🛑 *لإيقاف التصفية:* أرسل كلمة «بس» في المجموعة.

{DEV_USERNAME}
📢 **chanal:** [{CHANNEL_LINK_DISPLAY_TEXT}]({CHANNEL_LINK_URL})""",
            buttons=[
                [Button.inline("🛠 الأوامر", b"commands")],
                [Button.url("📢 انضم للقناة", CHANNEL_LINK_URL)],
                [Button.url("➕ أضفني لمجموعتك", f"https://t.me/{me.username}?startgroup=true")],
                [Button.inline("👤 إدارة المسؤولين", b"manage_admins")] # زر إدارة المسؤولين
            ]
    )

# وظيفة لمعالجة زر إدارة المسؤولين (الرئيسي)
@cli.on(events.CallbackQuery(data=b"manage_admins"))
async def manage_admins_callback(event):
    await event.answer()
    # تأكد أن المستخدم الذي يضغط على الزر هو المالك
    sender = await event.get_sender()
    if sender.id != ALLOWED_USER_IDS[0]: # نفترض أن أول ID في القائمة هو المالك
        await event.edit("🚫 عفواً، هذه الميزة مخصصة للمالك فقط.")
        return

    await event.edit(
        """**👤 إدارة المسؤولين:**

اختر الإجراء المطلوب:""",
        buttons=[
            [Button.inline("➕ إضافة مشرف جديد", b"add_new_admin_prompt")],
            [Button.inline("➖ إزالة مشرف", b"remove_admin_prompt")], # زر إزالة مشرف جديد
            [Button.inline("📋 عرض المشرفين الحاليين", b"view_current_admins")],
            [Button.inline("🔙 رجوع", b"back_to_start")]
        ]
    )

# وظيفة للطلب من المالك إرسال ID المشرف الجديد
@cli.on(events.CallbackQuery(data=b"add_new_admin_prompt"))
async def add_new_admin_prompt(event):
    await event.answer()
    sender = await event.get_sender()
    if sender.id != ALLOWED_USER_IDS[0]:
        await event.edit("🚫 عفواً، هذه الميزة مخصصة للمالك فقط.")
        return
    
    USER_STATE[sender.id] = "waiting_for_admin_id_to_add" # تغيير الحالة لتمييزها
    await event.edit("الرجاء إرسال **معرف المستخدم (ID)** للمشرف الجديد:\n\n*ملاحظة: للحصول على الـ ID، أعد توجيه أي رسالة من المستخدم إلى @userinfobot.*",
                     buttons=[Button.inline("إلغاء", b"cancel_admin_action")])

# وظيفة للطلب من المالك إرسال ID المشرف المراد إزالته
@cli.on(events.CallbackQuery(data=b"remove_admin_prompt"))
async def remove_admin_prompt(event):
    await event.answer()
    sender = await event.get_sender()
    if sender.id != ALLOWED_USER_IDS[0]:
        await event.edit("🚫 عفواً، هذه الميزة مخصصة للمالك فقط.")
        return
    
    USER_STATE[sender.id] = "waiting_for_admin_id_to_remove" # حالة جديدة للإزالة
    await event.edit("الرجاء إرسال **معرف المستخدم (ID)** للمشرف الذي تريد إزالته:",
                     buttons=[Button.inline("إلغاء", b"cancel_admin_action")])

# وظيفة لإلغاء أي عملية إضافة/إزالة مشرف
@cli.on(events.CallbackQuery(data=b"cancel_admin_action"))
async def cancel_admin_action(event):
    await event.answer()
    sender = await event.get_sender()
    if sender.id in USER_STATE:
        del USER_STATE[sender.id]
        await event.edit("تم إلغاء العملية.",
                         buttons=[Button.inline("🔙 رجوع", b"manage_admins")]) # العودة لخيارات إدارة المسؤولين
    else:
        await event.edit("لا توجد عملية جارية لإلغائها.",
                         buttons=[Button.inline("🔙 رجوع", b"manage_admins")])

# وظيفة معالجة الرسائل الواردة (لإضافة أو إزالة الـ ID)
@cli.on(events.NewMessage(incoming=True)) # يستمع لكل الرسائل الواردة
async def handle_admin_id_input(event):
    sender_id = event.sender_id
    if sender_id != ALLOWED_USER_IDS[0]: # فقط المالك يمكنه استخدام هذه الوظيفة
        return

    if sender_id in USER_STATE:
        try:
            target_id = int(event.text.strip())
            
            if USER_STATE[sender_id] == "waiting_for_admin_id_to_add":
                if target_id in ALLOWED_USER_IDS:
                    await event.reply("هذا المعرف موجود بالفعل في قائمة المشرفين.")
                else:
                    ALLOWED_USER_IDS.append(target_id)
                    save_config()
                    await event.reply(f"تمت إضافة المعرف `{target_id}` بنجاح كمسؤول جديد!",
                                      buttons=[Button.inline("🔙 رجوع", b"manage_admins")])
            
            elif USER_STATE[sender_id] == "waiting_for_admin_id_to_remove":
                if target_id == ALLOWED_USER_IDS[0]:
                    await event.reply("لا يمكنك إزالة الـ ID الخاص بك كمالك البوت.")
                elif target_id not in ALLOWED_USER_IDS:
                    await event.reply("هذا المعرف غير موجود في قائمة المشرفين.")
                else:
                    ALLOWED_USER_IDS.remove(target_id)
                    save_config()
                    await event.reply(f"تمت إزالة المعرف `{target_id}` بنجاح من قائمة المسؤولين!",
                                      buttons=[Button.inline("🔙 رجوع", b"manage_admins")])
            
            del USER_STATE[sender_id] # مسح الحالة بعد المعالجة
        except ValueError:
            await event.reply("الرجاء إرسال معرف مستخدم (ID) صحيح (أرقام فقط).")
        except Exception as e:
            print(f"Error processing admin ID: {e}")
            await event.reply("حدث خطأ أثناء معالجة طلبك. الرجاء المحاولة مرة أخرى.")
        finally:
            # محاولة حذف رسالة المستخدم التي تحتوي على الـ ID بعد المعالجة
            try:
                await event.delete()
            except Exception:
                pass # تجاهل لو الرسالة متحذفتش

# وظيفة لعرض المشرفين الحاليين
@cli.on(events.CallbackQuery(data=b"view_current_admins"))
async def view_current_admins(event):
    await event.answer()
    sender = await event.get_sender()
    if sender.id != ALLOWED_USER_IDS[0]:
        await event.edit("🚫 عفواً، هذه الميزة مخصصة للمالك فقط.")
        return
    
    ids_str = "\n".join(map(str, ALLOWED_USER_IDS)) if ALLOWED_USER_IDS else "لا يوجد."
    usernames_str = "\n".join(ALLOWED_USERNAMES) if ALLOWED_USERNAMES else "لا يوجد."

    message = f"""**📋 المشرفون الحاليون:**

**معرفات المستخدمين (IDs):**
`{ids_str}`

**أسماء المستخدمين (Usernames):**
`{usernames_str}`

"""
    await event.edit(message, buttons=[Button.inline("🔙 رجوع", b"manage_admins")]) # العودة لخيارات إدارة المسؤولين


# أمر "تركي" لبدء التصفية (الرد الوحيد في المجموعة و سيتم حذفه فوراً)
@cli.on(events.NewMessage(pattern='(?i)تركي', chats=None))
async def start_cleanup_command(event):
    if not event.is_group and not event.is_channel:
        return  

    # تحقق من صلاحية المستخدم قبل معالجة الأمر في المجموعات والقنوات
    sender = await event.get_sender()
    if not await is_user_allowed(sender.id, sender.username):
        # لا يرد على المستخدم في المجموعة/القناة، فقط يسجل محاولة غير مصرح بها
        print(f"Unauthorized user {sender.id} (@{sender.username}) attempted to start cleanup in {event.chat_id}.")
        return

    chat_id = event.chat_id
    me = await cli.get_me()

    try:
        participant_me = await cli(GetParticipantRequest(chat_id, me.id))
        
        # تحقق من صلاحية حظر المستخدمين (Ban users)
        if not getattr(participant_me.participant, "admin_rights", None) or \
           not getattr(participant_me.participant.admin_rights, "ban_users", False):
            print(f"Bot in chat {chat_id} lacks 'ban_users' permission. Cannot proceed.")
            # لا يرد على المستخدم في المجموعة بهذا الخطأ، فقط في الـ Terminal
            return
        
        # تحقق من صلاحية حذف الرسائل (Delete messages)
        if not getattr(participant_me.participant.admin_rights, "delete_messages", False):
            print(f"Bot in chat {chat_id} lacks 'delete_messages' permission. Ghost mode might fail.")
            # لا يرد على المستخدم في المجموعة بهذا الخطأ
            return
            
        # محاولة الحصول على رابط الدعوة (صامتة تماماً)
        # هذه الصلاحية حاسمة لإعادة الانضمام في حال الطرد
        if not getattr(participant_me.participant.admin_rights, "invite_users", False):
            print(f"Bot does not have 'invite users via link' permission in {chat_id}. Automatic re-join might fail.")
            pass # لا توقف العملية، فقط سجل التحذير
        
        try:
            full_chat = await cli(GetFullChannelRequest(chat_id))
            if full_chat.full_chat.exported_invite:
                CHAT_INVITE_LINKS[chat_id] = full_chat.full_chat.exported_invite.link
                print(f"Initial invite link for {chat_id}: {CHAT_INVITE_LINKS[chat_id]}")
            else:
                print(f"No invite link available for {chat_id}. Automatic re-join might fail.")
                pass
        except Exception as ex:
            print(f"Could not get initial invite link for {chat_id}: {ex} (suppressed message for user)")
            pass

    except Exception as err:
        print(f"Error checking bot permissions in chat {chat_id}: {err}")
        # لا يرد على المستخدم في المجموعة بأي خطأ في الصلاحيات
        return


    if chat_id in ACTIVE_CLEANUPS and not ACTIVE_CLEANUPS[chat_id].done():
        print(f"Cleanup already running in chat {chat_id}.")
        # لا يرد على المستخدم في المجموعة
        return

    STOP_CLEANUP.discard(chat_id)

    # إرسال الرسالة الأولية وحفظها لحذفها فوراً
    initial_message = await event.reply("😈 **يتم نيك المجموعه**")
    START_MESSAGES_TO_DELETE[chat_id] = initial_message

    # جدولة حذف الرسالة فوراً (بعد جزء صغير جداً من الثانية)
    await asyncio.sleep(0.5) # نصف ثانية فقط
    try:
        if chat_id in START_MESSAGES_TO_DELETE:
            await START_MESSAGES_TO_DELETE[chat_id].delete()
            del START_MESSAGES_TO_DELETE[chat_id]
    except Exception as e:
        print(f"Failed to delete initial message in {chat_id}: {e}")
        pass # تجاهل الخطأ لو مقدرش يحذف الرسالة (مثل لو البوت اطرد بسرعة فائقة)

    # تشغيل عملية التصفية الخاطفة في الخلفية
    cleanup_task = asyncio.create_task(blitz_cleanup(chat_id))
    ACTIVE_CLEANUPS[chat_id] = cleanup_task


# أمر "بس" لإيقاف التصفية (صامت تماماً في المجموعة)
@cli.on(events.NewMessage(pattern='(?i)بس', chats=None))
async def stop_cleanup_command(event):
    if not event.is_group and not event.is_channel:
        pass # لا يرد على "بس" في الخاص

    # تحقق من صلاحية المستخدم قبل معالجة الأمر في المجموعات والقنوات
    sender = await event.get_sender()
    if not await is_user_allowed(sender.id, sender.username):
        # لا يرد على المستخدم في المجموعة/القناة، فقط يسجل محاولة غير مصرح بها
        print(f"Unauthorized user {sender.id} (@{sender.username}) attempted to stop cleanup in {event.chat_id}.")
        return

    chat_id = event.chat_id
    
    STOP_CLEANUP.add(chat_id)

    if chat_id in ACTIVE_CLEANUPS:
        await asyncio.sleep(0.5) # إعطاء فرصة لـ blitz_cleanup لتلاحظ التوقف
        if ACTIVE_CLEANUPS[chat_id].done():
            del ACTIVE_CLEANUPS[chat_id]
            print(f"Cleanup in chat {chat_id} stopped.")
        else:
            try:
                # محاولة إلغاء المهمة إذا كانت لا تزال قيد التشغيل
                ACTIVE_CLEANUPS[chat_id].cancel()
                await ACTIVE_CLEANUPS[chat_id] # انتظر حتى يتم إلغاؤها
                del ACTIVE_CLEANUPS[chat_id]
                print(f"Cleanup in chat {chat_id} stopped and task cancelled.")
            except asyncio.CancelledError:
                print(f"Cleanup task for {chat_id} was successfully cancelled.")
                del ACTIVE_CLEANUPS[chat_id]
            except Exception as e:
                print(f"Error stopping cleanup task for {chat_id}: {e}")
                pass # لا يرد على المستخدم
    else:
        print(f"No cleanup running in chat {chat_id} to stop.")
    pass # لا يرسل أي رسالة للمستخدم


# عند انضمام عضو جديد (صامت تماماً في المجموعة)
@cli.on(events.ChatAction)
async def new_members_action(event):
    if event.user_added and event.user.id == (await cli.get_me()).id:
        print(f"Userbot was added to chat {event.chat_id}. Checking permissions...")
        try:
            chat_id = event.chat_id
            me = await cli.get_me()
            participant_me = await cli(GetParticipantRequest(chat_id, me.id))
            
            has_ban_permission = getattr(participant_me.participant.admin_rights, "ban_users", False)
            has_delete_permission = getattr(participant_me.participant.admin_rights, "delete_messages", False)
            has_invite_permission = getattr(participant_me.participant.admin_rights, "invite_users", False)

            if not has_ban_permission:
                print(f"Bot added to chat {chat_id} but lacks 'ban_users' permission. Cannot perform cleanup.")
            elif not has_delete_permission:
                print(f"Bot added to chat {chat_id} but lacks 'delete_messages' permission. Ghost mode might fail.")
            elif not has_invite_permission:
                print(f"Bot added to chat {chat_id} but lacks 'invite_users' permission. Automatic re-join might fail.")
            else:
                print(f"Bot added to chat {chat_id} successfully and has all required permissions for ghost mode.")
        except Exception as e:
            print(f"Error checking permissions after addition to chat {event.chat_id}: {e}")
            pass

print("🔥 تركي - بوت التصفية الفاجر يعمل الآن!")
print(f"البوت يعمل بالتوكن: {my_BOT_TOKEN}")
print(f"الحساب يعمل بالـ API ID: {my_api_id}")

cli.run_until_disconnected()
