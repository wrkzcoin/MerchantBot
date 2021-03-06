import discord
from discord.ext import commands
from discord.ext.commands import Bot, AutoShardedBot, when_mentioned_or, CheckFailure
from discord.utils import get

import time, timeago
from datetime import datetime
from config import config
import click
import sys, traceback
import asyncio
# ascii table
from terminaltables import AsciiTable

import uuid, json

import store, addressvalidation, walletapi
from wallet import *

from generic_xmr.address_msr import address_msr as address_msr
from generic_xmr.address_xmr import address_xmr as address_xmr
from generic_xmr.address_upx import address_upx as address_upx
from generic_xmr.address_xam import address_xam as address_xam

# regex
import re

# redis
import redis
redis_pool = None
redis_conn = None
redis_expired = 120

bot_help_deposit = "Get your wallet address for deposit."

# Coin using wallet-api
ENABLE_COIN = config.Enable_Coin.split(",")
ENABLE_XMR = config.Enable_Coin_XMR.split(",")
ENABLE_SWAP = config.Enabe_Swap_Coin.split(",")

MIN_RATIO = float(config.Min_Ratio)
TRADE_PERCENT = config.Trade_Margin
IS_TESTING = False
IS_RESTARTING = False
TESTER = [386761001808166912, 430148078855520296, 185223615107694592, 431654339359277067]
NOTIFY_CHAN = config.discord.channelNotify

EMOJI_ERROR = "\u274C"
EMOJI_OK_BOX = "\U0001F197"
EMOJI_MAINTENANCE = "\U0001F527"
EMOJI_CHECK = "\u2705"
EMOJI_WARNING = "\u26A1"
EMOJI_RED_NO = "\u26D4"
EMOJI_SCALE = "\u2696"
EMOJI_OK_HAND = "\U0001F44C"
EMOJI_MONEYBAG = "\U0001F4B0"
EMOJI_QUESTEXCLAIM = "\u2049"
EMOJI_ARROW_RIGHTHOOK = "\u21AA"
EMOJI_REFRESH = "\U0001F504"

# param introduce by @bobbieltd
WITHDRAW_IN_PROCESS = []

# Some notice about coin that going to swap or take out.
NOTICE_COIN = {
    "WRKZ" : getattr(getattr(config,"coinWRKZ"),"coin_notice", None),
    "TRTL" : getattr(getattr(config,"coinTRTL"),"coin_notice", None),
    "DEGO" : getattr(getattr(config,"coinDEGO"),"coin_notice", None),
    "BTCMZ" : getattr(getattr(config,"coinBTCMZ"),"coin_notice", None),
    "PLE" : getattr(getattr(config,"coinPLE"),"coin_notice", None),
    "XTOR" : getattr(getattr(config,"coinXTOR"),"coin_notice", None),
    "LOKI" : getattr(getattr(config,"coinLOKI"),"coin_notice", None),
    "XMR" : getattr(getattr(config,"coinXMR"),"coin_notice", None),
    "ARQ" : getattr(getattr(config,"coinARQ"),"coin_notice", None),
    "UPX" : getattr(getattr(config,"coinUPX"),"coin_notice", None),
    "XEQ" : getattr(getattr(config,"coinARQ"),"coin_notice", None),
    "default": "Thank you for using."
    }

bot_help_admin_lockuser = "Lock a user from any action by user id"
bot_help_admin_unlockuser = "Unlock a user"
bot_help_balance = "Check your balance."
bot_help_send = "Send coin to an address from your balance."
bot_help_coininfo = "List of coin status."
bot_help_market = "List of coin open order market."
bot_help_buy = "Buy from open order number."
bot_help_sell = "Sell for another coin."
bot_help_cancel = "Cancel sell order by ticker or ALL."
bot_help_myorder = "List your active open sell orders"
bot_help_order_num = "Show an order number"
bot_help_admin_baluser = "Show a user balance"
bot_help_swap = "Swap balance amount between our bot to our bot"


bot = AutoShardedBot(command_prefix=[','], owner_id = config.discord.ownerID, case_insensitive=True)
#bot.remove_command("help")


def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=10)


def openRedis():
    global redis_pool, redis_conn
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


def get_notice_txt(coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME in NOTICE_COIN:
        if NOTICE_COIN[COIN_NAME] is None:
            return "*Any support for this TradeBot, please join* `https://chat.wrkz.work`"
        else:
            return NOTICE_COIN[COIN_NAME]
    else:
        return "*Any support for this TradeBot, please join* `https://chat.wrkz.work`"


@bot.event
async def on_shard_ready(shard_id):
    print(f'Shard {shard_id} connected')

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    game = discord.Game(name="Testing Only")
    await bot.change_presence(status=discord.Status.online, activity=game)


@bot.group(hidden = True)
@commands.is_owner()
async def admin(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send('Invalid `admin` command passed...')
    return


@commands.is_owner()
@admin.command(help=bot_help_admin_baluser)
async def baluser(ctx, user_id: str):
    global ENABLE_COIN
    table_data = [
        ['TICKER', 'Available', 'Open Order']
        ]
    for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN]:
        if not is_maintenance_coin(COIN_NAME):
            wallet = await store.sql_get_userwallet(user_id, COIN_NAME, 'DISCORD')
            if wallet is None:
                table_data.append([COIN_NAME, "N/A", "N/A"])
            else:
                actual = wallet['actual_balance']
                userdata_balance = store.sql_user_balance(user_id, COIN_NAME, 'DISCORD')
                balance_actual = num_format_coin(actual + float(userdata_balance['Adjust']), COIN_NAME)
                table_data.append([COIN_NAME, balance_actual, num_format_coin(userdata_balance['OpenOrder'], COIN_NAME)])
        else:
            table_data.append([COIN_NAME, "***", "***"])

    table = AsciiTable(table_data)
    # table.inner_column_border = False
    # table.outer_border = False
    table.padding_left = 0
    table.padding_right = 0
    await ctx.message.author.send(f'**[ {user_id} BALANCE LIST ]**\n'
                                  f'```{table.table}```')
    return


@commands.is_owner()
@admin.command(pass_context=True, name='shutdown', aliases=['restart'])
async def shutdown(ctx):
    global IS_RESTARTING
    if IS_RESTARTING:
        await ctx.send(f'{EMOJI_REFRESH} {ctx.author.mention} I already got this command earlier.')
        return
    IS_RESTARTING = True
    await ctx.send(f'{EMOJI_REFRESH} {ctx.author.mention} .. I will restarting in 10s.. back soon.')
    await asyncio.sleep(10)
    await bot.logout()


@commands.is_owner()
@admin.command(aliases=['addbalance'])
async def credit(ctx, amount: str, coin: str, to_userid: str):
    global IS_RESTARTING
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN:
        await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in our list.')
        return

    # check if bot can find user
    member = bot.get_user(id=int(to_userid))
    if not member:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} I cannot find user with userid **{to_userid}**.')
        return
    # check if user / address exist in database
    amount = amount.replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid credit amount.')
        return

    coin_family = None
    wallet = None
    try:
        coin_family = getattr(getattr(config,"coin"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return

    COIN_DEC = get_decimal(COIN_NAME)
    real_amount = int(amount * COIN_DEC) if coin_family in ["XMR", "TRTL"] else amount * COIN_DEC

    if coin_family == "TRTL" or coin_family == "CCX" or coin_family == "XMR":
        wallet = await store.sql_get_userwallet(to_userid, COIN_NAME, 'DISCORD')
        if wallet is None:
            userregister = await store.sql_register_user(to_userid, COIN_NAME, 'DISCORD')
            wallet = await store.sql_get_userwallet(to_userid, COIN_NAME, 'DISCORD')
    credit_to = store.sql_cn_xmr_credit(str(ctx.message.author.id), to_userid, real_amount, COIN_NAME, ctx.message.content)
    if credit_to:
        msg = await ctx.send(f'{ctx.author.mention} amount **{num_format_coin(real_amount, COIN_NAME)}{COIN_NAME}** has been credited to userid **{to_userid}**.')
        return


@commands.is_owner()
@admin.command(aliases=['maintenance'])
async def maint(ctx, coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN:
        await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in our list.')
        return

    if is_maintenance_coin(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** to maintenance **OFF**.')
        set_main = set_maintenance_coin(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** to maintenance **ON**.')
        set_main = set_maintenance_coin(COIN_NAME, True)
    return


@commands.is_owner()
@admin.command(aliases=['txable'])
async def sendable(ctx, coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN:
        await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in our list.')
        return

    if is_coin_sendable(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **DISABLE** TX.')
        set_main = set_coin_sendable(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **ENABLE** TX.')
        set_main = set_coin_sendable(COIN_NAME, True)
    return


@commands.is_owner()
@admin.command(aliases=['withdraw'])
async def withdrawable(ctx, coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN:
        await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in our list.')
        return

    if is_withdrawable_coin(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **DISABLE** withdraw.')
        set_main = set_withdrawable_coin(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **ENABLE** withdraw.')
        set_main = set_withdrawable_coin(COIN_NAME, True)
    return


@commands.is_owner()
@admin.command(aliases=['deposit'])
async def depositable(ctx, coin: str):
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN:
        await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in our list.')
        return

    if is_depositable_coin(COIN_NAME):
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **DISABLE** deposit.')
        set_main = set_depositable_coin(COIN_NAME, False)
    else:
        await ctx.send(f'{EMOJI_OK_BOX} Set **{COIN_NAME}** **ENABLE** deposit.')
        set_main = set_depositable_coin(COIN_NAME, True)
    return


## todo just use only one command to switch ON/OFF
@commands.is_owner()
@admin.command(help=bot_help_admin_lockuser)
async def lockuser(ctx, user_id: str, *, reason: str):
    get_discord_userinfo = store.sql_discord_userinfo_get(user_id)
    if get_discord_userinfo is None:
        store.sql_userinfo_locked(user_id, 'YES', reason, str(ctx.message.author.id))
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        await ctx.message.author.send(f'{user_id} is locked.')
        return
    else:
        if get_discord_userinfo['locked'].upper() == "YES":
            await ctx.message.author.send(f'{user_id} was already locked.')
        else:
            store.sql_userinfo_locked(user_id, 'YES', reason, str(ctx.message.author.id))
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            await ctx.message.author.send(f'Turn {user_id} to locked.')
        return


@commands.is_owner()
@admin.command(help=bot_help_admin_unlockuser)
async def unlockuser(ctx, user_id: str):
    get_discord_userinfo = store.sql_discord_userinfo_get(user_id)
    if get_discord_userinfo:
        if get_discord_userinfo['locked'].upper() == "NO":
            await ctx.message.author.send(f'**{user_id}** was already unlocked. Nothing to do.')
        else:
            store.sql_change_userinfo_single(user_id, 'locked', 'NO')
            await ctx.message.author.send(f'Unlocked {user_id} done.')
        return      
    else:
        await ctx.message.author.send(f'{user_id} not stored in **discord userinfo** yet. Nothing to unlocked.')
        return


@bot.command(pass_context=True, name='deposit', help=bot_help_deposit)
async def deposit(ctx, coin: str, pub: str = None):
    global ENABLE_COIN
    if not is_testing(ctx):
        return # to delete after test
        await ctx.send(f'{ctx.author.mention} Wait, we are still testing it.')
        return

    show_pub = False
    if pub and (pub.upper() == "PUB" or pub.upper() == "PUBLIC"):
        show_pub = True
    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_COIN:
        await ctx.message.add_reaction(EMOJI_RED_NO)
        if show_pub:
            await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in not in our list.')
        else:
            await ctx.message.author.send(f'{EMOJI_RED_NO} {COIN_NAME} in not in our list.')
        return
    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        if show_pub:
            await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        else:
            await ctx.message.author.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return

    if not is_depositable_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        if show_pub:
            await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} deposit currently disable.')
        else:
            await ctx.message.author.send(f'{EMOJI_RED_NO} {COIN_NAME} deposit currently disable.')
        return

    coin_family = None
    wallet = None
    try:
        coin_family = getattr(getattr(config,"coin"+COIN_NAME),"coin_family","TRTL")
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        if show_pub:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        else:
            await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} **INVALID TICKER**')
        return
    if coin_family in ["TRTL", "XMR", "DOGE"]:
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
        if wallet is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
    if wallet is None:
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error for `.info`')
        return
    if wallet['balance_wallet_address']:
        await ctx.message.add_reaction(EMOJI_OK_HAND)
        if show_pub:
            await ctx.send(f'**[{COIN_NAME} DEPOSIT INFO]**\n'
                                        f'{EMOJI_MONEYBAG} Deposit Address: `' + wallet['balance_wallet_address'] + '`\n'
                                        f'{get_notice_txt(COIN_NAME)}')
        else:
            await ctx.message.author.send(f'**[{COIN_NAME} DEPOSIT INFO]**\n'
                                        f'{EMOJI_MONEYBAG} Deposit Address: `' + wallet['balance_wallet_address'] + '`\n'
                                        f'{get_notice_txt(COIN_NAME)}')
    return


@bot.command(pass_context=True, name='balance', aliases=['bal'], help=bot_help_balance)
async def balance(ctx, pub: str = None):
    global IS_RESTARTING, ENABLE_COIN
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    if not is_testing(ctx):
        await ctx.send(f'{ctx.author.mention} Wait, we are still testing it.')
        return

    show_pub = False
    if pub and (pub.upper() == "PUB" or pub.upper() == "PUBLIC"):
        show_pub = True

    table_data = [
        ['TICKER', 'Available', 'Open Order']
        ]
    for COIN_NAME in [coinItem.upper() for coinItem in ENABLE_COIN]:
        if not is_maintenance_coin(COIN_NAME):
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
            if wallet is None:
                userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
                wallet = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
            if wallet:
                userdata_balance = store.sql_user_balance(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
                wallet['actual_balance'] = int(wallet['actual_balance']) if COIN_NAME not in ["DOGE", "LTC", "BTC", "DASH", "BCH"] else wallet['actual_balance']
                balance_actual = num_format_coin(wallet['actual_balance'] + float(userdata_balance['Adjust']), COIN_NAME)
                table_data.append([COIN_NAME, balance_actual, num_format_coin(userdata_balance['OpenOrder'], COIN_NAME)])
        else:
            table_data.append([COIN_NAME, "***", "***"])

    table = AsciiTable(table_data)
    # table.inner_column_border = False
    # table.outer_border = False
    table.padding_left = 0
    table.padding_right = 0
    if show_pub:
        msg = await ctx.send('**[ YOUR BALANCE LIST ]**\n'
                                            f'```{table.table}```')
    else:
        msg = await ctx.message.author.send('**[ YOUR BALANCE LIST ]**\n'
                                            f'```{table.table}```')
    return


@bot.command(pass_context=True, help=bot_help_send)
async def send(ctx, amount: str, ticker: str, CoinAddress: str):
    global IS_RESTARTING, WITHDRAW_IN_PROCESS, ENABLE_COIN
    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    if not is_testing(ctx):
        return # to delete after test
        await ctx.send(f'{ctx.author.mention} Wait, we are still testing it.')
        return

    if ctx.message.author.id in WITHDRAW_IN_PROCESS:
        # reject and tell to wait
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
        return

    amount = amount.replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    # Check which coinname is it.
    COIN_NAME = get_cn_coin_from_address(CoinAddress)
    if not is_withdrawable_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} withdraw is currently disable.')
        return
    coin_family = None

    if ticker.upper() != COIN_NAME:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} It seemed I can not catch `{CoinAddress}` as **{ticker.upper()}**.')
        return

    if COIN_NAME:
        coin_family = getattr(getattr(config,"coin"+COIN_NAME),"coin_family","TRTL")
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        try:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} could not find what address it is.')
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            try:
                await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} could not find what address it is.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                return
        return

    # add redis action
    random_string = str(uuid.uuid4())
    await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "START"]), False)

    COIN_DEC = get_decimal(COIN_NAME)
    MinTx = get_min_tx_amount(COIN_NAME)
    MaxTX = get_max_tx_amount(COIN_NAME)
    real_amount = int(amount * COIN_DEC) if (coin_family == "TRTL" or coin_family == "XMR") else amount
    NetFee = get_reserved_fee(COIN_NAME)

    if coin_family == "TRTL" or coin_family == "CCX":
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)
        print('{} - {} - {}'.format(COIN_NAME, addressLength, IntaddressLength))
        if len(CoinAddress) == int(addressLength):
            valid_address = addressvalidation.validate_address_cn(CoinAddress, COIN_NAME)
            # print(valid_address)
            if valid_address != CoinAddress:
                valid_address = None

            if valid_address is None:
                await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                   f'`{CoinAddress}`')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                                      f'`{CoinAddress}`')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
        elif len(CoinAddress) == int(IntaddressLength):
            valid_address = addressvalidation.validate_integrated_cn(CoinAddress, COIN_NAME)
            # print(valid_address)
            if valid_address == 'invalid':
                await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid integrated address:\n'
                                   f'`{CoinAddress}`')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid integrated address:\n'
                                                      f'`{CoinAddress}`')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
            if len(valid_address) == 2:
                iCoinAddress = CoinAddress
                CoinAddress = valid_address['address']
                paymentid = valid_address['integrated_id']
        elif len(CoinAddress) == int(addressLength) + 64 + 1:
            valid_address = {}
            check_address = CoinAddress.split(".")
            if len(check_address) != 2:
                await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid {COIN_NAME} address + paymentid')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid {COIN_NAME} address + paymentid')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
            else:
                valid_address_str = addressvalidation.validate_address_cn(check_address[0], COIN_NAME)
                paymentid = check_address[1].strip()
                if valid_address_str is None:
                    await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                    try:
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                       f'`{check_address[0]}`')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        try:
                            await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                                          f'`{check_address[0]}`')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            return
                    return
                else:
                    valid_address['address'] = valid_address_str
            # Check payment ID
                if len(paymentid) == 64:
                    if not re.match(r'[a-zA-Z0-9]{64,}', paymentid.strip()):
                        await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                        try:
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                            'Should be in 64 correct format.')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            try:
                                await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                                              'Should be in 64 correct format.')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                return
                        return
                    else:
                        CoinAddress = valid_address['address']
                        valid_address['paymentid'] = paymentid
                        iCoinAddress = addressvalidation.make_integrated_cn(valid_address['address'], COIN_NAME, paymentid)['integrated_address']
                        pass
                else:
                    await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
                    try:
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                        'Incorrect length')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        try:
                            await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} PaymentID: `{paymentid}`\n'
                                                         'Incorrect length')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            return
                    return
        else:
            await ctx.message.add_reaction(EMOJI_QUESTEXCLAIM)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                               f'`{CoinAddress}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                try:
                    await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                                  f'`{CoinAddress}`')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    return
            return
        # Check available balance
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
        if user_from is None:
            userregister = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
            user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')

        userdata_balance = store.sql_user_balance(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
        user_from['actual_balance'] = user_from['actual_balance'] + float(userdata_balance['Adjust'])

        if real_amount + NetFee > user_from['actual_balance']:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient reserved fee to send '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME} to {CoinAddress}.')

            return

        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        elif real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')

            return

        if len(valid_address) == 2:
            sending = None
            try:
                sending = await store.sql_external_cn_xmr_single('DISCORD', str(ctx.message.author.id), real_amount, CoinAddress, COIN_NAME, paymentid)
                tip_tx_tipper = "Transaction hash: `{}`".format(sending['transactionHash'])
                tip_tx_tipper += "\nTx Fee: `{}{}`".format(num_format_coin(sending['fee'], COIN_NAME), COIN_NAME)
                await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if sending:
                await ctx.message.add_reaction(EMOJI_OK_BOX)
                await ctx.message.author.send(
                                       f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                       f'{COIN_NAME} '
                                       f'to `{iCoinAddress}`\n\n'
                                       f'Address: `{CoinAddress}`\n'
                                       f'Payment ID: `{paymentid}`\n'
                                       f'{tip_tx_tipper}')
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{ctx.author.mention} You may need to `optimize` or retry.')
                
                return
        else:
            sending = None
            try:
                sending = await store.sql_external_cn_xmr_single('DISCORD', str(ctx.message.author.id), real_amount, CoinAddress, COIN_NAME)
                tip_tx_tipper = "Transaction hash: `{}`".format(sending['transactionHash'])
                tip_tx_tipper += "\nTx Fee: `{}{}`".format(num_format_coin(sending['fee'], COIN_NAME), COIN_NAME)
                await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if sending:
                await ctx.message.add_reaction(EMOJI_OK_BOX)
                await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                              f'{COIN_NAME} '
                                              f'to `{CoinAddress}`\n'
                                              f'{tip_tx_tipper}')
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{ctx.author.mention} Can not deliver TX for {COIN_NAME} right now. Try again soon.')
                return
    elif coin_family == "XMR":
        addressLength = get_addrlen(COIN_NAME)
        IntaddressLength = get_intaddrlen(COIN_NAME)

        # If not Masari
        if COIN_NAME != "MSR":
            valid_address = await validate_address_xmr(str(CoinAddress), COIN_NAME)
            if valid_address['valid'] == False or valid_address['nettype'] != 'mainnet':
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Address: `{CoinAddress}` '
                                   'is invalid.')
                    return
        # OK valid address
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
        userdata_balance = store.sql_user_balance(str(ctx.message.author.id), COIN_NAME, 'DISCORD')

        # If balance 0, no need to check anything
        if float(user_from['actual_balance']) + float(userdata_balance['Adjust']) <= 0:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please check your **{COIN_NAME}** balance.')
            return
        if real_amount > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return

        NetFee = await get_tx_fee_xmr(coin = COIN_NAME, amount = real_amount, to_address = CoinAddress)
        if NetFee is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Can not get fee from network for: '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}. Please try again later in a few minutes.')
            return
        if real_amount + NetFee > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}. You need to leave at least network fee: {num_format_coin(NetFee, COIN_NAME)}{COIN_NAME}')
            return
        if real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return

        SendTx = None
        if ctx.message.author.id not in WITHDRAW_IN_PROCESS:
            WITHDRAW_IN_PROCESS.append(ctx.message.author.id)
            try:
                SendTx = await store.sql_external_cn_xmr_single('DISCORD', str(ctx.message.author.id), real_amount,
                                                                CoinAddress, COIN_NAME)
                await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            WITHDRAW_IN_PROCESS.remove(ctx.message.author.id)
        else:
            # reject and tell to wait
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
            
            return
        if SendTx:
            SendTx_hash = SendTx['tx_hash']
            await ctx.message.add_reaction(EMOJI_OK_BOX)
            await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                          f'{COIN_NAME} to `{CoinAddress}`.\n'
                                          f'Transaction hash: `{SendTx_hash}`\n'
                                          'Network fee deducted from your account balance.')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return
        return
    elif coin_family == "DOGE":
        valid_address = await doge_validaddress(str(CoinAddress), COIN_NAME)
        if 'isvalid' in valid_address:
            if str(valid_address['isvalid']) == "True":
                pass
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Address: `{CoinAddress}` '
                               'is invalid.')
                return

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
        userdata_balance = store.sql_user_balance(str(ctx.message.author.id), COIN_NAME, 'DISCORD')        

        real_amount = float(amount)
        userdata_balance = store.sql_user_balance(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
        if real_amount + NetFee > float(user_from['actual_balance']) + float(userdata_balance['Adjust']):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out '
                           f'{num_format_coin(real_amount, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than '
                           f'{num_format_coin(MinTx, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        if real_amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be bigger than '
                           f'{num_format_coin(MaxTX, COIN_NAME)} '
                           f'{COIN_NAME}.')
            return
        SendTx = None
        if ctx.message.author.id not in WITHDRAW_IN_PROCESS:
            WITHDRAW_IN_PROCESS.append(ctx.message.author.id)
            try:
                SendTx = await store.sql_external_doge('DISCORD', str(ctx.message.author.id), real_amount, NetFee,
                                                       CoinAddress, COIN_NAME)
                await add_tx_action_redis(json.dumps([random_string, "SEND", str(ctx.message.author.id), ctx.message.author.name, float("%.3f" % time.time()), ctx.message.content, "DISCORD", "COMPLETE"]), False)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            WITHDRAW_IN_PROCESS.remove(ctx.message.author.id)
        else:
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if SendTx:
            await ctx.message.author.send(f'{EMOJI_ARROW_RIGHTHOOK} You have sent {num_format_coin(real_amount, COIN_NAME)} '
                                          f'{COIN_NAME} to `{CoinAddress}`.\n'
                                          f'Transaction hash: `{SendTx}`\n'
                                          'Network fee deducted from the amount.')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return


@bot.command(pass_context=True, help=bot_help_swap)
async def swap(ctx, amount: str, coin: str, to: str):
    global IS_RESTARTING, WITHDRAW_IN_PROCESS
    to = to.upper()
    if to != "TIPBOT":
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} supporting to **TIPBOT** only right now.')
        return

    # check if bot is going to restart
    if IS_RESTARTING:
        await ctx.message.add_reaction(EMOJI_REFRESH)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Bot is going to restart soon. Wait until it is back for using this.')
        return

    if not is_testing(ctx):
        return # to delete after test
        await ctx.send(f'{ctx.author.mention} Wait, we are still testing it.')
        return

    if ctx.message.author.id in WITHDRAW_IN_PROCESS:
        # reject and tell to wait
        msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
        return

    amount = amount.replace(",", "")
    try:
        amount = float(amount)
    except ValueError:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
        return

    COIN_NAME = coin.upper()
    if COIN_NAME not in ENABLE_SWAP:
        await ctx.send(f'{EMOJI_ERROR} **{COIN_NAME}** is not in swap list.')
        return

    if is_maintenance_coin(COIN_NAME):
        await ctx.message.add_reaction(EMOJI_MAINTENANCE)
        if show_pub:
            await ctx.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        else:
            await ctx.message.author.send(f'{EMOJI_RED_NO} {COIN_NAME} in maintenance.')
        return

    coin_family = getattr(getattr(config,"coin"+COIN_NAME),"coin_family","TRTL")

    user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
    if user_from is None:
        user_reg = await store.sql_register_user(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
    COIN_DEC = get_decimal(COIN_NAME)
    real_amount = int(amount * COIN_DEC) if coin_family in ["TRTL", "XMR"] else amount
    MinTx = get_min_tx_amount(COIN_NAME)
    MaxTX = get_max_tx_amount(COIN_NAME)

    userdata_balance = store.sql_user_balance(str(ctx.message.author.id), COIN_NAME, 'DISCORD')
    user_from['actual_balance'] = user_from['actual_balance'] + float(userdata_balance['Adjust'])

    if real_amount > user_from['actual_balance']:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to swap '
                       f'{num_format_coin(real_amount, COIN_NAME)} '
                       f'{COIN_NAME} to {to.upper()}.')
        return

    if real_amount > MaxTX:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be bigger than '
                       f'{num_format_coin(MaxTX, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return
    elif real_amount < MinTx:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than '
                       f'{num_format_coin(MinTx, COIN_NAME)} '
                       f'{COIN_NAME}.')
        return

    swapit = None
    try:
        swapit = await store.sql_swap_balance(COIN_NAME, str(ctx.message.author.id), ctx.message.author.name, 'MARKETBOT', to.upper(), real_amount)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    if swapit:
        await ctx.message.add_reaction(EMOJI_OK_BOX)
        await ctx.message.author.send(
                f'{EMOJI_ARROW_RIGHTHOOK} You swap {num_format_coin(real_amount, COIN_NAME)} '
                f'{COIN_NAME} to **{to.upper()}**.')
        return
    else:
        await ctx.message.add_reaction(EMOJI_ERROR)
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal error during swap.')
        return


def is_depositable_coin(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'MarketBOT:COIN_' + COIN_NAME + '_DEPOSIT'
        if redis_conn and redis_conn.exists(key):
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def set_depositable_coin(coin: str, set_deposit: bool = True):
    global redis_conn, redis_expired 
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'MarketBOT:COIN_' + COIN_NAME + '_DEPOSIT'
        if set_deposit == True:
            if redis_conn and redis_conn.exists(key):
                return True
            else:
                redis_conn.set(key, "ON")
                return True
        else:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_withdrawable_coin(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'MarketBOT:COIN_' + COIN_NAME + '_WITHDRAW'
        if redis_conn and redis_conn.exists(key):
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def set_withdrawable_coin(coin: str, set_withdraw: bool = True):
    global redis_conn, redis_expired 
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'MarketBOT:COIN_' + COIN_NAME + '_WITHDRAW'
        if set_withdraw == True:
            if redis_conn and redis_conn.exists(key):
                return True
            else:
                redis_conn.set(key, "ON")
                return True
        else:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)



def is_maintenance_coin(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'MarketBOT:COIN_' + COIN_NAME + '_MAINT'
        if redis_conn and redis_conn.exists(key):
            return True
        else:
            return False
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def set_maintenance_coin(coin: str, set_maint: bool = True):
    global redis_conn, redis_expired 
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'MarketBOT:COIN_' + COIN_NAME + '_MAINT'
        if set_maint == True:
            if redis_conn and redis_conn.exists(key):
                return True
            else:
                redis_conn.set(key, "ON")
                return True
        else:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_coin_sendable(coin: str):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()
    if is_maintenance_coin(COIN_NAME):
        return False
    # Check if exist in redis
    try:
        openRedis()
        key = 'MarketBOT:COIN_' + COIN_NAME + '_TX'
        if redis_conn and redis_conn.exists(key):
            return False
        else:
            return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


def is_testing(ctx):
    if IS_TESTING:
        if ctx.message.author.id in TESTER:
            return True
        else:
            return False
    else:
        return True

def set_coin_sendable(coin: str, set_sendable: bool = True):
    global redis_conn, redis_expired
    COIN_NAME = coin.upper()

    # Check if exist in redis
    try:
        openRedis()
        key = 'MarketBOT:COIN_' + COIN_NAME + '_TX'
        if set_sendable == True:
            if redis_conn and redis_conn.exists(key):
                redis_conn.delete(key)
                return True
        else:
            if redis_conn and not redis_conn.exists(key):
                redis_conn.set(key, "ON")                
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# Let's run balance update by a separate process
async def update_balance():
    INTERVAL_EACH = 10
    while True:
        print('sleep in second: '+str(INTERVAL_EACH))
        for coinItem in ["BCH", "DASH", "BTC", "DEGO", "DOGE", "LTC", "XTOR", "TRTL", "WRKZ", "BTCMZ", "LOKI", "XMR", "ARQ", "PLE", "UPX"]:
            await asyncio.sleep(INTERVAL_EACH)
            print('Update balance: '+ coinItem)
            start = time.time()
            try:
                await store.sql_update_balances(coinItem)
            except Exception as e:
                print(e)
            end = time.time()


# Notify user
async def notify_new_tx_user():
    INTERVAL_EACH = 10
    while True:
        pending_tx = await store.sql_get_new_tx_table('NO', 'NO')
        if pending_tx and len(pending_tx) > 0:
            # let's notify_new_tx_user
            for eachTx in pending_tx:
                user_tx = None
                if eachTx['coin_name'] not in ["DOGE"]:
                    user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'], eachTx['coin_name'])
                else:
                    user_tx = await store.sql_get_userwallet_by_paymentid(eachTx['payment_id'], eachTx['coin_name'])
                if user_tx:
                    user_found = bot.get_user(id=int(user_tx['user_id']))
                    if user_found:
                        is_notify_failed = False
                        try:
                            msg = None
                            if eachTx['coin_name'] not in ["DOGE", "LTC", "BTC", "DASH", "BCH"]:
                                msg = "You got a new deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nHeight: {:,.0f}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['height']) + "```"
                            else:
                                msg = "You got a new deposit: ```" + "Coin: {}\nTx: {}\nAmount: {}\nBlock Hash: {}".format(eachTx['coin_name'], eachTx['txid'], num_format_coin(eachTx['amount'], eachTx['coin_name']), eachTx['blockhash']) + "```"
                            await user_found.send(msg)
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            is_notify_failed = True
                            pass
                        update_notify_tx = await store.sql_update_notify_tx_table(eachTx['payment_id'], user_tx['user_id'], user_found.name, 'YES', 'NO' if is_notify_failed == False else 'YES')
                    else:
                        print('Can not find user id {} to notification tx: {}'.format(user_tx['user_id'], eachTx['txid']))
        else:
            print('No tx for notification')
        print('Sleep {}s'.format(INTERVAL_EACH))
        await asyncio.sleep(INTERVAL_EACH)


# Notify user
async def notify_new_swap_user():
    INTERVAL_EACH = 10
    while True:
        pending_tx = await store.sql_get_new_swap_table('NO', 'NO')
        if pending_tx and len(pending_tx) > 0:
            # let's notify_new_tx_user
            for eachSwap in pending_tx:
                user_found = bot.get_user(id=int(eachSwap['owner_id']))
                if user_found:
                    is_notify_failed = False
                    try:
                        msg = "You got incoming swap: ```" + "Coin: {}\nAmount: {}\nFrom: {}".format(eachSwap['coin_name'], num_format_coin(eachSwap['amount'], eachSwap['coin_name']), eachSwap['from']) + "```"
                        await user_found.send(msg)
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        is_notify_failed = True
                        pass
                    update_notify_tx = await store.sql_update_notify_swap_table(eachSwap['id'], 'YES', 'NO' if is_notify_failed == False else 'YES')
                else:
                    print('Can not find user id {} to notification swap: #{}'.format(eachSwap['owner_id'], eachSwap['id']))
        await asyncio.sleep(INTERVAL_EACH)


def get_cn_coin_from_address(CoinAddress: str):
    COIN_NAME = None
    if CoinAddress.startswith("Wrkz"):
        COIN_NAME = "WRKZ"
    elif CoinAddress.startswith("dg"):
        COIN_NAME = "DEGO"
    elif CoinAddress.startswith("cat1"):
        COIN_NAME = "CX"
    elif CoinAddress.startswith("btcm"):
        COIN_NAME = "BTCMZ"
    elif CoinAddress.startswith("dicKTiPZ"):
        COIN_NAME = "MTIP"
    elif CoinAddress.startswith("PLe"):
        COIN_NAME = "PLE"
    elif CoinAddress.startswith("Nib1"):
        COIN_NAME = "NBXC"
    elif CoinAddress.startswith("guns"):
        COIN_NAME = "ARMS"
    elif CoinAddress.startswith("ir"):
        COIN_NAME = "IRD"
    elif CoinAddress.startswith("NaCa"):
        COIN_NAME = "NACA"
    elif CoinAddress.startswith("TRTL"):
        COIN_NAME = "TRTL"
    elif CoinAddress.startswith("bit") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "XTOR"
    elif (CoinAddress.startswith("4") or CoinAddress.startswith("8") or CoinAddress.startswith("5") or CoinAddress.startswith("9")) \
        and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        # XMR / MSR
        # 5, 9: MSR
        # 4, 8: XMR
        addr = None
        # Try MSR
        try:
            addr = address_msr(CoinAddress)
            COIN_NAME = "MSR"
            return COIN_NAME
        except Exception as e:
            # traceback.print_exc(file=sys.stdout)
            pass
        # Try UPX
        try:
            addr = address_upx(CoinAddress)
            COIN_NAME = "UPX"
            return COIN_NAME
        except Exception as e:
            # traceback.print_exc(file=sys.stdout)
            pass
        # Try XAM
        try:
            addr = address_xam(CoinAddress)
            COIN_NAME = "XAM"
            return COIN_NAME
        except Exception as e:
            # traceback.print_exc(file=sys.stdout)
            pass
        # Try XMR
        try:
            addr = address_xmr(CoinAddress)
            COIN_NAME = "XMR"
            return COIN_NAME
        except Exception as e:
            # traceback.print_exc(file=sys.stdout)
            pass
    elif (CoinAddress.startswith("amit") and len(CoinAddress) == 98) or (CoinAddress.startswith("aint") and len(CoinAddress) == 109)  or \
        (CoinAddress.startswith("asub") and len(CoinAddress) == 99):
        COIN_NAME = "XAM"
    elif CoinAddress.startswith("L") and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "LOKI"
    elif CoinAddress.startswith("T") and (len(CoinAddress) == 97 or len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "XEQ"
    elif CoinAddress.startswith("cms") and (len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "BLOG"
    elif (CoinAddress.startswith("ar") or CoinAddress.startswith("aR")) and (len(CoinAddress) == 97 or len(CoinAddress) == 98 or len(CoinAddress) == 109):
        COIN_NAME = "ARQ"
    elif ((CoinAddress.startswith("UPX") and len(CoinAddress) == 98) or (CoinAddress.startswith("UPi") and len(CoinAddress) == 109) or (CoinAddress.startswith("Um") and len(CoinAddress) == 97)):
        COIN_NAME = "UPX"
    elif (CoinAddress.startswith("5") or CoinAddress.startswith("9")) and (len(CoinAddress) == 95 or len(CoinAddress) == 106):
        COIN_NAME = "MSR"
    elif CoinAddress.startswith("D") and len(CoinAddress) == 34:
        COIN_NAME = "DOGE"
    elif (CoinAddress[0] in ["M", "L"]) and len(CoinAddress) == 34:
        COIN_NAME = "LTC"
    elif (CoinAddress[0] in ["3", "1"]) and len(CoinAddress) == 34:
        COIN_NAME = "BTC"
    elif CoinAddress.startswith("bitcoincash") and len(CoinAddress) == 54:
        COIN_NAME = "BCH"
    elif (CoinAddress[0] in ["X"]) and len(CoinAddress) == 34:
        COIN_NAME = "DASH"
    print('get_cn_coin_from_address return: ')
    print(COIN_NAME)
    return COIN_NAME


@buy.error
async def buy_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                       '```'
                       ',buy ref_number (to buy from opened order)\n'
                       ',buy ticker (to list available selling tickers)'
                       '```')
    return


async def store_action_list():
    while True:
        interval_action_list = 60
        try:
            openRedis()
            key = "MarketBOT:ACTIONTX"
            if redis_conn and redis_conn.llen(key) > 0 :
                temp_action_list = []
                for each in redis_conn.lrange(key, 0, -1):
                    temp_action_list.append(tuple(json.loads(each)))
                num_add = store.sql_add_logs_tx(temp_action_list)
                if num_add > 0:
                    redis_conn.delete(key)
                else:
                    print(f"Failed delete {key}")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        await asyncio.sleep(interval_action_list)


async def add_tx_action_redis(action: str, delete_temp: bool = False):
    try:
        openRedis()
        key = "MarketBOT:ACTIONTX"
        if redis_conn:
            if delete_temp:
                redis_conn.delete(key)
            else:
                redis_conn.lpush(key, action)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


@click.command()
def main():
    bot.loop.create_task(update_balance())
    bot.loop.create_task(notify_new_tx_user())
    bot.loop.create_task(notify_new_swap_user())
    bot.loop.create_task(store_action_list())
    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()
