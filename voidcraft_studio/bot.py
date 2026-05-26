import discord
from discord.ext import commands
from aiohttp import web
import requests
import datetime
import time
import asyncio
import json


# --- CONFIG ---
TOKEN = "MTQ4NzQ2ODI1OTcwMjczOTEzNQ.GoPwyd.F9MyLJT-d3TRXneER5SwqfEVnVK0ElwjWTj9ck"
API_BASE_URL = "http://127.0.0.1:5000/api"
BOT_API_KEY = "VOID_BOT_SECRET_2026"
BOT_HTTP_PORT = 6000   # Internal HTTP server the Flask app calls

# Review channels
REVIEW_CHANNEL_ID           = 1492349779613585559
GIVEAWAY_REVIEW_ID          = 1493070439822397562
INVESTIGATION_REVIEW_ID     = 1496059422873485332   # <-- where inv reviews are posted
CASE_LOG_REVIEW_ID          = 1496059422873485332   # <-- same channel for case logs

# Final accepted channels
FINAL_SALES_CHANNEL_ID         = 1342116437858455612
FINAL_OUTREACH_CHANNEL_ID      = 1342116565159776357
FINAL_GIVEAWAY_CHANNEL_ID      = 1342108858096554014
FINAL_INVESTIGATION_CHANNEL_ID = 1342423579223920686  # <-- accepted inv logs go here


# ---------------- HELPERS ----------------
def api_headers():
    return {
        "Content-Type": "application/json",
        "X-Bot-Key": BOT_API_KEY
    }


def build_payload(data, log_type):
    data["type"] = log_type
    data["created_at"] = datetime.datetime.utcnow().isoformat()
    return data


def build_embed(title, color, payload, user):
    embed = discord.Embed(title=title, color=color, timestamp=datetime.datetime.now())
    embed.add_field(name="Operator", value=user.mention, inline=False)

    t = payload["type"]

    if t == "Sales":
        embed.add_field(name="Username",          value=payload.get("operator", "—"),          inline=False)
        embed.add_field(name="Customer Username", value=payload.get("customer_username", "—"), inline=True)
        embed.add_field(name="User ID",           value=payload.get("customer_id", "—"),       inline=True)
        embed.add_field(name="Sale Type",         value=payload.get("sale_type", "—"),         inline=False)
        embed.add_field(name="Product(s) Bought", value=payload.get("products", "—"),          inline=False)
        embed.add_field(name="Server",            value=payload.get("server", "—"),            inline=False)
        embed.add_field(name="Prize",             value=payload.get("prize", "—"),             inline=False)
        embed.add_field(name="Note",              value=payload.get("note", "—"),              inline=False)
        embed.add_field(name="Discount Given",    value=payload.get("discount", "—"),          inline=False)

    elif t == "Outreach":
        embed.add_field(name="Username",             value=payload.get("operator", "—"),  inline=False)
        embed.add_field(name="Server Outreached To", value=payload.get("server", "—"),   inline=False)
        embed.add_field(name="Outcome",              value=payload.get("outcome", "—"),  inline=False)
        embed.add_field(name="Server Link",          value=payload.get("link", "—"),     inline=False)

    elif t == "Giveaway":
        embed.add_field(name="Username",      value=payload.get("username", "—"),    inline=False)
        embed.add_field(name="Server Name",   value=payload.get("server", "—"),     inline=False)
        embed.add_field(name="Their Ping",    value=payload.get("their_ping", "—"), inline=False)
        embed.add_field(name="Our Ping",      value=payload.get("our_ping", "—"),   inline=False)
        embed.add_field(name="Server Invite", value=payload.get("invite", "—"),     inline=False)

    elif t == "Investigation":
        embed.add_field(name="Case Number",    value=payload.get("case_number", "—"),    inline=True)
        embed.add_field(name="Date",           value=payload.get("date", "—"),           inline=True)
        embed.add_field(name="Reported User",  value=payload.get("reported_user", "—"),  inline=False)
        embed.add_field(name="Reporting User", value=payload.get("reporting_user", "—"), inline=False)
        embed.add_field(name="Investigator",   value=payload.get("investigator", "—"),   inline=False)
        embed.add_field(name="Reason",         value=payload.get("reason", "—"),         inline=False)
        embed.add_field(name="Outcome",        value=payload.get("outcome", "—"),        inline=False)
        embed.add_field(name="Google Doc",     value=payload.get("proof", "—"),          inline=False)

    if payload.get("proof") and t != "Investigation":
        embed.set_image(url=payload["proof"])

    return embed


def push_log_to_api(log_id, staff_id, payload, log_type, status, reviewed_by="", deny_reason=""):
    body = {
        "id": log_id,
        "user_id": str(staff_id),
        "username": payload.get("investigator") or payload.get("operator") or payload.get("username"),
        "type": log_type,
        "proof": payload.get("proof", ""),
        "details": payload,
        "amount": payload.get("prize", ""),
        "dept": (
            "investigation" if log_type == "Investigation"
            else "marketing" if log_type == "Giveaway"
            else "sales"
        ),
        "status": status,
        "reviewed_by": reviewed_by,
        "reviewed_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "deny_reason": deny_reason
    }
    try:
        res = requests.post(
            f"{API_BASE_URL}/submit-log",
            json=body,
            headers=api_headers(),
            timeout=8
        )
        print(f"[API] submit-log ({status}): {res.status_code} — {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"[API] submit-log ERROR: {e}")
        return False


# ---------------- DENY MODAL ----------------
class DenyModal(discord.ui.Modal, title="❌ Deny Case Log"):
    reason = discord.ui.TextInput(
        label="Reason for Denial",
        style=discord.TextStyle.paragraph,
        placeholder="Please explain why this case log is being denied...",
        required=True,
        max_length=500
    )

    def __init__(self, staff_id, log_id, payload, original_message, review_view):
        super().__init__()
        self.staff_id = staff_id
        self.log_id = log_id
        self.payload = payload
        self.original_message = original_message
        self.review_view = review_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        log_type = self.payload["type"]
        deny_reason = self.reason.value
        reviewer_name = interaction.user.name

        # Call Flask API to update status
        try:
            res = requests.post(
                f"{API_BASE_URL}/deny-log/{self.log_id}",
                json={"reason": deny_reason, "reviewed_by": reviewer_name},
                headers=api_headers(),
                timeout=8
            )
            print(f"[API] deny-log: {res.status_code} — {res.text}")
        except Exception as e:
            print(f"[API] deny-log ERROR: {e}")

        # Also push if it was a Discord-originated log (handles both cases)
        push_log_to_api(
            log_id=self.log_id,
            staff_id=self.staff_id,
            payload=self.payload,
            log_type=log_type,
            status="Denied",
            reviewed_by=reviewer_name,
            deny_reason=deny_reason
        )

        # Disable all buttons on the review message
        for child in self.review_view.children:
            child.disabled = True

        await self.original_message.edit(
            content=f"❌ **DENIED** by {interaction.user.mention}\n📋 **Reason:** {deny_reason}",
            view=self.review_view
        )

        # DM the submitter with reviewer name and reason
        try:
            uid = int(self.staff_id) if str(self.staff_id).isdigit() else None
            if uid:
                user = await interaction.client.fetch_user(uid)
                dm_embed = discord.Embed(
                    title=f"❌ Your {log_type} Log Has Been Rejected",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now()
                )
                dm_embed.add_field(name="Log ID",     value=f"`{self.log_id}`",  inline=False)
                dm_embed.add_field(name="Rejected By", value=reviewer_name,       inline=True)
                dm_embed.add_field(name="Reason",     value=deny_reason,          inline=False)
                dm_embed.set_footer(text="Please fix any issues and resubmit if needed.")
                await user.send(embed=dm_embed)
        except Exception as e:
            print(f"[BOT] Could not DM user {self.staff_id}: {e}")

        await interaction.followup.send(
            f"✅ Log `{self.log_id}` has been **denied** and the submitter has been notified.",
            ephemeral=True
        )


# ---------------- REVIEW BUTTONS ----------------
class ReviewButtons(discord.ui.View):
    def __init__(self, staff_id, log_id, payload, original_message=None):
        super().__init__(timeout=None)
        self.staff_id = staff_id
        self.log_id = log_id
        self.payload = payload
        self.original_message = original_message

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success, custom_id="accept_button")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        log_type = self.payload["type"]
        reviewer_name = interaction.user.name

        channel_map = {
            "Sales":         FINAL_SALES_CHANNEL_ID,
            "Outreach":      FINAL_OUTREACH_CHANNEL_ID,
            "Giveaway":      FINAL_GIVEAWAY_CHANNEL_ID,
            "Investigation": FINAL_INVESTIGATION_CHANNEL_ID,
        }
        channel_id = channel_map.get(log_type, FINAL_OUTREACH_CHANNEL_ID)
        final_channel = interaction.client.get_channel(channel_id)

        # Build accepted embed for the final channel
        accepted_embed = discord.Embed(
            title=f"✅ {log_type} Log Accepted | {self.log_id}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        accepted_embed.add_field(name="Accepted By", value=interaction.user.mention, inline=False)

        if log_type == "Sales":
            accepted_embed.add_field(name="Customer",   value=self.payload.get("customer_username", "—"), inline=True)
            accepted_embed.add_field(name="Sale Type",  value=self.payload.get("sale_type", "—"),         inline=True)
            accepted_embed.add_field(name="Products",   value=self.payload.get("products", "—"),          inline=False)
            accepted_embed.add_field(name="Prize",      value=self.payload.get("prize", "—"),             inline=True)
        elif log_type == "Outreach":
            accepted_embed.add_field(name="Server",     value=self.payload.get("server", "—"),  inline=False)
            accepted_embed.add_field(name="Outcome",    value=self.payload.get("outcome", "—"), inline=True)
        elif log_type == "Giveaway":
            accepted_embed.add_field(name="Server",     value=self.payload.get("server", "—"),     inline=False)
            accepted_embed.add_field(name="Their Ping", value=self.payload.get("their_ping", "—"), inline=True)
            accepted_embed.add_field(name="Our Ping",   value=self.payload.get("our_ping", "—"),   inline=True)
        elif log_type == "Investigation":
            accepted_embed.add_field(name="Case Number",   value=self.payload.get("case_number", "—"),   inline=True)
            accepted_embed.add_field(name="Reported User", value=self.payload.get("reported_user", "—"), inline=False)
            accepted_embed.add_field(name="Investigator",  value=self.payload.get("investigator", "—"),  inline=True)
            accepted_embed.add_field(name="Outcome",       value=self.payload.get("outcome", "—"),       inline=True)
            accepted_embed.add_field(name="Reason",        value=self.payload.get("reason", "—"),        inline=False)
            if self.payload.get("proof"):
                accepted_embed.add_field(name="Google Doc", value=self.payload.get("proof"), inline=False)

        # Post to the final accepted channel
        if final_channel:
            await final_channel.send(embed=accepted_embed)
        else:
            print(f"[BOT] WARNING: Final channel {channel_id} not found for log type {log_type}")

        # Update Flask API
        try:
            res = requests.post(
                f"{API_BASE_URL}/accept-log/{self.log_id}",
                json={"reviewed_by": reviewer_name},
                headers=api_headers(),
                timeout=8
            )
            print(f"[API] accept-log: {res.status_code} — {res.text}")
        except Exception as e:
            print(f"[API] accept-log ERROR: {e}")

        # Disable buttons on the review message
        for child in self.children:
            child.disabled = True

        msg = self.original_message or interaction.message
        await msg.edit(
            content=f"✅ **ACCEPTED** by {interaction.user.mention}",
            view=self
        )

        # DM the submitter
        try:
            uid = int(self.staff_id) if str(self.staff_id).isdigit() else None
            if uid:
                user = await interaction.client.fetch_user(uid)
                dm_embed = discord.Embed(
                    title=f"✅ Your {log_type} Log Has Been Accepted",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )
                dm_embed.add_field(name="Log ID",     value=f"`{self.log_id}`", inline=False)
                dm_embed.add_field(name="Accepted By", value=reviewer_name,     inline=True)
                dm_embed.set_footer(text="Great work! Keep it up.")
                await user.send(embed=dm_embed)
        except Exception as e:
            print(f"[BOT] Could not DM user: {e}")

        await interaction.followup.send(
            f"✅ Log `{self.log_id}` accepted and submitter notified!",
            ephemeral=True
        )

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="deny_button")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = self.original_message or interaction.message
        modal = DenyModal(
            staff_id=self.staff_id,
            log_id=self.log_id,
            payload=self.payload,
            original_message=msg,
            review_view=self
        )
        await interaction.response.send_modal(modal)


# ---------------- SALES MODAL ----------------
class SalesModal(discord.ui.Modal, title="Sales Log Submission"):
    customer_username = discord.ui.TextInput(label="Customer Username", placeholder="Enter customer's username", required=True)
    customer_id       = discord.ui.TextInput(label="Customer ID", placeholder="Enter customer's Discord/Roblox ID", required=True)
    sale_type         = discord.ui.TextInput(label="Sale Type", placeholder="e.g., VIP, Rank, Product", required=True)
    products          = discord.ui.TextInput(label="Product(s) Bought", placeholder="List all products purchased", required=True, style=discord.TextStyle.paragraph)
    server            = discord.ui.TextInput(label="Server", placeholder="Server name where sale occurred", required=True)
    prize             = discord.ui.TextInput(label="Prize/Amount", placeholder="Amount in Robux or currency", required=True)
    note              = discord.ui.TextInput(label="Additional Notes", placeholder="Any extra information", required=False, style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "📎 **Please upload your proof/screenshot now** (you have 5 minutes).\nJust send the image in this channel.",
            ephemeral=True
        )
        log_id = f"SL-{int(time.time())}"
        def check(m): return m.author.id == interaction.user.id and m.attachments
        proof_url = None
        try:
            msg = await bot.wait_for("message", check=check, timeout=300)
            proof_url = msg.attachments[0].url
            try: await msg.delete()
            except: pass
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Timeout! Please resubmit your log.", ephemeral=True)
            return

        payload = build_payload({
            "operator": interaction.user.name,
            "customer_username": self.customer_username.value,
            "customer_id": self.customer_id.value,
            "sale_type": self.sale_type.value,
            "products": self.products.value,
            "server": self.server.value,
            "prize": self.prize.value,
            "note": self.note.value or "—",
            "proof": proof_url
        }, "Sales")

        embed = build_embed(f"📥 Sales Log Review | {log_id}", discord.Color.blue(), payload, interaction.user)
        review_channel = bot.get_channel(REVIEW_CHANNEL_ID)
        if review_channel:
            view = ReviewButtons(interaction.user.id, log_id, payload)
            message = await review_channel.send(embed=embed, view=view)
            view.original_message = message
            await message.edit(view=view)
            await interaction.followup.send("✅ Sales log submitted for review!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Review channel not found! Please contact an admin.", ephemeral=True)


# ---------------- OUTREACH MODAL ----------------
class OutreachModal(discord.ui.Modal, title="Outreach Log Submission"):
    server  = discord.ui.TextInput(label="Server Outreached To", placeholder="Server name", required=True)
    outcome = discord.ui.TextInput(label="Outcome", placeholder="e.g., Partnership Accepted, Pending, Denied", required=True)
    link    = discord.ui.TextInput(label="Server Link/Invite", placeholder="Discord invite link", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("📎 **Please upload your proof/screenshot now** (you have 5 minutes).", ephemeral=True)
        log_id = f"OR-{int(time.time())}"
        def check(m): return m.author.id == interaction.user.id and m.attachments
        proof_url = None
        try:
            msg = await bot.wait_for("message", check=check, timeout=300)
            proof_url = msg.attachments[0].url
            try: await msg.delete()
            except: pass
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Timeout! Please resubmit.", ephemeral=True)
            return

        payload = build_payload({
            "operator": interaction.user.name,
            "server": self.server.value,
            "outcome": self.outcome.value,
            "link": self.link.value,
            "proof": proof_url
        }, "Outreach")

        embed = build_embed(f"📡 Outreach Review | {log_id}", discord.Color.purple(), payload, interaction.user)
        review_channel = bot.get_channel(REVIEW_CHANNEL_ID)
        if review_channel:
            view = ReviewButtons(interaction.user.id, log_id, payload)
            message = await review_channel.send(embed=embed, view=view)
            view.original_message = message
            await message.edit(view=view)
            await interaction.followup.send("✅ Outreach log submitted for review!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Review channel not found!", ephemeral=True)


# ---------------- GIVEAWAY MODAL ----------------
class GiveawayModal(discord.ui.Modal, title="Giveaway Log Submission"):
    username    = discord.ui.TextInput(label="Your Username", placeholder="Your Discord username", required=True)
    server      = discord.ui.TextInput(label="Server Name", placeholder="Server where giveaway was hosted", required=True)
    their_ping  = discord.ui.TextInput(label="Their Ping", placeholder="Ping to their server", required=True)
    our_ping    = discord.ui.TextInput(label="Our Ping", placeholder="Ping to our server", required=True)
    invite      = discord.ui.TextInput(label="Server Invite", placeholder="Discord invite link", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("📎 **Please upload your proof/screenshot now** (you have 5 minutes).", ephemeral=True)
        log_id = f"GV-{int(time.time())}"
        def check(m): return m.author.id == interaction.user.id and m.attachments
        proof_url = None
        try:
            msg = await bot.wait_for("message", check=check, timeout=300)
            proof_url = msg.attachments[0].url
            try: await msg.delete()
            except: pass
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Timeout! Please resubmit.", ephemeral=True)
            return

        payload = build_payload({
            "operator": interaction.user.name,
            "username": self.username.value,
            "server": self.server.value,
            "their_ping": self.their_ping.value,
            "our_ping": self.our_ping.value,
            "invite": self.invite.value,
            "proof": proof_url
        }, "Giveaway")

        embed = build_embed(f"🎁 Giveaway Review | {log_id}", discord.Color.gold(), payload, interaction.user)
        review_channel = bot.get_channel(GIVEAWAY_REVIEW_ID)
        if review_channel:
            view = ReviewButtons(interaction.user.id, log_id, payload)
            message = await review_channel.send(embed=embed, view=view)
            view.original_message = message
            await message.edit(view=view)
            await interaction.followup.send("✅ Giveaway log submitted for review!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Review channel not found!", ephemeral=True)


# ---------------- CASE LOG MODAL ----------------
class CaseLogModal(discord.ui.Modal, title="Investigation Case Log"):
    reported_user  = discord.ui.TextInput(label="Reported User", placeholder="Username of the person being reported", required=True)
    reporting_user = discord.ui.TextInput(label="Reporting User", placeholder="Username of the person who reported", required=True)
    investigator   = discord.ui.TextInput(label="Investigator", placeholder="Your username", required=True)
    date           = discord.ui.TextInput(label="Date of Investigation", placeholder="YYYY-MM-DD", required=True)
    outcome        = discord.ui.TextInput(label="Outcome", placeholder="Guilty / Innocent / Inconclusive", required=True)
    reason         = discord.ui.TextInput(label="Reason/Summary", placeholder="Explain the investigation findings...", required=True, style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "📄 **Please send your Google Doc link now** (you have 5 minutes).",
            ephemeral=True
        )
        log_id = f"CASE-{int(time.time())}"
        def check(m): return m.author.id == interaction.user.id and m.content and ("docs.google.com" in m.content or "http" in m.content)
        doc_link = None
        try:
            msg = await bot.wait_for("message", check=check, timeout=300)
            doc_link = msg.content.strip()
            try: await msg.delete()
            except: pass
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Timeout! Please resubmit your case log.", ephemeral=True)
            return

        payload = build_payload({
            "operator": interaction.user.name,
            "investigator": self.investigator.value,
            "reported_user": self.reported_user.value,
            "reporting_user": self.reporting_user.value,
            "date": self.date.value,
            "outcome": self.outcome.value,
            "reason": self.reason.value,
            "case_number": log_id,
            "proof": doc_link
        }, "Investigation")

        embed = discord.Embed(
            title=f"🔍 Case Log Review | {log_id}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Submitted By",   value=interaction.user.mention,     inline=False)
        embed.add_field(name="Investigator",   value=self.investigator.value,      inline=True)
        embed.add_field(name="Date",           value=self.date.value,              inline=True)
        embed.add_field(name="Reported User",  value=self.reported_user.value,     inline=False)
        embed.add_field(name="Reporting User", value=self.reporting_user.value,    inline=False)
        embed.add_field(name="Outcome",        value=self.outcome.value,           inline=True)
        embed.add_field(name="Reason",         value=self.reason.value[:500],      inline=False)
        embed.add_field(name="Google Doc",     value=doc_link,                     inline=False)
        embed.set_footer(text=f"Log ID: {log_id}")

        # Post to the investigation review channel (1496059422873485332)
        review_channel = bot.get_channel(CASE_LOG_REVIEW_ID)
        if review_channel:
            view = ReviewButtons(interaction.user.id, log_id, payload)
            message = await review_channel.send(embed=embed, view=view)
            view.original_message = message
            await message.edit(view=view)
            await interaction.followup.send(f"✅ Case log `{log_id}` submitted for review!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Review channel not found! Please contact an admin.", ephemeral=True)


# -----------------------------------------------------------------------
#  INTERNAL HTTP SERVER  (Flask → Bot bridge for web-portal submissions)
# -----------------------------------------------------------------------
async def handle_post_review(request: web.Request) -> web.Response:
    """
    Flask calls POST http://127.0.0.1:6000/post-review when a case log is
    submitted via the web portal. The bot then posts the embed + buttons
    to channel 1496059422873485332.
    """
    try:
        auth = request.headers.get("X-Bot-Key", "")
        if auth != BOT_API_KEY:
            return web.json_response({"status": "unauthorized"}, status=401)

        data = await request.json()
        log_id   = data.get("log_id")
        staff_id = data.get("user_id")
        payload  = data.get("payload", {})
        log_type = payload.get("type", "Investigation")

        # Always use the investigation review channel for inv/case logs
        channel_map = {
            "Sales":         REVIEW_CHANNEL_ID,
            "Outreach":      REVIEW_CHANNEL_ID,
            "Giveaway":      GIVEAWAY_REVIEW_ID,
            "Investigation": CASE_LOG_REVIEW_ID,   # 1496059422873485332
        }
        channel_id = channel_map.get(log_type, CASE_LOG_REVIEW_ID)
        channel = bot.get_channel(channel_id)

        if not channel:
            print(f"[HTTP] Channel {channel_id} not found — bot may not be in guild yet")
            return web.json_response({"status": "error", "message": f"Channel {channel_id} not found"}, status=404)

        # Build the review embed
        embed = discord.Embed(
            title=f"🔍 Case Log Review | {log_id}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Source",         value="🌐 Web Portal Submission",             inline=False)
        embed.add_field(name="Investigator",   value=payload.get("investigator", "—"),      inline=True)
        embed.add_field(name="Date",           value=payload.get("date", "—"),              inline=True)
        embed.add_field(name="Reported User",  value=payload.get("reported_user", "—"),     inline=False)
        embed.add_field(name="Reporting User", value=payload.get("reporting_user", "—"),    inline=False)
        embed.add_field(name="Outcome",        value=payload.get("outcome", "—"),           inline=True)
        embed.add_field(name="Reason",         value=(payload.get("reason") or "—")[:500],  inline=False)
        embed.add_field(name="Google Doc",     value=payload.get("proof") or "None",        inline=False)
        embed.set_footer(text=f"Log ID: {log_id}")

        view = ReviewButtons(staff_id, log_id, payload)
        message = await channel.send(embed=embed, view=view)
        view.original_message = message
        await message.edit(view=view)

        print(f"[HTTP] Posted review for log {log_id} to channel {channel_id}")
        return web.json_response({"status": "ok", "message_id": message.id})

    except Exception as e:
        print(f"[HTTP] handle_post_review error: {e}")
        import traceback; traceback.print_exc()
        return web.json_response({"status": "error", "message": str(e)}, status=500)


async def start_http_server():
    """Start the internal aiohttp bridge server BEFORE the bot connects."""
    app_http = web.Application()
    app_http.router.add_post("/post-review", handle_post_review)
    runner = web.AppRunner(app_http)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", BOT_HTTP_PORT)
    await site.start()
    print(f"[HTTP] Internal bridge server running on port {BOT_HTTP_PORT}")


# ---------------- BOT SETUP ----------------
class VoidBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Start the HTTP bridge FIRST so Flask can reach it immediately
        await start_http_server()
        await self.tree.sync()
        print(f"[BOT] Slash commands synced!")

    async def on_ready(self):
        print(f"[BOT] ONLINE — {self.user}")
        print(f"[BOT] Guild: {self.guilds[0].id if self.guilds else 'None'}")
        print(f"[BOT] Watching review channel: {CASE_LOG_REVIEW_ID}")
        print(f"[BOT] Accepted logs go to:     {FINAL_INVESTIGATION_CHANNEL_ID}")


bot = VoidBot()


# ---------------- SLASH COMMANDS ----------------
@bot.tree.command(name="log-sale", description="Submit a sales log for review")
async def log_sale(interaction: discord.Interaction):
    await interaction.response.send_modal(SalesModal())


@bot.tree.command(name="log-outreach", description="Submit an outreach log for review")
async def log_outreach(interaction: discord.Interaction):
    await interaction.response.send_modal(OutreachModal())


@bot.tree.command(name="log-giveaway", description="Submit a giveaway log for review")
async def log_giveaway(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())


@bot.tree.command(name="case-log", description="Submit an IA case log for review")
async def case_log(interaction: discord.Interaction):
    await interaction.response.send_modal(CaseLogModal())


# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    bot.run(TOKEN)