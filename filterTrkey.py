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

# ============== بيانات الدخول والإعدادات ==============
# الـ API ID والـ API Hash الخاصين بحسابك الشخصي (Userbot)
# **تأكد أن هذه القيم صحيحة من my.telegram.org**
my_api_id = 25202058 # تم تحديث الـ API ID
my_api_hash = 'ff6480cf0caf92223033f597401e5bf4' # تم تحديث الـ API Hash

# توكن البوت اللي أنت عاوزه يشتغل كواجهة (من @BotFather)
my_BOT_TOKEN = '1887695108:AAFLzc_KasLNKltLILSJoOQculfLYl9g8CU' # تم تحديث توكن البوت

# معلومات المطور والقناة (للاستخدام في الخاص فقط)
DEV_USERNAME = "developer: @x_4_f" # تم تحديث يوزر المطور
CHANNEL_LINK_DISPLAY_TEXT = "source" # تم تحديث نص لينك القناة
CHANNEL_LINK_URL = "https://t.me/ALTRKI_Story" # تم تحديث لينك القناة

# إنشاء الكلاينت: سيعمل كـ Userbot (بصلاحيات حسابك) وسيستقبل الأوامر كبوت (بالتوكن)
cli = TelegramClient("tito_session", api_id, api_hash).start(bot_token=BOT_TOKEN)

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

# قائمة المستخدمين المسموح لهم باستخدام البوت (معرف المطور مضاف تلقائياً)
# ملاحظة: هذه القائمة غير دائمة وستُمسح عند إعادة تشغيل البوت.
# لجعلها دائمة، ستحتاج إلى حفظها في ملف أو قاعدة بيانات.
AUTHORIZED_USERS = {api_id} 

# --- وظائف مساعدة ---

async def is_owner(user_id):
    me = await cli.get_me()
    return user_id == me.id

async def is_authorized(user_id):
    return user_id in AUTHORIZED_USERS or await is_owner(user_id)

# حظر مستخدم مع تجاوز FloodWait والأخطاء الشائعة
async def ban_user(chat_id, user_id):
    while True:
        try:
            await cli(EditBannedRequest(chat_id, user_id, BAN_RIGHTS))
            return True
        except FloodWait as e:
            print(f"FloodWait: Waiting for {e.seconds} seconds before retrying ban for {user_id} in {chat_id}")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            error_str = str(e).lower()
            if "user_admin_invalid" in error_str or "not an admin" in error_str or "participant is not a member" in error_str or "user_not_participant" in error_str:
                return False
            elif "channelprivateerror" in error_str or "chat_write_forbidden" in error_str or "peer_id_invalid" in error_str:
                print(f"Bot lost access to chat {chat_id}. Attempting to re-join. Error: {e}")
                STOP_CLEANUP.add(chat_id) # أوقف العملية
                await re_join_chat(chat_id) # حاول إعادة الانضمام
                return False
            else:
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
        
        if user.id == me_id or user.bot: # لا تحظر البوت نفسه أو البوتات الأخرى
            queue.task_done()
            continue

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
        me = await event.client.get_me()
        await event.respond(
            f"""✨ مرحباً بك في عالم تيتو! ✨

أنا هنا لأجعل مجموعتك أكثر نظاماً ونظافة.
أقوم بتصفية الأعضاء غير المرغوب فيهم بسرعة وكفاءة عالية.

🔥 *كيف أبدأ العمل؟*
فقط أرسل كلمة «تركي» في المجموعة وسأبدأ مهمتي فوراً.

🛑 *لإيقاف التصفية:* أرسل كلمة «Dur» في المجموعة.

{DEV_USERNAME}
📢 **chanal:** [{CHANNEL_LINK_DISPLAY_TEXT}]({CHANNEL_LINK_URL})""",
            buttons=[
                [Button.inline("🛠 الأوامر", b"commands")],
                [Button.url("📢 انضم للقناة", CHANNEL_LINK_URL)],
                [Button.url("➕ أضفني لمجموعتك", f"https://t.me/{me.username}?startgroup=true")]
            ]
        )
    elif event.is_group:
        pass

# زر الأوامر والرجوع (فقط في الخاص)
@cli.on(events.CallbackQuery(data=b"commands"))
async def command_help_callback(event):
    await event.answer()
    await event.edit(
        """🧠 *طريقة التشغيل:*

- أرسل كلمة `تركي` في أي مجموعة وأنا مشرف فيها وسأبدأ التصفية فوراً.
- أرسل `Dur` لإيقاف التصفية.

📌 *ملاحظة هامة:* تأكد أن البوت لديه صلاحيات المشرف الكاملة و'حظر المستخدمين' و'حذف الرسائل' ليعمل بكفاءة.

*أوامر إدارة المستخدمين (للمطور فقط):*
- `/adduser <معرف_المستخدم>`: لإضافة مستخدم لقائمة السماح.
- `/removeuser <معرف_المستخدم>`: لحذف مستخدم من قائمة السماح.
""",
        buttons=[Button.inline("🔙 رجوع", b"back_to_start")]
    )

@cli.on(events.CallbackQuery(data=b"back_to_start"))
async def back_to_start_callback(event):
    await event.answer()
    me = await event.client.get_me()
    await event.edit(
        f"""✨ مرحباً بك في عالم تيتو! ✨

أنا هنا لأجعل مجموعتك أكثر نظاماً ونظافة.
أقوم بتصفية الأعضاء غير المرغوب فيهم بسرعة وكفاءة عالية.

🔥 *كيف أبدأ العمل؟*
فقط أرسل كلمة «تركي» في المجموعة وسأبدأ مهمتي فوراً.

🛑 *لإيقاف التصفية:* أرسل كلمة «Dur» في المجموعة.

{DEV_USERNAME}
📢 **chanal:** [{CHANNEL_LINK_DISPLAY_TEXT}]({CHANNEL_LINK_URL})""",
            buttons=[
                [Button.inline("🛠 الأوامر", b"commands")],
                [Button.url("📢 انضم للقناة", CHANNEL_LINK_URL)],
                [Button.url("➕ أضفني لمجموعتك", f"https://t.me/{me.username}?startgroup=true")]
            ]
    )

# أمر "تركي" لبدء التصفية (الرد الوحيد في المجموعة و سيتم حذفه فوراً)
@cli.on(events.NewMessage(pattern='(?i)تركي', chats=None))
async def start_cleanup_command(event):
    if not event.is_group and not event.is_channel:
        return    

    if not await is_authorized(event.sender_id):
        print(f"User {event.sender_id} is not authorized to use the bot.")
        return # لا يرد على المستخدم في المجموعة إذا لم يكن مصرحاً له

    chat_id = event.chat_id
    me = await cli.get_me()

    try:
        participant_me = await cli(GetParticipantRequest(chat_id, me.id))
        
        if not getattr(participant_me.participant, "admin_rights", None) or \
           not getattr(participant_me.participant.admin_rights, "ban_users", False):
            print(f"Bot in chat {chat_id} lacks 'ban_users' permission. Cannot proceed.")
            return
        
        if not getattr(participant_me.participant.admin_rights, "delete_messages", False):
            print(f"Bot in chat {chat_id} lacks 'delete_messages' permission. Ghost mode might fail.")
            return
            
        if not getattr(participant_me.participant.admin_rights, "invite_users", False):
            print(f"Bot does not have 'invite users via link' permission in {chat_id}. Automatic re-join might fail.")
            pass 
        
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
        return


    if chat_id in ACTIVE_CLEANUPS and not ACTIVE_CLEANUPS[chat_id].done():
        print(f"Cleanup already running in chat {chat_id}.")
        return

    STOP_CLEANUP.discard(chat_id)

    initial_message = await event.reply("😈 **يتم نيك المجموعه**")
    START_MESSAGES_TO_DELETE[chat_id] = initial_message

    await asyncio.sleep(0.5) 
    try:
        if chat_id in START_MESSAGES_TO_DELETE:
            await START_MESSAGES_TO_DELETE[chat_id].delete()
            del START_MESSAGES_TO_DELETE[chat_id]
    except Exception as e:
        print(f"Failed to delete initial message in {chat_id}: {e}")
        pass 

    cleanup_task = asyncio.create_task(blitz_cleanup(chat_id))
    ACTIVE_CLEANUPS[chat_id] = cleanup_task


# أمر "Dur" لإيقاف التصفية (صامت تماماً في المجموعة)
@cli.on(events.NewMessage(pattern='(?i)Dur', chats=None))
async def stop_cleanup_command(event):
    if not event.is_group and not event.is_channel:
        pass 

    if not await is_authorized(event.sender_id):
        print(f"User {event.sender_id} is not authorized to stop the bot.")
        return # لا يرد على المستخدم في المجموعة إذا لم يكن مصرحاً له

    chat_id = event.chat_id
    
    STOP_CLEANUP.add(chat_id)

    if chat_id in ACTIVE_CLEANUPS:
        await asyncio.sleep(0.5) 
        if ACTIVE_CLEANUPS[chat_id].done():
            del ACTIVE_CLEANUPS[chat_id]
            print(f"Cleanup in chat {chat_id} stopped.")
        else:
            try:
                ACTIVE_CLEANUPS[chat_id].cancel()
                await ACTIVE_CLEANUPS[chat_id] 
                del ACTIVE_CLEANUPS[chat_id]
                print(f"Cleanup in chat {chat_id} stopped and task cancelled.")
            except asyncio.CancelledError:
                print(f"Cleanup task for {chat_id} was successfully cancelled.")
                del ACTIVE_CLEANUPS[chat_id]
            except Exception as e:
                print(f"Error stopping cleanup task for {chat_id}: {e}")
                pass 
    else:
        print(f"No cleanup running in chat {chat_id} to stop.")
    pass 

# أمر إضافة مستخدم لقائمة السماح
@cli.on(events.NewMessage(pattern='/adduser (\d+)'))
async def add_user_command(event):
    if not await is_owner(event.sender_id):
        await event.reply("عذراً، هذا الأمر مخصص للمطور فقط.")
        return

    try:
        user_id_to_add = int(event.pattern_match.group(1))
        AUTHORIZED_USERS.add(user_id_to_add)
        await event.reply(f"تم إضافة المستخدم `{user_id_to_add}` إلى قائمة السماح.")
        print(f"User {user_id_to_add} added to AUTHORIZED_USERS. Current list: {AUTHORIZED_USERS}")
    except ValueError:
        await event.reply("صيغة الأمر خاطئة. الرجاء استخدام: `/adduser <معرف_المستخدم>`")

# أمر حذف مستخدم من قائمة السماح
@cli.on(events.NewMessage(pattern='/removeuser (\d+)'))
async def remove_user_command(event):
    if not await is_owner(event.sender_id):
        await event.reply("عذراً، هذا الأمر مخصص للمطور فقط.")
        return

    try:
        user_id_to_remove = int(event.pattern_match.group(1))
        if user_id_to_remove == api_id: # منع المطور من حذف نفسه
            await event.reply("لا يمكنك حذف معرف المطور الخاص بك من قائمة السماح.")
            return

        if user_id_to_remove in AUTHORIZED_USERS:
            AUTHORIZED_USERS.remove(user_id_to_remove)
            await event.reply(f"تم حذف المستخدم `{user_id_to_remove}` من قائمة السماح.")
            print(f"User {user_id_to_remove} removed from AUTHORIZED_USERS. Current list: {AUTHORIZED_USERS}")
        else:
            await event.reply(f"المستخدم `{user_id_to_remove}` ليس موجوداً في قائمة السماح أصلاً.")
    except ValueError:
        await event.reply("صيغة الأمر خاطئة. الرجاء استخدام: `/removeuser <معرف_المستخدم>`")


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

print("🔥 تيتو - بوت التصفية الفاجر يعمل الآن!")
print(f"البوت يعمل بالتوكن: {BOT_TOKEN}")
print(f"الحساب يعمل بالـ API ID: {api_id}")
print(f"المستخدمون المصرح لهم حالياً: {AUTHORIZED_USERS}")

cli.run_until_disconnected()
