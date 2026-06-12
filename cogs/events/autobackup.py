import discord
from discord.ext import commands, tasks
import shutil
import os
from datetime import datetime

class AutoBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_path = "database_backup"
        self.database_dir = "database"
        self.target_user_id =   1368989570816802886
        self.backup_task.start()

    def cog_unload(self):
        self.backup_task.cancel()

    async def create_and_send_backup(self):
        file_path = self.backup_path + ".zip"
        try:
            shutil.make_archive(self.backup_path, 'zip', self.database_dir)
            
            owner = self.bot.get_user(self.target_user_id) or await self.bot.fetch_user(self.target_user_id)
            if not owner:
                print(f"AutoBackup Error: Could not find user with ID {self.target_user_id}")
                return
            
            file_size = os.path.getsize(file_path)
            if file_size <= 25 * 1024 * 1024:
                file = discord.File(file_path, filename=f"DB_Backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.zip")
                embed = discord.Embed(
                    title="📦 Database Backup",
                    description=f"Your scheduled database backup for {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
                    color=0x2b2d31
                )
                await owner.send(embed=embed, file=file)
            else:
                await owner.send(f"⚠️ **Database Backup Failed:** The zip file is too large ({file_size / (1024*1024):.2f} MB) to send via Discord constraints (Max 25MB).")
                
        except Exception as e:
            try:
                owner_fallback = self.bot.get_user(self.target_user_id) or await self.bot.fetch_user(self.target_user_id)
                if owner_fallback:
                    await owner_fallback.send(f"⚠️ **Backup Error:** An error occurred while creating or sending the database backup:\n```py\n{e}\n```")
            except Exception:
                pass
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    @tasks.loop(hours=12)
    async def backup_task(self):
        await self.create_and_send_backup()

    @backup_task.before_loop
    async def before_backup_task(self):
        await self.bot.wait_until_ready()

    @commands.command(name="forcebackup", aliases=["fbackup"])
    async def force_backup(self, ctx):
        """Forces a database backup and sends it to your DMs."""
        if ctx.author.id != self.target_user_id:
            return await ctx.send("You are not authorized to force a database backup.")
        msg = await ctx.send("<a:Loadixd:1469568214169288890> Packing up the databases and sending to your DMs...")
        await self.create_and_send_backup()
        await msg.edit(content="✅ Backup sent successfully to your DMs.")

async def setup(bot):
    await bot.add_cog(AutoBackup(bot))
