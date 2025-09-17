# =====================================================================================
# SCRIPT LENGKAP BOT KASIR V8 (Final & Teruji)
# DIBUAT DENGAN BANTUAN GOOGLE GEMINI
# =====================================================================================

import os
import json
import logging
import hashlib
import locale
import calendar
from datetime import date, datetime
from dotenv import load_dotenv
from fpdf import FPDF

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- KONFIGURASI & SETUP ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RESTAURANT_NAME = "Warung Percobaan"
RESTAURANT_LOCATION = "Pucang Gading"
TAX_PERCENTAGE = 0
SERVICE_PERCENTAGE = 0
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- STATE UNTUK CONVERSATION HANDLER ---
USERNAME, PASSWORD, CONFIRM_PASSWORD = range(3)
MENU_NAMA, MENU_HARGA, MENU_STOK = range(3, 6)
PENGELUARAN_DESKRIPSI, PENGELUARAN_NOMINAL = range(6, 8)
KASBON_NAMA, KASBON_NOMINAL = range(8, 10)
EDIT_MENU_PILIH_AKSI, EDIT_MENU_NAMA_BARU, EDIT_MENU_HARGA_BARU = range(10, 13)
GET_REPORT_PERIOD = range(13, 14)
GET_CUSTOMER_NAME = range(14, 15)
CART_INTERACTION = 16
ADJUST_STOCK_AMOUNT = range(17, 18)

# --- FUNGSI HELPER DATA (Multi-Tenant) ---
def load_central_data(file_path):
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_central_data(file_path, data):
    with open(file_path, 'w') as f: json.dump(data, f, indent=4)

def get_user_data_path(username):
    safe_username = "".join(c for c in username if c.isalnum())
    return f"data_{safe_username}.json"

def load_user_data(username):
    file_path = get_user_data_path(username)
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"menu": [], "penjualan": [], "pengeluaran": [], "kasbon": []}

def save_user_data(username, data):
    file_path = get_user_data_path(username)
    with open(file_path, 'w') as f: json.dump(data, f, indent=4)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- FUNGSI-FUNGSI PEMBUATAN PDF ---
def generate_monthly_recap_pdf(data, year_month):
    try:
        report_date = date.fromisoformat(f"{year_month}-01"); month_name = report_date.strftime("%B"); year = int(year_month.split('-')[0]); month = int(year_month.split('-')[1])
    except ValueError: return None
    filename = f"laporan_bulanan_{year_month}.pdf"; daily_summary = {}
    for sale in [p for p in data.get('penjualan', []) if p['tanggal'].startswith(year_month)]:
        day = sale['tanggal']; daily_summary.setdefault(day, {'pemasukan': 0, 'pengeluaran': 0})['pemasukan'] += sale['harga'] * sale['jumlah']
    for expense in [e for e in data.get('pengeluaran', []) if e['tanggal'].startswith(year_month)]:
        day = expense['tanggal']; daily_summary.setdefault(day, {'pemasukan': 0, 'pengeluaran': 0})['pengeluaran'] += expense['nominal']
    total_pemasukan, total_pengeluaran = sum(d['pemasukan'] for d in daily_summary.values()), sum(d['pengeluaran'] for d in daily_summary.values())
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Helvetica", "B", 16); pdf.cell(0, 10, f"Laporan Bulanan - {month_name} {year}", 0, 1, 'C'); pdf.ln(10)
    pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 10, "REKAPITULASI HARIAN", 0, 1); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 8, "Tanggal", 1, 0, 'C'); pdf.cell(50, 8, "Pemasukan", 1, 0, 'C'); pdf.cell(50, 8, "Pengeluaran", 1, 0, 'C'); pdf.cell(50, 8, "Laba Bersih", 1, 1, 'C')
    pdf.set_font("Helvetica", "", 10)
    num_days = calendar.monthrange(year, month)[1]
    for day_num in range(1, num_days + 1):
        current_date_str = f"{year_month}-{day_num:02d}"; day_data = daily_summary.get(current_date_str, {'pemasukan': 0, 'pengeluaran': 0})
        pemasukan_harian, pengeluaran_harian = day_data['pemasukan'], day_data['pengeluaran']; laba_harian = pemasukan_harian - pengeluaran_harian
        formatted_date = date.fromisoformat(current_date_str).strftime("%d %b %Y")
        pdf.cell(40, 8, formatted_date, 1); pdf.cell(50, 8, f"Rp {pemasukan_harian:,}", 1, 0, 'R'); pdf.cell(50, 8, f"Rp {pengeluaran_harian:,}", 1, 0, 'R'); pdf.cell(50, 8, f"Rp {laba_harian:,}", 1, 1, 'R')
    pdf.ln(10); pdf.set_font("Helvetica", "B", 12); pdf.cell(70, 8, "Total Pemasukan Bulan Ini:", 0, 0, 'R'); pdf.cell(40, 8, f"Rp {total_pemasukan:,}", 0, 1, 'R')
    pdf.cell(70, 8, "Total Pengeluaran Bulan Ini:", 0, 0, 'R'); pdf.cell(40, 8, f"Rp {total_pengeluaran:,}", 0, 1, 'R'); pdf.set_font("Helvetica", "B", 14)
    pdf.cell(70, 10, "LABA BERSIH BULANAN:", 0, 0, 'R'); pdf.cell(40, 10, f"Rp {total_pemasukan - total_pengeluaran:,}", 0, 1, 'R'); pdf.output(filename)
    return filename

def generate_order_receipt_pdf(cart, menu_map, customer_name, cashier_name):
    order_id = f"TX-{datetime.now().strftime('%Y%m%d-%H%M%S')}"; filename = f"nota_{customer_name.replace(' ', '_')}_{order_id}.pdf"
    pdf = FPDF(orientation='P', unit='mm', format=(80, 200)); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=5); pdf.set_font("Helvetica", "B", 12); pdf.set_margin(5)
    pdf.cell(0, 6, RESTAURANT_NAME, 0, 1, 'C'); pdf.set_font("Helvetica", "", 8); pdf.cell(0, 4, RESTAURANT_LOCATION, 0, 1, 'C'); pdf.ln(5)
    col_width, line_height = pdf.w / 2 - pdf.l_margin, 4; pdf.set_font("Helvetica", "", 8)
    pdf.cell(col_width, line_height, f"Date: {date.today().strftime('%b %d %Y')}", 0, 0, 'L'); pdf.cell(col_width, line_height, f"Cashier: {cashier_name}", 0, 1, 'R')
    pdf.cell(col_width, line_height, f"Trx ID: {order_id}", 0, 0, 'L'); pdf.cell(col_width, line_height, f"Customer: {customer_name}", 0, 1, 'R')
    pdf.ln(3); pdf.dashed_line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y()); pdf.ln(3)
    subtotal = sum(menu_map.get(item_id)['harga'] * jumlah for item_id, jumlah in cart.items() if item_id in menu_map)
    for item_id, jumlah in cart.items():
        menu_item = menu_map.get(item_id)
        if menu_item:
            pdf.set_font("Helvetica", "B", 8); pdf.cell(col_width + 10, line_height, f"{menu_item['nama']} x{jumlah}", 0, 0, 'L'); pdf.set_font("Helvetica", "", 8); pdf.cell(col_width - 10, line_height, f"Rp{menu_item['harga'] * jumlah:,}", 0, 1, 'R')
    pdf.ln(3); pdf.dashed_line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y()); pdf.ln(3); pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, line_height, "Payment Details", 0, 1, 'L'); pdf.set_font("Helvetica", "", 8)
    discount, service = 0, int(subtotal * (SERVICE_PERCENTAGE / 100)); tax = int((subtotal + service - discount) * (TAX_PERCENTAGE / 100)); total = subtotal + service + tax - discount
    pdf.cell(col_width, line_height, "Subtotal", 0, 0, 'L'); pdf.cell(col_width, line_height, f"Rp{subtotal:,}", 0, 1, 'R'); pdf.cell(col_width, line_height, "Discount", 0, 0, 'L'); pdf.cell(col_width, line_height, f"-Rp{discount:,}", 0, 1, 'R'); pdf.cell(col_width, line_height, f"Service ({SERVICE_PERCENTAGE}%)", 0, 0, 'L'); pdf.cell(col_width, line_height, f"Rp{service:,}", 0, 1, 'R'); pdf.cell(col_width, line_height, f"Tax ({TAX_PERCENTAGE}%)", 0, 0, 'L'); pdf.cell(col_width, line_height, f"Rp{tax:,}", 0, 1, 'R')
    pdf.set_font("Helvetica", "B", 10); pdf.cell(col_width, line_height + 2, "Total", 0, 0, 'L'); pdf.cell(col_width, line_height + 2, f"Rp{total:,}", 0, 1, 'R'); pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "PAID", 0, 1, 'C'); pdf.set_font("Helvetica", "", 8); pdf.cell(0, 4, datetime.now().strftime("%b %d %Y - %H:%M"), 0, 1, 'C'); pdf.ln(5); pdf.cell(0, 4, "Thank you for your order!", 0, 1, 'C'); pdf.output(filename)
    return filename

# --- FUNGSI INTI & DASHBOARD ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'username' in context.user_data: await show_dashboard(update, context)
    else: keyboard = [[InlineKeyboardButton("🔐 Login", callback_data="login"), InlineKeyboardButton("✍️ Register", callback_data="register")]]; await update.message.reply_text("Selamat datang di Bot Kasir!", reply_markup=InlineKeyboardMarkup(keyboard))

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear(); await update.message.reply_text("Anda telah berhasil logout."); await start(update, context)

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = context.user_data.get('username')
    if not username: logger.warning("Dashboard dipanggil tanpa login."); keyboard = [[InlineKeyboardButton("🔐 Login", callback_data="login"), InlineKeyboardButton("✍️ Register", callback_data="register")]]; await context.bot.send_message(chat_id=update.effective_chat.id, text="Sesi tidak ditemukan.", reply_markup=InlineKeyboardMarkup(keyboard)); return
    user_data = load_user_data(username); today_str = date.today().isoformat()
    pemasukan, pengeluaran = sum(i['harga']*i['jumlah'] for i in user_data.get('penjualan',[]) if i['tanggal']==today_str), sum(i['nominal'] for i in user_data.get('pengeluaran',[]) if i['tanggal']==today_str)
    kasbon_aktif, kasbon_text = [i['nama'] for i in user_data.get('kasbon',[]) if not i['lunas']], "Tidak ada"
    if kasbon_aktif: kasbon_text = f"{len(kasbon_aktif)} Orang ({', '.join(kasbon_aktif)})"
    text = (f"📊 *Dashboard Harian* ---\n👤 Login sebagai: *{username}*\n\n💰 Pemasukan : Rp {pemasukan:,}\n💸 Pengeluaran: Rp {pengeluaran:,}\n📈 Laba Bersih: Rp {pemasukan - pengeluaran:,}\n✋ Kasbon Aktif: {kasbon_text}")
    keyboard = [[InlineKeyboardButton("🛒 Buat Pesanan Baru", callback_data="order_start")], [InlineKeyboardButton("⚙️ Kelola Menu", callback_data="manage_menu"), InlineKeyboardButton("✋ Kelola Kasbon", callback_data="manage_kasbon")], [InlineKeyboardButton("💸 Kelola Pengeluaran", callback_data="manage_expenses"), InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard")], [InlineKeyboardButton("🖨️ Cetak Laporan Bulanan", callback_data="print_report")], [InlineKeyboardButton("🚪 Logout", callback_data="logout")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else: await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e: logger.error(f"Gagal update dashboard: {e}"); await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keys_to_clear = ['edit_menu_id', 'new_menu_name', 'new_menu_price', 'new_expense_desc', 'new_kasbon_name', 'adjust_stock_menu_id', 'customer_name', 'cart']
    for key in keys_to_clear:
        if key in context.user_data: del context.user_data[key]
    await update.message.reply_text("Proses dibatalkan."); await show_dashboard(update, context); return ConversationHandler.END

# --- HANDLER TOMBOL NAVIGASI ---
async def logout_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer(); context.user_data.clear()
    keyboard = [[InlineKeyboardButton("🔐 Login", callback_data="login"), InlineKeyboardButton("✍️ Register", callback_data="register")]]; await query.edit_message_text(text="Anda telah berhasil logout.", reply_markup=InlineKeyboardMarkup(keyboard))
async def report_ask_period(update: Update, context: ContextTypes.DEFAULT_TYPE): query=update.callback_query; await query.answer(); await query.message.reply_text("Masukkan periode (YYYY-MM):"); return GET_REPORT_PERIOD
async def report_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return ConversationHandler.END
    period = update.message.text; await update.message.reply_text(f"Membuat laporan untuk {period}..."); user_data = load_user_data(username); pdf_file = generate_monthly_recap_pdf(user_data, period)
    if pdf_file: await update.message.reply_document(document=open(pdf_file, 'rb'), filename=pdf_file); os.remove(pdf_file)
    else: await update.message.reply_text("Format periode tidak valid.")
    await show_dashboard(update, context); return ConversationHandler.END

# --- FUNGSI-FUNGSI FITUR ---
# (LOGIN & REGISTER)
async def login_ask_username(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.reply_text("Masukkan username:"); return USERNAME
async def login_ask_password(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['login_username']=update.message.text; await update.message.reply_text("Masukkan password:"); return PASSWORD
async def login_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username, password, users = context.user_data.get('login_username',''), update.message.text, load_central_data('users.json')
    if username in users and users[username] == hash_password(password): context.user_data['username'] = username; await show_dashboard(update, context)
    else: await update.message.reply_text("Username/password salah."); keyboard=[[InlineKeyboardButton("🔐 Login", callback_data="login"), InlineKeyboardButton("✍️ Register", callback_data="register")]]; await update.message.reply_text("Coba lagi:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END
async def register_ask_username(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.reply_text("Buat username baru:"); return USERNAME
async def register_ask_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username, users = update.message.text, load_central_data('users.json')
    if username in users: await update.message.reply_text("Username sudah terpakai. Pilih lain:"); return USERNAME
    else: context.user_data['register_username']=username; await update.message.reply_text("Username tersedia. Buat password:"); return PASSWORD
async def register_ask_confirm_password(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['register_password1']=update.message.text; await update.message.reply_text("Ketik ulang password:"); return CONFIRM_PASSWORD
async def register_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password2, password1 = update.message.text, context.user_data.get('register_password1','')
    if password1 != password2: await update.message.reply_text("Password tidak cocok. Buat password lagi:"); return PASSWORD
    else: username, users = context.user_data.get('register_username',''), load_central_data('users.json'); users[username] = hash_password(password1); save_central_data('users.json', users); save_user_data(username, {"menu": [], "penjualan": [], "pengeluaran": [], "kasbon": []}); context.user_data['username'] = username; await show_dashboard(update, context)
    return ConversationHandler.END

# (KELOLA MENU + STOK)
async def menu_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE): keyboard = [[InlineKeyboardButton("➕ Tambah Menu", callback_data="add_menu_start")], [InlineKeyboardButton("✏️ Edit Menu", callback_data="edit_menu_start"), InlineKeyboardButton("❌ Hapus Menu", callback_data="delete_menu_start")], [InlineKeyboardButton("📦 Sesuaikan Stok", callback_data="adjust_stock_start")], [InlineKeyboardButton("📖 Lihat Semua Menu", callback_data="view_menu")], [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_main")]]; await update.callback_query.edit_message_text("--- ⚙️ Kelola Menu ---", reply_markup=InlineKeyboardMarkup(keyboard))
async def add_menu_ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.reply_text("Nama menu baru:"); return MENU_NAMA
async def add_menu_ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['new_menu_name']=update.message.text; await update.message.reply_text("Harga (contoh: 15000):"); return MENU_HARGA
async def add_menu_ask_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: context.user_data['new_menu_price'] = int(update.message.text); await update.message.reply_text("Masukkan jumlah stok awal:")
    except ValueError: await update.message.reply_text("Harga tidak valid. Masukkan angka."); return MENU_HARGA
    return MENU_STOK
async def add_menu_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username');
    if not username: return ConversationHandler.END
    try: stock, name, price, user_data = int(update.message.text), context.user_data['new_menu_name'], context.user_data['new_menu_price'], load_user_data(username); new_id = max([m.get('id',0) for m in user_data['menu']]+[0])+1; user_data['menu'].append({'id':new_id,'nama':name,'harga':price,'stok':stock}); save_user_data(username, user_data); await update.message.reply_text(f"✅ Menu '{name}' (Stok: {stock}) Rp {price:,} ditambahkan.")
    except ValueError: await update.message.reply_text("Stok tidak valid.")
    for key in ['new_menu_name','new_menu_price']:
        if key in context.user_data: del context.user_data[key]
    await show_dashboard(update, context); return ConversationHandler.END
async def view_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username');
    if not username: return
    menu_list=load_user_data(username).get('menu',[]); text="--- 📖 Daftar Menu ---\n";
    if not menu_list: text += "Belum ada menu."
    else: text += '\n'.join([f"- {i['nama']} : Rp {i['harga']:,} (Stok: {i.get('stok',0)}){' (HABIS)' if i.get('stok',0)<=0 else ''}" for i in sorted(menu_list, key=lambda x:x['nama'])])
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Kembali", callback_data="manage_menu")]]))
async def delete_menu_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username');
    if not username: return
    menu_list = load_user_data(username).get('menu',[]);
    if not menu_list: await update.callback_query.answer("Tidak ada menu untuk dihapus.", show_alert=True); return
    keyboard = [[InlineKeyboardButton(f"❌ {i['nama']}", callback_data=f"delete_menu_confirm_{i['id']}")] for i in sorted(menu_list, key=lambda x:x['nama'])] + [[InlineKeyboardButton("↩️ Batal", callback_data="manage_menu")]]; await update.callback_query.edit_message_text("Pilih menu untuk dihapus:", reply_markup=InlineKeyboardMarkup(keyboard))
async def delete_menu_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username');
    if not username: return
    menu_id, user_data = int(update.callback_query.data.split('_')[-1]), load_user_data(username); initial_len=len(user_data['menu']); user_data['menu']=[m for m in user_data['menu'] if m['id']!=menu_id]
    if len(user_data['menu'])<initial_len: save_user_data(username, user_data); await update.callback_query.answer("Menu dihapus!", show_alert=True); await show_dashboard(update, context)
    else: await update.callback_query.answer("Gagal hapus.", show_alert=True); await menu_management_menu(update, context)
async def edit_menu_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username');
    if not username: return ConversationHandler.END
    menu_list = load_user_data(username).get('menu',[]);
    if not menu_list: await update.callback_query.answer("Tidak ada menu untuk diedit.", show_alert=True); return
    keyboard = [[InlineKeyboardButton(f"✏️ {i['nama']}", callback_data=f"edit_menu_select_{i['id']}")] for i in sorted(menu_list, key=lambda x:x['nama'])] + [[InlineKeyboardButton("↩️ Batal", callback_data="manage_menu")]]; await update.callback_query.edit_message_text("Pilih menu untuk diedit:", reply_markup=InlineKeyboardMarkup(keyboard)); return EDIT_MENU_PILIH_AKSI
async def edit_menu_pilih_aksi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username');
    if not username: return ConversationHandler.END
    menu_id = int(update.callback_query.data.split('_')[-1]); context.user_data['edit_menu_id']=menu_id; menu_item=next((i for i in load_user_data(username)['menu'] if i['id']==menu_id), None)
    if not menu_item: await update.callback_query.answer("Menu tidak ditemukan.", show_alert=True); return ConversationHandler.END
    keyboard=[[InlineKeyboardButton("Ubah Nama", callback_data="edit_name"), InlineKeyboardButton("Ubah Harga", callback_data="edit_price")], [InlineKeyboardButton("↩️ Kembali", callback_data="manage_menu")]]; await update.callback_query.edit_message_text(f"Edit menu: *{menu_item['nama']}*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'); return EDIT_MENU_PILIH_AKSI
async def edit_menu_ask_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.reply_text("Masukkan nama baru:"); return EDIT_MENU_NAMA_BARU
async def edit_menu_save_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username');
    if not username: return ConversationHandler.END
    new_name, menu_id, user_data = update.message.text, context.user_data['edit_menu_id'], load_user_data(username)
    for i in user_data['menu']:
        if i['id']==menu_id: i['nama']=new_name; break
    save_user_data(username, user_data); await update.message.reply_text("✅ Nama menu diubah."); del context.user_data['edit_menu_id']; await show_dashboard(update, context); return ConversationHandler.END
async def edit_menu_ask_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.reply_text("Masukkan harga baru:"); return EDIT_MENU_HARGA_BARU
async def edit_menu_save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username')
    if not username: return ConversationHandler.END
    try:
        new_price = int(update.message.text); menu_id = context.user_data['edit_menu_id']; user_data = load_user_data(username)
        for item in user_data['menu']:
            if item['id'] == menu_id: item['harga'] = new_price; break
        save_user_data(username, user_data); await update.message.reply_text("✅ Harga menu berhasil diubah."); del context.user_data['edit_menu_id']; await show_dashboard(update, context)
    except ValueError: await update.message.reply_text("Harga tidak valid. Proses edit dibatalkan.")
    return ConversationHandler.END
async def adjust_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username')
    if not username: return ConversationHandler.END
    query=update.callback_query; await query.answer(); menu_list=load_user_data(username).get('menu',[])
    if not menu_list: await query.answer("Tidak ada menu.", show_alert=True); return ConversationHandler.END
    return await display_adjust_stock_menu(update, context)
async def adjust_stock_ask_new_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer(); menu_id=int(query.data.split('_')[-1]); context.user_data['adjust_stock_menu_id']=menu_id; username = context.user_data.get('username')
    if not username: return ConversationHandler.END
    menu_item = next((item for item in load_user_data(username)['menu'] if item['id'] == menu_id), None)
    if not menu_item: await query.answer("Menu tidak ditemukan.", show_alert=True); return ConversationHandler.END
    await query.message.reply_text(f"Stok '{menu_item['nama']}' saat ini: {menu_item.get('stok',0)}.\nMasukkan jumlah stok baru:"); return ADJUST_STOCK_AMOUNT
async def adjust_stock_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username')
    if not username: return ConversationHandler.END
    try:
        new_stock, menu_id, user_data = int(update.message.text), context.user_data['adjust_stock_menu_id'], load_user_data(username); item_updated = None
        for item in user_data['menu']:
            if item['id'] == menu_id: item['stok']=new_stock; item_updated=item; break
        if item_updated: save_user_data(username, user_data); await update.message.reply_text(f"✅ Stok '{item_updated['nama']}' diubah menjadi {new_stock}.")
        else: await update.message.reply_text("Gagal ubah stok.")
    except ValueError: await update.message.reply_text("Jumlah stok tidak valid.")
    del context.user_data['adjust_stock_menu_id']; return await display_adjust_stock_menu(update, context)
async def display_adjust_stock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get('username')
    if not username: return ConversationHandler.END
    menu_list = load_user_data(username).get('menu', [])
    if not menu_list: await update.effective_message.reply_text("Tidak ada menu."); await menu_management_menu(update, context); return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{i['nama']} (Stok: {i.get('stok', 0)})", callback_data=f"adjust_stock_select_{i['id']}")] for i in sorted(menu_list, key=lambda x:x['nama'])]
    keyboard.append([InlineKeyboardButton("↩️ Selesai & Kembali", callback_data="manage_menu")])
    text = "Pilih menu lain untuk disesuaikan, atau selesai.";
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ADJUST_STOCK_AMOUNT

# (Sisa fungsi-fungsi lain yang sudah dimodifikasi)
async def expenses_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE): keyboard = [[InlineKeyboardButton("➕ Catat Pengeluaran", callback_data="add_expense_start")], [InlineKeyboardButton("📖 Lihat Hari Ini", callback_data="view_expenses_today")], [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_main")]]; await update.callback_query.edit_message_text("--- 💸 Kelola Pengeluaran ---", reply_markup=InlineKeyboardMarkup(keyboard))
async def view_expenses_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return
    pengeluaran_harian = [e for e in load_user_data(username).get('pengeluaran',[]) if e['tanggal']==date.today().isoformat()]
    if not pengeluaran_harian: text="Belum ada pengeluaran hari ini."
    else: text, total = "--- 📖 Pengeluaran Hari Ini ---\n", 0; text += '\n'.join([f"- {i['deskripsi']}: Rp {i['nominal']:,}" for i in pengeluaran_harian]); total = sum(i['nominal'] for i in pengeluaran_harian); text += f"\n\n*Total: Rp {total:,}*"
    await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Kembali", callback_data="manage_expenses")]]))
async def add_expense_ask_desc(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.reply_text("Deskripsi pengeluaran:"); return PENGELUARAN_DESKRIPSI
async def add_expense_ask_nominal(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['new_expense_desc']=update.message.text; await update.message.reply_text("Nominal (contoh: 50000):"); return PENGELUARAN_NOMINAL
async def add_expense_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return ConversationHandler.END
    try: nominal, desc, user_data = int(update.message.text), context.user_data['new_expense_desc'], load_user_data(username); user_data['pengeluaran'].append({'deskripsi':desc,'nominal':nominal,'tanggal':date.today().isoformat()}); save_user_data(username, user_data); await update.message.reply_text(f"✅ Pengeluaran '{desc}' Rp {nominal:,} dicatat.")
    except ValueError: await update.message.reply_text("Nominal tidak valid.")
    del context.user_data['new_expense_desc']; await show_dashboard(update, context); return ConversationHandler.END
async def kasbon_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE): keyboard = [[InlineKeyboardButton("➕ Tambah Kasbon", callback_data="add_kasbon_start")], [InlineKeyboardButton("✅ Lunasi Kasbon", callback_data="pay_kasbon_start")], [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_main")]]; await update.callback_query.edit_message_text("--- ✋ Kelola Kasbon ---", reply_markup=InlineKeyboardMarkup(keyboard))
async def add_kasbon_ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.reply_text("Nama penghutang:"); return KASBON_NAMA
async def add_kasbon_ask_nominal(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['new_kasbon_name']=update.message.text; await update.message.reply_text("Nominal hutang (contoh: 25000):"); return KASBON_NOMINAL
async def add_kasbon_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return ConversationHandler.END
    try: nominal, name, user_data = int(update.message.text), context.user_data['new_kasbon_name'], load_user_data(username); new_id=max([k.get('id',0) for k in user_data.get('kasbon',[])]+[0])+1; user_data['kasbon'].append({'id':new_id,'nama':name,'nominal':nominal,'tanggal_ambil':date.today().isoformat(),'lunas':False}); save_user_data(username, user_data); await update.message.reply_text(f"✅ Kasbon '{name}' Rp {nominal:,} dicatat.")
    except ValueError: await update.message.reply_text("Nominal tidak valid.")
    del context.user_data['new_kasbon_name']; await show_dashboard(update, context); return ConversationHandler.END
async def pay_kasbon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return
    kasbon_aktif = [k for k in load_user_data(username).get('kasbon',[]) if not k['lunas']]
    if not kasbon_aktif: await update.callback_query.answer("Tidak ada kasbon aktif.", show_alert=True); return
    keyboard = [[InlineKeyboardButton(f"{k['nama']} - Rp {k['nominal']:,}", callback_data=f"pay_kasbon_confirm_{k['id']}")] for k in kasbon_aktif]
    keyboard.append([InlineKeyboardButton("↩️ Kembali", callback_data="manage_kasbon")]); await update.callback_query.edit_message_text("Pilih kasbon untuk dilunasi:", reply_markup=InlineKeyboardMarkup(keyboard))
async def pay_kasbon_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return
    kasbon_id, user_data, kasbon_lunas = int(update.callback_query.data.split('_')[-1]), load_user_data(username), None
    for k in user_data['kasbon']:
        if k['id'] == kasbon_id: k['lunas'], kasbon_lunas = True, k; break
    if kasbon_lunas: save_user_data(username, user_data); await update.callback_query.answer(f"Kasbon an. {kasbon_lunas['nama']} lunas.", show_alert=True)
    await show_dashboard(update, context)

async def order_ask_customer_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return ConversationHandler.END
    query=update.callback_query; await query.answer()
    if not load_user_data(username).get('menu',[]): await query.answer("Tidak ada menu.", show_alert=True); return ConversationHandler.END
    await query.message.reply_text("Masukkan nama pemesan:"); return GET_CUSTOMER_NAME
async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['customer_name']=update.message.text; context.user_data['cart']={}; await order_update_display(update, context, is_new=True); return CART_INTERACTION
async def order_update_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return CART_INTERACTION
    query, action, item_id, cart = update.callback_query, update.callback_query.data.split('_')[1], int(update.callback_query.data.split('_')[2]), context.user_data.get('cart',{})
    user_data, menu_item = load_user_data(username), next((item for item in load_user_data(username)['menu'] if item['id'] == item_id), None)
    if not menu_item: await query.answer("Menu tidak ditemukan!", show_alert=True); return CART_INTERACTION
    stok_saat_ini, item_di_keranjang = menu_item.get('stok', 0), cart.get(item_id, 0)
    if action == 'add':
        if stok_saat_ini > item_di_keranjang: cart[item_id] = item_di_keranjang + 1
        else: await query.answer("Stok tidak mencukupi!", show_alert=True)
    elif action == 'rem' and item_id in cart:
        cart[item_id] -= 1;_ = cart.pop(item_id) if cart[item_id]<=0 else None
    context.user_data['cart'] = cart; await order_update_display(update, context); return CART_INTERACTION
async def order_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return ConversationHandler.END
    cart, customer_name = context.user_data.get('cart',{}), context.user_data.get('customer_name','Pelanggan')
    if not cart: await update.callback_query.answer("Keranjang kosong!", show_alert=True); return CART_INTERACTION
    user_data, menu_map, today_str = load_user_data(username), {item['id']:item for item in load_user_data(username)['menu']}, date.today().isoformat()
    for item_id, jumlah in cart.items():
        menu_item = menu_map.get(item_id)
        if menu_item:
            user_data['penjualan'].append({'menu_id':item_id,'nama_pemesan':customer_name,'nama':menu_item['nama'],'harga':menu_item['harga'],'jumlah':jumlah,'tanggal':today_str})
            for menu_in_db in user_data['menu']:
                if menu_in_db['id'] == item_id: menu_in_db['stok'] = menu_in_db.get('stok', 0) - jumlah; break
    save_user_data(username, user_data); await update.callback_query.answer("Nota sedang dibuat...", show_alert=True)
    pdf_file = generate_order_receipt_pdf(cart, menu_map, customer_name, username); await context.bot.send_document(chat_id=update.effective_chat.id, document=open(pdf_file, 'rb'), filename=pdf_file); os.remove(pdf_file)
    await update.callback_query.edit_message_text("✅ Pesanan berhasil disimpan!"); del context.user_data['cart']; del context.user_data['customer_name']; await show_dashboard(update, context); return ConversationHandler.END
async def order_update_display(update: Update, context: ContextTypes.DEFAULT_TYPE, is_new=False):
    username=context.user_data.get('username');
    if not username: return
    cart, user_data, customer_name = context.user_data.get('cart',{}), load_user_data(username), context.user_data.get('customer_name','-'); menu_map={i['id']:i for i in user_data['menu']}
    text, total = f"--- 🛒 Pesanan a/n *{customer_name}* ---\n", 0
    if not cart: text+="\nKeranjang masih kosong."
    else:
        for item_id, jumlah in cart.items():
            if item_id in menu_map: subtotal=menu_map[item_id]['harga']*jumlah; total+=subtotal; text+=f"\n- {menu_map[item_id]['nama']} (x{jumlah}) : Rp {subtotal:,}"
        text+=f"\n----------------------\n*TOTAL: Rp {total:,}*"
    keyboard = []
    for i in sorted(user_data['menu'], key=lambda x:x['nama']):
        label = f"{i['nama']} ({cart.get(i['id'],0)})" if i['id'] in cart else i['nama']
        if i.get('stok', 0) <= 0 and i['id'] not in cart: label = f"HABIS - {i['nama']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"o_{i['id']}"), InlineKeyboardButton("➖", callback_data=f"order_rem_{i['id']}"), InlineKeyboardButton("➕", callback_data=f"order_add_{i['id']}")])
    keyboard.extend([[InlineKeyboardButton("✅ Selesai & Simpan", callback_data="order_finish")], [InlineKeyboardButton("↩️ Batal", callback_data="back_to_main")]])
    if is_new: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        try: await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except: await update.callback_query.answer()

async def report_ask_period(update: Update, context: ContextTypes.DEFAULT_TYPE): query=update.callback_query; await query.answer(); await query.message.reply_text("Masukkan periode (YYYY-MM):"); return GET_REPORT_PERIOD
async def report_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username=context.user_data.get('username');
    if not username: return ConversationHandler.END
    period = update.message.text; await update.message.reply_text(f"Membuat laporan untuk {period}..."); user_data = load_user_data(username); pdf_file = generate_monthly_recap_pdf(user_data, period)
    if pdf_file: await update.message.reply_document(document=open(pdf_file, 'rb'), filename=pdf_file); os.remove(pdf_file)
    else: await update.message.reply_text("Format periode tidak valid.")
    await show_dashboard(update, context); return ConversationHandler.END

def main() -> None:
    """Fungsi utama untuk menjalankan seluruh bot dengan struktur handler yang benar."""
    # Atur locale ke Bahasa Indonesia untuk format tanggal
    try:
        locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'Indonesian_Indonesia.1252')

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # --- 1. DEFINISI SEMUA CONVERSATION HANDLER ---
    login_handler = ConversationHandler(entry_points=[CallbackQueryHandler(login_ask_username, pattern='^login$')], states={USERNAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, login_ask_password)], PASSWORD:[MessageHandler(filters.TEXT & ~filters.COMMAND, login_verify)]}, fallbacks=[CommandHandler("cancel", cancel)], per_message=False)
    register_handler = ConversationHandler(entry_points=[CallbackQueryHandler(register_ask_username, pattern='^register$')], states={USERNAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, register_ask_password)], PASSWORD:[MessageHandler(filters.TEXT & ~filters.COMMAND, register_ask_confirm_password)], CONFIRM_PASSWORD:[MessageHandler(filters.TEXT & ~filters.COMMAND, register_save)]}, fallbacks=[CommandHandler("cancel", cancel)], per_message=False)
    add_menu_handler = ConversationHandler(entry_points=[CallbackQueryHandler(add_menu_ask_name, pattern='^add_menu_start$')], states={MENU_NAMA:[MessageHandler(filters.TEXT & ~filters.COMMAND, add_menu_ask_price)], MENU_HARGA:[MessageHandler(filters.TEXT & ~filters.COMMAND, add_menu_ask_stock)], MENU_STOK:[MessageHandler(filters.TEXT & ~filters.COMMAND, add_menu_save)]}, fallbacks=[CommandHandler("cancel", cancel)], per_message=False)
    edit_menu_handler = ConversationHandler(entry_points=[CallbackQueryHandler(edit_menu_start, pattern='^edit_menu_start$')], states={EDIT_MENU_PILIH_AKSI:[CallbackQueryHandler(edit_menu_pilih_aksi, pattern=r'^edit_menu_select_\d+$'), CallbackQueryHandler(edit_menu_ask_new_name, pattern='^edit_name$'), CallbackQueryHandler(edit_menu_ask_new_price, pattern='^edit_price$'), CallbackQueryHandler(menu_management_menu, pattern='^manage_menu$')], EDIT_MENU_NAMA_BARU:[MessageHandler(filters.TEXT & ~filters.COMMAND, edit_menu_save_new_name)], EDIT_MENU_HARGA_BARU:[MessageHandler(filters.TEXT & ~filters.COMMAND, edit_menu_save_new_price)]}, fallbacks=[CommandHandler("cancel", cancel)], per_message=False)
    add_expense_handler = ConversationHandler(entry_points=[CallbackQueryHandler(add_expense_ask_desc, pattern='^add_expense_start$')], states={PENGELUARAN_DESKRIPSI:[MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_ask_nominal)], PENGELUARAN_NOMINAL:[MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_save)]}, fallbacks=[CommandHandler("cancel", cancel)], per_message=False)
    add_kasbon_handler = ConversationHandler(entry_points=[CallbackQueryHandler(add_kasbon_ask_name, pattern='^add_kasbon_start$')], states={KASBON_NAMA:[MessageHandler(filters.TEXT & ~filters.COMMAND, add_kasbon_ask_nominal)], KASBON_NOMINAL:[MessageHandler(filters.TEXT & ~filters.COMMAND, add_kasbon_save)]}, fallbacks=[CommandHandler("cancel", cancel)], per_message=False)
    report_handler = ConversationHandler(entry_points=[CallbackQueryHandler(report_ask_period, pattern='^print_report$')], states={GET_REPORT_PERIOD:[MessageHandler(filters.Regex(r'^\d{4}-\d{2}$'), report_generate)]}, fallbacks=[CommandHandler("cancel", cancel)], per_message=False)
    order_handler = ConversationHandler(entry_points=[CallbackQueryHandler(order_ask_customer_name, pattern='^order_start$')], states={GET_CUSTOMER_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, order_start)], CART_INTERACTION:[CallbackQueryHandler(order_update_item, pattern=r'^order_(add|rem)_\d+$'), CallbackQueryHandler(order_finish, pattern='^order_finish$'), CallbackQueryHandler(show_dashboard, pattern='^back_to_main$')]}, fallbacks=[CommandHandler("cancel", cancel)], per_message=False)
    adjust_stock_handler = ConversationHandler(entry_points=[CallbackQueryHandler(adjust_stock_start, pattern='^adjust_stock_start$')], states={ADJUST_STOCK_AMOUNT:[CallbackQueryHandler(adjust_stock_ask_new_amount, pattern=r'^adjust_stock_select_\d+$'), MessageHandler(filters.TEXT & ~filters.COMMAND, adjust_stock_save)]}, fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(menu_management_menu, pattern='^manage_menu$')], per_message=False)

    # --- 2. PENDAFTARAN SEMUA HANDLER KE BOT ---
    
    # Command Handlers Utama
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("logout", logout))
    application.add_handler(CommandHandler("cancel", cancel))

    # Conversation Handlers (untuk alur multi-langkah)
    all_conversation_handlers = [login_handler, register_handler, add_menu_handler, edit_menu_handler, add_expense_handler, add_kasbon_handler, report_handler, order_handler, adjust_stock_handler]
    application.add_handlers(all_conversation_handlers)
    
    # Callback Query Handlers (untuk tombol-tombol sederhana)
    application.add_handler(CallbackQueryHandler(view_menu, pattern='^view_menu$'))
    application.add_handler(CallbackQueryHandler(view_expenses_today, pattern='^view_expenses_today$'))
    application.add_handler(CallbackQueryHandler(delete_menu_start, pattern='^delete_menu_start$'))
    application.add_handler(CallbackQueryHandler(delete_menu_confirm, pattern=r'^delete_menu_confirm_\d+$'))
    application.add_handler(CallbackQueryHandler(pay_kasbon_start, pattern='^pay_kasbon_start$'))
    application.add_handler(CallbackQueryHandler(pay_kasbon_confirm, pattern=r'^pay_kasbon_confirm_\d+$'))
    
    # Handler Navigasi Umum (pengganti main_button_handler)
    application.add_handler(CallbackQueryHandler(show_dashboard, pattern='^(back_to_main|refresh_dashboard)$'))
    application.add_handler(CallbackQueryHandler(menu_management_menu, pattern='^manage_menu$'))
    application.add_handler(CallbackQueryHandler(kasbon_management_menu, pattern='^manage_kasbon$'))
    application.add_handler(CallbackQueryHandler(expenses_management_menu, pattern='^manage_expenses$'))
    application.add_handler(CallbackQueryHandler(logout_button, pattern='^logout$'))
    
    # --- 3. JALANKAN BOT ---
    print("Bot sedang berjalan...")
    application.run_polling()

if __name__ == "__main__":
    main()