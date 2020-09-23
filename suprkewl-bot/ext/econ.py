# -*- coding: utf-8 -*-

"""
Copyright (C) 2020 Dante "laggycomputer" Dam

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import asyncio
import datetime
import typing

import discord
from discord.ext import commands

from .utils import human_timedelta, Plural, use_potential_nickname


class Economy(commands.Cog):
    async def get_user_money(self, ctx, user_id):
        resp = (await (
            await ctx.bot.db.execute("SELECT money FROM economy WHERE user_id == ?;", (user_id,))
        ).fetchone())
        return resp[0] if resp else 0

    async def get_money_prefix(self, ctx, guild_id=None):
        if not guild_id:
            return "$"
        resp = (await (
            await ctx.bot.db.execute("SELECT custom_dollar_sign FROM guilds WHERE guild_id == ?;", (guild_id,))
        ).fetchone())
        return resp[0] if resp else 0

    @commands.command(aliases=["bal"])
    @commands.cooldown(2, 1, commands.BucketType.user)
    async def balance(self, ctx, *, user: typing.Union[discord.Member, discord.User] = None):
        """Get the balance of a user or yourself."""

        user = user or ctx.author

        if user.bot:
            return await ctx.send(":x: Bots do not have money. Sorry to any robots out there.")

        dollar_sign = await self.get_money_prefix(ctx, ctx.guild.id if ctx.guild else None)
        money = await self.get_user_money(ctx, user.id)
        await ctx.send(use_potential_nickname(user) + f" has a balance of {dollar_sign}{money:,}.")

    @commands.command()
    @commands.cooldown(10, 10, commands.BucketType.user)
    async def daily(self, ctx):
        """Claim your daily currency stipend. Increases when claimed on consecutive days."""

        db_entry = await (
            await ctx.bot.db.execute("SELECT money, last_daily, daily_streak FROM economy WHERE user_id == ?;",
                                     (ctx.author.id,))
        ).fetchone()
        dollar_sign = await self.get_money_prefix(ctx, ctx.guild.id if ctx.guild else None)

        can_claim = False

        if not db_entry:
            can_claim = True
            last_claimed_at = datetime.datetime.utcfromtimestamp(0)
            daily_streak = 0
            current_money = 0
        else:
            last_claimed_at = datetime.datetime.utcfromtimestamp(db_entry[1] or 0)
            daily_streak = db_entry[2] or 0
            current_money = db_entry[0]
        utcnow = datetime.datetime.utcnow()
        days_since_last_claim = (utcnow - last_claimed_at).days
        if days_since_last_claim >= 1:
            can_claim = True
        if days_since_last_claim > 2:
            old_daily_streak = daily_streak
            daily_streak = 0
        else:
            old_daily_streak = 0
        if can_claim:
            streak_bonus = (lambda x: (x // 3 * 2.5) // 1)(daily_streak)  # Streak bonus is floor(floor(streak/3) * 2.5)
            money_post_claim = current_money + 200 + streak_bonus
            claimed_timestamp = utcnow.replace(tzinfo=datetime.timezone.utc).timestamp() // 1
            await ctx.bot.db.execute(
                "INSERT INTO economy (user_id, money, last_daily, daily_streak) VALUES (?, ?, ?, ?) ON CONFLICT "
                "(user_id) DO UPDATE SET money = ?, last_daily = ?, daily_streak = ?;",
                (ctx.author.id, money_post_claim, claimed_timestamp, daily_streak,
                 money_post_claim, claimed_timestamp, daily_streak + 1))
            await ctx.bot.db.commit()
            if streak_bonus:
                await ctx.send(f"Claimed {dollar_sign}{(200 + streak_bonus):,} (including "
                               f"{dollar_sign}{streak_bonus:,} from {format(Plural(daily_streak), 'day')} of streak "
                               f"bonus.)")
            else:
                if old_daily_streak and not daily_streak:
                    await ctx.send(f"Claimed {dollar_sign}200 (An old streak of "
                                   f"{format(Plural(old_daily_streak), 'day')} was broken.)")
                else:
                    await ctx.send(f"Claimed {dollar_sign}200, starting a new streak of "
                                   f"{format(Plural(daily_streak + 1), 'day')}.")
        else:
            timedelta = human_timedelta(last_claimed_at + datetime.timedelta(days=1), source=utcnow, brief=True)
            await ctx.send(f"You cannot claim a daily yet. Try again in {timedelta}.")

    @commands.command(aliases=["lb"])
    @commands.cooldown(2, 10, commands.BucketType.channel)
    async def leaderboard(self, ctx):
        """Show the richest players on the bot economy."""

        dollar_sign = await self.get_money_prefix(ctx, ctx.guild.id if ctx.guild else None)
        records = await (await ctx.bot.db.execute(
            "SELECT user_id, money FROM economy ORDER BY money DESC LIMIT 10;"
        )).fetchall()
        if not records:
            return await ctx.send("Nobody seems to have economy records...")
        else:
            emb = ctx.default_embed()
            emb.description = f"Showing (up to) top 10 richest players. Find you or another user's ranking with " \
                              f"`{ctx.prefix}ranking <user>`."
            for index, record in enumerate(records):
                fetch = None
                if ctx.guild:
                    try:
                        fetch = await ctx.guild.fetch_member(record[0])
                    except discord.NotFound:
                        pass
                if not ctx.guild or fetch is None:
                    fetch = await ctx.bot.fetch_user(record[0])
                emb.add_field(
                    name=f"`{index + 1}:` {use_potential_nickname(fetch)}", value=f"{dollar_sign}{record[1]:,}",
                    inline=False
                )
            await ctx.send(embed=emb)

    @commands.command()
    @commands.cooldown(5, 10, commands.BucketType.user)
    async def ranking(self, ctx, *, user: typing.Union[discord.Member, discord.User, int] = None):
        """Get the ranking of you or another user on the economy leaderboards."""

        user = user or ctx.author
        uid = user.id if not isinstance(user, int) else user
        money = await self.get_user_money(ctx, uid)
        record_count = (await (await ctx.bot.db.execute("SELECT COUNT(user_id) FROM economy;")).fetchone())[0]
        if money == 0:
            await ctx.send("This user does not have any money.")
        else:
            ranking = await (await ctx.bot.db.execute(
                "SELECT money, RANK() OVER (ORDER BY money DESC) r FROM economy;")).fetchall()
            for db_money, rank in ranking:
                if db_money == money:
                    ranking = rank
            await ctx.send(f"{use_potential_nickname(user)} is #{ranking:,} out of {record_count:,} total users on "
                           f"record.")

    @commands.command(aliases=["wipeeconomy"])
    @commands.is_owner()
    async def reseteconomy(self, ctx, *, user: typing.Union[discord.Member, discord.User, int] = None):
        """Reset a user's economy records."""

        user = user or ctx.author
        uid = user.id if not isinstance(user, int) else user
        records = await (await ctx.bot.db.execute("SELECT * FROM economy WHERE user_id == ?;", (uid,))).fetchone()
        if not records:
            return await ctx.send(":x: That user does not have economy data.")
        else:
            await ctx.send("Please type \"confirm\" within 10 seconds to confirm that you are DELETING this user's "
                           "economy data.")

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower().strip() == "confirm"

            try:
                msg = await ctx.bot.wait_for("message", check=check, timeout=10)
            except asyncio.TimeoutError:
                return
            await ctx.bot.db.execute("DELETE FROM economy WHERE user_id == ?;", (uid,))
            await ctx.bot.db.commit()
            try:
                await msg.add_reaction("\U0001f44d")
            except (discord.Forbidden, discord.NotFound):
                try:
                    await ctx.send("\U0001f44d")
                except (discord.Forbidden, discord.NotFound):
                    return

    @commands.command(aliases=["give"],
                      description="A 5% tax is applied to all transfers, except for ones larger than 50% of the "
                                  "account or over $1000, which take a 20% tax.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def pay(self, ctx, amount: int, *, user: typing.Union[discord.Member, discord.User]):
        """Pay someone else some of your money. Subject to taxes:tm:."""

        dollar_sign = await self.get_money_prefix(ctx, ctx.guild.id if ctx.guild else None)

        if user.bot:
            return await ctx.send("Bots can't have money.")
        if user == ctx.author:
            return await ctx.send("You can email yourself, but not pay yourself. At least not here.")
        if amount <= 0:
            return await ctx.send("That's not how it works!")

        payer_money = await self.get_user_money(ctx, ctx.author.id)
        target_money = await self.get_user_money(ctx, user.id)

        if amount > payer_money:
            return await ctx.send("One does not simply pay with money he does not have.")

        if amount > 1000 or amount > payer_money / 2:
            tax = amount // 5
            high_tax = True
        else:
            tax = amount // 20
            high_tax = False

        await ctx.bot.db.execute("UPDATE economy SET money = ? WHERE user_id == ?;",
                                 (payer_money - amount, ctx.author.id))
        await ctx.bot.db.execute("UPDATE economy SET money = ? WHERE user_id == ?;",
                                 (target_money + (amount - tax), user.id))

        await ctx.send(
            f"Transferring {dollar_sign}{amount:,} to {use_potential_nickname(user)} with a "
            f"{'20' if high_tax else '5'}% tax, or {dollar_sign}{tax:,}. This user will receive "
            f"{dollar_sign}{(amount - tax):,}.")

    @commands.command(aliases=["payforce"])
    @commands.is_owner()
    async def forcepay(
            self, ctx, amount: int,
            a: typing.Union[discord.Member, discord.User], b: typing.Union[discord.Member, discord.User], tax: int = 0):
        """Forcibly move money from one account to another."""

        dollar_sign = await self.get_money_prefix(ctx, ctx.guild.id if ctx.guild else None)
        if tax < 0 or tax > 100:
            return await ctx.send("Invalid tax rate.")

        taxes = (amount * (tax / 100)) // 1

        payer_money = await self.get_user_money(ctx, a.id)
        target_money = await self.get_user_money(ctx, b.id)
        if amount > payer_money:
            return await ctx.send(f"Payer has insufficient funds ({dollar_sign}{(amount - payer_money):,} short).")

        await ctx.bot.db.execute("UPDATE economy SET money = ? WHERE user_id == ?;",
                                 (payer_money - amount, a.id))
        await ctx.bot.db.execute("UPDATE economy SET money = ? WHERE user_id == ?;",
                                 (target_money + (amount - taxes), b.id))

        payer_name, target_name = use_potential_nickname(a), use_potential_nickname(b)
        if tax:
            await ctx.send(f"Forced {payer_name} to pay {dollar_sign}{amount:,} to {target_name}, who receives "
                           f"{dollar_sign}{(amount - taxes):,} due to a tax of {tax}%.")
        else:
            await ctx.send(f"Forced {payer_name} to pay {dollar_sign}{amount:,} to {target_name}.")

    @commands.group(invoke_without_command=True, aliases=["setcurrency", "scp"],
                    description="Requires Manage Server to update. Can either be an emoji or up to 10 characters of "
                                "text.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def currencyprefix(self, ctx, *, prefix: typing.Union[discord.Emoji, str]):
        """Set the custom currency prefix for this server."""

        if isinstance(prefix, str) and len(prefix) > 10:
            return await ctx.send("Prefix too long.")
        if isinstance(prefix, discord.Emoji):
            prefix = str(prefix)
        await ctx.bot.db.execute(
            "INSERT INTO guilds (guild_id, custom_dollar_sign) VALUES (?, ?) ON CONFLICT (guild_id) DO "
            "UPDATE SET custom_dollar_sign = ?;", (ctx.guild.id, prefix, prefix)
        )
        await ctx.bot.db.commit()
        
        await ctx.send(f":white_check_mark: Economy commands used in this server will now use the prefix {prefix}.")

    @currencyprefix.command(name="reset")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def currencyprefix_reset(self, ctx):
        """Reset the currency prefix for this guild."""

        await ctx.bot.db.execute("UPDATE guilds SET custom_dollar_sign = NULL where guild_id == ?;", (ctx.guild.id,))
        await ctx.bot.db.commit()
        try:
            await ctx.msg.add_reaction("\U0001f44d")
        except (discord.Forbidden, discord.NotFound):
            try:
                await ctx.send("\U0001f44d")
            except (discord.Forbidden, discord.NotFound):
                return


def setup(bot):
    bot.add_cog(Economy())
