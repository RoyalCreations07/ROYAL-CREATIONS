import random
import asyncio
import re
import ast
import math
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, \
    make_inactive
from info import ADMINS, AUTH_CHANNEL, LOG_CHANNEL, SUPPORT_LINK, UPDATES_LINK, PICS, \
    PROTECT_CONTENT, IMDB, AUTO_FILTER, SPELL_CHECK, IMDB_TEMPLATE, AUTO_DELETE
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid, ChatAdminRequired
from utils import get_size, is_subscribed, get_shortlink, get_poster, temp, get_settings, save_group_settings
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    settings = await get_settings(message.chat.id)
    if settings["auto_filter"]:
        userid = message.from_user.id if message.from_user else None
        if not userid:
            search = message.text
            k = await message.reply(f"You'r anonymous admin! Sorry you can't get '{search}' from here.\nYou can get '{search}' from bot inline search.")
            await asyncio.sleep(30)
            await k.delete()
            try:
                await message.delete()
            except:
                pass
            return

        if AUTH_CHANNEL and not await is_subscribed(client, message):
            try:
                invite_link = await client.create_chat_invite_link(int(AUTH_CHANNEL))
            except ChatAdminRequired:
                logger.error("Make sure Bot is admin in Forcesub channel")
                return
            buttons = [[
                InlineKeyboardButton("📢 Updates Channel 📢", url=invite_link.invite_link)
            ],[
                InlineKeyboardButton("🔁 Request Again 🔁", callback_data="grp_checksub")
            ]]
            reply_markup = InlineKeyboardMarkup(buttons)
            k = await message.reply_photo(
                photo=random.choice(PICS),
                caption=f"👋 Hello {message.from_user.mention},\n\nPlease join my 'Updates Channel' and request again. 😇",
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
            await asyncio.sleep(300)
            await k.delete()
            try:
                await message.delete()
            except:
                pass
        else:
            await auto_filter(client, message)
    else:
        k = await message.reply_text('Auto Filter Off! ❌')
        await asyncio.sleep(5)
        await k.delete()
        try:
            await message.delete()
        except:
            pass


@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    try:
        offset = int(offset)
    except:
        offset = 0
    search = BUTTONS.get(key)
    if not search:
        await query.answer(f"Hello {query.from_user.first_name},\nSend New Request Again!", show_alert=True)
        return

    files, n_offset, total = await get_search_results(search, offset=offset, filter=True)
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0

    if not files:
        return
    temp.FILES[key] = files
    settings = await get_settings(query.message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["shortlink"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"✨ {get_size(file.file_size)} ⚡️ {file.file_name}", url=await get_shortlink(query.message.chat.id, f'https://t.me/{temp.U_NAME}?start={pre}_{query.message.chat.id}_{file.file_id}')
                )
            ]
            for file in files
        ]
        btn.insert(0,
            [InlineKeyboardButton("🎈 Send All 🎈", url=await get_shortlink(query.message.chat.id, f'https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{pre}_{key}'))]
        )
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"✨ {get_size(file.file_size)} ⚡️ {file.file_name}", callback_data=f'{pre}#{file.file_id}',
                )
            ]
            for file in files
        ]
        btn.insert(0,
            [InlineKeyboardButton("🎈 Send All 🎈", callback_data=f"send_all#{pre}#{key}")]
        )

    if 0 < offset <= 10:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - 10
    if n_offset == 0:

        btn.append(
            [InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
             InlineKeyboardButton(f"🗓 PAGES {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}",
                                  callback_data="buttons")]
        )
        btn.append(
            [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")]
        )
    elif off_set is None:
        btn.append(
            [InlineKeyboardButton(f"🗓 PAGES {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="buttons"),
             InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")])
        btn.append(
            [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")])
    else:
        btn.append(
            [
                InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"🗓 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="buttons"),
                InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
            ]
        )
        btn.append(
            [
                InlineKeyboardButton("❌ Close ❌", callback_data="close_data")
            ]
        )
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex(r"^spolling"))
async def advantage_spoll_choker(bot, query):
    _, id, user = query.data.split('#')
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)

    movie = await get_poster(id, id=True)
    search = movie.get('title')
    await query.answer('Checking My Database...')
    files, offset, total_results = await get_search_results(search, offset=0, filter=True)
    if files:
        k = (search, files, offset, total_results)
        await auto_filter(bot, query, k)
    else:
        await bot.send_message(LOG_CHANNEL, script.NO_RESULT_TXT.format(query.message.chat.title, query.message.chat.id, query.from_user.mention, search))
        k = await query.message.edit(f"👋 Hello {query.from_user.mention},\n\nI don't find <b>'{search}'</b> in my database. 😔")
        await asyncio.sleep(60)
        await k.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        try:
            user = query.message.reply_to_message.from_user.id
            if int(user) != 0 and query.from_user.id != int(user):
                return await query.answer(f"Hello {query.from_user.first_name},\nThis Is Not For You!", show_alert=True)
            await query.answer("Closed!")
            await query.message.delete()
            try:
                await query.message.reply_to_message.delete()
            except:
                pass
        except:
            await query.answer("Closed!")
            await query.message.delete()

    elif "groupcb" in query.data:
        group_id = query.data.split(":")[1]
        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id

        if act == "":
            stat = "CONNECT"
            cb = "connectcb"
        else:
            stat = "DISCONNECT"
            cb = "disconnect"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
             InlineKeyboardButton("DELETE", callback_data=f"deletecb:{group_id}")],
            [InlineKeyboardButton("BACK", callback_data="backcb")]
        ])

        await query.message.edit_text(
            f"Group Name: **{title}**\nGroup ID: `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return

    elif "connectcb" in query.data:
        group_id = query.data.split(":")[1]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id
        mkact = await make_active(str(user_id), str(group_id))

        if mkact:
            await query.message.edit_text(
                f"Connected to **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Some error occurred!', parse_mode=enums.ParseMode.MARKDOWN)
        return

    elif "disconnect" in query.data:
        group_id = query.data.split(":")[1]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id
        mkinact = await make_inactive(str(user_id))

        if mkinact:
            await query.message.edit_text(
                f"Disconnected from **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return

    elif "deletecb" in query.data:
        user_id = query.from_user.id
        group_id = query.data.split(":")[1]
        delcon = await delete_connection(str(user_id), str(group_id))

        if delcon:
            await query.message.edit_text(
                "Successfully deleted connection"
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return

    elif query.data == "backcb":
        userid = query.from_user.id
        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text(
                "There are no active connections! Connect to some groups first.",
            )
            return
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ACTIVE" if active else ""
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        if buttons:
            await query.message.edit_text(
                "Your connected group details:\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    if query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{query.message.chat.id}_{file_id}")

    if query.data.startswith("checksub"):
        ident, file_id = query.data.split("#")
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer(f"Hello {query.from_user.first_name},\nPlease join my updates channel and try again.", show_alert=True)
            return

        settings = await get_settings(query.message.chat.id)
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No Such File Exist!', show_alert=True)
        files = files_[0]
        CAPTION = settings['caption']
        f_caption = CAPTION.format(
            file_name = files.file_name,
            file_size = get_size(files.file_size),
            file_caption = files.caption
        )

        btn = [[
            InlineKeyboardButton('⚡️ Updates Channel ⚡️', url=UPDATES_LINK),
            InlineKeyboardButton('🔥 Support Group 🔥', url=SUPPORT_LINK)
        ]]
        await query.message.delete()
        await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'checksubp' else False,
            reply_markup=InlineKeyboardMarkup(btn)
        )

    elif query.data == "grp_checksub":
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nThis Is Not For You!", show_alert=True)
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer(f"Hello {query.from_user.first_name},\nPlease join my updates channel and request again.", show_alert=True)
            return
        await query.answer(f"Hello {query.from_user.first_name},\nGood, Can You Request Now!", show_alert=True)
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass

    elif query.data == "buttons":
        await query.answer()

    elif query.data == "instructions":
        await query.answer("Movie request format.\nExample:\nBlack Adam or Black Adam 2022\n\nTV Reries request format.\nExample:\nLoki S01E01 or Loki S01 E01\n\nDon't use symbols.", show_alert=True)

    elif query.data == "start":
        await query.answer('Welcome!')
        buttons = [[
            InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ yᴏᴜ ɢʀᴏᴜᴩ ➕", url=f'http://t.me/{temp.U_NAME}?startgroup=start')
        ],[
            InlineKeyboardButton('🔎 ɪɴʟɪɴᴇ ꜱᴇᴀʀᴄʜ', switch_inline_query_current_chat='')
        ],[
            InlineKeyboardButton('ʙᴏᴛ ᴏᴡɴᴇʀ', callback_data='my_owner'),
            InlineKeyboardButton('ᴀʙᴏᴜᴛ', callback_data='my_about')
        ],[
            InlineKeyboardButton('• ᴄʟᴏꜱᴇ •', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "my_about":
        buttons = [[
            InlineKeyboardButton('🏠 Home 🏠', callback_data='start'),
            InlineKeyboardButton('Report Bugs and Feedback', url=SUPPORT_LINK)
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MY_ABOUT_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "my_owner":
        buttons = [[
            InlineKeyboardButton('🏠 Home 🏠', callback_data='start'),
            InlineKeyboardButton('Contact', url='https://t.me/Hansaka_Anuhas')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MY_OWNER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )


    elif query.data.startswith("opn_pm_setgs"):
        ident, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("This Is Not For You!", show_alert=True)
            return
        if str(grp_id) != str(grpid):
            await query.message.edit("I'm not connected to this group! Check /connections or /connect to this group.")
            return
        title = query.message.chat.title
        settings = await get_settings(grpid)
        btn = [[
            InlineKeyboardButton("⚡️ Go To Chat ⚡️", url=f"https://t.me/{temp.U_NAME}")
        ]]

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Auto Filter',
                                         callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["auto_filter"] else '❌ No',
                                         callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('File Secure',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["file_secure"] else '❌ No',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["imdb"] else '❌ No',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Spelling Check',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["spell_check"] else '❌ No',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Auto Delete', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('One Hours' if settings["auto_delete"] else '❌ No',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Welcome', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["welcome"] else '❌ No',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Shortlink', callback_data=f'setgs#shortlink#{settings["shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["shortlink"] else '❌ No',
                                         callback_data=f'setgs#shortlink#{settings["shortlink"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('❌ Close ❌', callback_data='close_data')
                ]
            ]

            try:
                await client.send_message(
                    chat_id=userid,
                    text=f"Change your settings for <b>'{title}'</b> as your wish. ⚙",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                k = await query.message.edit_text(text="Settings menu sent in private chat. ⚙️", reply_markup=InlineKeyboardMarkup(btn))
                await asyncio.sleep(60)
                await k.delete()
                try:
                    await query.message.reply_to_message.delete()
                except:
                    pass
            except UserIsBlocked:
                await query.answer('You blocked me, Please unblock me and try again.', show_alert=True)
            except PeerIdInvalid:
                await query.answer("You didn't started this bot yet, Please start me and try again.", show_alert=True)

    elif query.data.startswith("opn_grp_setgs"):
        ident, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("This Is Not For You!", show_alert=True)
            return
        if str(grp_id) != str(grpid):
            await query.message.edit("I'm not connected to this group! Check /connections or /connect to this group.")
            return
        title = query.message.chat.title
        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Auto Filter',
                                         callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["auto_filter"] else '❌ No',
                                         callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('File Secure',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["file_secure"] else '❌ No',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["imdb"] else '❌ No',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Spelling Check',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["spell_check"] else '❌ No',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Auto Delete', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('One Hours' if settings["auto_delete"] else '❌ No',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Welcome', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["welcome"] else '❌ No',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Shortlink', callback_data=f'setgs#shortlink#{settings["shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["shortlink"] else '❌ No',
                                         callback_data=f'setgs#shortlink#{settings["shortlink"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('❌ Close ❌', callback_data='close_data')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            k = await query.message.edit_text(text=f"Change your settings for <b>'{title}'</b> as your wish. ⚙", reply_markup=reply_markup)
            await asyncio.sleep(300)
            await k.delete()
            try:
                await query.message.reply_to_message.delete()
            except:
                pass

    elif query.data.startswith("setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("This Is Not For You!", show_alert=True)
            return

        if str(grp_id) != str(grpid):
            await query.message.edit("I'm not connected to this group! Check /connections or /connect to this group.")
            return

        if set_type == 'shortlink' and userid not in ADMINS:
            return await query.answer("You can't change this setting.")

        if status == "True":
            await save_group_settings(grpid, set_type, False)
        else:
            await save_group_settings(grpid, set_type, True)

        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Auto Filter',
                                         callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["auto_filter"] else '❌ No',
                                         callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('File Secure',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["file_secure"] else '❌ No',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["imdb"] else '❌ No',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Spelling Check',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["spell_check"] else '❌ No',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Auto Delete', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('One Hours' if settings["auto_delete"] else '❌ No',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Welcome', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["welcome"] else '❌ No',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Shortlink', callback_data=f'setgs#shortlink#{settings["shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["shortlink"] else '❌ No',
                                         callback_data=f'setgs#shortlink#{settings["shortlink"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('❌ Close ❌', callback_data='close_data')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.answer("Changed!")
            await query.message.edit_reply_markup(reply_markup)


    elif query.data == "srt_delete":
        await query.message.edit_text("Deleting...")
        result = await Media.collection.delete_many({'mime_type': 'application/x-subrip'})
        if result.deleted_count:
            await query.message.edit_text(f"Successfully deleted srt files")
        else:
            await query.message.edit_text("Nothing to delete files")

    elif query.data == "avi_delete":
        await query.message.edit_text("Deleting...")
        result = await Media.collection.delete_many({'mime_type': 'video/x-msvideo'})
        if result.deleted_count:
            await query.message.edit_text(f"Successfully deleted avi files")
        else:
            await query.message.edit_text("Nothing to delete files")
            
    elif query.data == "zip_delete":
        await query.message.edit_text("Deleting...")
        result = await Media.collection.delete_many({'mime_type': 'application/zip'})
        if result.deleted_count:
            await query.message.edit_text(f"Successfully deleted zip files")
        else:
            await query.message.edit_text("Nothing to delete files")
            
    elif query.data == "rar_delete":
        await query.message.edit_text("Deleting...")
        result = await Media.collection.delete_many({'mime_type': 'application/x-rar-compressed'})
        if result.deleted_count:
            await query.message.edit_text(f"Successfully deleted rar files")
        else:
            await query.message.edit_text("Nothing to delete files")
            
    elif query.data.startswith("delete_all"):
        files = await Media.count_documents()
        await query.answer('Deleting...')
        await Media.collection.drop()
        await query.message.edit_text(f"Successfully deleted {files} files")
        
        
    elif query.data.startswith("send_all"):
        ident, pre, key = query.data.split("#")
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
        
        files = temp.FILES.get(key)
        if not files:
            await query.answer(f"Hello {query.from_user.first_name},\nSend New Request Again!", show_alert=True)
            return
        
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{pre}_{key}")
        
        
async def auto_filter(client, msg, spoll=False):
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id)
        if message.text.startswith("/"): return  # ignore commands
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if 2 < len(message.text) < 100:
            search = message.text
            files, offset, total_results = await get_search_results(search.lower(), offset=0, filter=True)
            if not files:
                if settings["spell_check"]:
                    return await advantage_spell_chok(msg)
                else:
                    return
        else:
            return
    else:
        settings = await get_settings(msg.message.chat.id)
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = spoll
    if spoll:
        await msg.message.delete()
    pre = 'filep' if settings['file_secure'] else 'file'
    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    if settings["shortlink"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"✨ {get_size(file.file_size)} ⚡️ {file.file_name}", url=await get_shortlink(message.chat.id, f'https://t.me/{temp.U_NAME}?start={pre}_{message.chat.id}_{file.file_id}')
                )
            ]
            for file in files
        ]
        btn.insert(0,
            [InlineKeyboardButton("🎈 Send All 🎈", url=await get_shortlink(message.chat.id, f'https://t.me/{temp.U_NAME}?start=all_{message.chat.id}_{pre}_{key}'))]
        )
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"✨ {get_size(file.file_size)} ⚡️ {file.file_name}", callback_data=f'{pre}#{file.file_id}',
                )
            ]
            for file in files
        ]
        btn.insert(0,
            [InlineKeyboardButton("🎈 Send All 🎈", callback_data=f"send_all#{pre}#{key}")]
        )

    if offset != "":
        BUTTONS[key] = search
        req = message.from_user.id if message.from_user else 0
        btn.append(
            [InlineKeyboardButton(text=f"🗓 PAGES 1 / {math.ceil(int(total_results) / 10)}", callback_data="buttons"),
             InlineKeyboardButton(text="NEXT ⏩", callback_data=f"next_{req}_{key}_{offset}")]
        )
        btn.append(
            [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="🗓 PAGES 1 / 1", callback_data="buttons")]
        )
        btn.append(
            [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")]
        )
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    TEMPLATE = settings['template']
    if imdb:
        cap = TEMPLATE.format(
            query=search,
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
            **locals()
        )
    else:
        cap = f"✅ I Found: <code>{search}</code>\n\n🗣 Requested by: {message.from_user.mention}\n©️ Powered by: <b>{message.chat.title}</b>"
    if imdb and imdb.get('poster'):
        try:
            if settings["auto_delete"]:
                k = await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024] + "\n\n<i>⚠️ This message will be auto delete after One Hours to avoid copyright issues.</i>", reply_markup=InlineKeyboardMarkup(btn))
                await asyncio.sleep(3600)
                await k.delete()
                try:
                    await message.delete()
                except:
                    pass
            else:
                await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn))
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            if settings["auto_delete"]:
                k = await message.reply_photo(photo=poster, caption=cap[:1024] + "\n\n<i>⚠️ This message will be auto delete after One Hours to avoid copyright issues.</i>", reply_markup=InlineKeyboardMarkup(btn))
                await asyncio.sleep(3600)
                await k.delete()
                try:
                    await message.delete()
                except:
                    pass
            else:
                await message.reply_photo(photo=poster, caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn))
        except Exception as e:
            logger.exception(e)
            if settings["auto_delete"]:
                k = await message.reply_text(cap + "\n\n<i>⚠️ This message will be auto delete after One Hours to avoid copyright issues.</i>", reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
                await asyncio.sleep(3600)
                await k.delete()
                try:
                    await message.delete()
                except:
                    pass
            else:
                await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
    else:
        if settings["auto_delete"]:
            k = await message.reply_text(cap + "\n\n<i>⚠️ This message will be auto delete after One Hours to avoid copyright issues.</i>", reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
            await asyncio.sleep(3600)
            await k.delete()
            try:
                await message.delete()
            except:
                pass
        else:
            await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)


async def advantage_spell_chok(msg):
    message = msg
    search = message.text
    google_search = search.replace(" ", "+")
    btn = [[
        InlineKeyboardButton("⚠️ Instructions ⚠️", callback_data='instructions'),
        InlineKeyboardButton("🔎 Search Google 🔍", url=f"https://www.google.com/search?q={google_search}")
    ]]
    try:
        movies = await get_poster(search, bulk=True)
    except:
        n = await message.reply_photo(photo=random.choice(PICS), caption=script.NOT_FILE_TXT.format(message.from_user.mention, search), reply_markup=InlineKeyboardMarkup(btn))
        await asyncio.sleep(60)
        await n.delete()
        try:
            await message.delete()
        except:
            pass
        return

    if not movies:
        n = await message.reply_photo(photo=random.choice(PICS), caption=script.NOT_FILE_TXT.format(message.from_user.mention, search), reply_markup=InlineKeyboardMarkup(btn))
        await asyncio.sleep(60)
        await n.delete()
        try:
            await message.delete()
        except:
            pass
        return

    user = message.from_user.id if message.from_user else 0
    buttons = [[
        InlineKeyboardButton(text=movie.get('title'), callback_data=f"spolling#{movie.movieID}#{user}")
    ]
        for movie in movies
    ]
    buttons.append(
        [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")]
    )
    s = await message.reply_photo(photo=random.choice(PICS), caption=f"👋 Hello {message.from_user.mention},\n\nI couldn't find the <b>'{search}'</b> you requested.\nSelect if you meant one of these? 👇", reply_markup=InlineKeyboardMarkup(buttons))
    await asyncio.sleep(300)
    await s.delete()
    try:
        await message.delete()
    except:
        pass
